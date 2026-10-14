"""绑定本包源码和暂存字节，原始日志/XML 必须与 Git blob 完全一致。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUN_DIRECTORY = Path(__file__).resolve().parent


def main() -> None:
    paths = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "fd4f1d42e1ad2e39ff7c80897fd50511c3faf299"], cwd=REPOSITORY_ROOT
    ).decode().splitlines()
    snapshot_relative_path = (RUN_DIRECTORY / "source_snapshot.json").relative_to(REPOSITORY_ROOT).as_posix()
    primary_paths = [
        "backend/tests/security/test_t06_authentication_and_scope.py",
        "backend/tests/security/test_r01_secret_classification.py",
        "scripts/security_scan.py", "reports/security/recovery_fixture_false_positives.json",
        ".gitattributes", "reports/tasks/R01-secret-classification.md",
    ]
    records = []
    for relative_path in paths:
        if relative_path == snapshot_relative_path:
            continue
        raw_content = (REPOSITORY_ROOT / relative_path).read_bytes()
        staged_content = subprocess.check_output(["git", "show", ":" + relative_path], cwd=REPOSITORY_ROOT)
        is_raw_evidence = Path(relative_path).suffix in {".log", ".xml"}
        if is_raw_evidence:
            assert raw_content == staged_content, "raw_evidence_bytes_changed: " + relative_path
        if is_raw_evidence or relative_path in primary_paths:
            records.append({
                "path": relative_path, "raw_sha256": hashlib.sha256(raw_content).hexdigest(),
                "staged_sha256": hashlib.sha256(staged_content).hexdigest(),
                "git_blob": subprocess.check_output(
                    ["git", "rev-parse", ":" + relative_path], cwd=REPOSITORY_ROOT
                ).decode().strip(),
                "raw_evidence": is_raw_evidence,
            })
    historical_paths = [
        "reports/runs/recovery_r01_frontend_20261014/recheck_rg_before.log",
        "reports/runs/recovery_r01_frontend_20261014/atomic_secret_scan.log",
    ]
    historical_records = []
    for relative_path in historical_paths:
        raw_content = (REPOSITORY_ROOT / relative_path).read_bytes()
        original = subprocess.check_output(
            ["git", "show", "fd4f1d42e1ad2e39ff7c80897fd50511c3faf299:" + relative_path],
            cwd=REPOSITORY_ROOT,
        )
        assert raw_content == original
        historical_records.append({"path": relative_path,
                                   "raw_sha256": hashlib.sha256(raw_content).hexdigest(),
                                   "unchanged_from_fixed_input": True})
    snapshot = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        "input_commit": "fd4f1d42e1ad2e39ff7c80897fd50511c3faf299",
        "code_commit": "fd49be0979703db25ac86672d703a840f008b553",
        "cwd": str(REPOSITORY_ROOT), "branch": "codex/recovery-r01-secret-scan",
        "owned_file_list": sorted(set(paths + [snapshot_relative_path])),
        "records": records, "historical_records": historical_records,
        "actual_secret_exact_scan": "not_run",
    }
    (RUN_DIRECTORY / "source_snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"owned_files": len(snapshot["owned_file_list"]),
                      "raw_evidence_files_verified": sum(record["raw_evidence"] for record in records),
                      "historical_files_unchanged": len(historical_records)}))


if __name__ == "__main__":
    main()
