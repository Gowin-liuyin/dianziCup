"""Verify author manifests against immutable Git blobs and report checkout byte differences."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from review_checks import ROOT, RUN, now

BASELINE = "ed0e14a03a06ed104f23afd0be5407d873ed8edf"
CODE = "2fe903eaff4030b64b3f5789e8027e1e11e41694"
MATERIAL = "569d8a7dc81fcea6b524b4fa172a5c7977388b93"
PG = "6b10f2c4ed013f4375d51fc31e1cb317409730ac"
AUTHOR_RUN = "reports/runs/recovery_r11_forward_rules_sbom_20261016"


def git(*arguments):
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, timeout=30, check=False
    )
    assert result.returncode == 0
    return result.stdout


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    assert git("rev-parse", "HEAD").decode().strip() == MATERIAL
    assert not git(
        "status", "--porcelain", "--", "backend", "docs", "progress", "contracts"
    ).strip()
    source_path = AUTHOR_RUN + "/source_manifest.json"
    artifact_path = AUTHOR_RUN + "/artifact_manifest.json"
    source_blob = git("show", MATERIAL + ":" + source_path)
    artifact_blob = git("show", MATERIAL + ":" + artifact_path)
    source_manifest = json.loads(source_blob)
    artifacts = json.loads(artifact_blob)
    source_results = []
    artifact_results = []
    for entry in source_manifest["entries"]:
        name = entry["path"]
        raw = (ROOT / name).read_bytes()
        blob = git("show", CODE + ":" + name)
        source_results.append(
            {
                "path": name,
                "git_blob_sha256": sha(blob),
                "raw_sha256": sha(raw),
                "git_blob_id": git("rev-parse", CODE + ":" + name).decode().strip(),
                "frozen_blob_matches": sha(blob) == entry["git_blob_sha256"],
                "raw_matches_author": sha(raw) == entry["worktree_sha256"],
                "raw_equals_code_blob": raw == blob,
                "crlf_to_lf_equals_code_blob": raw.replace(b"\r\n", b"\n") == blob,
            }
        )
    for entry in artifacts:
        name = entry["path"]
        raw = (ROOT / name).read_bytes()
        blob = git("show", MATERIAL + ":" + name)
        artifact_results.append(
            {
                "path": name,
                "git_blob_sha256": sha(blob),
                "raw_sha256": sha(raw),
                "bytes": len(blob),
                "frozen_manifest_matches": sha(blob) == entry["sha256"]
                and len(blob) == entry["bytes"],
                "checkout_matches": raw == blob,
                "crlf_to_lf_equals_blob": raw.replace(b"\r\n", b"\n") == blob,
            }
        )
    old_paths = (
        git(
            "ls-tree",
            "-r",
            "--name-only",
            BASELINE,
            "--",
            "backend/src",
            "backend/migrations",
            "backend/tests",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "contracts",
            "config",
        )
        .decode()
        .splitlines()
    )
    old_results = []
    for name in old_paths:
        baseline = git("show", BASELINE + ":" + name)
        current = git("show", MATERIAL + ":" + name)
        old_results.append(
            {
                "path": name,
                "baseline_sha256": sha(baseline),
                "current_sha256": sha(current),
                "unchanged": baseline == current,
            }
        )
    approved_paths = [
        "backend/src/ai_intel/assessment/" + name + ".py"
        for name in (
            "assessment_persistence",
            "assessment_service",
            "persistence_contracts",
            "rule_persistence",
            "rule_service",
        )
    ] + [
        "backend/tests/integration/test_r11_pg_assessments.py",
        "backend/tests/integration/test_r11_assessment_raw_rechecks_pg.py",
        "backend/tests/contract/test_r11_pg_assessment_contracts.py",
        "backend/tests/unit/test_r11_pg_assessment_scope.py",
    ]
    approved = []
    for name in approved_paths:
        reference, current = git("show", PG + ":" + name), git("show", MATERIAL + ":" + name)
        approved.append(
            {
                "path": name,
                "reference": PG,
                "reference_sha256": sha(reference),
                "current_sha256": sha(current),
                "unchanged": reference == current,
            }
        )
    report_path = "reports/tasks/R11-forward-rules-sbom.md"
    report_blob = git("show", MATERIAL + ":" + report_path)
    (RUN / "fixed_author_report.md.txt").write_bytes(report_blob)
    junit = {}
    for path in (ROOT / AUTHOR_RUN).glob("*.xml"):
        doc = ET.parse(path).getroot()
        cases = doc.findall(".//testcase")
        junit[path.name] = {
            "tests": len(cases),
            "failed": len(doc.findall(".//failure")),
            "errors": len(doc.findall(".//error")),
            "skipped": len(doc.findall(".//skipped")),
        }
    prior_report = Path(
        "D:/wt/r12-production-review1/reports/reviews/recovery/G-D-R12-production-migration-review-1.md"
    )
    prior_manifest = Path(
        "D:/wt/r12-production-review1/reports/runs/recovery_r12_production_review1_20261016/review_manifest.json"
    )
    prior_report_raw, prior_manifest_raw = prior_report.read_bytes(), prior_manifest.read_bytes()
    prior_json = json.loads(prior_manifest_raw)
    prior_entries = prior_json if isinstance(prior_json, list) else prior_json["members"]
    prior_failures = []
    for entry in prior_entries:
        name = entry["path"]
        raw = (Path("D:/wt/r12-production-review1") / name).read_bytes()
        if sha(raw) != entry["sha256"]:
            prior_failures.append(name)
    (RUN / "fixed_prior_0020_review.md.txt").write_bytes(prior_report_raw)
    result = {
        "audited_at": now(),
        "baseline": BASELINE,
        "code": CODE,
        "material": MATERIAL,
        "author_source_manifest_path": source_path,
        "author_source_manifest_raw_sha256": sha((ROOT / source_path).read_bytes()),
        "author_source_manifest_blob_sha256": sha(source_blob),
        "source_entries": len(source_results),
        "author_artifact_manifest_path": artifact_path,
        "author_artifact_manifest_raw_sha256": sha((ROOT / artifact_path).read_bytes()),
        "author_artifact_manifest_blob_sha256": sha(artifact_blob),
        "artifact_entries": len(artifact_results),
        "author_report_raw_sha256": sha((ROOT / report_path).read_bytes()),
        "author_report_blob_sha256": sha(report_blob),
        "source_results": source_results,
        "artifact_results": artifact_results,
        "old_results": old_results,
        "approved_pg_results": approved,
        "author_junit_counts": junit,
        "prior_0020_report_raw_sha256": sha(prior_report_raw),
        "prior_0020_manifest_raw_sha256": sha(prior_manifest_raw),
        "prior_0020_manifest_entries": len(prior_entries),
        "prior_0020_manifest_failures": prior_failures,
    }
    (RUN / "material_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    summary = {
        key: value
        for key, value in result.items()
        if key not in {"source_results", "artifact_results", "old_results", "approved_pg_results"}
    }
    summary.update(
        source_blob_failures=sum(not x["frozen_blob_matches"] for x in source_results),
        source_raw_author_differences=sum(not x["raw_matches_author"] for x in source_results),
        artifact_blob_failures=sum(not x["frozen_manifest_matches"] for x in artifact_results),
        artifact_checkout_differences=sum(not x["checkout_matches"] for x in artifact_results),
        old_file_changes=sum(not x["unchanged"] for x in old_results),
        old_file_count=len(old_results),
        approved_pg_changes=sum(not x["unchanged"] for x in approved),
    )
    print(json.dumps(summary, indent=2))
    assert not any(not x["frozen_blob_matches"] for x in source_results)
    assert not any(not x["frozen_manifest_matches"] for x in artifact_results)
    assert not any(not x["unchanged"] for x in old_results + approved)
    assert (
        sha(prior_report_raw) == "89579f9db93b36a48154ef6f8f301ad0fcabe1882e855bd91cad5f06c4559edb"
    )
    assert (
        sha(prior_manifest_raw)
        == "cb27ac0e914a48a4d49587b144b0d46b855f25d031f324e4bc4f8b8c65ac3bd6"
    )
    assert len(prior_entries) == 113 and not prior_failures


if __name__ == "__main__":
    main()
