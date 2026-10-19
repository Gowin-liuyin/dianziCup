"""Bound the corrected browser instrument within the original source run deadline."""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import runtime_limits

RUN = Path(__file__).resolve().parent
ROOT = Path("D:/wt/r06-integrated-live-1156")
SHA = "1156b2ed6616e3a4297215c2893d2cbe633f5215"
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def write(name, value):
    (RUN / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def combined_private_memory(supervisor_pid):
    command = "$rows=@(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId); $owned=[System.Collections.Generic.HashSet[uint32]]::new(); [void]$owned.Add(" + str(supervisor_pid) + "); [void]$owned.Add(" + str(os.getpid()) + "); do { $added=$false; foreach($row in $rows) { if($owned.Contains($row.ParentProcessId) -and $owned.Add($row.ProcessId)) { $added=$true } } } while($added); $total=0L; foreach($id in $owned) { $entry=Get-Process -Id $id -ErrorAction SilentlyContinue; if($entry) { $total+=$entry.PrivateMemorySize64 } }; [PSCustomObject]@{private_bytes=$total;process_count=$owned.Count} | ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, check=True, timeout=8, creationflags=0x08000000)
    return json.loads(result.stdout)["private_bytes"]


def main():
    started = now()
    assert not (RUN / "browser_command_v2.json").exists()
    original = json.loads((RUN / "runtime_start.json").read_text())
    deadline = datetime.fromisoformat(original["hard_deadline"])
    assert datetime.now(CLOCK) < deadline
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
    runtime_limits.MEMORY_TOTAL = 1024**3
    resource_job = runtime_limits.OwnedJob()
    secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
    command = ["node.exe", str(ROOT / "frontend/node_modules/@playwright/test/cli.js"), "test", "--config", str(RUN / "playwright.v2.config.cjs")]
    process = subprocess.Popen(command, cwd=ROOT / "frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)
    log_limit = threading.Event()

    def drain():
        count = 0
        with (RUN / "browser_v2.log").open("xb") as output:
            while chunk := process.stdout.readline(65536):
                for secret in sorted(secrets, key=len, reverse=True):
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                count += len(chunk)
                if count > 16 * 1024**2:
                    log_limit.set()
                    break
                output.write(chunk)
                output.flush()

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    reason = "completed"
    observed_peak_private = 0
    usage = {}
    wall_deadline = min(time.monotonic() + 180, time.monotonic() + (deadline - datetime.now(CLOCK)).total_seconds())
    write("browser_start_v2.json", {"started_at": started, "code_sha": SHA, "controller_pid": os.getpid(), "browser_command": command, "cwd": str(ROOT / "frontend"), "original_source_deadline": original["hard_deadline"], "maximum_seconds": 180, "separate_browser_owned_job": True, "browser_process_memory_bytes": runtime_limits.MEMORY_PER_PROCESS, "browser_job_memory_bytes": runtime_limits.MEMORY_TOTAL, "browser_cpu_percent_of_host": 20, "combined_private_memory_watchdog_bytes": 2 * 1024**3, "aggregate_cpu_seconds_budget_original_plus_v2": 1200, "observation_gap_or_new_source_segment": False})
    try:
        while process.poll() is None:
            private_bytes = combined_private_memory(original["supervisor_pid"])
            observed_peak_private = max(observed_peak_private, private_bytes)
            usage = resource_job.usage()
            original_usage = json.loads((RUN / "runtime_heartbeat.json").read_text())["usage"]
            if time.monotonic() >= wall_deadline or private_bytes > 2 * 1024**3 or usage["cpu_seconds"] + original_usage["cpu_seconds"] >= 1200 or log_limit.is_set():
                reason = "original_deadline_or_combined_resource_budget"
                break
            time.sleep(1)
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        thread.join(timeout=2)
        write("browser_command_v2.json", {"started_at": started, "ended_at": now(), "code_sha": SHA, "exit_code": process.returncode, "reason": reason, "browser_usage": usage, "peak_combined_private_memory_bytes": observed_peak_private, "source_collection_not_restarted": True, "scope": "fixed product; new selector/filter instrument; first red remains; separate bounded browser Job with one-second combined memory watchdog", "configured_cpu_rate_limitation": "Each source/browser Job has20%; sum can theoretically40%; actual CPU samples retained, no claim of one aggregate20% Job for v2"})


if __name__ == "__main__":
    main()
