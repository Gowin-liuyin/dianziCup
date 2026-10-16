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
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"
BASELINE = "9726363e0d9b33467ba40a06a8bde9548b46bccf"
QUALIFIED = "1dafd15ff1c25d08489fd69efa44e8481d6dda22"


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
        PYTHONPATH=os.pathsep.join(
            [
                str(ROOT / "backend/src"),
                str(ROOT),
                str(ROOT / "backend/tests/unit"),
                str(ROOT / "backend/tests/contract"),
                str(ROOT / "backend/tests/integration"),
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
    with (
        (RUN / (label + ".stdout.log")).open("wb") as stdout,
        (RUN / (label + ".stderr.log")).open("wb") as stderr,
    ):
        child = subprocess.Popen(
            command, cwd=ROOT / "backend", env=environment(), stdout=stdout, stderr=stderr
        )
        deadline = time.monotonic() + timeout
        while child.poll() is None:
            tree = metadata.descendants(control)
            seen.update(tree)
            if len(tree) > len(peak):
                peak = tree
            if len(tree) > process_cap:
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
    record = {
        "started_at": start,
        "ended_at": now(),
        "command": command,
        "cwd": str(ROOT / "backend"),
        "timeout_seconds": timeout,
        "exit_code": child.returncode,
        "failure": failure,
        "windows_peak_count": len(peak),
        "windows_peak_chain": list(peak.values()),
        "control_chain": chain,
        "owned_process_cap": process_cap,
        "preexisting_control_processes": list(preexisting.values()),
        "remaining_owned_processes": residual,
        "baseline_sha": BASELINE,
        "qualified_source_sha": QUALIFIED,
        "source_hashes": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "backend/src/ai_intel/investigation/graph.py",
                "backend/src/ai_intel/investigation/workflow_service.py",
            )
        },
        "wsl_scope": "none" if command[0] != "wsl" else "separate CBM Linux receipt",
        "service_credentials_loaded": False,
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
    return child.returncode or bool(failure or residual)


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1], [PYTHON, *sys.argv[2:]]))
