"""Summarize receipts without treating captured fault or command exit zero as a pass."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import xml.etree.ElementTree as ET

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]
read_json = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
commands = {path.stem: read_json(path) for path in OUTPUT.glob("*.json")
            if "command" in read_json(path) and "exit_code" in read_json(path)}
tests = {path.stem: {key: value for key, value in ET.parse(path).getroot()[0].attrib.items()
                    if key in ("tests", "failures", "errors", "skipped", "time")}
         for path in OUTPUT.glob("*.xml")}
attempts = [read_json(path) for path in OUTPUT.glob("*.json")
            if "timeout_seconds" in read_json(path) and "samples" in read_json(path)]
cost = {}
for mode in ("before", "after"):
    matching = [attempt for attempt in attempts if attempt["name"].startswith("incremental_" + mode)]
    row = {"count": len(matching), "startup_median_seconds": statistics.median(
        attempt["metadata"][0]["limit_wall_seconds"] for attempt in matching)}
    for process_key in ("worker_pid", "guard_pid"):
        values = [snapshot["processes"][process_key] for attempt in matching
                  for snapshot in attempt["samples"] if process_key in snapshot["processes"]
                  and not snapshot["processes"][process_key]["signaled"]]
        row[process_key] = {
            key: {"minimum": min(item[key] for item in values if key in item),
                  "maximum": max(item[key] for item in values if key in item)}
            for key in ("private_bytes", "working_set_bytes", "handle_count")
        }
    cost[mode] = row
coverage = read_json(OUTPUT / "full_unit_frozen_coverage.json")["totals"]
summary = {
    "frozen_code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "generated_at": datetime.now().astimezone().isoformat(), "command_receipts": commands,
    "junit_results": tests, "coverage": coverage,
    "diagnostic_attempts": len(attempts), "diagnostic_wall_sum_seconds": sum(item["wall_seconds"] for item in attempts),
    "command_wall_sum_seconds": sum(item["wall_seconds"] for item in commands.values()),
    "diagnostic_worker_cpu_sum_seconds": sum(item["final"].get("worker_pid", {}).get("cpu_seconds", 0) for item in attempts),
    "timeouts": sum(item["outcome"] == "timeout" for item in attempts),
    "incremental_cost": cost,
    "source_files": {str(path.relative_to(ROOT)).replace("\\", "/"): {
        "working_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "git_blob": subprocess.check_output(["git", "rev-parse", f"HEAD:{str(path.relative_to(ROOT)).replace(chr(92), '/')}"], cwd=ROOT, text=True).strip(),
    } for path in (ROOT / "backend/src/ai_intel/infrastructure/process_limits.py",
                   ROOT / "backend/tests/unit/test_r20_native_cpu_guard.py",
                   ROOT / "backend/tests/unit/test_r05_process_limits.py")},
}
(OUTPUT / "fix_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
assert len(attempts) == 30 and summary["timeouts"] == 0
assert tests["full_unit_frozen"]["failures"] == "0" and tests["full_unit_frozen"]["skipped"] == "0"
print(json.dumps({key: summary[key] for key in ("frozen_code_sha", "junit_results", "coverage", "diagnostic_attempts", "diagnostic_wall_sum_seconds", "diagnostic_worker_cpu_sum_seconds", "command_wall_sum_seconds", "incremental_cost", "source_files")}, indent=2))
