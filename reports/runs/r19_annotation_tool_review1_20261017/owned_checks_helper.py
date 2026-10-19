"""Run bounded offline checks and record the birth-aware owned process tree."""

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

import batch13_process_metadata as metadata

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = "C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe"
BASELINE = "9726363e0d9b33467ba40a06a8bde9548b46bccf"
QUALIFIED = "982532dd564f3eda5d85a6e252b2cf9ce16f98d1"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds")


def environment():
    result = os.environ.copy()
    for key in tuple(result):
        if key.startswith(("TEST_", "DIANZI_TEST_")) or key in {
            "DATABASE_URL",
            "REDIS_URL",
            "GENERATION_API_KEY",
            "REVALIDATION_CURSOR_SIGNING_KEY",
        }:
            result.pop(key)
    result.update(
        APP_ENV="test",
        DATA_MODE="fixture",
        SOURCE_POLLING_ENABLED="false",
        ENRICHMENT_GENERATION_ENABLED="false",
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join(
            [
                str(ROOT / "backend/src"),
                str(ROOT),
                str(ROOT / "backend/tests/unit"),
                str(ROOT / "backend/tests/contract"),
                str(ROOT / "backend/tests/integration"),
                "D:/dianzi/backend/.venv/Lib/site-packages",
            ]
        ),
    )
    return result


def execute(label, command, *, timeout=60, process_cap=10):
    receipt_path = RUN / (label + ".command.json")
    if receipt_path.exists():
        raise RuntimeError("refusing evidence overwrite")
    control, chain = metadata.control_root(metadata.current_identity())
    preexisting = metadata.descendants(control)
    start = now()
    peak, seen, failure = {}, {}, None
    linux_seen, combined_peak = {}, 0
    linux_peak = {}
    is_wsl = Path(command[0]).name.lower() in {"wsl", "wsl.exe"}
    with (
        (RUN / (label + ".stdout.log")).open("wb") as stdout,
        (RUN / (label + ".stderr.log")).open("wb") as stderr,
    ):
        child = subprocess.Popen(
            command, cwd=ROOT, env=environment(), stdout=stdout, stderr=stderr
        )
        deadline = time.monotonic() + timeout
        while True:
            tree = metadata.descendants(control)
            seen.update(tree)
            if len(tree) > len(peak):
                peak = tree
            linux_tree = {}
            linux_seen.update(linux_tree)
            if len(linux_tree) > len(linux_peak):
                linux_peak = linux_tree
            combined_peak = max(combined_peak, len(tree) + len(linux_tree))
            if child.poll() is not None:
                break
            windows_component_cap = 7 if is_wsl else process_cap
            if len(tree) > windows_component_cap:
                failure = "owned_process_limit_exceeded"
            elif time.monotonic() >= deadline:
                failure = "deadline_exceeded"
            if failure:
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenProcess.restype = wintypes.HANDLE
                for pid, item in reversed(list(tree.items())):
                    if pid in {os.getpid(), control["pid"]}:
                        continue
                    try:
                        if metadata.identity(pid) != {"pid": pid, "birth_utc": item["birth_utc"]}:
                            continue
                    except OSError:
                        continue
                    handle = kernel.OpenProcess(1, False, pid)
                    if handle:
                        kernel.TerminateProcess(wintypes.HANDLE(handle), 124)
                        kernel.CloseHandle(wintypes.HANDLE(handle))
                break
            time.sleep(0.02)
        child.wait(timeout=10)
    residual = []
    release_deadline = time.monotonic() + 3
    while time.monotonic() < release_deadline:
        active_children = metadata.descendants(control)
        if not any(pid not in preexisting for pid in active_children):
            break
        time.sleep(0.05)
    for pid, item in seen.items():
        if pid in preexisting:
            continue
        if pid not in active_children:
            continue
        try:
            if metadata.identity(pid) == {"pid": pid, "birth_utc": item["birth_utc"]}:
                residual.append(item)
        except OSError:
            pass
    linux_residual = []
    linux_receipt = None
    if is_wsl:
        linux_receipt_path = RUN / (label + ".linux_receipt.json")
        if not linux_receipt_path.exists():
            failure = failure or "linux_identity_receipt_missing"
        else:
            linux_receipt = json.loads(linux_receipt_path.read_text())
            linux_seen.update({item["pid"]: item for item in linux_receipt["process_rows"]})
            linux_peak = {item["pid"]: item for item in linux_receipt["peak_process_rows"]}
            linux_residual = linux_receipt["remaining_owned_children"]
            if len(peak) + len(linux_peak) > process_cap:
                failure = failure or "combined_component_process_limit_exceeded"
    record = {
        "started_at": start,
        "ended_at": now(),
        "command": command,
        "cwd": str(ROOT),
        "timeout_seconds": timeout,
        "exit_code": child.returncode,
        "failure": failure,
        "windows_peak_count": len(peak),
        "windows_peak_chain": list(peak.values()),
        "windows_processes_observed": list(seen.values()),
        "linux_peak_count": len(linux_peak),
        "linux_peak_chain": list(linux_peak.values()),
        "linux_processes_observed": list(linux_seen.values()),
        "combined_peak_count": combined_peak,
        "conservative_windows_plus_linux_peak_sum": len(peak) + len(linux_peak),
        "linux_receipt": linux_receipt,
        "control_chain": chain,
        "owned_process_cap": process_cap,
        "windows_component_cap": 7 if is_wsl else process_cap,
        "linux_component_cap": 9 if is_wsl else 0,
        "preexisting_control_processes": list(preexisting.values()),
        "remaining_owned_processes": residual,
        "remaining_owned_linux_processes": linux_residual,
        "baseline_sha": BASELINE,
        "qualified_source_sha": QUALIFIED,
        "source_hashes": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "scripts/annotation/prepare.py",
                "scripts/annotation/tests/test_crash_recovery.py",
                "scripts/annotation/tests/test_fd_metadata_error.py",
            )
        },
        "wsl_scope": "none" if not is_wsl else "birth-aware WSL host/session/complete descendants",
        "service_credentials_loaded": False,
        "review_material_sha": "3b001f288a63a336eb27cd8ef1b985745437cef4",
        "helper_hashes": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in RUN.glob("*.py")
        },
    }
    receipt_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "label": label,
                "exit_code": child.returncode,
                "failure": failure,
                "windows_peak": len(peak),
                "remaining_owned": len(residual),
            }
        ),
        flush=True,
    )
    return int(child.returncode or bool(failure or residual or linux_residual))


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1], [PYTHON, *sys.argv[2:]]))
