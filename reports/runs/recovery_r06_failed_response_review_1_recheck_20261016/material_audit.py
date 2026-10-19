"""Audit old and fix1 material bytes and unchanged original test case identities."""

import ast
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ORIGINAL = Path("D:/wt/r06-failed-response-persistence")
OLD_SHA = "9eb01d7ba843116122a9a2462f3b74a2626cc48c"
FIX_SHA = "b7817239022caed52ba6b8912b2d827c58a60181"
EXPECTED_FIX_MANIFEST = "cf585ab7063ffda419532951e903259d6bb1a2fca579b41edd0bda0e108dd1d4"


def blob(sha, path):
    return subprocess.check_output(["git", "show", sha + ":" + path], cwd=ROOT)


for label, sha, prefix, expected_count in (
    ("old87", OLD_SHA, "reports/runs/recovery_r06_failed_response_persistence_20261016", 87),
    ("fix33", FIX_SHA, "reports/runs/recovery_r06_failed_response_persistence_fix1_20261016", 33),
):
    manifest_path = prefix + "/artifact_manifest.json"
    manifest_blob = blob(sha, manifest_path)
    manifest = json.loads(manifest_blob)
    manifest_sha = hashlib.sha256(manifest_blob).hexdigest()
    if label == "fix33":
        assert manifest_sha == EXPECTED_FIX_MANIFEST
    rows = []
    for path, expected in list(manifest["artifacts"].items()) + [(manifest_path, {"sha256": manifest_sha, "size_bytes": len(manifest_blob)})]:
        path = path.replace("\\", "/")
        committed = blob(sha, path)
        original = (ORIGINAL / path).read_bytes()
        checkout = (ROOT / path).read_bytes()
        rows.append({"path": path, "expected_sha256": expected["sha256"], "git_blob_sha256": hashlib.sha256(committed).hexdigest(), "original_sha256": hashlib.sha256(original).hexdigest(), "review_checkout_sha256": hashlib.sha256(checkout).hexdigest(), "size_bytes": len(committed), "manifest_match": hashlib.sha256(committed).hexdigest() == expected["sha256"] and len(committed) == expected["size_bytes"], "original_match": original == committed, "checkout_match": checkout == committed, "original_crlf_count": original.count(b"\r\n"), "checkout_crlf_count": checkout.count(b"\r\n")})
    assert len(rows) == expected_count and all(row["manifest_match"] and row["original_match"] for row in rows)
    receipt = {"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "material_sha": sha, "manifest_sha256": manifest_sha, "count": len(rows), "all_original_match": True, "checkout_difference_count": sum(not row["checkout_match"] for row in rows), "artifacts": rows}
    (RUN / (label + "_bytes.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("count", "manifest_sha256", "checkout_difference_count")}))

path = "backend/tests/integration/test_r06_source_worker_pg.py"
old = ast.parse(blob(OLD_SHA, path))
fixed = ast.parse(blob(FIX_SHA, path))
old_functions = {node.name: node for node in old.body if isinstance(node, ast.FunctionDef)}
fixed_functions = {node.name: node for node in fixed.body if isinstance(node, ast.FunctionDef)}
assert old_functions.keys() == fixed_functions.keys()
target = "test_catalog_failure_never_publishes_partial_page_or_cursor"
fixture = "catalog_worker_engine"
assert all(ast.dump(old_functions[name], include_attributes=False) == ast.dump(fixed_functions[name], include_attributes=False) for name in old_functions if name not in {target, fixture})
assert ast.dump(ast.Module(body=old_functions[target].body[:-1], type_ignores=[]), include_attributes=False) == ast.dump(ast.Module(body=fixed_functions[target].body[:len(old_functions[target].body)-1], type_ignores=[]), include_attributes=False)
assert [ast.dump(node, include_attributes=False) for node in old_functions[target].decorator_list] == [ast.dump(node, include_attributes=False) for node in fixed_functions[target].decorator_list]
fixture_old = old_functions[fixture].body
fixture_new = fixed_functions[fixture].body
assert len(fixture_old) == len(fixture_new)
assert all(ast.dump(a, include_attributes=False) == ast.dump(b, include_attributes=False) for index, (a, b) in enumerate(zip(fixture_old, fixture_new)) if index != 1)
receipt = {"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "fixed_sha": FIX_SHA, "old_sha": OLD_SHA, "function_names_equal": True, "other_functions_ast_equal": True, "failure_input_and_outcome_prefix_ast_equal": True, "failure_parametrization_ast_equal": True, "fixture_all_statements_except_database_assert_ast_equal": True, "deleted_wrapper_exists": (ROOT / "backend/tests/integration/test_r06_failed_response_legacy_pg.py").exists()}
assert receipt["deleted_wrapper_exists"] is False
(RUN / "case_identity_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print("case_identity_and_fixture_audit_passed")
