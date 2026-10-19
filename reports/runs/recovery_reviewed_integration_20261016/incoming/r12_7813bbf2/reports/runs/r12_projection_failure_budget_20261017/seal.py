"""Hash immutable inputs and preserve original command logs in lossless compressed archives."""

import gzip
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASELINE = "8c48b61c02860166bdda0986e984058e8a824188"
SOURCE_COMMIT = "9cd6381eacc67853c055643d634ffb1812875214"
INPUTS = (
    "AGENTS.md",
    "docs/plan/00_execution_map.md",
    "docs/plan/12_recovery_task_cards_20261014.md",
    "docs/plan/08_code_style.md",
    "docs/plan/04_workflows_and_algorithms.md",
    "docs/plan/05_api_and_tool_contracts.md",
    "docs/plan/06_testing_and_evaluation.md",
    "docs/tasks/T30_hybrid_retrieval.md",
    "docs/decisions/CR-R12_default_projection_runtime.md",
    "docs/decisions/CR-R12_production_hybrid_migration.md",
    "docs/decisions/CR-R12_projection_terminal_constraint_budget.md",
    "progress/task_state.json",
    "progress/context_handoff.md",
    "backend/src/ai_intel/retrieval/opensearch_client.py",
    "backend/src/ai_intel/retrieval/runtime_policy.py",
    "backend/src/ai_intel/retrieval/indexing.py",
    "backend/src/ai_intel/infrastructure/settings.py",
    "backend/tests/contract/test_r12_projection_total_budget_fix2.py",
)


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT).strip().decode()


def metadata(path):
    return {
        "bytes": path.stat().st_size,
        "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main():
    original_report = Path(
        "D:/wt/r10-default-worker-graph/reports/tasks/R10-default-worker-graph.md"
    )
    original_test = "backend/tests/contract/test_r12_projection_total_budget_fix2.py"
    assert git("hash-object", original_test) == git("rev-parse", BASELINE + ":" + original_test)
    inputs = {
        relative: {
            **metadata(ROOT / relative),
            "baseline_git_blob": git("rev-parse", BASELINE + ":" + relative),
            "current_git_blob": git("hash-object", relative),
        }
        for relative in INPUTS
    }
    inputs[str(original_report)] = metadata(original_report)
    skill = Path(
        "C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.3.1/skills/ponytail/SKILL.md"
    )
    inputs[str(skill)] = metadata(skill)
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "baseline": BASELINE,
        "source_commit": SOURCE_COMMIT,
        "inputs": inputs,
        "source_files": {
            relative: {
                **metadata(ROOT / relative),
                "source_git_blob": git("rev-parse", SOURCE_COMMIT + ":" + relative),
            }
            for relative in (
                "backend/src/ai_intel/retrieval/opensearch_client.py",
                "backend/src/ai_intel/retrieval/runtime_policy.py",
                "backend/tests/contract/test_r12_projection_failure_budget.py",
            )
        },
        "junit": {},
        "original_oracle_unchanged": True,
        "real_services_started": 0,
        "paid_model_calls": 0,
        "actual_secret_scan": "not_run",
    }
    for path in RUN.glob("*.junit.xml"):
        suites = ElementTree.parse(path).getroot()
        result["junit"][path.name] = [suite.attrib for suite in suites.iter("testsuite")]
    (RUN / "input_metadata.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    logs = {}
    for path in (*RUN.glob("*.log"), *RUN.glob("*.xml")):
        original = path.read_bytes()
        archive = path.with_name(path.name + ".gz")
        archive.write_bytes(gzip.compress(original, mtime=0))
        assert gzip.decompress(archive.read_bytes()) == original
        logs[path.name] = {
            **metadata(path),
            "archive": archive.name,
            "archive_metadata": metadata(archive),
        }
    (RUN / "raw_log_manifest.json").write_text(json.dumps(logs, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"source_commit": SOURCE_COMMIT, "inputs": len(inputs), "lossless_logs": len(logs)}
        )
    )


if __name__ == "__main__":
    main()
