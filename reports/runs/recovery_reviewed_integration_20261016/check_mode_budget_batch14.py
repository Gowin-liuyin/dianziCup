"""Run the actual combined mode, workflow and lifecycle regressions on root."""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import batch13_checks_helper as checks

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
original_run = "reports/runs/r14_source_report_output_budget_20261017/"
author = Path("D:/wt/r14-source-report-budget-fix") / original_run
command = json.loads((author / "frozen_combined_final.command.json").read_text())["command"]
dependency = original_run + "original_graph_unknown_samples.json"
data = subprocess.check_output(["git", "show", "7b1747cd1322957bc9f9b24b49bf28012e17fd9e:" + dependency], cwd=ROOT)
target = ROOT / dependency
if target.exists():
    assert target.read_bytes() == data
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
paths = [item for item in command if item.endswith(".py")]
selected = []
for item in paths:
    if "reports" in item:
        filename = Path(item).name
        relative = original_run + filename
        data = subprocess.check_output(["git", "show", "7b1747cd1322957bc9f9b24b49bf28012e17fd9e:" + relative], cwd=ROOT)
        target = ROOT / relative
        if target.exists():
            assert target.read_bytes() == data
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        selected.append(str(target))
    else:
        selected.append(item)
selected.extend([
    "tests/unit/test_r06_revision_mode.py",
    "tests/unit/test_r06_revision_mode_reads.py",
    "tests/unit/test_r07_source_report_revision_mode.py",
    "tests/contract/test_r06_revision_mode_router_contract.py",
    "tests/unit/test_r18_public_read_boundaries.py",
    "tests/unit/test_r01_migration_engine_disposal.py",
    "tests/unit/test_r01_migration_pg_helpers.py",
    "tests/contract/test_r01_migration_configuration.py",
])
selected = list(dict.fromkeys(selected))
label = "mode_budget_batch14_unit_fix1"
checks.QUALIFIED = "db922460dbc6b45284201be7c5cbefe35de07427+ff972ebb7fe1183950cf83cb20107124f4b0995b+dbf9927206cb3ce7aa55f34a8c828771285ef365"
code = checks.execute(label, [checks.PYTHON, "-m", "pytest", *selected, "--no-cov", "-q", "--junitxml=" + str(RUN / (label + ".xml"))])
counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
if (RUN / (label + ".xml")).exists():
    for suite in ET.parse(RUN / (label + ".xml")).getroot().iter("testsuite"):
        for key in counts:
            counts[key] += int(suite.get(key, 0))
(RUN / (label + ".counts.json")).write_text(json.dumps({"exit_code": int(code), "counts": counts, "integration": "not_run", "live": "not_run", "test_paths": selected}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"exit_code": int(code), "counts": counts}))
raise SystemExit(code)
