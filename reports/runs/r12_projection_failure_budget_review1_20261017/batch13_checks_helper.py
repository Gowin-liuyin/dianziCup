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
import linux_control_metadata
import runtime_limits

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = "C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe"
BASELINE = "8c48b61c02860166bdda0986e984058e8a824188"
QUALIFIED = "9cd6381eacc67853c055643d634ffb1812875214"


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
        PYTHONNOUSERSITE="1",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        NUMEXPR_NUM_THREADS="2",
        PYTHONPATH=os.pathsep.join(
            [
                "D:/dianzi/backend/.venv/Lib/site-packages",
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
    preexisting_linux = metadata.linux_owned(RUN) if label == "cbm_resource_recheck" else {}
    runtime_limits.MEMORY_TOTAL = 1024**3
    runtime_limits.MEMORY_PER_PROCESS = 512 * 1024**2
    runtime_limits.CPU_RATE = max(1, 20000 // os.cpu_count())
    owned_job = runtime_limits.OwnedJob()
    actual_limits = owned_job.query(9, runtime_limits.ExtendedLimits)
    actual_rate = owned_job.query(15, runtime_limits.CpuRate)
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
        linux_peak, combined_peak, linux_coverage = {}, 0, None
        is_wsl = Path(command[0]).name.lower() in {"wsl", "wsl.exe"}
        while child.poll() is None:
            tree = metadata.descendants(control)
            if label == "cbm_resource_recheck":
                linux, coverage = linux_control_metadata.observe(RUN)
                if coverage.get("state") == "captured":
                    linux_coverage = coverage
            else:
                linux = metadata.linux_owned(RUN) if is_wsl else {}
            if len(linux) > len(linux_peak):
                linux_peak = linux
            combined_peak = max(combined_peak, len(tree) + len(linux))
            seen.update(tree)
            if len(tree) > len(peak):
                peak = tree
            if len(tree) + len(linux) > process_cap:
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
        "linux_peak_count": len(linux_peak),
        "linux_peak_chain": list(linux_peak.values()),
        "combined_peak_count": combined_peak,
        "linux_control_coverage": linux_coverage,
        "preexisting_linux_tools": list(preexisting_linux.values()),
        "windows_peak_chain": list(peak.values()),
        "control_chain": chain,
        "owned_process_cap": process_cap,
        "preexisting_control_processes": list(preexisting.values()),
        "remaining_owned_processes": residual,
        "native_job": {
            "scope": "supervisor and inherited children; PowerShell ancestors sampled separately",
            "actual_flags": actual_limits.basic.flags,
            "actual_process_memory_bytes": actual_limits.process_memory,
            "actual_job_memory_bytes": actual_limits.job_memory,
            "actual_cpu_flags": actual_rate.flags,
            "actual_cpu_rate": actual_rate.rate,
            "logical_processors": os.cpu_count(),
            "equivalent_cpu_cores": actual_rate.rate * os.cpu_count() / 10000,
            "final_usage": owned_job.usage(),
            "kill_on_close_handle_held_until_supervisor_exit": True,
        },
        "baseline_sha": BASELINE,
        "qualified_source_sha": QUALIFIED,
        "source_hashes": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "backend/src/ai_intel/retrieval/opensearch_client.py",
                "backend/src/ai_intel/retrieval/runtime_policy.py",
                "backend/tests/contract/test_r12_projection_failure_budget.py",
                "backend/tests/contract/test_r12_projection_total_budget_fix2.py",
            )
        },
        "wsl_scope": "none" if not is_wsl else "native proc birth-aware Linux receipt",
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
