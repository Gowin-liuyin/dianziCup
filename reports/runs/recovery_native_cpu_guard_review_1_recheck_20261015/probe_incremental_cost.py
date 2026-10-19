"""Compare three old and three fixed guardians with the same harmless scaffold."""

import ctypes
from ctypes import wintypes
import json
import statistics
import subprocess

import probe_review_windows as probe

probe.OUTPUT = probe.OUTPUT / "incremental_cost"
probe.OUTPUT.mkdir(parents=True, exist_ok=True)
old_source = subprocess.check_output([
    "git", "show", "994c381edd2c4f0743d9c76f83abefaf51359f14:backend/src/ai_intel/infrastructure/process_limits.py",
], cwd=probe.ROOT)
(probe.OUTPUT / "baseline_process_limits.py").write_bytes(old_source)
probe.KERNEL.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
original_sample = probe.sample


def sample_with_handle_count(handle):
    result = original_sample(handle)
    count = wintypes.DWORD()
    if probe.KERNEL.GetProcessHandleCount(handle, ctypes.byref(count)):
        result["handle_count"] = count.value
    return result


probe.sample = sample_with_handle_count
results = [probe.attempt(f"{'old_guard' if old else 'fixed_guard'}_{index}",
                         "time.sleep(0.3)\nprint('RESULT_OK',flush=True)\n",
                         baseline=old, cpu_seconds=5)
           for old in (True, False) for index in range(3)]
summary = {"attempts": len(results), "samples": [], "startup_medians_seconds": {}}
for run in results:
    live = [entry["processes"]["guard_pid"] for entry in run["samples"]
            if "guard_pid" in entry["processes"] and not entry["processes"]["guard_pid"]["signaled"]]
    worker_live = [entry["processes"]["worker_pid"] for entry in run["samples"]
                   if "worker_pid" in entry["processes"] and not entry["processes"]["worker_pid"]["signaled"]]
    summary["samples"].append({
        "name": run["name"], "limit_wall_seconds": run["metadata"][0]["limit_wall_seconds"],
        "guardian_handle_counts": sorted({item["handle_count"] for item in live}),
        "worker_handle_counts": sorted({item["handle_count"] for item in worker_live}),
        "guardian_max_private_bytes": max(item["private_bytes"] for item in live),
        "guardian_max_working_set_bytes": max(item["working_set_bytes"] for item in live),
        "all_observed_handles_signaled": all(item["signaled"] for item in run["final"].values()),
        "returncode": run["returncode"],
    })
for prefix in ("old_guard", "fixed_guard"):
    summary["startup_medians_seconds"][prefix] = statistics.median(
        item["limit_wall_seconds"] for item in summary["samples"] if item["name"].startswith(prefix)
    )
(probe.OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
