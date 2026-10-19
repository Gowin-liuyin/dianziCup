"""Replay the frozen R07 stdin boundary with its real installed runtime paths."""

import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

RUN = Path(__file__).parent
SOURCE = Path("D:/wt/r07-io-deadline")
seen = {}
peak = {}
stop_monitor = threading.Event()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


limits = load_module("diagnostic_limits", RUN / "runtime_limits.original.py")
metadata = load_module("diagnostic_metadata", SOURCE / "reports/runs/r07_source_io_deadline_20261017/batch13_process_metadata.py")
assert os.cpu_count() == 24
limits.MEMORY_TOTAL = 1024**3
limits.CPU_RATE = 833
job = limits.OwnedJob()
control, chain = metadata.control_root(metadata.current_identity())
preexisting = metadata.descendants(control)
safe_python_path = os.pathsep.join((str(SOURCE / "backend/src"), "D:/dianzi/backend/.venv/Lib/site-packages"))
os.environ["PYTHONPATH"] = safe_python_path
sys.path[:0] = safe_python_path.split(os.pathsep)
watchdog = threading.Timer(6, os._exit, args=(124,))
watchdog.daemon = True
watchdog.start()


def observe():
    global peak
    while not stop_monitor.is_set():
        tree = metadata.descendants(control)
        seen.update(tree)
        if len(tree) > len(peak):
            peak = tree
        if len(tree) > 10:
            os._exit(124)
        stop_monitor.wait(0.005)


monitor = threading.Thread(target=observe)
monitor.start()
from ai_intel.infrastructure.content_store import _read_with_deadline

request = json.dumps({"storage": "local", "root_directory": "D:/" + "x" * 8192,
                      "content_hash": "a" * 64, "remaining_seconds": 0.15, "byte_limit": 1}).encode()
assert len(request) == 8365
started = time.monotonic()
outcome = "returned"
try:
    _read_with_deadline(request, started + 0.15, 1)
except (TimeoutError, OSError, ValueError) as error:
    outcome = type(error).__name__
elapsed = time.monotonic() - started
release_deadline = time.monotonic() + 1
while time.monotonic() < release_deadline:
    remaining = {pid: value for pid, value in metadata.descendants(control).items() if pid not in preexisting}
    if not remaining:
        break
    time.sleep(0.005)
stop_monitor.set()
monitor.join(timeout=1)
watchdog.cancel()
watchdog.join(timeout=1)
result = {"source_sha": "4d85343a6117f1be215313aacd4652a554e334e4", "input_bytes": len(request),
          "deadline_seconds": 0.15, "elapsed_seconds": elapsed, "outcome": outcome,
          "deadline_overrun_reproduced": elapsed > 0.2, "python_path": safe_python_path,
          "native_worker_before_stdin_evidence": [value for pid, value in seen.items() if pid not in preexisting],
          "full_windows_peak_count": len(peak), "full_windows_peak": list(peak.values()),
          "preexisting_control_processes": list(preexisting.values()), "control_chain": chain,
          "remaining_owned_processes": list(remaining.values()), "job_usage": job.usage(),
          "process_memory_bytes": limits.MEMORY_PER_PROCESS, "job_memory_bytes": limits.MEMORY_TOTAL,
          "cpu_rate": limits.CPU_RATE, "logical_cpu_count": os.cpu_count(), "kill_on_close": True,
          "input_hashes": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
              Path(__file__), RUN / "runtime_limits.original.py",
              SOURCE / "backend/src/ai_intel/infrastructure/content_store.py",
              SOURCE / "backend/src/ai_intel/infrastructure/_content_read_worker.py",
              SOURCE / "backend/src/ai_intel/infrastructure/process_limits.py")}}
(RUN / "native_source_followup_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"outcome": outcome, "elapsed_seconds": elapsed, "input_bytes": len(request),
                  "full_windows_peak_count": len(peak), "remaining_owned": len(remaining)}), flush=True)
assert elapsed > 0.2 and not remaining and not monitor.is_alive() and not watchdog.is_alive()
