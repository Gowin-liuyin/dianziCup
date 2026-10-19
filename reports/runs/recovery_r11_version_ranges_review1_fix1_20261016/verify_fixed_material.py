"""Verify both author material seals, copied original cases, and protected source/test blobs."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ElementTree

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
OLD = "5a35cc5e6dec307e7d5fbdf06c9d49881679cb61"
FIX = "65838b42c0dcff863036968e39a1404aa323b3c9"
CODE = "71e724131daf4d03372392d58cd17c764c3e2e40"
MATERIAL = "8f5fe818774349b41b0b5aceb45d69ba81410678"


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def blob(revision, path):
    return git("show", f"{revision}:{path}")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def summarize_xml(value):
    root = ElementTree.fromstring(value)
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    return {key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}


material_checks = []
for folder, expected_manifest_hash in [("recovery_r11_version_ranges_20261016", "85fb8c8074bff0ebd5594339b4e465beab58656f446591a0c307b657cc480861"), ("recovery_r11_version_ranges_fix1_20261016", "a90e7ed882d62c1312f000f7a5178a2d324ab07c92d1383e0dbb1a6df6cba861")]:
    path = f"reports/runs/{folder}/artifact_manifest.json"
    manifest_bytes = blob(MATERIAL, path)
    source = json.loads(manifest_bytes)
    rows = []
    for item in source["artifacts"]:
        fixed = blob(MATERIAL, item["path"])
        working = (ROOT / item["path"]).read_bytes()
        raw_evidence = item["path"].endswith((".log", ".xml", ".json", "test_independent_version_cases.py"))
        rows.append(item | {"git_sha256": digest(fixed), "working_raw_sha256": digest(working), "git_matches_manifest": digest(fixed) == item["sha256"] and len(fixed) == item["bytes"], "working_raw_matches": digest(working) == item["sha256"] and len(working) == item["bytes"], "raw_evidence": raw_evidence, "working_eol_normalized_equal_git": working.replace(b"\r\n", b"\n") == fixed.replace(b"\r\n", b"\n")})
    result = {"folder": folder, "expected_manifest_hash": expected_manifest_hash, "manifest_git_sha256": digest(manifest_bytes), "manifest_working_sha256": digest((ROOT / path).read_bytes()), "listed_artifacts": len(rows), "including_manifest": len(rows) + 1, "git_mismatches": [item["path"] for item in rows if not item["git_matches_manifest"]], "raw_evidence_mismatches": [item["path"] for item in rows if item["raw_evidence"] and not item["working_raw_matches"]], "ordinary_eol_only_paths": [item["path"] for item in rows if not item["raw_evidence"] and not item["working_raw_matches"] and item["working_eol_normalized_equal_git"]], "non_eol_ordinary_mismatches": [item["path"] for item in rows if not item["raw_evidence"] and not item["working_eol_normalized_equal_git"]], "artifacts": rows}
    assert result["manifest_git_sha256"] == expected_manifest_hash
    assert result["manifest_working_sha256"] == expected_manifest_hash
    assert not result["git_mismatches"] and not result["raw_evidence_mismatches"] and not result["non_eol_ordinary_mismatches"]
    material_checks.append(result)
original = Path("C:/Users/yinha/.codex/worktrees/r11-version-ranges-review1/dianzi/reports/runs/recovery_r11_version_ranges_review1_20261016/test_independent_version_cases.py").read_bytes()
author_copy = blob(MATERIAL, "reports/runs/recovery_r11_version_ranges_fix1_20261016/test_independent_version_cases.py")
review_copy = (RUN / "test_independent_version_cases.py").read_bytes()
original_cases = {"bytes": len(original), "original_sha256": digest(original), "author_fixed_blob_sha256": digest(author_copy), "review_copy_sha256": digest(review_copy), "all_exact_raw_equal": original == author_copy == review_copy}
assert original_cases["all_exact_raw_equal"]
assert digest(original) == "b76bd21296694bf47cebf01d2878f22f17830bb86d8fbdbedfa166a6630af5e6"
protected_paths = [item["path"] for item in json.loads(blob(MATERIAL, "reports/runs/recovery_r11_version_ranges_fix1_20261016/preserved_blob_verification.json"))["files"]]
protected = [{"path": path, "old_sha256": digest(blob(OLD, path)), "fixed_sha256": digest(blob(MATERIAL, path)), "same_git_blob": blob(OLD, path) == blob(MATERIAL, path)} for path in protected_paths]
changed = git("diff", "--name-only", OLD, MATERIAL, "--", "backend/src", "backend/tests", "contracts", "progress", "docs/plan", "backend/pyproject.toml", "backend/uv.lock").decode().splitlines()
assert changed == ["backend/src/ai_intel/assessment/version_ranges.py", "backend/tests/unit/test_r11_version_branch_context.py"]
assert all(item["same_git_blob"] for item in protected)
source_same = blob(FIX, "backend/src/ai_intel/assessment/version_ranges.py") == blob(CODE, "backend/src/ai_intel/assessment/version_ranges.py") == blob(MATERIAL, "backend/src/ai_intel/assessment/version_ranges.py")
assert source_same
final_changed = git("diff", "--numstat", FIX, CODE).decode().splitlines()
assert final_changed == ["0\t1\tbackend/tests/unit/test_r11_version_branch_context.py"]
junit = {label: summarize_xml(blob(MATERIAL, f"reports/runs/recovery_r11_version_ranges_fix1_20261016/{label}.xml")) for label in ("independent_original_red", "new_boundaries_before_red", "final_original_94", "final_original_175", "final_original_33", "final_new_67")}
junit["old_fixed_unit_regression"] = summarize_xml(blob(MATERIAL, "reports/runs/recovery_r11_version_ranges_20261016/fixed_unit_regression.xml"))
result = {"source_fix_sha": FIX, "code_sha": CODE, "material_sha": MATERIAL, "material_checks": material_checks, "original_cases": original_cases, "protected_blobs": protected, "changed_source_test_contract_progress_lock_paths": changed, "source_same_from_fix_to_final_material": source_same, "fix_to_final_code_numstat": final_changed, "junit": junit}
(RUN / "fixed_material_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"materials": [{key: item[key] for key in ("folder", "manifest_git_sha256", "listed_artifacts", "including_manifest", "git_mismatches", "raw_evidence_mismatches", "ordinary_eol_only_paths", "non_eol_ordinary_mismatches")} for item in material_checks], "original_cases": original_cases, "protected_blob_mismatches": [item["path"] for item in protected if not item["same_git_blob"]], "junit": junit}, ensure_ascii=False, indent=2))
