"""Bind the independent connector package to source blobs and actual recorded output."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

RUN_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = RUN_DIRECTORY.parents[2]
CODE_SHA = "8e150878a76e541e377b300f851d9c7caf919019"
SOURCE_PATHS = (
    "backend/src/ai_intel/assets/aggregate_observations.py",
    "backend/src/ai_intel/assets/hunter_aggregate.py",
    "backend/src/ai_intel/assets/quake_aggregate.py",
    "backend/tests/unit/test_r08_aggregate_connectors.py",
    "backend/tests/contract/test_r08_aggregate_contract.py",
    "backend/tests/security/test_r08_aggregate_boundary.py",
)


def freeze_artifacts() -> None:
    code_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
    ).strip()
    if code_head != CODE_SHA:
        raise ValueError("freeze manifest must be generated at the named code commit")
    source_entries = []
    for relative_path in SOURCE_PATHS:
        blob = subprocess.check_output(
            ["git", "show", f"{CODE_SHA}:{relative_path}"], cwd=REPOSITORY_ROOT
        )
        current = (REPOSITORY_ROOT / relative_path).read_bytes()
        if current != blob:
            raise ValueError("source working bytes must equal the frozen Git blob")
        source_entries.append({
            "path": relative_path,
            "size_bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        })
    verification = {}
    for label in ("new_checks_freeze", "network_regression", "r07_contract_regression"):
        output = (RUN_DIRECTORY / f"{label}.log").read_text(encoding="utf-8")
        match = re.search(r"(\d+) passed", output)
        if match is None:
            raise ValueError("recorded pytest output must report passed test count")
        verification[label] = {"passed": int(match[1]), "log": f"{label}.log"}
    paths = sorted(path for path in RUN_DIRECTORY.iterdir() if path.is_file())
    paths.append(REPOSITORY_ROOT / "reports/tasks/R08-aggregate-connectors.md")
    artifact_entries = [
        {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in paths
        if path.name != "artifact_manifest.json"
    ]
    manifest = {
        "schema_version": "r08-aggregate-artifact-manifest-1",
        "generated_at": datetime.now(UTC).isoformat(),
        "code_sha": CODE_SHA,
        "base_sha": "cb34097898b412390ee7e119d0d5c2c90d090673",
        "status": "awaiting_review",
        "verification": verification,
        "integration": "not_run",
        "live": "not_run",
        "manual": "not_run",
        "live_query_count": 0,
        "account_authentication_count": 0,
        "official_document_operations": 7,
        "source_blobs": source_entries,
        "artifacts": artifact_entries,
    }
    (RUN_DIRECTORY / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"code_sha": CODE_SHA, "artifact_count": len(artifact_entries), "verification": verification}))


if __name__ == "__main__":
    freeze_artifacts()
