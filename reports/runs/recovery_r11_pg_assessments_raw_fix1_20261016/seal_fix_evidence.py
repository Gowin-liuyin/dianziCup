"""Retain original red evidence and verify this fix's committed source and raw artifacts."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from run_checks import ROOT, RUN, connection, now, seal

CODE_COMMIT = "2ddc8fe2ff3e7becfad3b1774a10407911eacbe6"
PRIOR_CODE = "d56a1ed306d975be408a2f6f8fbe3e905d940643"
PRIOR_MATERIAL = "ad122224b02ec16194e03f937b02a218ff6faaa5"
SOURCE_PATHS = (
    "backend/src/ai_intel/assessment/assessment_service.py",
    "backend/src/ai_intel/assessment/rule_persistence.py",
    "backend/tests/integration/test_r11_assessment_raw_rechecks_pg.py",
    "backend/src/ai_intel/assessment/rule_service.py",
    "backend/src/ai_intel/infrastructure/content_store.py",
    "backend/src/ai_intel/knowledge/revisions.py",
    "backend/tests/integration/test_r11_pg_assessments.py",
)


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, timeout=10)


def main():
    counts = {}
    for path in sorted(RUN.glob("*.xml")):
        suites = ET.parse(path).getroot().findall("testsuite")
        counts[path.name] = {
            key: sum(int(suite.get(key, "0")) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
    assert counts["original_two_red.xml"]["failures"] == 2
    assert counts["raw_final_15.xml"] == {
        "tests": 15, "failures": 0, "errors": 0, "skipped": 0
    }
    sources = []
    for relative in SOURCE_PATHS:
        path = ROOT / relative
        blob = git("rev-parse", CODE_COMMIT + ":" + relative).decode().strip()
        assert blob == git("hash-object", "--", relative).decode().strip()
        sources.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "git_blob": blob,
            "git_blob_sha256": hashlib.sha256(git("cat-file", "blob", blob)).hexdigest(),
        })
    original_tests = SOURCE_PATHS[-1]
    assert git("rev-parse", CODE_COMMIT + ":" + original_tests) == git(
        "rev-parse", PRIOR_CODE + ":" + original_tests
    )
    prior_run = ROOT / "reports/runs/recovery_r11_pg_assessments_20261016"
    prior_manifest = json.loads((prior_run / "artifact_manifest.json").read_text())
    for entry in prior_manifest:
        assert hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
        assert hashlib.sha256(git("show", PRIOR_MATERIAL + ":" + entry["path"])).hexdigest() == entry["sha256"]
    reviewer_probe = Path("D:/wt/r11-pg-assessments-review1/reports/runs/recovery_r11_pg_assessments_review1_20261016/test_independent_boundaries.py")
    copied_probe = RUN / "independent_probe_original.py"
    assert copied_probe.read_bytes() == reviewer_probe.read_bytes()
    for name, payload in (
        ("test_counts.json", counts),
        ("source_manifest.json", sources),
        ("freeze_receipt.json", {
            "recorded_at": now(),
            "code_commit": CODE_COMMIT,
            "prior_code_commit": PRIOR_CODE,
            "prior_material_commit": PRIOR_MATERIAL,
            "prior_raw_artifacts_verified_unchanged": len(prior_manifest),
            "original_pg_test_blob_unchanged": True,
            "reviewer_probe_path": str(reviewer_probe),
            "reviewer_probe_sha256": hashlib.sha256(copied_probe.read_bytes()).hexdigest(),
            "copied_probe_executed": False,
            "independent_review": "awaiting_review",
            "external_model_calls": 0,
            "external_provider_calls": 0,
            "external_source_calls": 0,
            "cost": "unknown",
            "human_labels": 0,
            "live": "not_run",
            "manual": "not_run",
            "production_0021": "not_run",
        }),
    ):
        (RUN / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    password = connection().password or ""
    leaked = [
        path.name for path in RUN.rglob("*") if path.is_file()
        and password and password.encode() in path.read_bytes()
    ]
    assert not leaked, "credential leakage detected; never print the secret"
    (RUN / "credential_scan.json").write_text(json.dumps({
        "recorded_at": now(), "actual_test_password_matches": leaked,
    }, indent=2), encoding="utf-8")
    seal()
    print(f"Verified {len(sources)} committed sources and {len(prior_manifest)} unchanged prior artifacts.")


if __name__ == "__main__":
    main()
