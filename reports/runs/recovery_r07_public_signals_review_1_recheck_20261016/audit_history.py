"""Check preserved red cases, checkout line endings, and frozen test evidence identity."""

import ast
import json
import subprocess
from xml.etree import ElementTree

from run_commands import CODE, MATERIAL, ROOT, RUN, SOURCE_PATHS, hashes, timestamp

started = timestamp()
material = json.loads((RUN / "author_material_verification.json").read_bytes())
differences = material["working_byte_differences"]
line_endings = {}
for path in differences:
    blob = subprocess.check_output(["git", "show", MATERIAL + ":" + path], cwd=ROOT)
    line_endings[path] = (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
assert all(line_endings.values())
author_run = ROOT / "reports/runs/recovery_r07_public_signals_fix1_20261016"


def test_functions(path):
    return {node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


red_functions = test_functions(author_run / "new_red_test_snapshot.py")
current_functions = {}
for path in SOURCE_PATHS[4:6]:
    current_functions.update(test_functions(ROOT / path))
assert red_functions == current_functions
new_red = json.loads((author_run / "new_red.command.json").read_bytes())
assert new_red["exit_code"] == 1 and new_red["pytest_counts"] == {"tests": 24, "failures": 11, "errors": 0, "skipped": 0}
assert "11 failed, 13 passed" in (author_run / "new_red.log").read_text(encoding="utf-8")
counts = {}
for name in ("original_triggers", "independent_all", "new_regression", "focused", "regression"):
    suite = ElementTree.parse(RUN / (name + ".xml")).getroot()[0]
    counts[name] = {key: int(suite.get(key, "0")) for key in ("tests", "failures", "errors", "skipped")}
    assert counts[name]["failures"] == counts[name]["errors"] == counts[name]["skipped"] == 0
frozen = json.loads((author_run / "new_regression_frozen.command.json").read_bytes())
early = json.loads((author_run / "new_regression.command.json").read_bytes())
assert frozen["candidate_sha"] == CODE
assert any(str(value).endswith("new_regression.xml") for value in frozen["argv"])
assert any(str(value).endswith("new_regression.xml") for value in early["argv"])
result = {"started_at": started, "ended_at": timestamp(), "candidate_sha": MATERIAL, "code_sha": CODE,
          "author_manifest_actual_sha256": material["manifest_sha256"], "author_manifest_provided_sha256": material["provided_manifest_sha256"],
          "checkout_line_endings_only": line_endings, "red_and_final_test_function_ast_equal": True,
          "test_function_count": len(red_functions), "red_pytest_counts": new_red["pytest_counts"],
          "independent_pytest_counts": counts, "early_green_xml_reused_for_frozen": True,
          "final_author_evidence_receipt": "new_regression_frozen.command.json",
          "business_hashes": hashes(), "new_network_calls": 0, "new_model_calls": 0, "pg_calls": 0}
(RUN / "history_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"checkout_line_ending_differences": len(line_endings), "unchanged_test_functions": len(red_functions),
                  "author_red": "11 failed / 13 passed", "independent_counts": counts,
                  "early_green_xml_reused_for_frozen": True}))
