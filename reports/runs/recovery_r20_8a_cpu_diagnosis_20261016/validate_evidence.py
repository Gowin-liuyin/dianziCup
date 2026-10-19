"""Check recorded evidence consistency without starting any worker sample."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
summary = json.loads((RUN / "execution_summary.json").read_text(encoding="utf-8"))
totals = summary["totals"]
assert totals["primary_worker_samples"] == 20
assert totals["sample_wall_seconds_sum"] < 240
assert totals["observed_cpu_seconds"] < 60
assert totals["all_observed_signaled"] and totals["outer_timeout_count"] == 0
assert len(summary["original_test_cases"]) == 4
assert sum(case["failure"] is not None for case in summary["original_test_cases"]) == 2
samples = {sample["sample_id"]: sample for sample in summary["samples"]}
for name in ("short", "python", "idle", "native"):
    assert samples[f"coverage_valid_{name}"]["events"][0]["coverage_active"] is True
    assert samples[f"no_coverage_{name}"]["events"][0]["coverage_active"] is False
    assert "ConfigError" in json.loads((RUN / f"coverage_{name}.json").read_text())["stderr"]
short = samples["coverage_valid_short"]
first = next(event for event in short["guard_events"] if event.get("api") == "GetProcessTimes")
assert first["result"] and first["win32_error"] == 0
assert (first["times"][2] + first["times"][3]) / 10_000_000 == 1.015625
assert not any(event.get("api") == "SetEvent" for event in short["guard_events"])
assert any(event.get("api") == "TerminateProcess" and event["result"] == 1 and event["win32_error"] == 0
           for event in short["guard_events"])
idle = samples["controlled_idle_near_budget"]
assert idle["target_final"]["cpu_seconds"] == 1.0
assert next(event["self_cpu"] for event in idle["events"] if event["event"] == "before_workload") == 1.0
assert idle["result_lines"] and not any("UNSUPERVISED" in line for line in idle["result_lines"])
native = samples["coverage_valid_native"]["target_final"]
assert native["user_ticks"] < 10_000_000 < native["user_ticks"] + native["kernel_ticks"]
assert samples["real_pdf_parent"]["exit_code"] == 0
assert samples["real_pdf_parent"]["result_lines"] == ["PDF_RESULT parsed 4 [1, 2, 3, 4]"]
cpu_queries = 0
for path in RUN.glob("*.json"):
    value = json.loads(path.read_text(encoding="utf-8"))
    if "sample_id" not in value:
        continue
    for sample in value["samples"]:
        for times in sample["processes"].values():
            assert times["success"] and times["win32_error"] == 0
            assert times["kernel_ticks"] % 156250 == times["user_ticks"] % 156250 == 0
            cpu_queries += 1
for path in RUN.glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
for source in summary["identity"]["sources"]:
    path = RUN.parents[2] / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
print(json.dumps({"evidence_checks": "passed", "cpu_query_records": cpu_queries, "worker_samples_added": 0,
                  "observed_quantum_seconds": 0.015625, "totals": totals}))
