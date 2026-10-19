"""Bound the incremental lifecycle Job cost against the exact previous implementation."""

from concurrent.futures import ThreadPoolExecutor
import ctypes
from ctypes import wintypes
import hashlib
import json
import statistics
import subprocess

import probe_review_windows as probe

original_sample = probe.sample
probe.KERNEL.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.c_void_p]


def sample_handles(handle: int) -> dict[str, object]:
    result = original_sample(handle)
    count = wintypes.DWORD()
    if probe.KERNEL.GetProcessHandleCount(handle, ctypes.byref(count)):
        result["handle_count"] = count.value
    return result


probe.sample = sample_handles
previous = subprocess.check_output(
    ["git", "show", "994c381edd2c4f0743d9c76f83abefaf51359f14:backend/src/ai_intel/infrastructure/process_limits.py"],
    cwd=probe.ROOT,
)
(probe.OUTPUT / "previous_guard_process_limits.py").write_bytes(previous)
previous_baseline = (probe.OUTPUT / "baseline_process_limits.py").read_bytes()
(probe.OUTPUT / "baseline_process_limits.py").write_bytes(previous)
results = []
try:
    for old in (True, False):
        for index in range(3):
            results.append(probe.attempt(
                f"incremental_{'before' if old else 'after'}_{index}",
                "time.sleep(0.3)\nprint('RESULT_OK',flush=True)\n",
                baseline=old, cpu_seconds=5,
            ))
finally:
    (probe.OUTPUT / "baseline_process_limits.py").write_bytes(previous_baseline)
leaf_setup = (
    "leaf=subprocess.Popen([os.path.join(sys.base_prefix,'python.exe'),'-I','-S','-c',"
    "'import time;time.sleep(10)'],creationflags=0x08000000)\n"
    "print('LEAF '+json.dumps({'leaf_pid':leaf.pid}),flush=True)\n"
)
with ThreadPoolExecutor(max_workers=2) as executor:
    results.extend(executor.map(
        lambda index: probe.attempt(
            f"concurrent_guard_death_{index}",
            leaf_setup + "ctypes.PyDLL('kernel32').Sleep(2000)\nprint('UNSUPERVISED_RESULT',flush=True)\n",
            fault="abrupt_exit",
        ),
        range(2),
    ))
summary = {
    "attempts": len(results), "previous_source_sha256": hashlib.sha256(previous).hexdigest(),
    "startup_medians_seconds": {
        mode: statistics.median(result["metadata"][0]["limit_wall_seconds"]
                                for result in results if result["name"].startswith("incremental_" + mode))
        for mode in ("before", "after")
    },
    "scope": "six short cost attempts and two concurrent guardian-death tree attempts; maximum two workers",
}
(probe.OUTPUT / "incremental_cost_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
assert all(result["outcome"] == "exited" for result in results)
assert all(all(values["signaled"] for values in result["final"].values()) for result in results)
assert all(result["returncode"] == 0 and "RESULT_OK" in result["stdout"]
           for result in results if result["name"].startswith("incremental_"))
assert all("UNSUPERVISED_RESULT" not in result["stdout"]
           for result in results if result["name"].startswith("concurrent_guard_death"))
print(json.dumps(summary), flush=True)
