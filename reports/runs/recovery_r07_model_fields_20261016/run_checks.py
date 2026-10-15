"""Record bounded local checks without reading model credentials or invoking live APIs."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"


def record(label: str, command: list[str], cwd: Path = ROOT) -> None:
    if sys.argv[1] == "final" and len(sys.argv) > 2:
        label = sys.argv[2] + "_" + label
    started = datetime.now(UTC).isoformat()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    completed = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, check=False)
    (RUN / f"{label}.log").write_bytes(completed.stdout + completed.stderr)
    receipt = {
        "command": command,
        "cwd": str(cwd),
        "started_at": started,
        "completed_at": datetime.now(UTC).isoformat(),
        "exit_code": completed.returncode,
    }
    (RUN / f"{label}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(label, completed.returncode, completed.stdout.decode("utf-8", errors="replace")[-4000:])


def cbm(label: str, operation: str) -> None:
    record(
        label,
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "--",
            "sh",
            "-c",
            "CBM_CACHE_DIR=/tmp/dianzi-cbm-r07-model-fields-20261016 "
            "CBM_ALLOWED_ROOT=/mnt/d/wt/r07-model-fields/backend/src "
            "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli " + operation,
        ],
    )


if sys.argv[1] == "preflight":
    cbm(
        "cbm_index",
        "index_repository --repo-path /mnt/d/wt/r07-model-fields/backend/src "
        "--mode fast --persistence false --name r07-model-fields-src",
    )
    cbm("cbm_schema", "get_graph_schema --project r07-model-fields-src")
    cbm("cbm_architecture", "get_architecture --project r07-model-fields-src --format json")
    cbm(
        "cbm_generate_trace",
        "trace_path --project r07-model-fields-src "
        "--function-name r07-model-fields-src.ai_intel.infrastructure.models.generation."
        "GenerationClient.generate --direction both --format json --depth 3 --limit 70",
    )
    record(
        "rg_model_callers",
        [
            "rg",
            "-n",
            ("GenerationClient|\\.generate\\(|EnrichmentContext|EvidenceBoundCandidate"),
            "backend/src",
            "backend/tests",
        ],
    )
elif sys.argv[1] == "tests":
    label = sys.argv[2] if len(sys.argv) > 2 else "tests_initial"
    record(
        label,
        [
            PYTHON,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "-v",
            "tests/unit/test_r07_model_fields.py",
            "tests/contract/test_r07_model_field_contract.py",
            "tests/security/test_r07_model_field_security.py",
            "--junitxml=" + str(RUN / f"{label}.xml"),
        ],
        ROOT / "backend",
    )
elif sys.argv[1] == "final":
    files = [
        "src/ai_intel/enrichment/model_fields.py",
        "src/ai_intel/enrichment/field_sources.py",
        "tests/unit/test_r07_model_fields.py",
        "tests/contract/test_r07_model_field_contract.py",
        "tests/security/test_r07_model_field_security.py",
    ]
    record("ruff", [PYTHON, "-m", "ruff", "check", *files], ROOT / "backend")
    record("format", [PYTHON, "-m", "ruff", "format", "--check", *files], ROOT / "backend")
    record(
        "mypy",
        [PYTHON, "-m", "mypy", "--config-file", "pyproject.toml", *files[:2]],
        ROOT / "backend",
    )
    record(
        "regression",
        [
            PYTHON,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "-v",
            "tests/unit/test_r07_model_fields.py",
            "tests/contract/test_r07_model_field_contract.py",
            "tests/security/test_r07_model_field_security.py",
            "tests/unit/test_r07_enrichment_contracts.py",
            "tests/unit/test_t19_structured_enrichment.py",
            "tests/unit/test_r05_generation.py",
            "tests/unit/test_r05_generation_review_fixes.py",
            "tests/contract/test_t18_model_clients.py",
            "tests/contract/test_t20_claim_extraction.py",
            "tests/contract/test_t22_research_and_document_links.py",
            "tests/contract/test_t23_poc_scores_impact.py",
            "--junitxml=" + str(RUN / "regression.xml"),
        ],
        ROOT / "backend",
    )
    record("diff_check", ["git", "diff", "--check"])
    cbm(
        "cbm_index_final",
        "index_repository --repo-path /mnt/d/wt/r07-model-fields/backend/src "
        "--mode fast --persistence false --name r07-model-fields-src",
    )
    cbm(
        "cbm_field_trace",
        "trace_path --project r07-model-fields-src "
        "--function-name r07-model-fields-src.ai_intel.enrichment.model_fields."
        "generate_model_field_attempts --direction both --format json --depth 3 --limit 70",
    )
    record(
        "rg_model_callers_final",
        [
            "rg",
            "-n",
            ("generate_model_field_attempts|validate_field_candidate|GenerationClient"),
            "backend/src",
            "backend/tests",
        ],
    )
    record("secret_scan", [PYTHON, str(Path(__file__).resolve()), "scope_scan"])
elif sys.argv[1] == "scope_scan":
    sys.path.insert(0, str(ROOT / "scripts"))
    from security_scan import PATTERNS

    owned_paths = [
        ROOT / "backend/src/ai_intel/enrichment/model_fields.py",
        ROOT / "backend/src/ai_intel/enrichment/field_sources.py",
        ROOT / "backend/tests/unit/test_r07_model_fields.py",
        ROOT / "backend/tests/contract/test_r07_model_field_contract.py",
        ROOT / "backend/tests/security/test_r07_model_field_security.py",
    ]
    owned_paths.extend(path for path in RUN.iterdir() if path.suffix in {".py", ".json", ".log"})
    findings = [
        {"path": str(path.relative_to(ROOT)), "pattern_id": pattern_name}
        for path in owned_paths
        for pattern_name, pattern in PATTERNS.items()
        if pattern.search(path.read_text(encoding="utf-8", errors="replace"))
    ]
    print(json.dumps({"files_checked": len(owned_paths), "findings": findings}))
    sys.exit(1 if findings else 0)
elif sys.argv[1] == "seal":
    source_commit = "6463e62bd0504e6cf83fd84b6d64c8bbfd33f994"
    base_commit = "cb34097898b412390ee7e119d0d5c2c90d090673"
    source_diff = subprocess.run(
        ["git", "diff", "--binary", base_commit, source_commit],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    (RUN / "source.patch").write_bytes(source_diff)
    changed_paths = (
        subprocess.run(
            ["git", "diff", "--name-only", base_commit, source_commit],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .splitlines()
    )
    source_files = [
        {
            "path": path,
            "worktree_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
            "git_blob_sha256": hashlib.sha256(
                subprocess.run(
                    ["git", "show", source_commit + ":" + path],
                    cwd=ROOT,
                    capture_output=True,
                    check=True,
                ).stdout
            ).hexdigest(),
        }
        for path in changed_paths
    ]
    artifact_paths = [ROOT / "reports/tasks/R07-model-fields.md"]
    artifact_paths.extend(
        path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json"
    )
    artifacts = [
        {
            "path": str(path.relative_to(ROOT)),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(artifact_paths)
    ]
    manifest = {
        "status": "awaiting_review",
        "source_commit": source_commit,
        "base_commit": base_commit,
        "sealed_at": datetime.now(UTC).isoformat(),
        "source_files": source_files,
        "artifacts": artifacts,
        "verification": {
            "unit": "passed",
            "contract": "passed",
            "security": "passed",
            "integration": "not_run",
            "live": "not_run",
            "manual": "not_run",
        },
        "tests": {
            "new_unit": 56,
            "new_contract": 4,
            "new_security": 16,
            "related_regression": 160,
            "total": 236,
        },
        "external_calls": 0,
        "fee": "unknown",
    }
    (RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "source_commit": source_commit,
                "source_files": len(source_files),
                "artifact_files": len(artifacts),
                "status": "awaiting_review",
            }
        )
    )
elif sys.argv[1] == "handoff_checks":
    record(
        "report_ruff",
        [
            PYTHON,
            "-m",
            "ruff",
            "check",
            "--config",
            "backend/pyproject.toml",
            str(Path(__file__).resolve()),
        ],
    )
    record(
        "report_format",
        [
            PYTHON,
            "-m",
            "ruff",
            "format",
            "--check",
            "--config",
            "backend/pyproject.toml",
            str(Path(__file__).resolve()),
        ],
    )
    record("final_scope_scan", [PYTHON, str(Path(__file__).resolve()), "scope_scan"])
    record("frozen_source", ["git", "show", "--stat", "--oneline", "HEAD"])
elif sys.argv[1] == "post_commit_checks":
    record(
        "delivered_diff_check",
        ["git", "diff", "--check", "cb34097898b412390ee7e119d0d5c2c90d090673", "HEAD"],
    )
    record(
        "delivered_source_diff_check",
        [
            "git",
            "diff",
            "--check",
            "cb34097898b412390ee7e119d0d5c2c90d090673",
            "HEAD",
            "--",
            "backend/src/ai_intel/enrichment/model_fields.py",
            "backend/src/ai_intel/enrichment/field_sources.py",
            "backend/tests/unit/test_r07_model_fields.py",
            "backend/tests/contract/test_r07_model_field_contract.py",
            "backend/tests/security/test_r07_model_field_security.py",
        ],
    )
