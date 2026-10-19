"""Bind review scope, document versions and test counts to the fixed worktree."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ElementTree

RUN_DIRECTORY = Path(__file__).resolve().parent
WORKTREE = RUN_DIRECTORY.parents[2]
CODE = "8e150878a76e541e377b300f851d9c7caf919019"
HEAD = "82a85b08eea39acd10b4ebf6a2966f5e39108799"
BASE = "cb34097898b412390ee7e119d0d5c2c90d090673"


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=WORKTREE)


def main():
    paths = [
        "AGENTS.md",
        "docs/plan/00_execution_map.md",
        "docs/plan/12_recovery_task_cards_20261014.md",
        "docs/tasks/T08_network_and_sources.md",
        "docs/tasks/T19_structured_enrichment.md",
        "docs/tasks/T23_poc_scores_impact.md",
        "docs/plan/03_data_contracts.md",
        "docs/plan/04_workflows_and_algorithms.md",
        "docs/plan/05_api_and_tool_contracts.md",
        "docs/plan/06_testing_and_evaluation.md",
        "docs/plan/07_sources_and_resources.md",
        "docs/decisions/CR-R06.md",
        "docs/decisions/CR-R07_enrichment_candidate_seam.md",
        "docs/decisions/CR-R07_typed_signal_claim_v3.md",
        "progress/task_state.json",
        "progress/context_handoff.md",
        "contracts/task_manifest.json",
        "reports/tasks/R08-aggregate-connectors.md",
    ]
    documents = [{"path": path, "git_blob_sha256": hashlib.sha256(git("show", f"{HEAD}:{path}")).hexdigest()} for path in paths]
    counts = {}
    for label in ("new_unit", "new_contract", "new_security", "network_regression", "r07_regression", "independent_boundaries_final"):
        document = ElementTree.parse(RUN_DIRECTORY / f"{label}.xml")
        suites = document.findall("testsuite")
        counts[label] = {key: sum(int(suite.attrib[key]) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
    author = json.loads((RUN_DIRECTORY / "author_manifest_validation.json").read_text(encoding="utf-8"))
    receipt = {
        "worktree": str(WORKTREE),
        "head_sha": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("branch", "--show-current").decode().strip(),
        "base_sha": BASE,
        "code_sha": CODE,
        "tracked_worktree_diff": git("diff", "--name-only").decode().splitlines(),
        "code_to_head_business_diff": git("diff", "--name-only", f"{CODE}..{HEAD}", "--", "backend", "frontend", "config", "contracts", "progress", "docs").decode().splitlines(),
        "base_to_code_files": git("diff", "--name-only", f"{BASE}..{CODE}").decode().splitlines(),
        "counts": counts,
        "author_manifest_git_blob_failures": author["git_blob_failures"],
        "checkout_differences_are_only_crlf": all(entry["checkout_equals_blob"] or entry["checkout_lf_normalized_equals_blob"] for entry in author["entries"]),
        "reviewer_external_operations": {"official_document": 0, "account_authentication": 0, "provider_search": 0, "model": 0},
        "whole_r08_verification_changed": False,
        "initial_tool_diagnostic": {"code": 267, "cause": "review worktree did not exist before its explicitly authorized creation", "business_test": False},
        "documents": documents,
    }
    (RUN_DIRECTORY / "review_input_audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key != "documents"}, ensure_ascii=False))
    assert receipt["head_sha"] == HEAD
    assert receipt["tracked_worktree_diff"] == []
    assert receipt["code_to_head_business_diff"] == []
    assert not receipt["author_manifest_git_blob_failures"]
    assert receipt["checkout_differences_are_only_crlf"]
    assert all(count["tests"] > 0 and count["failures"] == count["errors"] == count["skipped"] == 0 for count in counts.values())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
