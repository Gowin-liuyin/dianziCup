"""Summarize stored evidence and frozen source hashes without running more workers."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]
checks = []
for path in OUTPUT.glob("*.json"):
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(value, dict) and "command" in value:
        value["record"] = path.name
        xml = path.with_suffix(".xml")
        if xml.exists():
            value["junit_suites"] = [suite.attrib for suite in ET.parse(xml).iter("testsuite")]
        checks.append(value)
checks.sort(key=lambda item: item["started_at"])
coverage = json.loads((OUTPUT / "unit_recheck_coverage.json").read_text(encoding="utf-8"))
samples = json.loads((OUTPUT / "fixed_cpu_measurement.json").read_text(encoding="utf-8"))
samples = [{"attempt": sample["attempt"], "wall_seconds": sample["wall_seconds"], "worker": sample["final_process_times"][str(sample["child_metadata"]["pid"])], "job": sample["final_job"], "returncode": sample["returncode"]} for sample in samples["results"]]
source_paths = ["backend/src/ai_intel/infrastructure/process_limits.py", "backend/tests/unit/test_r05_process_limits.py", "backend/tests/unit/test_r20_native_cpu_guard.py"]
summary = {"baseline": "45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b", "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_hashes": [{"path": path, "working_file_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), "git_blob": subprocess.check_output(["git", "rev-parse", f"HEAD:{path}"], cwd=ROOT, text=True).strip()} for path in source_paths], "checks": checks, "check_command_wall_seconds_sum": sum(item["wall_seconds"] for item in checks), "final_unit_totals": coverage["totals"], "fixed_cpu_samples": samples}
(OUTPUT / "delivery_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key != "checks"}))
