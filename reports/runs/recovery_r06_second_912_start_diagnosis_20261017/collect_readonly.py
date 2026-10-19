"""Collect fixed public lifecycle fields without copying raw logs or secrets."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
CORE = Path("D:/dianzi-runtime-cache/r06-f3-core-20261017")
OPS = Path("D:/dianzi-runtime-cache/r06-f3-ops-20261017")
ZONE = timezone(timedelta(hours=8))
FIELDS = {
    "startup_failure.json": (
        "error_type", "failure_reason", "phase", "actual_phase", "actual_identity",
        "role", "launcher_pid", "launcher_creation_ticks", "launcher_poll",
        "launchers", "registered_roles", "product_sha", "core_source_sha",
        "operations_source_sha", "runtime_binding_sha256", "observation_id",
        "formal_six_hour_pass",
    ),
    "owned_stop_failure.json": (
        "reason", "actual_actor_stop", "observer_terminal_guaranteed",
        "formal_six_hour_pass",
    ),
    "guardian_start.json": (
        "started_at", "guardian_pid", "launcher_pid", "actual_source_identity",
        "product_sha", "runtime_binding_sha256", "observation_id", "maximum_seconds",
    ),
    "guardian_end.json": (
        "started_at", "ended_at", "reason", "actual_source_kernel_exit_ack",
        "source_job_kill_on_close_required", "descendant_exit_confirmation",
        "cpu_seconds_used", "formal_six_hour_pass",
    ),
    "minio_end.json": (
        "started_at", "ended_at", "reason", "exit_code", "cleanup_error_type",
        "descriptor_error_type", "pidfd_kernel_exit_ack", "waitpid_kernel_exit_ack",
        "emergency_kernel_empty_ack", "control_error_types",
        "final_group_contains_only_supervisor", "objects_deleted", "formal_six_hour_pass",
    ),
    "minio_controller_end.json": (
        "started_at", "ended_at", "target_inode", "target_empty",
        "helper_pidfd_kernel_exit_ack", "emergency_kernel_empty_ack", "events",
        "error_types", "whole_tree_cleanup_guaranteed", "formal_six_hour_pass",
    ),
}


def main() -> None:
    started = datetime.now(ZONE).isoformat()
    rows = []
    for name, fields in FIELDS.items():
        directory = CORE if name in {"startup_failure.json", "owned_stop_failure.json"} else OPS
        path = directory / name
        raw = path.read_bytes()
        content = json.loads(raw)
        selected = {key: content[key] for key in fields if key in content}
        if name == "guardian_start.json":
            identity = content.get("actual_source_identity", {})
            selected["actual_source_identity"] = {
                key: identity[key] for key in ("actual_pid", "creation_ticks") if key in identity
            }
        rows.append({
            "file": str(path), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "fields": selected,
        })
    logs = []
    for directory in (CORE, OPS):
        for path in sorted(directory.glob("*.log")):
            raw = path.read_bytes()
            logs.append({
                "file": str(path), "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "classified_error_tokens": [
                    token for token in (
                        "ModuleNotFoundError", "RuntimeError", "OwnershipError", "TimeoutError",
                    ) if token.encode() in raw
                ],
            })
    failure = rows[0]["fields"]
    expected_failure_observed = (
        failure.get("failure_reason") == "ready_timeout"
        and failure.get("phase") == "actor_ready_wait"
        and failure.get("role") == "worker"
        and failure.get("registered_roles") == []
        and failure.get("actual_identity") is None
        and failure.get("launcher_poll") is None
        and not (CORE / "control").exists()
    )
    record = {
        "started_at": started, "ended_at": datetime.now(ZONE).isoformat(),
        "scope": "fixed public receipt fields, raw log hash/size/static tokens only",
        "rows": rows, "logs": logs,
        "ready_directory_exists": (CORE / "control").exists(),
        "runtime_start_exists": (CORE / "runtime_start.json").exists(),
        "runtime_end_exists": (CORE / "runtime_end.json").exists(),
        "observer_log_exists": (CORE / "observer.log").exists(),
        "expected_failure_observed": expected_failure_observed,
        "live_reproduction_performed": False,
    }
    (RUN / "sanitized_actual_evidence.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "expected_failure_observed": expected_failure_observed,
        "receipts": len(rows), "logs": len(logs),
        "runtime_start_exists": record["runtime_start_exists"],
        "ready_directory_exists": record["ready_directory_exists"],
    }))
    raise SystemExit(0 if expected_failure_observed else 1)


if __name__ == "__main__":
    main()
