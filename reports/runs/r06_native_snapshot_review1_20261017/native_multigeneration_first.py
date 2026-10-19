"""Review only: bind three harmless owned generations and verify held exit handles."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CORE = ROOT / "reports/runs/recovery_r06_activation_prep_20261016/candidate/core"
sys.path.insert(0, str(CORE))
from runtime_limits import CpuRate, ExtendedLimits, OwnedJob
from windows_actor import WindowsOwnedActor, _creation_ticks, _snapshot_ticks, process_tree


def main() -> None:
    started = datetime.now(timezone.utc).isoformat()
    begin = time.monotonic()
    evidence = RUN / "native_multigeneration.json"
    ready = RUN / "native_multigeneration_ready.json"
    if evidence.exists() or ready.exists():
        raise RuntimeError("review evidence already exists")
    job = OwnedJob()
    kernel = job.kernel
    kernel.GetActiveProcessorCount.argtypes = [wintypes.WORD]
    kernel.GetActiveProcessorCount.restype = wintypes.DWORD
    cpus = kernel.GetActiveProcessorCount(0xFFFF)
    limits = job.query(9, ExtendedLimits)
    limits.basic.active_limit = 10
    limits.basic.flags |= 0x8
    limits.job_memory = 1024**3
    rate = CpuRate(5, min(10000, 20000 // cpus))
    for kind, value in ((9, limits), (15, rate)):
        if not kernel.SetInformationJobObject(job.handle, kind, ctypes.byref(value), ctypes.sizeof(value)):
            raise OSError("review caps unavailable")
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    leaf_code = "import time; time.sleep(12)"
    middle_code = (
        "import json,os,subprocess,sys,time; from pathlib import Path; "
        f"leaf=subprocess.Popen([sys.executable,'-I','-B','-c',{leaf_code!r}],creationflags=0x08000000); "
        f"Path({str(ready)!r}).write_text(json.dumps({{'root':os.getppid(),'child':os.getpid(),'grandchild':leaf.pid}})); "
        "time.sleep(12)"
    )
    root_code = (
        "import subprocess,sys,time; "
        f"child=subprocess.Popen([sys.executable,'-I','-B','-c',{middle_code!r}],creationflags=0x08000000); "
        "time.sleep(12)"
    )
    root = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", root_code],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000,
    )
    root_birth = _creation_ticks(kernel, int(root._handle))
    actor = None
    rows = []
    error = None
    post_absent = False
    try:
        ready_deadline = time.monotonic() + 3
        while not ready.exists():
            if time.monotonic() >= ready_deadline or root.poll() is not None:
                raise RuntimeError("harmless descendants not ready within three seconds")
            time.sleep(0.01)
        pids = json.loads(ready.read_bytes())
        if pids["root"] != root.pid or len(set(pids.values())) != 3:
            raise RuntimeError("harmless descendant identity ambiguous")
        actor = WindowsOwnedActor(root.pid, root_birth, os.getpid(), job.handle)
        tree = process_tree()
        parents = {"root": os.getpid(), "child": root.pid, "grandchild": pids["child"]}
        for role in ("root", "child", "grandchild"):
            pid = pids[role]
            handle = kernel.OpenProcess(0x100000 | 0x1000 | 1, False, pid)
            if not handle:
                raise RuntimeError("owned descendant held handle unavailable")
            birth = _creation_ticks(kernel, handle)
            rows.append({"role": role, "pid": pid, "parent": parents[role], "creation_ticks": birth, "handle": handle})
            if not actor.in_owned_job(handle) or tree[pid]["parent"] != parents[role]:
                raise RuntimeError("owned descendant Job or parent differs")
            if _snapshot_ticks(str(tree[pid]["created"])) // 10 != birth // 10:
                raise RuntimeError("owned descendant snapshot generation differs")
        actor.kill_owned_tree()
        if root.wait(timeout=1) != 70 or not actor.exited():
            raise RuntimeError("root real shutdown ACK differs")
        for row in rows:
            handle = row["handle"]
            row["held_exit_ack"] = kernel.WaitForSingleObject(handle, 0) == 0
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise OSError("held exit code unavailable")
            row["exit_code"] = int(code.value)
            row["held_birth_unchanged"] = _creation_ticks(kernel, handle) == row["creation_ticks"]
            if not row["held_exit_ack"] or code.value != 70 or not row["held_birth_unchanged"]:
                raise RuntimeError("owned descendant real shutdown ACK differs")
        remaining = process_tree()
        post_absent = all(row["pid"] not in remaining for row in rows)
        if not post_absent:
            raise RuntimeError("owned generation remains in snapshot")
    except Exception as exception:
        error = {"type": type(exception).__name__, "message": str(exception)}
    finally:
        for row in rows:
            handle = row["handle"]
            if kernel.WaitForSingleObject(handle, 0) != 0:
                if _creation_ticks(kernel, handle) != row["creation_ticks"] or actor is None or not actor.in_owned_job(handle):
                    raise RuntimeError("cleanup ownership unavailable")
                kernel.TerminateProcess(handle, 71)
                kernel.WaitForSingleObject(handle, 1000)
            kernel.CloseHandle(handle)
            row.pop("handle")
        if root.poll() is None:
            if _creation_ticks(kernel, int(root._handle)) != root_birth:
                raise RuntimeError("cleanup root generation differs")
            root.kill()
            root.wait(timeout=1)
        if actor is not None:
            actor.close()
    record = {
        "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": time.monotonic() - begin, "status": "passed" if error is None else "failed",
        "generations": rows, "post_snapshot_all_absent": post_absent, "error": error,
        "job_usage_after": job.usage(), "source_pg_minio_wsl_started": False, "paid_requests": 0,
    }
    evidence.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "generations": len(rows), "wall_seconds": record["wall_seconds"], "error": error}))
    raise SystemExit(error is not None)


if __name__ == "__main__":
    main()
