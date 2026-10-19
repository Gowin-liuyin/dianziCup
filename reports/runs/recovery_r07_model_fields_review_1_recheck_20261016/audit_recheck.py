"""Audit named original, fixed repair and recheck evidence without rewriting any raw file."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FULL = "ef24758bd8e9e3e1e8e24760d330a9ffe62af341"
CODE = "696b1d88045ee862db1af3aaf569574ad361feaf"
BASE = "6199ad193d36da17c6597ee286aae40af887d425"
AUTHOR = Path("D:/wt/r07-model-fields-two-root-causes-fix")
ORIGINAL = Path("D:/wt/r07-model-fields")
OLD_REVIEW = Path("D:/wt/r07-model-fields-review-1/reports/runs/recovery_r07_model_fields_review_1_20261016")


def blob(sha, path):
    return subprocess.run(["git", "show", sha + ":" + path], cwd=ROOT, capture_output=True, check=True).stdout


def digest(value):
    return hashlib.sha256(value).hexdigest()


manifest_path = "reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/artifact_manifest.json"
manifest_bytes = blob(FULL, manifest_path)
manifest = json.loads(manifest_bytes)
assert digest(manifest_bytes) == "1d57ce725de521581cd3798ead71f47d17975430ab42747d2f1afce9606e5943"
fixed = []
for item in manifest["artifacts"]:
    path = item["path"].replace("\\", "/")
    committed = blob(FULL, path)
    author_raw = (AUTHOR / path).read_bytes()
    local = (ROOT / path).read_bytes()
    fixed.append({"path": path, "sha256": item["sha256"], "bytes": item["bytes"], "git_match": digest(committed) == item["sha256"] and len(committed) == item["bytes"], "author_match": digest(author_raw) == item["sha256"] and len(author_raw) == item["bytes"], "review_checkout_match": digest(local) == item["sha256"] and len(local) == item["bytes"]})
sources = []
for item in manifest["source_files"]:
    path = item["path"]
    committed = blob(FULL, path)
    sources.append({"path": path, "git_blob_sha256": digest(committed), "expected_git_blob_sha256": item["git_blob_sha256"], "full_equal_code": committed == blob(CODE, path), "git_match": digest(committed) == item["git_blob_sha256"], "author_worktree_match": digest((AUTHOR / path).read_bytes()) == item["worktree_sha256"]})
old_manifest_path = "reports/runs/recovery_r07_model_fields_20261016/artifact_manifest.json"
original_manifest = json.loads(blob(BASE, old_manifest_path))
original = []
for item in original_manifest["artifacts"]:
    path = item["path"].replace("\\", "/")
    raw = (ORIGINAL / path).read_bytes()
    old = blob(BASE, path)
    current = blob(FULL, path)
    original.append({"path": path, "raw_match": digest(raw) == item["sha256"] and len(raw) == item["bytes"], "git_exact_match": digest(current) == item["sha256"] and len(current) == item["bytes"], "git_unchanged": old == current, "lf_contents_equal": raw.replace(b"\r\n", b"\n") == current.replace(b"\r\n", b"\n")})
copied = [{"path": name, "byte_equal": (RUN / name).read_bytes() == (OLD_REVIEW / name).read_bytes(), "sha256": digest((RUN / name).read_bytes())} for name in ("test_independent_model_fields.py", "test_independent_boundary_extra.py")]
summary = {"manifest_sha256": digest(manifest_bytes), "fixed_full_sha": FULL, "fixed_code_sha": CODE, "repair_artifact_count": len(fixed), "repair_git_matches": sum(item["git_match"] for item in fixed), "repair_raw_matches": sum(item["author_match"] for item in fixed), "repair_review_matches": sum(item["review_checkout_match"] for item in fixed), "source_results": sources, "repair_artifacts": fixed, "original_count": len(original), "original_raw_matches": sum(item["raw_match"] for item in original), "original_git_exact_matches": sum(item["git_exact_match"] for item in original), "original_unchanged_git": sum(item["git_unchanged"] for item in original), "original_lf_equal": sum(item["lf_contents_equal"] for item in original), "original_artifacts": original, "review_test_copies": copied, "original_manifest_git_unchanged": blob(BASE, old_manifest_path) == blob(FULL, old_manifest_path)}
(RUN / "material_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key not in {"source_results", "repair_artifacts", "original_artifacts"}}, indent=2))
assert len(fixed) == 103 and all(item["git_match"] and item["author_match"] for item in fixed)
assert all(item["git_match"] and item["full_equal_code"] and item["author_worktree_match"] for item in sources)
assert all(item["raw_match"] and item["git_unchanged"] and item["lf_contents_equal"] for item in original)
assert all(item["byte_equal"] for item in copied)
assert summary["original_manifest_git_unchanged"]
counts = []
for path in sorted(RUN.glob("*.xml")):
    cases = list(ET.parse(path).getroot().iter("testcase"))
    value = {"junit": path.name, "collected": len(cases), "passed": sum(all(case.find(tag) is None for tag in ("failure", "error", "skipped")) for case in cases), "failed": sum(case.find("failure") is not None for case in cases), "error": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)}
    counts.append(value)
for path in (ROOT / "reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/frozen_red.xml",):
    cases = list(ET.parse(path).getroot().iter("testcase"))
    counts.append({"junit": str(path.relative_to(ROOT)), "collected": len(cases), "passed": sum(all(case.find(tag) is None for tag in ("failure", "error", "skipped")) for case in cases), "failed": sum(case.find("failure") is not None for case in cases), "error": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)})
(RUN / "test_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
print(json.dumps(counts, indent=2))
