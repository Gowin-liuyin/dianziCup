"""封存实际检查、旧材料字节/断言和规范 Git blob；不输出秘密连接。"""

import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "16803ce6be9ad6adb6d89f46c594cfa420190c24"
CODE = "3516b9109b9b7f2c5691d78ad0439aea4a659f4f"
REVIEW_ORIGINAL = Path("D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_20261016/test_independent_graph_pg.py")


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def test_contract(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: {
            "decorators": [ast.dump(value) for value in node.decorator_list],
            "assertions": [ast.dump(value).replace("r10-graph-1.0.0", "r10-graph-1.1.0") for value in ast.walk(node) if isinstance(value, ast.Assert)],
        }
        for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def describe(path, commit=None):
    relative = path.relative_to(ROOT).as_posix()
    raw = path.read_bytes()
    if commit:
        oid = git("rev-parse", commit + ":" + relative).decode().strip()
    else:
        oid = git("hash-object", "-w", "--path=" + relative, relative).decode().strip()
    blob = git("cat-file", "blob", oid)
    return {"path": relative, "raw_bytes": len(raw), "raw_sha256": digest(raw), "git_blob_oid": oid, "git_blob_bytes": len(blob), "git_blob_sha256": digest(blob)}


def main():
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    original = RUN / "original_author_cases.py"
    old_contract = test_contract(original)
    new_contract = test_contract(ROOT / "backend/tests/integration/test_r10_evidence_graph_pg.py")
    assert old_contract == new_contract
    original_raw = original.read_bytes()
    assert digest(original_raw) == "dca8f657fc384c6af9363b020c7ce49ce9bd1d2b08f913fa73625ff2d13d3bf9"
    assert original_raw == (RUN / "test_original_graph_pg.py").read_bytes()
    review_raw = (RUN / "test_independent_graph_pg.py").read_bytes()
    assert review_raw == REVIEW_ORIGINAL.read_bytes()
    assert digest(review_raw) == "cfbbb95d227f4e884d2765bde6da5dbd1121c5ffd9c159ac99a1e9eadf0bfe16"
    old_blob_oid = git("rev-parse", BASE + ":backend/tests/integration/test_r10_evidence_graph_pg.py").decode().strip()
    assert old_blob_oid == "2ccfb158d3d231af1a442cdda0e20d41023d515e"
    preservation = {"recorded_at": now(), "original_author_raw_sha256": digest(original_raw), "original_author_git_blob_oid": old_blob_oid, "old_author_test_function_count": len(old_contract), "test_ids_param_decorators_assertions_equal": True, "only_assertion_normalization": "r10-graph-1.0.0 -> r10-graph-1.1.0", "review_copy_raw_sha256": digest(review_raw), "review_original_equals_copy": True, "review_original_read_only_path": str(REVIEW_ORIGINAL), "review20_execution": "same unchanged 32-case script; explicit -k exclusion of 12 newly added cases; not a recovered separate 20-case byte version"}
    (RUN / "original_preservation.json").write_text(json.dumps(preservation, ensure_ascii=False, indent=2), encoding="utf-8")
    executions = []
    for path in sorted(RUN.glob("*.xml")):
        root = ET.parse(path).getroot()
        cases = list(root.iter("testcase"))
        failures = [item for item in cases if item.find("failure") is not None]
        errors = [item for item in cases if item.find("error") is not None]
        skipped = [item for item in cases if item.find("skipped") is not None]
        receipt = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        executions.append({"label": path.stem, "tests": len(cases), "passed": len(cases)-len(failures)-len(errors)-len(skipped), "failed": len(failures), "errors": len(errors), "skipped": len(skipped), "exit_code": receipt["exit_code"], "code_input_sha": receipt["baseline"], "failed_case_ids": [item.attrib.get("classname", "") + "::" + item.attrib["name"] for item in failures]})
    final_by_label = {item["label"]: item for item in executions}
    assert final_by_label["frozen_author_and_validity"]["passed"] == 75
    assert final_by_label["frozen_regression"]["passed"] == 103
    assert (final_by_label["frozen_original_author35"]["passed"], final_by_label["frozen_original_author35"]["failed"]) == (24, 11)
    assert (final_by_label["frozen_original_reviewer32"]["passed"], final_by_label["frozen_original_reviewer32"]["failed"]) == (22, 10)
    assert (final_by_label["frozen_original_reviewer20_subset"]["passed"], final_by_label["frozen_original_reviewer20_subset"]["failed"]) == (16, 4)
    (RUN / "verification_summary.json").write_text(json.dumps({"recorded_at": now(), "code_commit": CODE, "primary_plus_regression_passed": 178, "original_red_compatibility_not_passed": True, "frontend_e2e_live_manual_full_coverage": "not_run", "executions": executions}, ensure_ascii=False, indent=2), encoding="utf-8")
    code_paths = git("diff", "--name-only", BASE, CODE, "--", "backend", "docs/decisions/CR-R10_graph_validity.md").decode().splitlines()
    (RUN / "frozen_code_manifest.json").write_text(json.dumps({"recorded_at": now(), "baseline": BASE, "code_commit": CODE, "files": [describe(ROOT / item, CODE) for item in code_paths]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN / "frozen_code.patch").write_bytes(git("diff", "--binary", BASE, CODE, "--", "backend", "docs/decisions/CR-R10_graph_validity.md"))
    paths = [path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json"]
    paths += [ROOT / "reports/tasks/R10-pg-evidence-graph.md", ROOT / "docs/decisions/CR-R10_graph_validity.md", *[ROOT / "reports/runs/recovery_r10_pg_evidence_graph_20261016" / name for name in ("cbm_validity_auth_trace.json", "cbm_validity_field_trace.json")]]
    private = json.loads(subprocess.check_output(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], text=True))
    connection = make_url(private["TEST_DATABASE_URL"])
    forbidden = [connection.password.encode(), private["TEST_DATABASE_URL"].encode(), connection.set(database="test_dianzi_r06_catalog_r10_graph_20261016").render_as_string(hide_password=False).encode()]
    match_count = sum(any(secret in path.read_bytes() for secret in forbidden) for path in paths)
    assert match_count == 0
    gate = RUN / "sensitive_data_gate.json"
    gate.write_text(json.dumps({"recorded_at": now(), "scanned_files": len(paths), "private_connection_capture": "memory_only", "private_password_or_complete_dsn_matching_files": match_count}, ensure_ascii=False, indent=2), encoding="utf-8")
    paths = sorted(set(paths + [gate]))
    (RUN / "artifact_manifest.json").write_text(json.dumps({"recorded_at": now(), "code_commit": CODE, "excluded": ["manifest itself", "__pycache__ directories"], "files": [describe(path) for path in paths]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"code_commit": CODE, "code_files": len(code_paths), "artifact_files": len(paths), "primary_plus_regression_passed": 178, "secret_matching_files": match_count}))


if __name__ == "__main__":
    main()
