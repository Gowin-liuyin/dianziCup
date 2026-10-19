"""Four fixed CPU probes retain worker timing and Job accounting; maximum two concurrent."""

from concurrent.futures import ThreadPoolExecutor
import json
import time

import probe_native_cpu as probe


started = time.perf_counter()
results = [probe.attempt(5, "instrumented"), probe.attempt(6, "instrumented")]
with ThreadPoolExecutor(max_workers=2) as executor:
    results.extend(executor.map(lambda number: probe.attempt(number, "parallel2"), (7, 8)))
summary = {"attempts": 4, "wall_seconds": time.perf_counter()-started, "timeouts": sum(result["outcome"] == "timeout" for result in results), "results": [{key: result.get(key) for key in ("attempt", "outcome", "wall_seconds", "returncode", "child_metadata", "final_process_times", "final_job")} for result in results]}
(probe.OUTPUT / "fixed_cpu_measurement.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary), flush=True)
