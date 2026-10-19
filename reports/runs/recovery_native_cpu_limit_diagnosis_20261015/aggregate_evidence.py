"""Summarize recorded attempts; do not rerun workloads."""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET


OUTPUT = Path(__file__).resolve().parent
attempts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(OUTPUT.glob("attempt_*.json"))]
rows = []
for item in attempts:
    times = item.get("final_process_times", {})
    rows.append({"attempt": item["attempt"], "mode": item.get("mode", "unmodified_test"), "outcome": item["outcome"], "wall_seconds": item["wall_seconds"], "returncode": item["returncode"], "worker_user_seconds": max((value.get("user_seconds", 0) for value in times.values()), default=None), "job_user_seconds": item.get("final_job", {}).get("user_seconds"), "limit_readback": item.get("child_metadata"), "prelaunch_delay_seconds": item.get("prelaunch_delay_seconds", 0)})
drivers = []
for summary_name, first_attempt, script, arguments in (("probe_summary.json", 1, "probe_native_cpu.py", []), ("phase_summary.json", 13, "probe_phase.py", []), ("unmodified_summary.json", 17, "replay_unmodified_test.py", []), ("unmodified_summary_21.json", 21, "replay_unmodified_test.py", ["21", "6.0", "3"])):
    summary = json.loads((OUTPUT / summary_name).read_text(encoding="utf-8"))
    first = next(item for item in attempts if item["attempt"] == first_attempt)
    started = datetime.fromisoformat(first["started_at"])
    driver_python = "D:/dianzi/backend/.venv/Scripts/python.exe" if first_attempt in (1, 13) else "D:/wt/r06-feeds/backend/.venv/Scripts/python.exe"
    drivers.append({"command": [driver_python, "-B", str(OUTPUT / script), *arguments], "started_at": first["started_at"], "completed_at_derived_from_measured_wall": (started + timedelta(seconds=summary["wall_seconds"])).isoformat(), "wall_seconds": summary["wall_seconds"], "exit_code": 0, "attempts": summary["attempts"], "timeouts": summary["timeouts"]})
unit_metadata = json.loads((OUTPUT / "unit.json").read_text(encoding="utf-8"))
tree = ET.parse(OUTPUT / "unit.xml")
suites = list(tree.iter("testsuite"))
unit = {"metadata": unit_metadata, "suites": [suite.attrib for suite in suites], "target": [{"attributes": case.attrib, "failure": [node.attrib for node in case.findall("failure")]} for case in tree.iter("testcase") if case.get("name") == "test_real_native_cpu_limit_terminates_busy_child"]}
summary = {"head": "1927eeb00a7e0c1335f76340b0382f46102f08f2", "platform": platform.platform(), "python": sys.version, "diagnostic_attempts": len(attempts), "unit_target_attempts": 1, "total_target_attempts": len(attempts) + 1, "diagnostic_execution_wall_seconds": sum(item["wall_seconds"] for item in drivers), "total_execution_wall_seconds_including_unit": sum(item["wall_seconds"] for item in drivers) + unit_metadata["wall_seconds"], "phase_sleeps_included": True, "instrumented_timeouts": sum(item["outcome"] == "timeout" for item in attempts), "unmodified_test_timeouts": sum(item["outcome"] == "TimeoutExpired" for item in attempts), "rows": rows, "drivers": drivers, "unit": unit}
(OUTPUT / "evidence_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(OUTPUT / "attempts.tsv").write_text("attempt\tmode\toutcome\twall_seconds\treturncode\tworker_user_seconds\tjob_user_seconds\tprelaunch_delay_seconds\n" + "\n".join("\t".join(str(item[column]) for column in ("attempt", "mode", "outcome", "wall_seconds", "returncode", "worker_user_seconds", "job_user_seconds", "prelaunch_delay_seconds")) for item in rows) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key not in ("rows", "drivers")}, ensure_ascii=False))
