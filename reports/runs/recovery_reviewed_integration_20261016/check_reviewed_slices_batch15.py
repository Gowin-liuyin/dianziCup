"""Check integrated, independently reviewed slices without opening business resources."""

import importlib.util
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SITE = ROOT / "backend/.venv/Lib/site-packages"
sys.path.insert(0, str(SITE))

import batch13_checks_helper as checks


def main() -> int:
    limiter_path = Path(
        "D:/wt/r06-activation-database-fix5-20261017/reports/runs/"
        "recovery_r06_activation_prep_20261016/candidate/core/runtime_limits.py"
    )
    spec = importlib.util.spec_from_file_location("batch15_owned_job", limiter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("fixed_owned_job_module_unavailable")
    limiter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(limiter)
    limiter.MEMORY_TOTAL = 1024**3
    limiter.CPU_RATE = max(1, 20000 // os.cpu_count())
    owned_job = limiter.OwnedJob()
    old_environment = checks.environment

    def environment():
        values = old_environment()
        values["PYTHONPATH"] = str(SITE) + os.pathsep + values["PYTHONPATH"]
        values["PYTHONNOUSERSITE"] = "1"
        return values

    checks.environment = environment
    checks.PYTHON = (
        "C:/Users/yinha/AppData/Roaming/uv/python/"
        "cpython-3.12-windows-x86_64-none/python.exe"
    )
    checks.QUALIFIED = "6bb19fcd+982532dd;baseline=8c48b61"
    selected_group = sys.argv[1] if len(sys.argv) == 2 else "all"
    groups = {
        "core": [
            "tests/contract/test_r06_revision_mode_fixture_input_contract.py",
            "tests/unit/test_r06_revision_mode_reads.py",
            "../scripts/annotation/tests/test_prepare.py::CandidateContractTests",
            "../scripts/annotation/tests/test_prepare.py::AnnotationTests",
            "../scripts/annotation/tests/test_prepare_fix1.py::FamilyIdentityRegressionTests",
            "../scripts/annotation/tests/test_prepare_fix1.py::ReviewRecordRegressionTests",
            "../scripts/annotation/tests/test_crash_recovery.py::AtomicWriteTests",
            "../scripts/annotation/tests/test_fd_metadata_error.py",
        ],
        "cli": [
            "../scripts/annotation/tests/test_prepare.py::CliTests",
        ],
        "registry": [
            "../scripts/annotation/tests/test_prepare_fix1.py::CliRegistryRegressionTests",
        ],
        "crash": [
            "../scripts/annotation/tests/test_crash_recovery.py::ProcessInterruptionTests",
        ],
        "r12": [
            "tests/contract/test_r12_projection_total_budget_fix2.py",
            "tests/contract/test_r12_projection_failure_budget.py",
        ],
        "r07": [
            "tests/unit/test_r07_source_io_deadline.py",
            "tests/unit/test_r07_source_report_reader.py",
            "tests/unit/test_r16_verified_content.py",
        ],
        "r18_question": [
            "tests/unit/test_r18_question_credential.py",
            "tests/contract/test_r18_question_credential_contract.py",
            "tests/unit/test_r05_question_routes.py",
            "tests/unit/test_r18_expired_answer_problem.py",
        ],
        "r18_adapters": [
            "tests/unit/test_public_write_adapters.py",
            "tests/contract/test_public_write_adapter_contracts.py",
        ],
        "r18_cors": ["tests/unit/test_r18_public_bearer_cors.py"],
    }
    groups["r18_question_fix1"] = groups["r18_question"]
    groups["r18_style"] = [
        "src/ai_intel/api/question_routes.py",
        "tests/unit/test_r18_expired_answer_problem.py",
    ]
    groups["r18_style_fix1"] = groups["r18_style"]
    groups["r18_style_final"] = [
        *groups["r18_style"],
        "src/ai_intel/api/app.py",
        "tests/unit/test_r18_public_bearer_cors.py",
    ]
    if selected_group == "all":
        raise ValueError("combined_timeout_preserved;select_one_test_group")
    if selected_group not in groups:
        raise ValueError("unknown_batch15_test_group")
    label = "reviewed_slices_batch15_" + selected_group + "_split2"
    paths = groups[selected_group]
    command = (
        [checks.PYTHON, "-m", "ruff", "check", *paths]
        if selected_group.startswith("r18_style")
        else [
            checks.PYTHON, "-m", "pytest", *paths, "--no-cov", "-q",
            "--junitxml=" + str(RUN / (label + ".xml")),
        ]
    )
    code = checks.execute(
        label,
        command,
        timeout=60,
        process_cap=10,
    )
    counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    xml_path = RUN / (label + ".xml")
    if xml_path.exists():
        for suite in ET.parse(xml_path).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.get(key, 0))
    result = {
        "exit_code": int(code),
        "counts": counts,
        "paths": paths,
        "job_usage_before_supervisor_exit": owned_job.usage(),
        "process_memory_bytes": limiter.MEMORY_PER_PROCESS,
        "job_memory_bytes": limiter.MEMORY_TOTAL,
        "cpu_rate": limiter.CPU_RATE,
        "logical_cpu_count": os.cpu_count(),
        "job_scope": "supervisor_and_descendants;tool_ancestors_sampled_separately",
        "integration": "not_run",
        "live": "not_run",
        "manual": "not_run",
    }
    (RUN / (label + ".counts.json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result))
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
