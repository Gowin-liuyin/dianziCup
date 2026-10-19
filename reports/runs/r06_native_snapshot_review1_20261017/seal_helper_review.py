"""Seal only the new helper source and independent offline review; never execute the audit."""

import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-native-snapshot-review-1.md"
HELPER = ROOT / "reports/runs/r06_actual_audit_helper_20261017/audit_failed_bootstrap.py"
OLD = ROOT / "reports/runs/recovery_r06_bootstrap_recovery_fix1_20261017/audit_failed_bootstrap.py"
raw = HELPER.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "1dd4cdb4736e86138292ccf22917163db16b982b1ef4f918285fbefe8d3d99c7"
assert raw == subprocess.check_output(["git", "cat-file", "blob", "5bfb9077fc66a97fa59bd7864a75a470c8f6ea78:reports/runs/r06_actual_audit_helper_20261017/audit_failed_bootstrap.py"], cwd=ROOT)
allowed = {"PACKAGE_MANIFEST", "PACKAGE_MANIFEST_SHA256", "PACKAGE_SOURCE_PINS"}
old_ast, new_ast = ast.parse(OLD.read_bytes()), ast.parse(raw)
def retained(tree):
    return [node for node in tree.body if not (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in allowed for target in node.targets))]
assert ast.dump(ast.Module(body=retained(old_ast), type_ignores=[])) == ast.dump(ast.Module(body=retained(new_ast), type_ignores=[]))
old_functions = [ast.dump(node) for node in ast.walk(old_ast) if isinstance(node, ast.FunctionDef)]
new_functions = [ast.dump(node) for node in ast.walk(new_ast) if isinstance(node, ast.FunctionDef)]
assert old_functions == new_functions
counts = {}
for label in ("helper_old14_new7", "helper_new_boundaries3"):
    cases = ET.parse(RUN / (label + ".xml")).getroot().findall(".//testcase")
    assert all(case.find("failure") is None and case.find("error") is None and case.find("skipped") is None for case in cases)
    counts[label] = len(cases)
record = {
    "observed_at": datetime.now(timezone.utc).isoformat(), "verdict": "LimitedShip",
    "helper_source_sha": "5bfb9077fc66a97fa59bd7864a75a470c8f6ea78", "helper_raw_sha256": hashlib.sha256(raw).hexdigest(),
    "old_helper_raw_sha256": hashlib.sha256(OLD.read_bytes()).hexdigest(),
    "allowed_top_level_assigns": sorted(allowed), "all_other_module_ast_same": True,
    "all_function_ast_same": True, "function_count": len(new_functions), "counts": counts,
    "core_sha": "37ffe6da1d9a258359363d42488d236b7c00ad87", "ops_sha": "81053fd680dbfb275bfcc511ae44f573340efd56",
    "source_manifest_raw_sha256": "6a1f1cccb510dffe00fa379166d2f423731baf67fa124853493d3b347f80ba55",
    "candidate_and_helper_tracked_diff": [], "actual_audit_main_dpapi_private_installed": "not_run",
    "actual_ready_installation_seven_gates_source_six_hours": "not_run",
    "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
}
diff = subprocess.check_output(["git", "diff", "--name-only", "HEAD", "--", "reports/runs/recovery_r06_activation_prep_20261016/candidate", "reports/runs/r06_actual_audit_helper_20261017/audit_failed_bootstrap.py", "reports/runs/recovery_r06_bootstrap_recovery_fix1_20261017/audit_failed_bootstrap.py"], cwd=ROOT)
assert not diff
(RUN / "helper_terminal_checks.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
rows = []
for path in sorted(RUN.rglob("*")):
    if path.is_file() and path.name != "artifact_manifest_helper.json":
        contents = path.read_bytes()
        rows.append({"path": str(path.relative_to(ROOT)), "bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()})
(RUN / "artifact_manifest_helper.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "helper_source_sha": record["helper_source_sha"], "report_sha256": record["report_sha256"], "files": rows}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": record["verdict"], "helper_raw_sha256": record["helper_raw_sha256"], "function_ast_count_same": record["function_count"], "counts": counts, "report_sha256": record["report_sha256"]}))
