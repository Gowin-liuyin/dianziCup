"""Run the combined frozen read and proof suites with owned-process observations."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
AUTHOR = Path("D:/wt/r14-qualified-root-integration/reports/runs/r14_qualified_root_integration_20261017")
helpers = []
for original, target in (("process_metadata.py", "batch13_process_metadata.py"), ("checks.py", "batch13_checks_helper.py")):
    raw = (AUTHOR / original).read_bytes()
    if target == "batch13_checks_helper.py":
        raw = raw.replace(b"import process_metadata as metadata", b"import batch13_process_metadata as metadata")
    destination = RUN / target
    if destination.exists():
        raise RuntimeError("refusing helper evidence overwrite")
    destination.write_bytes(raw)
    helpers.append({"original": str(AUTHOR / original), "original_sha256": hashlib.sha256((AUTHOR / original).read_bytes()).hexdigest(), "path": destination.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "change": "only private import alias" if target.endswith("checks_helper.py") else "byte unchanged"})
spec = importlib.util.spec_from_file_location("batch13_checks", RUN / "batch13_checks_helper.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.QUALIFIED = "0114779a2ebe3b39275b1a220ad6c13e531976ff"
paths = [
    "tests/unit/test_r14_unknown_incoming_fix3.py",
    "tests/unit/test_r14_unknown_boundary_fix2.py",
    "tests/contract/test_r14_unknown_recovery_contract.py",
    "tests/unit/test_r14_shared_read_consumers.py",
    "tests/contract/test_r14_shared_read_consumers_contract.py",
    "tests/unit/test_r14_langgraph_workflow.py",
    "tests/unit/test_r14_langgraph_workflow_fix1.py",
    "tests/unit/test_r14_qa_citation_prompt_fix1.py",
    "tests/contract/test_r14_qa_citation_prompt_wire_fix1.py",
    "tests/contract/test_r14_langgraph_workflow_contract.py",
    "tests/unit/test_r14_read_adapters.py",
    "tests/unit/test_r14_tool_gateway.py",
    "tests/unit/test_r14_tool_gateway_fix1.py",
    "tests/contract/test_r14_tool_gateway_contract.py",
    "tests/contract/test_r14_tool_gateway_review_negative.py",
    "tests/unit/test_r14_shared_read_consumers_fix1.py",
    "tests/unit/test_r14_default_runtime.py",
    "tests/unit/test_r14_preclaim_recovery.py",
    "tests/unit/test_r14_terminal_outbox_selection.py",
    "tests/contract/test_r14_default_investigation_mount.py",
    "tests/unit/test_r16_default_worker_registration.py",
    "tests/unit/test_r07_structured_fact_proofs.py",
    "tests/contract/test_r07_structured_fact_proof_contract.py",
    "tests/unit/test_r07_source_report_reader.py",
    "tests/unit/test_r07_source_report_node.py",
]
command = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", *paths, "-q", "--no-cov", "--junitxml=" + str(RUN / "read_proofs_batch13_unit.xml")]
exit_code = module.execute("read_proofs_batch13_unit", command)
counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
xml_path = RUN / "read_proofs_batch13_unit.xml"
if xml_path.exists():
    for suite in ET.parse(xml_path).getroot().iter("testsuite"):
        for key in counts:
            counts[key] += int(suite.get(key, 0))
(RUN / "read_proofs_batch13_checks.json").write_text(json.dumps({"exit_code": exit_code, "counts": counts, "helper_inputs": helpers, "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_inputs": "read_proofs_batch13_inputs.json", "integration": "not_run", "live": "not_run", "whole_task_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"exit_code": exit_code, "counts": counts}))
raise SystemExit(exit_code)
