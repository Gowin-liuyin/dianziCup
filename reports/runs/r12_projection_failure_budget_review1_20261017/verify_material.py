"""Verify frozen author's raw archives and distinct counts independently of report prose."""

import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
MATERIAL = "7813bbf27e31e66d5f53cd595a0278d962092a39"
AUTHOR_RUN = "reports/runs/r12_projection_failure_budget_20261017"
COPIED = RUN / "author_material_fixed"
COPIED.mkdir(exist_ok=True)


def from_git(path):
    return subprocess.check_output(["git", "show", MATERIAL + ":" + path], cwd=ROOT, timeout=10)


def archive_data(name):
    path = COPIED / name
    assert path.parent == COPIED
    assert not path.exists()
    raw = from_git(AUTHOR_RUN + "/" + name)
    path.write_bytes(raw)
    return raw


def test_keys(raw):
    cases = ET.fromstring(raw).findall(".//testcase")
    return {(case.get("classname"), case.get("name")) for case in cases}, cases


metadata = json.loads(archive_data("input_metadata.json"))
archives = json.loads(archive_data("raw_log_manifest.json"))
archive_results = []
for name, expected in archives.items():
    raw_archive = archive_data(expected["archive"])
    raw = gzip.decompress(raw_archive)
    checks = {
        "archive_hash_match": hashlib.sha256(raw_archive).hexdigest()
        == expected["archive_metadata"]["raw_sha256"],
        "archive_bytes_match": len(raw_archive) == expected["archive_metadata"]["bytes"],
        "raw_hash_match": hashlib.sha256(raw).hexdigest() == expected["raw_sha256"],
        "raw_bytes_match": len(raw) == expected["bytes"],
    }
    assert all(checks.values()), name
    (COPIED / name).write_bytes(raw)
    archive_results.append({"path": name, **checks})
report = from_git("reports/tasks/R12-projection-failure-budget.md")
(COPIED / "R12-projection-failure-budget.md").write_bytes(report)
author_counts = {}
author_keys = set()
for label in ("baseline_oracle", "focused_fixed", "related_regression_fixed"):
    receipt = json.loads(archive_data(label + ".json"))
    raw = (COPIED / (label + ".junit.xml")).read_bytes()
    keys, cases = test_keys(raw)
    author_counts[label] = {
        "exit_code": receipt["exit_code"],
        "tests": len(cases),
        "distinct_tests": len(keys),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
    }
    if label != "baseline_oracle":
        author_keys.update(keys)
    for relative, reported_hash in receipt["source_sha256"].items():
        raw_source = (
            subprocess.check_output(
                ["git", "show", "8c48b61c02860166bdda0986e984058e8a824188:" + relative],
                cwd=ROOT,
                timeout=10,
            )
            if label == "baseline_oracle"
            else (ROOT / relative).read_bytes()
        )
        assert reported_hash in {
            hashlib.sha256(raw_source).hexdigest(),
            hashlib.sha256(raw_source.replace(b"\r\n", b"\n")).hexdigest(),
            hashlib.sha256(raw_source.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest(),
        }, relative
own_counts = {}
own_keys = set()
for label in ("focused", "related"):
    keys, cases = test_keys((RUN / (label + ".xml")).read_bytes())
    own_counts[label] = len(keys)
    own_keys.update(keys)
result = {
    "author_material_sha": MATERIAL,
    "author_report_git_bytes_sha256": hashlib.sha256(report).hexdigest(),
    "archive_count": len(archive_results),
    "all_archives_and_raw_verified": True,
    "archives": archive_results,
    "author_counts": author_counts,
    "author_final_distinct": len(author_keys),
    "review_counts": own_counts,
    "review_final_distinct": len(own_keys),
    "author_tests_missing_from_review": sorted(author_keys - own_keys),
    "independent_new_tests": sorted(own_keys - author_keys),
    "original_oracle_metadata_unchanged": metadata["original_oracle_unchanged"],
    "baseline_receipt_matches_baseline_and_final_receipts_match_source": True,
}
assert len(author_keys) == 167
assert len(own_keys) == 179
assert not (author_keys - own_keys)
(RUN / "material_validation.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({key: value for key, value in result.items() if key not in {
    "archives", "independent_new_tests", "author_tests_missing_from_review"
}}))
