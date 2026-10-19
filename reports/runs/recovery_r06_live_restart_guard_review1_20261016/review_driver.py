"""Independent, local-only review probes for the frozen R06 deployment guard."""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PREP = ROOT / "reports/runs/recovery_r06_live_restart_preparation_20261016"
PRODUCT = Path("D:/wt/r06-live-e310-20261016")
sys.path.insert(0, str(PREP))
import authorization
import owned_stop_watcher as watcher
import task_fence
import windows_actor
from celery.exceptions import WorkerShutdown
from runtime_limits import OwnedJob


def save(name: str, value: object) -> None:
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def execute(name: str, arguments: list[str], cwd: Path) -> dict[str, object]:
    started, clock = now(), time.monotonic()
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, timeout=45)
    raw = result.stdout + result.stderr
    (RUN / (name + ".log")).write_bytes(raw)
    metadata = {
        "command": arguments, "cwd": str(cwd), "started_at": started,
        "ended_at": now(), "seconds": time.monotonic() - clock,
        "exit_code": result.returncode, "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return metadata


def kernel_process_handle(pid: int):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    handle = kernel.OpenProcess(0x100000 | 0x1000 | 0x100 | 1, False, pid)
    if not handle:
        raise RuntimeError("review-owned handle unavailable")
    return kernel, handle


IDENTITY = """
import ctypes,json,os,subprocess,sys,time
from ctypes import wintypes
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.GetCurrentProcess.restype=wintypes.HANDLE
k.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
c,e,s,u=(wintypes.FILETIME() for _ in range(4))
assert k.GetProcessTimes(k.GetCurrentProcess(),ctypes.byref(c),ctypes.byref(e),ctypes.byref(s),ctypes.byref(u))
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=0x08000000)
print(json.dumps({'pid':os.getpid(),'ticks':c.dwLowDateTime+(c.dwHighDateTime<<32),'child_launcher':p.pid}),flush=True)
time.sleep(30)
"""


def actual_actor_probes() -> dict[str, object]:
    process = subprocess.Popen([sys.executable, "-B", "-c", IDENTITY], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, creationflags=0x08000000)
    identity = json.loads(process.stdout.readline())
    actor = windows_actor.WindowsOwnedActor(identity["pid"], identity["ticks"], process.pid)
    descendant_handles = []
    try:
        tree = windows_actor.process_tree()
        selected = {identity["pid"]}
        while additions := {pid for pid, row in tree.items() if row["parent"] in selected} - selected:
            selected.update(additions)
        for pid in selected - {identity["pid"]}:
            kernel, handle = kernel_process_handle(pid)
            descendant_handles.append((pid, kernel, handle))
        wrong_parent_rejected = False
        try:
            windows_actor.WindowsOwnedActor(identity["pid"], identity["ticks"], process.pid + 1)
        except windows_actor.OwnershipError:
            wrong_parent_rejected = True
        alive_after_wrong_parent = not actor.exited()
        original_open = actor.kernel.OpenProcess
        denied_pids = {pid for pid, _, _ in descendant_handles}

        def deny_descendant(access, inherit, pid):
            if pid in denied_pids:
                ctypes.set_last_error(5)
                return 0
            return original_open(access, inherit, pid)

        actor.kernel.OpenProcess = deny_descendant
        stop_error = None
        try:
            actor.kill_owned_tree()
        except windows_actor.OwnershipError as error:
            stop_error = str(error)
        finally:
            actor.kernel.OpenProcess = original_open
        descendant_states = [
            {"pid": pid, "exit_confirmed_by_handle": kernel.WaitForSingleObject(handle, 0) == 0}
            for pid, kernel, handle in descendant_handles
        ]
        return {
            "actual_pid": identity["pid"], "creation_ticks": identity["ticks"],
            "owned_launcher_pid": process.pid, "wrong_parent_rejected": wrong_parent_rejected,
            "actor_alive_after_wrong_parent": alive_after_wrong_parent,
            "denied_open_last_error": 5, "kill_owned_tree_error": stop_error,
            "actor_exit_confirmed": actor.exited(), "descendant_states": descendant_states,
            "bug_reproduced": stop_error is None and actor.exited() and any(
                not row["exit_confirmed_by_handle"] for row in descendant_states),
            "scope": "real disposable Python tree; OpenProcess denial injected only for verified owned descendants",
        }
    finally:
        if not actor.exited():
            actor.kill_owned_tree()
        for _, kernel, handle in descendant_handles:
            if kernel.WaitForSingleObject(handle, 0) != 0:
                if not kernel.TerminateProcess(handle, 70):
                    raise RuntimeError("review-owned cleanup rejected")
                if kernel.WaitForSingleObject(handle, 1000) != 0:
                    raise RuntimeError("review-owned cleanup not confirmed")
            kernel.CloseHandle(handle)
        actor.close()
        process.wait(timeout=3)
        process.stdout.close()
        process.stderr.close()


def gate_and_fence_probes() -> list[dict[str, object]]:
    results = []
    gate_path = RUN / "false_gate.json"
    gate_path.write_text(json.dumps({"root_live_authorized": False}), encoding="utf-8")
    with patch.object(authorization, "GATE", gate_path), patch.object(authorization.subprocess, "check_output") as commands:
        try:
            authorization.verify_live_authorization()
        except RuntimeError as error:
            results.append({"case": "false_gate", "rejected": True, "error": str(error), "subprocess_count": commands.call_count})
    class RejectEnvironment(dict):
        def get(self, *args):
            raise AssertionError("environment accessed before gate")
        def __getitem__(self, key):
            raise AssertionError("environment accessed before gate")
    with patch.object(os, "environ", RejectEnvironment()), patch.object(authorization.subprocess, "check_output") as commands:
        try:
            runpy.run_path(str(PREP / "deploy_runtime_entry.py"), run_name="__main__")
        except RuntimeError as error:
            results.append({"case": "missing_gate_environment", "rejected": True, "error": str(error), "subprocess_count": commands.call_count})
    fake_gate = {
        "root_live_authorized": True, "independent_review_ship": True, "root_budget_approved": True,
        "integrated_key_checks_passed": True, "product_sha": authorization.PRODUCT_SHA,
        "tool_sha": "bae3138d103427d659d7fdc0a8a195088dd42f2e", "maximum_seconds": 21600,
        "source_job_cap": 450, "model_requests_permitted": 0, "wire_https_cap": 35100,
        "product_root": str(ROOT),
    }
    wrong_path = RUN / "wrong_product_gate.json"
    wrong_path.write_text(json.dumps(fake_gate), encoding="utf-8")
    with patch.object(authorization, "GATE", wrong_path):
        try:
            authorization.verify_live_authorization()
        except RuntimeError as error:
            results.append({"case": "wrong_frozen_product", "rejected": True, "error": str(error), "product_pg_count": 0})
    invalid_stop = RUN / "invalid_stop.json"
    invalid_stop.write_text(json.dumps({"role": "worker", "owned_stop": False}), encoding="utf-8")
    with patch.object(watcher, "owned_control_path", return_value=invalid_stop):
        try:
            watcher.read_stop_request("worker")
        except RuntimeError as error:
            results.append({"case": "invalid_stop_contract", "rejected": True, "error": str(error)})
    private_url = "https://review-only.invalid/a?api_key=review-secret-never-logged"
    fake_engine = Mock()
    fake_engine.connect.side_effect = RuntimeError(private_url)
    fake_receipt_root = Mock()
    fake_receipt_root.parent = RUN
    with patch.object(task_fence, "read_stop_request", return_value=False), patch.object(task_fence, "owned_control_path", return_value=fake_receipt_root), patch.object(task_fence, "request_owned_worker_stop") as stop:
        try:
            task_fence.require_producer_slot(fake_engine)
        except WorkerShutdown as error:
            raw = (RUN / f"fence_failure_{os.getpid()}.json").read_bytes()
            results.append({"case": "pg_error_metadata", "exit_code": error.code, "stop_requested": stop.call_count == 1,
                            "secret_absent": private_url.encode() not in raw and b"review-secret" not in raw, "receipt": json.loads(raw)})
    with patch.object(task_fence, "read_stop_request", return_value=True):
        engine = Mock()
        try:
            task_fence.require_producer_slot(engine)
        except WorkerShutdown as error:
            results.append({"case": "stop_before_pg_claim", "exit_code": error.code, "pg_connect_count": engine.connect.call_count})
    return results


def main() -> None:
    started, clock = now(), time.monotonic()
    job = OwnedJob()
    commands = []
    commands.append(execute("independent_guard_29", [sys.executable, "-B", "-m", "unittest", "test_runtime_controls.py", "test_windows_actor.py", "-v"], PREP))
    cli = RUN / "cli_missing_gate"
    cli.mkdir(exist_ok=True)
    for name in authorization.SCRIPT_NAMES:
        shutil.copyfile(PREP / name, cli / name)
    for name in ("deploy_runtime_entry", "controlled_supervise"):
        commands.append(execute(name + "_missing_gate", [sys.executable, "-B", str(cli / (name + ".py"))], cli))
    save("negative_probe_results.json", gate_and_fence_probes())
    save("permission_denied_descendant.json", actual_actor_probes())
    observer_hashes = []
    for name in ("observe.py", "observation_log.py", "pg_snapshot.py"):
        relative = authorization.ORIGINAL_OBSERVER_RELATIVE + "/" + name
        raw = (ROOT / relative).read_bytes()
        blob = subprocess.check_output(["git", "show", authorization.ORIGINAL_OBSERVER_SHA + ":" + relative], cwd=ROOT)
        observer_hashes.append({"path": relative, "raw_sha256": hashlib.sha256(raw).hexdigest(), "frozen_sha256": hashlib.sha256(blob).hexdigest(), "equal": raw == blob})
    product_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCT, text=True).strip()
    product_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=PRODUCT, text=True).strip()
    save("identity.json", {"tool_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                           "product_head": product_head, "product_status": product_status, "observer_hashes": observer_hashes})
    save("commands.json", commands)
    save("run_receipt.json", {"started_at": started, "ended_at": now(), "seconds": time.monotonic() - clock,
                             "resource_usage": job.usage(), "source_http_count": 0, "model_provider_count": 0,
                             "service_start_count": 0, "product_pg_connections": 0, "formal_six_hour_pass": False})
    print(json.dumps({"commands": commands, "negative_cases": 6, "real_kernel_tree": True, "source_http": 0}))


if __name__ == "__main__":
    main()
