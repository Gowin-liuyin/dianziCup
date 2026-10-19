"""Seal local artifacts and external input identities, without starting workers."""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-F-R20-8a-cpu-root-cause-diagnosis.md"


def digest(path: Path) -> dict:
    content = path.read_bytes()
    return {"path": str(path), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def main() -> None:
    current = (RUN / "observe_processes.py").read_text(encoding="utf-8")
    changes = [
        "KERNEL.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]\n",
        "    exit_code = wintypes.DWORD()\n    exit_success = KERNEL.GetExitCodeProcess(handle, ctypes.byref(exit_code))\n",
        '            "process_exit_code": exit_code.value if exit_success else None,\n',
    ]
    for change in changes:
        assert current.count(change) == 1
        current = current.replace(change, "")
    reconstructed = RUN / "observer_first16_reconstructed.py"
    reconstructed.write_text(current, encoding="utf-8")
    external_paths = [
        "D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/backend_full_pure_actual.stdout.log",
        "D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/backend_full_pure_actual.command.json",
        "D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/backend_full_pure.xml",
        "D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/privacy_environment_recheck.xml",
        "D:/dianzi/reports/reviews/recovery/G-F-R20-startup-fix-review-1.md",
        "D:/dianzi/reports/tasks/R20-process-startup-fix.md",
        "D:/dianzi/reports/tasks/R20-native-cpu-guard.md",
        "D:/dianzi/reports/reviews/recovery/G-C-native-cpu-limit-diagnosis.md",
        "D:/dianzi/reports/reviews/recovery/G-C-native-cpu-guard-review-1.md",
        "D:/dianzi/reports/reviews/recovery/G-C-native-cpu-guard-review-1-recheck.md",
        "D:/wt/r20-cpu-boundary-diagnosis/reports/tasks/R20-cpu-boundary-diagnosis.md",
        "D:/dianzi/reports/runs/r20_startup_fix_review_1_20261016/semantic_coverage_recheck.receipt.json",
        "D:/dianzi/reports/runs/r20_startup_fix_review_1_20261016/semantic_coverage_positive.json",
        "D:/dianzi/reports/runs/r20_startup_fix_review_1_20261016/semantic_coverage_worker.json",
    ]
    local_paths = ["AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/04_workflows_and_algorithms.md",
                   "docs/plan/06_testing_and_evaluation.md", "docs/plan/09_operations_delivery.md",
                   "docs/plan/12_recovery_task_cards_20261014.md", "docs/tasks/T45_security_regression.md",
                   "docs/tasks/T48_performance_benchmarks.md", "docs/tasks/T49_observability_alerts.md",
                   "docs/tasks/T50_recovery_and_backup.md", "progress/task_state.json", "progress/context_handoff.md",
                   "contracts/task_manifest.json", "backend/.venv/Lib/site-packages/pytest-cov.pth",
                   "backend/.venv/Lib/site-packages/pytest_cov/engine.py", "backend/.venv/Lib/site-packages/pytest_cov/embed.py"]
    inputs = [digest(Path(path)) for path in external_paths] + [digest(ROOT / path) for path in local_paths]
    (RUN / "input_identities.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    files = [REPORT] + sorted(path for path in RUN.rglob("*") if path.is_file() and path.name not in ("artifact_manifest.json", "manifest_identity.json"))
    manifest = {"sealed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                "head": "8a1b04d48346d8550f0326a77f003246a0ebbab5", "report": str(REPORT),
                "artifact_count": len(files), "artifacts": [digest(path) for path in files],
                "primary_worker_samples": 20, "business_changes": 0,
                "execution_version_note": "First sixteen observer variant reconstructed from recorded one-patch addition; other executed worker strings saved separately. Misconfigured coverage group retained and invalidated as tracing evidence."}
    manifest_path = RUN / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    identity = {**digest(manifest_path), "sealed_at": manifest["sealed_at"]}
    (RUN / "manifest_identity.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(identity))
    print(json.dumps({"report_sha256": digest(REPORT)["sha256"], "artifact_count": len(files)}))


if __name__ == "__main__":
    main()
