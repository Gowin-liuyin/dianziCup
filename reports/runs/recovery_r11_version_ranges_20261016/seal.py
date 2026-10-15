"""Seal this slice's original command bytes and separately verify unchanged R20 baseline blobs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as xml
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_DIRECTORY = Path(__file__).resolve().parent
WORKSPACE = RUN_DIRECTORY.parents[2]
BASELINE_SHA = "349c5e3ec27196257b98cdfcb63c75fb50157978"
DEPENDENCY_SHA = "f62466ff3282c872336288fc42e600e4e2dcc84a"
CODE_SHA = "3e896da58bdcabdd738a3430f7b77358e7f8b03a"
REPORT = "reports/tasks/R11-version-ranges.md"


def git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=WORKSPACE, capture_output=True, check=True
    ).stdout


def file_digest(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "path": path.relative_to(WORKSPACE).as_posix(),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def write_json(name: str, value: object) -> None:
    (RUN_DIRECTORY / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    assert git_bytes("rev-parse", "HEAD").decode().strip() == CODE_SHA
    r20_files = (
        "backend/src/ai_intel/infrastructure/process_limits.py",
        "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py",
        "backend/tests/unit/test_r20_native_cpu_guard.py",
    )
    comparison = []
    for filename in r20_files:
        baseline = git_bytes("show", f"{BASELINE_SHA}:{filename}")
        current = git_bytes("show", f"{CODE_SHA}:{filename}")
        comparison.append(
            {
                "path": filename,
                "baseline_sha256": hashlib.sha256(baseline).hexdigest(),
                "current_sha256": hashlib.sha256(current).hexdigest(),
                "same_bytes": baseline == current,
            }
        )
    write_json("r20_baseline_blob_comparison.json", comparison)
    test_results = []
    for path in sorted(RUN_DIRECTORY.glob("*.xml")):
        root = xml.parse(path).getroot()
        test_results.append(
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
    write_json("test_results.json", test_results)
    paths = [
        path
        for path in RUN_DIRECTORY.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    paths.append(WORKSPACE / REPORT)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "task": "R11:T26 internal exact version rules only",
        "status": "awaiting_review",
        "baseline_sha": BASELINE_SHA,
        "dependency_origin_sha": DEPENDENCY_SHA,
        "dependency_local_sha": "d7b3ea4d7c377cce8454b932d308e06feac85afd",
        "code_sha": CODE_SHA,
        "code_tree": git_bytes("rev-parse", f"{CODE_SHA}^{{tree}}").decode().strip(),
        "report": REPORT,
        "raw_attribute_scope": "Only this run's *.log/*.xml/*.json are -text -diff; .gitattributes is ordinary normalized Git text, not original run output.",
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
        "broader_unit_regression": "failed: 1627 passed / 4 existing R20 failures; default 60% threshold retained",
        "r20_replay_limit": "16 passed with --no-cov does not replace broad default-coverage failures or prove their cause",
        "artifacts": [file_digest(path) for path in sorted(paths)],
        "self_hash_policy": "Manifest excludes its own bytes; final response supplies the manifest SHA256 and material commit SHA to avoid circular claims.",
    }
    write_json("artifact_manifest.json", manifest)
    print(
        json.dumps(
            {
                "manifest": file_digest(RUN_DIRECTORY / "artifact_manifest.json"),
                "tests": test_results,
                "unchanged_r20": comparison,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
