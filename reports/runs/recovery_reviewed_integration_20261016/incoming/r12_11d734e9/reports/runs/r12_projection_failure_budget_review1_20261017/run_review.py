"""Use the frozen mature supervisor for short independent offline review checks."""

import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import batch13_checks_helper as checks

RUN = Path(__file__).parent
SOURCE_PATHS = [
    "src/ai_intel/retrieval/opensearch_client.py",
    "src/ai_intel/retrieval/runtime_policy.py",
    "tests/contract/test_r12_projection_failure_budget.py",
]
TEST_PATHS = [
    "tests/contract/test_r12_projection_total_budget_fix2.py",
    "tests/contract/test_r12_projection_failure_budget.py",
    str(RUN / "test_review_negative.py"),
]
RELATED_PATHS = [
    "tests/contract/test_r12_projection_deadline_io.py",
    "tests/unit/test_r12_default_projection_runtime.py",
    "tests/unit/test_r12_projection_terminal_constraints.py",
    "tests/unit/test_r12_hybrid.py",
    "tests/contract/test_r12_hybrid_contracts.py",
    "tests/unit/test_r01_runtime_settings.py",
    "tests/unit/test_r01_worker_configuration.py",
    "tests/unit/test_r03_jobs_contract.py",
    "tests/unit/test_r16_default_worker_registration.py",
    "tests/security/test_r12_retrieval_boundaries.py",
    "tests/security/test_r10_projection_scope.py",
    "tests/unit/test_r04_projection_boundaries.py",
    "tests/security/test_r07_job_execution_boundaries.py",
]


def pytest_command(label, paths):
    return [
        checks.PYTHON,
        "-m",
        "pytest",
        *paths,
        "-o",
        "addopts=",
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp=" + str(RUN / (label + "_tmp")),
        "--junitxml=" + str(RUN / (label + ".xml")),
    ]


label = sys.argv[1]
commands = {
    "focused": pytest_command("focused", TEST_PATHS),
    "related": pytest_command("related", RELATED_PATHS),
    "material": [checks.PYTHON, str(RUN / "verify_material.py")],
    "material_fixed": [checks.PYTHON, str(RUN / "verify_material.py")],
    "terminal": [checks.PYTHON, str(RUN / "terminal_check.py")],
    "terminal_resource": [checks.PYTHON, str(RUN / "terminal_resource_recheck.py")],
    "seal": [checks.PYTHON, str(RUN / "seal_review.py")],
    "seal_fixed": [checks.PYTHON, str(RUN / "seal_review.py")],
    "delivery_seal": [checks.PYTHON, str(RUN / "seal_delivery.py")],
    "callers": [
        shutil.which("rg"),
        "-n",
        "consume_job|build_projection_job_handlers|make_knowledge_change_handler|"
        "prepare_generation|create_index|require_projection_deadline|execute_job",
        "src/ai_intel/workers/runtime.py",
        "src/ai_intel/workers/executor.py",
        "src/ai_intel/retrieval/runtime_policy.py",
        "src/ai_intel/retrieval/indexing.py",
        "src/ai_intel/retrieval/opensearch_client.py",
    ],
    "boundary": [
        shutil.which("git"),
        "diff",
        "--check",
        checks.BASELINE,
        checks.QUALIFIED,
        "--",
        "src/ai_intel/retrieval/opensearch_client.py",
        "src/ai_intel/retrieval/runtime_policy.py",
        "tests/contract/test_r12_projection_failure_budget.py",
    ],
    "cbm": [
        "C:/Windows/System32/wsl.exe",
        "-d",
        "Ubuntu-22.04",
        "--",
        "python3",
        "/mnt/d/wt/r12-pfbr1/reports/runs/r12_projection_failure_budget_review1_20261017/cbm_review.py",
    ],
    "cbm_resource_recheck": [
        "C:/Windows/System32/wsl.exe", "-d", "Ubuntu-22.04", "--", "python3",
        "/mnt/d/wt/r12-pfbr1/reports/runs/r12_projection_failure_budget_review1_20261017/cbm_resource_recheck.py",
    ],
    "style": [checks.PYTHON, "-m", "ruff", "check", *SOURCE_PATHS],
    "format": [checks.PYTHON, "-m", "ruff", "format", "--check", *SOURCE_PATHS],
    "types": [
        checks.PYTHON,
        "-m",
        "mypy",
        "--cache-dir=" + str(RUN / "mypy_cache"),
        "src/ai_intel/retrieval/opensearch_client.py",
        "src/ai_intel/retrieval/runtime_policy.py",
    ],
}
result = checks.execute(
    label, commands[label], timeout=25 if label == "cbm_resource_recheck" else 60,
    process_cap=16 if label in {"cbm", "cbm_resource_recheck"} else 10,
)
xml_path = RUN / (label + ".xml")
if xml_path.exists():
    cases = ET.parse(xml_path).getroot().findall(".//testcase")
    keys = [(case.get("classname"), case.get("name")) for case in cases]
    counts = {
        "tests": len(cases),
        "distinct_tests": len(set(keys)),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
    }
    (RUN / (label + ".counts.json")).write_text(json.dumps(counts, indent=2) + "\n")
    print(json.dumps(counts))
raise SystemExit(result)
