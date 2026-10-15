"""Seal only this task's bounded evidence and explicit read-only contract inputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE = "c3a2abc9a5246993eabb351d26cfeb51d0270b31"
CODE = "41c61491b4429cc47dd970b201d9b2551cbb3a7f"


def identity(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    result: dict[str, object] = {
        "path": str(path),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        result["sha256_lf"] = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
    return result


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def main() -> None:
    tests = {}
    for path in sorted(RUN.glob("*.xml")):
        suite = ET.parse(path).getroot().find("testsuite")
        assert suite is not None
        tests[path.stem] = {
            **suite.attrib,
            "cases": [
                {
                    **case.attrib,
                    "failed": case.find("failure") is not None,
                    "skipped": case.find("skipped") is not None,
                }
                for case in suite.findall("testcase")
            ],
        }
    receipt_paths = []
    for path in sorted(RUN.glob("*.json")):
        if path.name == "artifact_manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "argv" in payload and "exit_code" in payload:
            receipt_paths.append(path)
    inputs = [
        ROOT / relative
        for relative in (
            "AGENTS.md",
            "docs/plan/00_execution_map.md",
            "docs/plan/04_workflows_and_algorithms.md",
            "docs/plan/06_testing_and_evaluation.md",
            "docs/plan/09_operations_delivery.md",
            "docs/plan/12_recovery_task_cards_20261014.md",
            "contracts/task_manifest.json",
            "progress/task_state.json",
            "progress/context_handoff.md",
            "docs/tasks/T45_security_regression.md",
            "docs/tasks/T49_observability_alerts.md",
            "docs/tasks/T50_recovery_and_backup.md",
            "docs/tasks/T51_ci_cd_release_pipeline.md",
            "backend/src/ai_intel/ingestion/parsing/pdf_text.py",
            "backend/src/ai_intel/infrastructure/models/semantic.py",
            "backend/tests/unit/test_r20_native_cpu_guard.py",
            "backend/tests/unit/test_r05_process_limits.py",
            "backend/pyproject.toml",
        )
    ]
    inputs.extend(
        Path(path)
        for path in (
            "D:/wt/r20-cpu-boundary-diagnosis/reports/tasks/R20-cpu-boundary-diagnosis.md",
            "D:/wt/r20-cpu-boundary-diagnosis/reports/runs/recovery_r20_cpu_boundary_diagnosis_20261015/artifact_manifest.json",
            "D:/dianzi/reports/reviews/recovery/G-C-native-cpu-guard-review-1.md",
            "D:/dianzi/reports/reviews/recovery/G-C-native-cpu-guard-review-1-recheck.md",
        )
    )
    products = [
        ROOT / path
        for path in (
            "backend/src/ai_intel/infrastructure/process_limits.py",
            "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py",
            "backend/tests/unit/test_r20_process_startup.py",
        )
    ]
    primary_cases = [
        {"source": "regression_guard.xml", "name": case["name"]}
        for case in tests["regression_guard"]["cases"]
        if case["name"] != "test_semantic_worker_retains_two_gib_and_thirty_cpu_seconds"
    ]
    primary_cases.extend(
        [
            {"source": "native_default.xml", "name": "original_default_coverage_python_gil_held"},
            {"source": "real_pdf_parent.xml", "name": "official_four_page_pdf_parent"},
            {"source": "initial_budget_exhausted.json", "name": "real_initial_cpu_exhaustion"},
            {"source": "pdf_coverage_after_fix.json", "name": "real_pypdf_coverage_after_limit"},
            {"source": "semantic_positive_control.json", "name": "real_spawn_pipe_synthetic_ok"},
        ]
    )
    assert len(primary_cases) == 20
    artifacts = [
        path
        for path in sorted(RUN.rglob("*"))
        if path.is_file()
        and path.name != "artifact_manifest.json"
        and "__pycache__" not in path.parts
    ]
    artifacts.append(ROOT / "reports/tasks/R20-process-startup-fix.md")
    manifest = {
        "task": "R20-process-startup-fix",
        "status": "awaiting_review",
        "baseline_sha": BASE,
        "code_sha": CODE,
        "material_parent_sha": git("rev-parse", "HEAD"),
        "frozen_utc": datetime.now(UTC).isoformat(),
        "primary_worker_samples": 20,
        "primary_worker_concurrency": 1,
        "primary_cases": primary_cases,
        "worker_commands_wall_seconds": sum(
            json.loads((RUN / f"{name}.json").read_text())["wall_seconds"]
            for name in (
                "regression_guard",
                "native_default",
                "real_pdf_parent",
                "measured_boundaries",
            )
        ),
        "aggregate_cpu_seconds": "not_fully_measured; do not infer from wall",
        "not_run": [
            "full_default_unit_coverage_60",
            "integration",
            "live",
            "manual",
            "real_model_inference",
            "semantic_coverage_spawn",
            "linux",
            "strict_early_total_cpu_hard_bound",
        ],
        "preserved_negative_evidence": [
            "red_startup",
            "native_default_coverage_gate_failed",
            "prior_diagnosis_1_328125_cpu",
            "initial_total_cpu_1_125",
        ],
        "measurement_limits": [
            "executed PDF observer writes stdin synchronously before reading READY",
            "current async-input harness not rerun",
            "other root work packages may run static or PostgreSQL checks",
        ],
        "junit": tests,
        "receipts": [identity(path) for path in receipt_paths],
        "products": [
            {
                **identity(path),
                "git_blob": git("rev-parse", f"{CODE}:{path.relative_to(ROOT).as_posix()}"),
            }
            for path in products
        ],
        "read_only_inputs": [identity(path) for path in inputs],
        "artifacts": [
            {
                **identity(path),
                "relative_path": path.relative_to(ROOT).as_posix(),
                "git_blob": git(
                    "hash-object", "--path", path.relative_to(ROOT).as_posix(), str(path)
                ),
            }
            for path in artifacts
        ],
    }
    (RUN / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "artifacts": len(artifacts),
                "receipts": len(receipt_paths),
                "primary_worker_samples": len(primary_cases),
                "code_sha": CODE,
            }
        )
    )


if __name__ == "__main__":
    main()
