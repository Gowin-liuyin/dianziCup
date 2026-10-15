"""保存实际分母、原材料字节、源码一致性与 Git blob；私有连接只在内存检查。"""

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
BASE = "29e1ebddca5cbadffc8c6533bdeeb08b8d63e469"
FIRST = "11d24131aff176cc97f138d2e4a222cd378590d4"
CODE = "08b141bd437c1de70a8435a1f7f6c448a131ed0d"
CANONICAL = Path("D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_recheck_20261016")


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def contract(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: {
            "parameters": [ast.dump(item) for item in node.decorator_list],
            "assertions": [ast.dump(item).replace("r10-graph-1.0.0", "r10-graph-1.2.0").replace("r10-graph-1.1.0", "r10-graph-1.2.0") for item in ast.walk(node) if isinstance(item, ast.Assert)],
        }
        for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def describe(path, commit=None):
    relative = path.relative_to(ROOT).as_posix()
    raw = path.read_bytes()
    oid = git("rev-parse", commit + ":" + relative).decode().strip() if commit else git("hash-object", "-w", "--path=" + relative, relative).decode().strip()
    blob = git("cat-file", "blob", oid)
    return {"path": relative, "raw_bytes": len(raw), "raw_sha256": digest(raw), "git_blob_oid": oid, "git_blob_bytes": len(blob), "git_blob_sha256": digest(blob)}


def main():
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    assert not git("diff", FIRST, CODE, "--", "backend/src")
    old = RUN / "original_author_cases.py"
    before = RUN / "before_fix2_author35.py"
    current = ROOT / "backend/tests/integration/test_r10_evidence_graph_pg.py"
    assert contract(old) == contract(before) == contract(current)
    assert digest(old.read_bytes()) == "dca8f657fc384c6af9363b020c7ce49ce9bd1d2b08f913fa73625ff2d13d3bf9"
    assert old.read_bytes() == (RUN / "test_original_graph_pg.py").read_bytes()
    originals = []
    for own, canonical in [("test_review2_pg.py", "test_review2_pg.py"), ("test_independent_graph_pg.py", "test_independent_graph_pg.py"), ("test_graph_load_pg.py", "test_graph_load_pg.py"), ("reviewer_fixture33_original.py", "test_original_graph_pg.py")]:
        content = (RUN / own).read_bytes()
        assert content == (CANONICAL / canonical).read_bytes()
        originals.append({"copy": own, "canonical_read_only_path": str(CANONICAL / canonical), "raw_sha256": digest(content), "raw_bytes": len(content)})
    assert digest((RUN / "test_review2_pg.py").read_bytes()) == "1b12f82583d8c067cc52d604c54aa53bddeb593c1cf8c2bfcccdc32d6d810c47"
    assert digest((RUN / "test_independent_graph_pg.py").read_bytes()) == "cfbbb95d227f4e884d2765bde6da5dbd1121c5ffd9c159ac99a1e9eadf0bfe16"
    preserved = {"recorded_at": now(), "base": BASE, "final_code": CODE, "first_code": FIRST, "first_to_final_backend_src_identical": True, "author_35_test_ids_parameters_assertions_preserved": True, "rule_assertion_only_normalization": "1.0.0/1.1.0 -> 1.2.0", "author_original": describe(old), "author_fix1_raw": describe(before), "unit_original": describe(RUN / "original_unit_cases.py"), "unit_fix1_raw": describe(RUN / "before_fix2_unit.py"), "canonical_copies": originals, "old_probe_execution_fixture": "unchanged original author helper with this slice exact DB guard; canonical reviewer helper is preserved but not executed against its other database", "probe_33_is_32_plus": "test_graph_load_pg.py (1 case)", "probe_20": "explicit -k subset from same unchanged 32 script, 12 deselected"}
    (RUN / "original_preservation.json").write_text(json.dumps(preserved, ensure_ascii=False, indent=2), encoding="utf-8")
    executions = []
    for path in sorted(RUN.glob("*.xml")):
        cases = list(ET.parse(path).getroot().iter("testcase"))
        failures = [item for item in cases if item.find("failure") is not None]
        errors = [item for item in cases if item.find("error") is not None]
        skipped = [item for item in cases if item.find("skipped") is not None]
        receipt = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        executions.append({"label": path.stem, "tests": len(cases), "passed": len(cases)-len(failures)-len(errors)-len(skipped), "failed": len(failures), "errors": len(errors), "skipped": len(skipped), "exit_code": receipt["exit_code"], "input_head": receipt["baseline"], "failed_case_ids": [item.attrib.get("classname", "") + "::" + item.attrib["name"] for item in failures]})
    by_label = {item["label"]: item for item in executions}
    for label, passed, failed in [("frozen_final_primary", 163, 0), ("frozen_final_related", 103, 0), ("frozen_final_model_fields", 122, 0), ("frozen_original_author35", 24, 11), ("frozen_original_probe32", 22, 10), ("frozen_original_probe20_subset", 16, 4), ("frozen_original_probe33", 23, 10)]:
        assert (by_label[label]["passed"], by_label[label]["failed"]) == (passed, failed)
    observations = [json.loads(line) for line in (RUN / "frozen_final_primary_http.jsonl").read_text(encoding="utf-8").splitlines()]
    compact = [{key: value for key, value in item.items() if key not in {"body", "snapshot"}} for item in observations]
    (RUN / "concurrency_summary.json").write_text(json.dumps({"recorded_at": now(), "code_commit": CODE, "observations": compact}, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN / "verification_summary.json").write_text(json.dumps({"recorded_at": now(), "code_commit": CODE, "primary_plus_regression_passed": 388, "original_red_compatibility_not_passed": True, "frontend_e2e_live_manual_full_coverage": "not_run", "executions": executions}, ensure_ascii=False, indent=2), encoding="utf-8")
    code_paths = git("diff", "--name-only", BASE, CODE, "--", "backend", "docs/decisions/CR-R10_graph_fix2.md").decode().splitlines()
    (RUN / "frozen_code_manifest.json").write_text(json.dumps({"recorded_at": now(), "base": BASE, "code_commit": CODE, "files": [describe(ROOT / item, CODE) for item in code_paths]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN / "frozen_code.patch").write_bytes(git("diff", "--binary", BASE, CODE, "--", "backend", "docs/decisions/CR-R10_graph_fix2.md"))
    paths = [path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json"]
    paths += [ROOT / "reports/tasks/R10-pg-evidence-graph.md", ROOT / "docs/decisions/CR-R10_graph_fix2.md"]
    private = json.loads(subprocess.check_output(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], text=True))
    connection = make_url(private["TEST_DATABASE_URL"])
    forbidden = [connection.password.encode(), private["TEST_DATABASE_URL"].encode(), connection.set(database="test_dianzi_r06_catalog_r10_graph_20261016").render_as_string(hide_password=False).encode()]
    matches = sum(any(secret in path.read_bytes() for secret in forbidden) for path in paths)
    assert matches == 0
    gate = RUN / "sensitive_data_gate.json"
    gate.write_text(json.dumps({"recorded_at": now(), "scanned_files": len(paths), "private_connection_capture": "memory_only", "private_password_or_complete_dsn_matching_files": matches}, indent=2), encoding="utf-8")
    paths = sorted(set(paths + [gate]))
    (RUN / "artifact_manifest.json").write_text(json.dumps({"recorded_at": now(), "code_commit": CODE, "excluded": ["manifest itself", "__pycache__ and other directories"], "files": [describe(path) for path in paths]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"code_commit": CODE, "code_files": len(code_paths), "artifact_files": len(paths), "passed_primary_plus_regression": 388, "secret_matches": matches}))


if __name__ == "__main__":
    main()
