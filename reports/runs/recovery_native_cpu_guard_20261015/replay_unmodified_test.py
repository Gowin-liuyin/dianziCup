"""Call the frozen test function unchanged; observe Popen only for bounded cleanup."""

import json
from pathlib import Path
import runpy
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

import probe_native_cpu as probe


test_path = probe.ROOT / "backend/tests/unit/test_r05_process_limits.py"
test = runpy.run_path(str(test_path))["test_real_native_cpu_limit_terminates_busy_child"]
original_popen = subprocess.Popen
observed = []


def observe_popen(*args, **kwargs):
    process = original_popen(*args, **kwargs)
    observed.append(process)
    return process


subprocess.Popen = observe_popen
started = time.perf_counter()
results = []
first_attempt = int(sys.argv[1]) if len(sys.argv) > 1 else 17
phase_delay = float(sys.argv[2]) if len(sys.argv) > 2 else 5.9
attempt_count = int(sys.argv[3]) if len(sys.argv) > 3 else 4
if not 1 <= attempt_count <= 4 or not 0 <= phase_delay <= 6.1:
    raise ValueError("diagnostic attempt bounds exceeded")
for offset in range(attempt_count):
    number = first_attempt + offset
    delay = phase_delay if offset else 0
    time.sleep(delay)
    attempt_started = time.perf_counter()
    result = {"attempt": number, "prelaunch_delay_seconds": delay, "started_at": datetime.now(timezone.utc).isoformat(), "test_path": str(test_path), "test_file_changed": False, "timeout_seconds": 8}
    try:
        test()
        result["outcome"] = "passed"
    except subprocess.TimeoutExpired as error:
        result.update(outcome="TimeoutExpired", exception=str(error), traceback=traceback.format_exc(), stdout=(error.stdout or b"").decode(errors="replace"), stderr=(error.stderr or b"").decode(errors="replace"))
    result["wall_seconds"] = time.perf_counter() - attempt_started
    result["launcher_pid"] = observed[-1].pid
    result["returncode"] = observed[-1].returncode
    remaining = probe.descendants(observed[-1].pid)
    result["remaining_descendants_before_cleanup"] = remaining
    for item in remaining:
        handle = probe.KERNEL.OpenProcess(0x0001 | 0x1000, False, item["pid"])
        if handle:
            try:
                probe.KERNEL.TerminateProcess(handle, 77)
            finally:
                probe.KERNEL.CloseHandle(handle)
    results.append(result)
    (probe.OUTPUT / f"attempt_{number:02d}_unmodified_test.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
summary = {"attempts": attempt_count, "wall_seconds": time.perf_counter() - started, "timeouts": sum(item["outcome"] == "TimeoutExpired" for item in results), "results": results}
summary_name = "unmodified_summary.json" if first_attempt == 17 else f"unmodified_summary_{first_attempt}.json"
(probe.OUTPUT / summary_name).write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key != "results"}), flush=True)
