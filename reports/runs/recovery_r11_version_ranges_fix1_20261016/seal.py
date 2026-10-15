"""Seal the scoped branch fix and verify unchanged baseline paths and copied review cases."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as xml
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_DIRECTORY = Path(__file__).resolve().parent
WORKSPACE = RUN_DIRECTORY.parents[2]
PREVIOUS_MATERIAL_SHA = "5a35cc5e6dec307e7d5fbdf06c9d49881679cb61"
CODE_SHA = "71e724131daf4d03372392d58cd17c764c3e2e40"
REPORT = "reports/tasks/R11-version-ranges-fix1.md"
INDEPENDENT_CASE_SHA256 = (
    "b76bd21296694bf47cebf01d2878f22f17830bb86d8fbdbedfa166a6630af5e6"
)


def git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=WORKSPACE, capture_output=True, check=True
    ).stdout


def write_json(name: str, value: object) -> None:
    (RUN_DIRECTORY / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def file_digest(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "path": path.relative_to(WORKSPACE).as_posix(),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def main() -> None:
    assert git_bytes("rev-parse", "HEAD").decode().strip() == CODE_SHA
    preserved_files = (
        "backend/src/ai_intel/infrastructure/process_limits.py",
        "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py",
        "backend/tests/unit/test_r20_native_cpu_guard.py",
        "backend/tests/unit/test_t26_version_engine.py",
        "backend/tests/contract/test_r11_version_ranges_contract.py",
        "backend/tests/security/test_r11_version_ranges_security.py",
        "backend/src/ai_intel/domain/enrichment_values.py",
        "backend/pyproject.toml",
        "backend/uv.lock",
    )
    comparisons = []
    for filename in preserved_files:
        original = git_bytes("show", f"{PREVIOUS_MATERIAL_SHA}:{filename}")
        current = git_bytes("show", f"{CODE_SHA}:{filename}")
        assert original == current, filename
        comparisons.append(
            {
                "path": filename,
                "same_bytes": True,
                "sha256": hashlib.sha256(current).hexdigest(),
            }
        )
    independent_cases = file_digest(RUN_DIRECTORY / "test_independent_version_cases.py")
    assert independent_cases["sha256"] == INDEPENDENT_CASE_SHA256
    write_json(
        "preserved_blob_verification.json",
        {"files": comparisons, "copied_original_cases": independent_cases},
    )
    results = []
    for path in sorted(RUN_DIRECTORY.glob("*.xml")):
        root = xml.parse(path).getroot()
        results.append(
            {
                "file": path.name,
                "tests": sum(
                    int(suite.get("tests", "0")) for suite in root.iter("testsuite")
                ),
                "failures": sum(
                    int(suite.get("failures", "0")) for suite in root.iter("testsuite")
                ),
                "errors": sum(
                    int(suite.get("errors", "0")) for suite in root.iter("testsuite")
                ),
                "skipped": sum(
                    int(suite.get("skipped", "0")) for suite in root.iter("testsuite")
                ),
            }
        )
    write_json("test_results.json", results)
    paths = [
        path
        for path in RUN_DIRECTORY.rglob("*")
        if path.is_file()
        and path.name != "artifact_manifest.json"
        and path.suffix in {".log", ".xml", ".json", ".py"}
    ]
    paths.append(WORKSPACE / REPORT)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "task": "R11:T26 branch context and exclusion audit fix only",
        "status": "awaiting_review",
        "previous_code_sha": "3e896da58bdcabdd738a3430f7b77358e7f8b03a",
        "previous_material_sha": PREVIOUS_MATERIAL_SHA,
        "previous_manifest_sha256": "85fb8c8074bff0ebd5594339b4e465beab58656f446591a0c307b657cc480861",
        "code_sha": CODE_SHA,
        "code_tree": git_bytes("rev-parse", f"{CODE_SHA}^{{tree}}").decode().strip(),
        "report": REPORT,
        "scope_verification": {
            "unit": "passed",
            "contract": "passed",
            "security": "passed",
            "integration": "not_run",
            "frontend": "not_run",
            "e2e": "not_run",
            "live": "not_run",
            "manual": "not_run",
            "performance": "not_run",
        },
        "repository_unit": "not_run this fix; previous original 1627 passed / 4 R20 failures retained, no new full-suite green claim",
        "case_preservation": independent_cases,
        "raw_attribute_scope": "This run's *.log/*.xml/*.json and exact copied test_independent_version_cases.py are -text -diff; helpers/report remain ordinary Git text.",
        "artifacts": [file_digest(path) for path in sorted(paths)],
        "self_hash_policy": "Manifest excludes its own bytes; final handoff provides the manifest hash and material commit to avoid circular hashes.",
    }
    write_json("artifact_manifest.json", manifest)
    print(
        json.dumps(
            {
                "manifest": file_digest(RUN_DIRECTORY / "artifact_manifest.json"),
                "cases": results,
                "preserved_files": len(comparisons),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
