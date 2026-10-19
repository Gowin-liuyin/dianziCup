"""Make counts and source receipts from independently executed raw results."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


results = {}
for name in ("original_and_guard", "full_unit"):
    suite = ET.parse(OUTPUT / f"{name}.xml").getroot().find("testsuite")
    results[name] = suite.attrib
coverage = json.loads((OUTPUT / "full_unit_coverage.json").read_text(encoding="utf-8"))
results["coverage_totals"] = coverage["totals"]
results["process_tree_memory"] = []
for run in json.loads((OUTPUT / "process_tree_memory.json").read_text(encoding="utf-8")):
    grouped = {}
    for entry in run["samples"]:
        for process in entry["processes"]:
            metrics = process["metrics"]
            if not metrics.get("signaled"):
                key = f"{process['pid']}:{process['executable']}"
                grouped.setdefault(key, {"private": [], "working_set": [], "unknown": []})
                if "private_bytes" in metrics:
                    grouped[key]["private"].append(metrics["private_bytes"])
                    grouped[key]["working_set"].append(metrics["working_set_bytes"])
                else:
                    grouped[key]["unknown"].append(metrics)
    results["process_tree_memory"].append({
        "run": run["name"], "processes": {
            key: {"max_private_bytes": max(value["private"], default=None),
                  "max_working_set_bytes": max(value["working_set"], default=None),
                  "unknown": value["unknown"]}
            for key, value in grouped.items()
        }, "all_observed_handles_signaled": all(value["signaled"] for value in run["final"].values()),
    })
results["overhead_guard_live"] = []
for path in sorted(OUTPUT.glob("guard_start_*.json")):
    run = json.loads(path.read_text(encoding="utf-8"))
    metrics = [entry["processes"]["guard_pid"] for entry in run["samples"]
               if "guard_pid" in entry["processes"] and not entry["processes"]["guard_pid"]["signaled"]]
    results["overhead_guard_live"].append({
        "name": path.stem, "max_private_bytes": max(entry["private_bytes"] for entry in metrics),
        "max_working_set_bytes": max(entry["working_set_bytes"] for entry in metrics),
    })
results["sources"] = {name: digest(ROOT / name) for name in (
    "backend/src/ai_intel/infrastructure/process_limits.py",
    "backend/tests/unit/test_r05_process_limits.py",
    "backend/tests/unit/test_r20_native_cpu_guard.py",
    "backend/src/ai_intel/ingestion/parsing/pdf_text.py",
    "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py",
    "backend/src/ai_intel/infrastructure/models/semantic.py",
    "reports/tasks/R20-native-cpu-guard.md",
)}
results["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
results["merge_base"] = subprocess.check_output(
    ["git", "merge-base", results["head"], "45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b"], cwd=ROOT, text=True,
).strip()
results["platform"] = {"python": sys.version, "base_prefix": sys.base_prefix,
                       "windows": platform.win32_ver()}
results["generated_at"] = datetime.now().astimezone().isoformat()
(OUTPUT / "review_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
