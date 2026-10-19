"""Bind one prepared public-source segment; absence of new root activation forbids startup."""

from __future__ import annotations

import hashlib
import json
import math
import re
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath

OPS = Path("D:/dianzi-runtime-cache/r06-f3-ops-20261017")
DEPLOY = Path("D:/dianzi-runtime-cache/r06-f3-tool-20261017")
CORE = Path("D:/dianzi-runtime-cache/r06-f3-core-20261017")
PRODUCT = Path("D:\\wt\\r06-product-912-runtime-20261017")
PRODUCT_SHA = "912d8b381eaab9260ead30d68f49b88fa8078384"
TOOL_SHA = "a1919643b715026938c12faa07ea15b4bd7deb89"
CORE_SOURCE_SHA = "6b86f43e34f3ab406cf8136c7106c7f340fc198d"
CONTROLLER_SOURCE_SHA = "87faa9e7ac48c17ac974cc2300d1bf03e8989d09"
CONTROLLER_SHA256 = "8d2f69c369bff148698d8382bc39c761bb70a5848e920de58e176710f6fd1ce7"
RUN_ID = "r06_nine_script_20261016"
NONCE = "ea89c345e404475d94de02cbe67874e3"
OBSERVER_SHA = "a1919643b715026938c12faa07ea15b4bd7deb89"
SOURCE_DATABASE = "test_dianzi_r06_912_20261017_f15191e6ea74"
SOURCE_SCHEMA = "0030_revalidation_actor_bindings"
REDIS_PREFIX = "r06-nine-script-20261016:"
REDIS_QUEUE = "r06_nine_script_20261016"
PARENT_END = datetime.fromisoformat("2026-10-17T21:49:15+08:00")
SOURCE_SECONDS = 21600
SHUTDOWN_SECONDS = 900
TOTAL_SECONDS = SOURCE_SECONDS + SHUTDOWN_SECONDS
ZONE = timezone(timedelta(hours=8))
SCRIPT_NAMES = (
    "configuration.py",
    "source_entry.py",
    "guardian.py",
    "minio_segment.py",
    "stop_minio.py",
    "launch.ps1",
    "stop_owned.py",
    "windows_preflight.ps1",
    "minio_controller.py",
)
CORE_NAMES = (
    "authorization.py",
    "controlled_supervise.py",
    "guard_observability.py",
    "runtime_limits.py",
    "stop_controller.py",
    "windows_actor.py",
    "deploy_runtime_entry.py",
    "runtime_controls.py",
    "owned_stop_watcher.py",
    "task_fence.py",
    "run_binding.py",
)
ACTIVATION_FLAGS = (
    "root_live_authorized",
    "independent_review_ship",
    "root_budget_approved",
    "integrated_key_checks_passed",
    "actual_kernel_guardian_checked",
    "fresh_resource_binding_checked",
    "source_db_oid_binding_approved",
)
PREPARED_KEYS = {
    "prepared_at",
    "run_id",
    "nonce",
    "product_sha",
    "tool_sha",
    "controller_source_sha",
    "operations_source_sha",
    "operations_git_blobs",
    "product_root",
    "deployment_root",
    "operations_root",
    "operations_sha256",
    "core_source_sha",
    "core_root",
    "core_source_sha256",
    "source_database",
    "source_database_oid",
    "source_database_marker_sha256",
    "source_schema",
    "redis_database",
    "redis_prefix",
    "redis_queue",
    "parent_deadline",
    "maximum_total_seconds",
    "activated",
    "ready",
    "blocking_preparation",
    "processes_started",
    "source_requests",
    "source_only_independence",
    "source_job_ledger_offset",
    "source_job_ledger_sha256",
}
ACTIVATION_KEYS = {
    "root_live_authorized",
    "independent_review_ship",
    "root_budget_approved",
    "integrated_key_checks_passed",
    "actual_kernel_guardian_checked",
    "fresh_resource_binding_checked",
    "source_db_oid_binding_approved",
    "run_id",
    "nonce",
    "product_sha",
    "tool_sha",
    "controller_source_sha",
    "maximum_seconds",
    "shutdown_seconds",
    "source_job_cap",
    "prestop",
    "solo_maximum_row_bound",
    "wire_https_cap",
    "model_requests_permitted",
    "paid_provider_requests_permitted",
    "source_database",
    "source_database_oid",
    "source_database_marker_sha256",
    "source_schema",
    "redis_database",
    "redis_prefix",
    "redis_queue",
    "parent_deadline",
    "actual_wire_count",
    "source_cost",
    "formal_six_hour_pass",
    "core_source_sha",
    "runtime_binding_sha256",
    "source_job_ledger_offset",
    "source_job_ledger_sha256",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate prepared or activation field")
        value[key] = item
    return value


def read_prepared() -> dict[str, object]:
    metadata = json.loads(
        (OPS / "prepared.json").read_bytes(), object_pairs_hook=unique_json_object
    )
    if not isinstance(metadata, dict):
        raise ValueError("prepared metadata object required")
    require(not set(metadata).difference(PREPARED_KEYS), "unknown prepared field")
    require(metadata["run_id"] == RUN_ID, "new run identity differs")
    require(
        metadata["product_sha"] == PRODUCT_SHA and metadata["tool_sha"] == TOOL_SHA,
        "fixed source versions differ",
    )
    require(
        re.fullmatch("[a-f0-9]{32}", metadata["nonce"]) is not None, "new generation nonce required"
    )
    for path in (OPS, DEPLOY, CORE, PRODUCT):
        require(
            path.resolve() == path and not path.is_symlink() and not path.is_junction(),
            "fixed path redirected",
        )
    return metadata


def validate_activation(
    metadata: dict[str, object],
    activation: dict[str, object],
    operations: Path,
    core: Path | None = None,
) -> dict[str, object]:
    """Validate the same exact nine-script policy from Windows or the Linux owner."""
    require(not set(activation).difference(ACTIVATION_KEYS), "unknown activation field")
    require(not set(metadata).difference(PREPARED_KEYS), "unknown prepared field")
    for key in ACTIVATION_FLAGS:
        require(activation.get(key) is True, "new activation prerequisites incomplete")
    nonce = metadata.get("nonce")
    if not isinstance(nonce, str) or re.fullmatch("[a-f0-9]{32}", nonce) is None:
        raise ValueError("new generation nonce required")
    require(nonce == NONCE, "prepared nonce binding differs")
    oid = metadata.get("source_database_oid")
    if not isinstance(oid, str) or not oid.isascii() or not oid.isdigit():
        raise ValueError("new marked source database binding is not prepared")
    require(int(oid) > 0 and oid != "3680428", "old source database must remain protected")
    marker_hash = metadata.get("source_database_marker_sha256")
    if not isinstance(marker_hash, str) or re.fullmatch("[a-f0-9]{64}", marker_hash) is None:
        raise ValueError("actual native source database marker hash is not prepared")
    ledger_offset = metadata.get("source_job_ledger_offset")
    ledger_hash = metadata.get("source_job_ledger_sha256")
    if type(ledger_offset) is not int or not 11 <= ledger_offset < 410:
        raise ValueError("existing source consumption is not accounted")
    if not isinstance(ledger_hash, str) or re.fullmatch("[a-f0-9]{64}", ledger_hash) is None:
        raise ValueError("actual source budget ledger hash is not prepared")
    for key, expected in {
        "run_id": RUN_ID,
        "product_sha": PRODUCT_SHA,
        "tool_sha": TOOL_SHA,
        "controller_source_sha": CONTROLLER_SOURCE_SHA,
        "source_database": SOURCE_DATABASE,
        "source_schema": SOURCE_SCHEMA,
        "redis_database": 15,
        "redis_prefix": REDIS_PREFIX,
        "redis_queue": REDIS_QUEUE,
    }.items():
        require(metadata.get(key) == expected, "prepared resource binding differs: " + key)
    for key, expected in {
        "run_id": RUN_ID,
        "nonce": metadata["nonce"],
        "product_sha": PRODUCT_SHA,
        "tool_sha": TOOL_SHA,
        "controller_source_sha": CONTROLLER_SOURCE_SHA,
        "maximum_seconds": SOURCE_SECONDS,
        "shutdown_seconds": SHUTDOWN_SECONDS,
        "source_job_cap": 450,
        "prestop": 410,
        "solo_maximum_row_bound": 418,
        "wire_https_cap": 35100,
        "model_requests_permitted": 0,
        "paid_provider_requests_permitted": 0,
        "source_database": SOURCE_DATABASE,
        "source_database_oid": oid,
        "source_database_marker_sha256": marker_hash,
        "source_job_ledger_offset": ledger_offset,
        "source_job_ledger_sha256": ledger_hash,
        "source_schema": SOURCE_SCHEMA,
        "redis_database": 15,
        "redis_prefix": REDIS_PREFIX,
        "redis_queue": REDIS_QUEUE,
        "parent_deadline": PARENT_END.isoformat(),
        "core_source_sha": metadata.get("core_source_sha"),
        "actual_wire_count": "unknown",
        "source_cost": "unknown",
        "formal_six_hour_pass": False,
    }.items():
        if type(expected) is int:
            require(type(activation.get(key)) is int, "integer resource field required")
        require(activation.get(key) == expected, "new activation binding differs: " + key)
    frozen = metadata["operations_sha256"]
    if not isinstance(frozen, dict) or set(frozen) != set(SCRIPT_NAMES):
        raise ValueError("operations freeze incomplete")
    for name in SCRIPT_NAMES:
        expected = frozen[name]
        require(
            isinstance(expected, str) and re.fullmatch("[a-f0-9]{64}", expected) is not None,
            "exact operation digest required",
        )
        path = operations / name
        require(path.resolve() == path and not path.is_symlink(), "operation path redirected")
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == expected,
            "prepared operation changed after review",
        )
    require(frozen["minio_controller.py"] == CONTROLLER_SHA256, "final controller differs")
    validate_core_binding(metadata, activation, CORE if core is None else core)
    return activation


def validate_core_binding(
    metadata: dict[str, object], activation: dict[str, object], core: Path
) -> None:
    """Refuse every entry point before IO when the reviewed eleven-file binding differs."""
    require(set(metadata) == PREPARED_KEYS, "prepared fields missing or unknown")
    require(set(activation) == ACTIVATION_KEYS, "activation fields missing or unknown")
    require(
        metadata["ready"] is True and metadata["activated"] is False, "prepared bundle not ready"
    )
    require(core.resolve() == core and not core.is_symlink(), "core path redirected")
    require(metadata["core_root"] == str(PureWindowsPath(str(CORE))), "prepared core root differs")
    source_sha = metadata["core_source_sha"]
    require(
        source_sha == CORE_SOURCE_SHA,
        "exact reviewed core source required",
    )
    frozen = metadata["core_source_sha256"]
    if not isinstance(frozen, dict) or set(frozen) != set(CORE_NAMES):
        raise ValueError("eleven core freeze incomplete")
    for name in CORE_NAMES:
        row = frozen[name]
        if not isinstance(row, dict) or set(row) != {"sha256", "bytes"}:
            raise ValueError("exact core hash and bytes required")
        path = core / name
        require(path.resolve() == path and not path.is_symlink(), "core file path redirected")
        raw = path.read_bytes()
        require(type(row["bytes"]) is int and len(raw) == row["bytes"], "core byte count differs")
        require(hashlib.sha256(raw).hexdigest() == row["sha256"], "reviewed core file differs")
    raw_binding = (core / "runtime_binding.json").read_bytes()
    require(len(raw_binding) <= 65536, "runtime binding exceeds bound")
    require(
        hashlib.sha256(raw_binding).hexdigest() == activation["runtime_binding_sha256"],
        "root runtime binding hash differs",
    )
    binding = json.loads(raw_binding, object_pairs_hook=unique_json_object)
    expected = {
        key: value
        for key, value in activation.items()
        if key not in set(ACTIVATION_FLAGS) | {"runtime_binding_sha256"}
    }
    expected.update(
        {
            "product_root": str(PureWindowsPath(str(PRODUCT))),
            "deployment_root": str(PureWindowsPath(str(DEPLOY))),
            "operations_root": str(PureWindowsPath(str(OPS))),
            "core_root": str(PureWindowsPath(str(CORE))),
            "original_observer_scripts_sha": OBSERVER_SHA,
            "operations_source_sha": metadata["operations_source_sha"],
            "operations_sha256": metadata["operations_sha256"],
            "core_source_sha256": frozen,
            "ready": True,
        }
    )
    require(
        isinstance(binding, dict) and set(binding) == set(expected), "runtime binding fields differ"
    )
    for key, value in expected.items():
        require(
            type(binding[key]) is type(value) and binding[key] == value,
            "runtime binding differs: " + key,
        )
    for key in set(metadata) & set(expected):
        require(
            type(metadata[key]) is type(expected[key]) and metadata[key] == expected[key],
            "prepared runtime binding differs: " + key,
        )
    require(metadata["maximum_total_seconds"] == TOTAL_SECONDS, "prepared total deadline differs")
    require(
        hashlib.sha256((core / "source_budget_ledger.json").read_bytes()).hexdigest()
        == activation["source_job_ledger_sha256"],
        "source budget ledger differs",
    )


def require_activation() -> dict[str, object]:
    activation_path = OPS / "activation.json"
    require(activation_path.is_file(), "new root activation absent; collector must not start")
    metadata = read_prepared()
    activation = json.loads(activation_path.read_bytes(), object_pairs_hook=unique_json_object)
    if not isinstance(activation, dict):
        raise ValueError("activation object required")
    return validate_activation(metadata, activation, OPS)


def require_start_window(observed_at: datetime) -> None:
    require(
        (PARENT_END - observed_at).total_seconds() >= TOTAL_SECONDS,
        "full bounded source segment does not fit existing daemon deadline",
    )


def write_runtime_gate(activation: dict[str, object]) -> None:
    validate_activation(read_prepared(), activation, OPS)
    value = dict(activation)
    value["product_root"] = str(PRODUCT)
    value["authorized_at"] = datetime.now(ZONE).isoformat()
    path = CORE / "root_live_authorization.json"
    try:
        with path.open("x", encoding="utf-8") as output:
            json.dump(value, output, indent=2)
            output.write("\n")
    except FileExistsError:
        require(path.resolve() == path and not path.is_symlink(), "runtime gate redirected")
        existing = json.loads(path.read_bytes(), object_pairs_hook=unique_json_object)
        require(
            isinstance(existing, dict) and set(existing) == set(value),
            "existing runtime gate fields differ",
        )
        for key in value.keys() - {"authorized_at"}:
            require(
                type(existing[key]) is type(value[key]) and existing[key] == value[key],
                "existing runtime gate differs: " + key,
            )
        require(
            isinstance(existing["authorized_at"], str),
            "existing authorization time invalid",
        )
        require(
            datetime.fromisoformat(existing["authorized_at"]).tzinfo is not None,
            "existing authorization time must be aware",
        )


def validate_launch_state(state: object) -> dict[str, object]:
    require(isinstance(state, dict), "launch state object required")
    require(
        set(state)
        == {
            "observation_id",
            "run_id",
            "nonce",
            "product_sha",
            "runtime_binding_sha256",
            "cpu_seconds_used",
            "component_log_bytes",
            "journal_bytes_used",
        },
        "launch state fields differ",
    )
    require(
        re.fullmatch("[a-f0-9]{32}", str(state["observation_id"])) is not None,
        "launch observation identity differs",
    )
    for key, expected in (
        ("run_id", RUN_ID),
        ("nonce", NONCE),
        ("product_sha", PRODUCT_SHA),
    ):
        require(state[key] == expected, "launch state binding differs: " + key)
    cpu = state["cpu_seconds_used"]
    require(
        type(cpu) in (int, float) and math.isfinite(cpu) and 0 <= cpu < 1200,
        "cumulative CPU budget exhausted or unknown",
    )
    logs = state["component_log_bytes"]
    require(
        isinstance(logs, dict) and set(logs) <= {"api", "worker", "beat", "observer", "minio"},
        "component log counters differ",
    )
    require(
        all(type(value) is int and 0 <= value < 8 * 1024**2 for value in logs.values()),
        "cumulative component log budget exhausted",
    )
    require(
        type(state["journal_bytes_used"]) is int
        and 0 <= state["journal_bytes_used"] < 16 * 1024**2 - 4 * 1024**2 - 16384,
        "remaining observer reserve insufficient",
    )
    return state


def read_launch_state() -> dict[str, object]:
    return validate_launch_state(
        json.loads(
            (OPS / "launch_state.json").read_bytes(),
            object_pairs_hook=unique_json_object,
        )
    )


def prepare_launch(activation: dict[str, object]) -> None:
    """Archive a proven closed same-version attempt; authorization and historical ledger stay byte exact."""

    class BootstrapRecoveryEvidenceError(ValueError):
        """Missing or uncertain old kernel evidence must never be interpreted as an empty run."""

    validate_activation(read_prepared(), activation, OPS)
    transition = False
    previous_binding = None
    state_path = OPS / "launch_state.json"
    history_path = OPS / "attempt_history"
    if not state_path.exists() and (
        history_path.exists() or history_path.is_symlink() or history_path.is_junction()
    ):
        require_archive_path(history_path, OPS)
        raise BootstrapRecoveryEvidenceError(
            "archived attempt without cumulative launch state; restore original evidence before Root audit"
        )
    if state_path.exists():
        state = read_launch_state()
        require(
            isinstance(state["runtime_binding_sha256"], str)
            and re.fullmatch("[a-f0-9]{64}", state["runtime_binding_sha256"])
            is not None,
            "launch runtime digest invalid",
        )
        if state["runtime_binding_sha256"] != activation["runtime_binding_sha256"]:
            legacy_hash = (
                "9e3066565a0fe45fed58574a77baee0e9492651baa3ed953a610abe2b5b5e8fd"
            )
            require(
                state["runtime_binding_sha256"] == legacy_hash,
                "unapproved previous runtime transition",
            )
            require(
                not (CORE / "runtime_start.json").exists(),
                "only failed bootstrap transition approved",
            )
            previous_path = OPS / "bootstrap_previous_runtime_binding.json"
            require_archive_path(previous_path, OPS)
            if not previous_path.is_file():
                raise BootstrapRecoveryEvidenceError(
                    "fixed previous runtime binding raw bytes required"
                )
            previous_raw = previous_path.read_bytes()
            require(
                len(previous_raw) <= 65536
                and hashlib.sha256(previous_raw).hexdigest() == legacy_hash,
                "fixed previous runtime digest differs",
            )
            previous_binding = json.loads(
                previous_raw, object_pairs_hook=unique_json_object
            )
            current_binding = json.loads(
                (CORE / "runtime_binding.json").read_bytes(),
                object_pairs_hook=unique_json_object,
            )
            require(
                isinstance(previous_binding, dict)
                and isinstance(current_binding, dict)
                and set(previous_binding) == set(current_binding),
                "previous runtime fields differ",
            )
            require(
                previous_binding.get("core_source_sha")
                == "37ffe6da1d9a258359363d42488d236b7c00ad87"
                and previous_binding.get("operations_source_sha")
                == "81053fd680dbfb275bfcc511ae44f573340efd56",
                "fixed previous source versions differ",
            )
            for key in previous_binding.keys() - {
                "core_source_sha",
                "operations_source_sha",
                "core_source_sha256",
                "operations_sha256",
            }:
                require(
                    type(previous_binding[key]) is type(current_binding[key])
                    and previous_binding[key] == current_binding[key],
                    "previous runtime resource or budget differs: " + key,
                )
            gate_path = CORE / "root_live_authorization.json"
            require_archive_path(gate_path, CORE)
            previous_gate = json.loads(
                gate_path.read_bytes(), object_pairs_hook=unique_json_object
            )
            expected_gate = {
                **activation,
                "core_source_sha": previous_binding["core_source_sha"],
                "runtime_binding_sha256": legacy_hash,
                "product_root": str(PRODUCT),
            }
            require(
                isinstance(previous_gate, dict)
                and set(previous_gate) == set(expected_gate) | {"authorized_at"},
                "previous runtime gate fields differ",
            )
            for key, value in expected_gate.items():
                require(
                    type(previous_gate[key]) is type(value)
                    and previous_gate[key] == value,
                    "previous runtime gate binding differs: " + key,
                )
            require(
                isinstance(previous_gate["authorized_at"], str)
                and datetime.fromisoformat(previous_gate["authorized_at"]).tzinfo
                is not None,
                "previous runtime authorization timestamp unknown",
            )
            transition = True
    if not transition:
        write_runtime_gate(activation)
    subprocess.run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "python3",
            "-B",
            "/mnt/d/dianzi-runtime-cache/r06-f3-ops-20261017/minio_segment.py",
            "--check-relaunch",
        ],
        check=True,
        timeout=10,
        capture_output=True,
    )
    observer = (
        DEPLOY / "reports/runs/recovery_r06_incremental_observation_fix2_20261017"
    )
    core_names = {
        "runtime_start.json",
        "runtime_end.json",
        "stop.request",
        "startup_failure.json",
        "owned_stop_failure.json",
        "heartbeat.json",
        "runtime_heartbeat.json",
        "api.log",
        "worker.log",
        "beat.log",
        "observer.log",
    }
    ops_names = {
        "launch_state.json",
        "source_identity.json",
        "source_identity.pending",
        "guardian_start.json",
        "guardian_end.json",
        "supervisor.stdout.log",
        "supervisor.stderr.log",
        "launch_receipt.json",
        "process_ownership_receipt.json",
        "minio_start.json",
        "minio_end.json",
        "minio_controller_start.json",
        "minio_controller_end.json",
        "minio.log",
        "minio_stop.request",
        "minio_supervisor.stdout.log",
        "minio_supervisor.stderr.log",
        "bootstrap_recovery_audit.json",
        "bootstrap_previous_runtime_binding.json",
    }
    paths = [
        root / name
        for root, names in ((CORE, core_names), (OPS, ops_names))
        for name in sorted(names)
        if (root / name).exists()
    ]
    control = CORE / "control"
    if control.exists():
        require(
            {path.name for path in control.iterdir()}
            <= {
                f"{role}_{kind}.json"
                for role in ("worker", "beat")
                for kind in ("ready", "ack", "stop")
            },
            "unknown or partial control artifact",
        )
        paths.extend(control.iterdir())
    live = observer / ("live_" + RUN_ID)
    if live.exists():
        require(
            {path.name for path in live.iterdir()}
            <= {
                "collection_observations.jsonl",
                "collection_latest.json",
                "collection_end.json",
                "collector_stop.request",
            },
            "unknown or partial observer artifact",
        )
        paths.extend(live.iterdir())
    if (observer / "root_live_gate.json").exists():
        paths.append(observer / "root_live_gate.json")
    if transition:
        paths.append(CORE / "root_live_authorization.json")
    elif (OPS / "bootstrap_previous_runtime_binding.json").exists():
        raise BootstrapRecoveryEvidenceError("unexpected previous runtime binding")
    for path in paths:
        root = (
            CORE
            if path.is_relative_to(CORE)
            else OPS
            if path.is_relative_to(OPS)
            else observer
        )
        require_archive_path(path, root)
        require(
            path.is_file() and path.suffix != ".pending",
            "previous runtime artifact incomplete",
        )
    counters: dict[str, object] = {
        "cpu_seconds_used": 0.0,
        "component_log_bytes": {},
        "journal_bytes_used": 0,
    }
    if paths:
        state = read_launch_state()
        sys.path.insert(0, str(CORE))
        from run_binding import read_object
        from stop_owned import positive_identity, receipt_ticks, validate_start_receipts

        for name in ("guardian_start.json", "guardian_end.json"):
            if not (OPS / name).is_file():
                raise BootstrapRecoveryEvidenceError(
                    "previous guardian start and final usage required"
                )
        guardian = read_object((OPS / "guardian_start.json").read_bytes())
        guardian_end = read_object((OPS / "guardian_end.json").read_bytes())
        binding = (
            previous_binding
            if transition
            else read_object((CORE / "runtime_binding.json").read_bytes())
        )
        expected_runtime = state["runtime_binding_sha256"]
        for key in ("product_sha", "runtime_binding_sha256"):
            expected = (
                expected_runtime if key == "runtime_binding_sha256" else activation[key]
            )
            require(
                guardian.get(key) == expected and guardian_end.get(key) == expected,
                "previous guardian frozen configuration differs",
            )
        require(
            guardian.get("observation_id") == state["observation_id"]
            and guardian_end.get("observation_id") == state["observation_id"],
            "previous guardian observation differs",
        )
        for key in ("run_id", "nonce"):
            require(
                guardian_end.get(key) == activation[key],
                "previous guardian identity differs",
            )
        require(
            guardian_end.get("started_at") == guardian["started_at"]
            and guardian_end.get("actual_source_kernel_exit_ack") is True,
            "previous source kernel exit ACK absent",
        )
        if (CORE / "runtime_start.json").is_file():
            start = read_object((CORE / "runtime_start.json").read_bytes())
            end = read_object((CORE / "runtime_end.json").read_bytes())
            validate_start_receipts(activation, binding, start, guardian)
            for key in (
                "product_sha",
                "tool_sha",
                "core_source_sha",
                "operations_source_sha",
                "started_at",
            ):
                require(
                    end.get(key) == start[key], "previous runtime end binding differs"
                )
            stops = end.get("actual_actor_stop")
            require(
                isinstance(stops, list)
                and len(stops) == 2
                and {row.get("role") for row in stops if isinstance(row, dict)}
                == {"worker", "beat"},
                "previous producer stops incomplete",
            )
            for row in stops:
                expected = start["actual_actors"][row["role"]]
                require(
                    all(
                        row.get(key) is True
                        for key in (
                            "ack_present",
                            "actual_pid_exited",
                            "owned_descendants_exited",
                        )
                    ),
                    "previous producer ACK incomplete",
                )
                require(
                    all(
                        row.get(key) == expected[key]
                        for key in ("actual_pid", "creation_ticks")
                    ),
                    "previous producer birth differs",
                )
            pids = {
                start["supervisor_pid"],
                guardian["guardian_pid"],
                guardian["launcher_pid"],
                *start["launchers"].values(),
                *(row["actual_pid"] for row in start["actual_actors"].values()),
            }
        else:
            audit_path = OPS / "bootstrap_recovery_audit.json"
            if not audit_path.is_file():
                raise BootstrapRecoveryEvidenceError(
                    "Root kernel closure audit required for missing runtime_start; actor identities remain unknown"
                )
            require(audit_path.stat().st_size <= 65536, "bootstrap audit exceeds bound")
            audit = read_object(audit_path.read_bytes())
            require(
                set(audit)
                == {
                    "schema",
                    "run_id",
                    "nonce",
                    "product_sha",
                    "runtime_binding_sha256",
                    "candidate_runtime_binding_sha256",
                    "observation_id",
                    "observed_at",
                    "actual_source_identity",
                    "guardian_pid",
                    "source_launcher_pid",
                    "kernel_closure_basis",
                    "frozen_job_sha256",
                    "windows_owned_job_exit_confirmed",
                    "windows_descendants_exit_confirmed",
                    "minio_closed_scope_checked",
                    "evidence_sha256",
                },
                "bootstrap audit fields differ",
            )
            source_path = OPS / "source_identity.json"
            if not source_path.is_file():
                raise BootstrapRecoveryEvidenceError(
                    "original actual source identity required"
                )
            source = read_object(source_path.read_bytes())
            require(
                set(source) == {"run_id", "nonce", "actual_pid", "creation_ticks"}
                and source == guardian.get("actual_source_identity"),
                "previous actual source identity differs",
            )
            for key in ("run_id", "nonce"):
                require(
                    source.get(key) == activation[key]
                    and guardian.get(key) == activation[key],
                    "previous source generation differs",
                )
            source_pid = positive_identity(source["actual_pid"])
            source_birth = positive_identity(source["creation_ticks"])
            guardian_pid = positive_identity(guardian["guardian_pid"])
            launcher_pid = positive_identity(guardian["launcher_pid"])
            require(
                len({source_pid, guardian_pid, launcher_pid}) == 3,
                "previous source identities ambiguous",
            )
            require(
                type(guardian.get("maximum_seconds")) is int
                and guardian["maximum_seconds"] == TOTAL_SECONDS,
                "previous guardian total budget differs",
            )
            guardian_started = datetime.fromisoformat(guardian["started_at"])
            require(
                guardian_started.tzinfo is not None
                and datetime.fromisoformat(guardian["hard_deadline"])
                == min(guardian_started + timedelta(seconds=TOTAL_SECONDS), PARENT_END),
                "previous guardian deadline differs",
            )
            require(
                receipt_ticks(guardian["started_at"])
                <= source_birth
                <= receipt_ticks(guardian_end.get("ended_at")),
                "previous source birth or final time differs",
            )
            require(
                guardian_end.get("source_job_kill_on_close_required") is True,
                "previous source Job closure contract unknown",
            )
            require(
                guardian_end.get("formal_six_hour_pass") is False,
                "failed bootstrap duration must remain unqualified",
            )
            expected_audit = {
                "schema": "r06_failed_bootstrap_kernel_closure_v1",
                "run_id": RUN_ID,
                "nonce": NONCE,
                "product_sha": PRODUCT_SHA,
                "runtime_binding_sha256": expected_runtime,
                "candidate_runtime_binding_sha256": activation[
                    "runtime_binding_sha256"
                ],
                "observation_id": state["observation_id"],
                "actual_source_identity": source,
                "guardian_pid": guardian_pid,
                "source_launcher_pid": launcher_pid,
                "kernel_closure_basis": "frozen_noninheritable_kill_on_close_guardian_exit",
                "frozen_job_sha256": {
                    "runtime_limits.py": binding["core_source_sha256"][
                        "runtime_limits.py"
                    ]["sha256"],
                    "guardian.py": binding["operations_sha256"]["guardian.py"],
                },
                "windows_owned_job_exit_confirmed": True,
                "windows_descendants_exit_confirmed": True,
                "minio_closed_scope_checked": True,
            }
            for key, expected in expected_audit.items():
                require(
                    type(audit.get(key)) is type(expected)
                    and audit.get(key) == expected,
                    "bootstrap closure audit differs: " + key,
                )
            require(
                receipt_ticks(guardian_end["ended_at"])
                <= receipt_ticks(audit["observed_at"])
                <= receipt_ticks(datetime.now(ZONE).isoformat()),
                "bootstrap audit time differs",
            )
            evidence = {}
            for path in paths:
                if path == audit_path:
                    continue
                category = (
                    "core"
                    if path.is_relative_to(CORE)
                    else "ops"
                    if path.is_relative_to(OPS)
                    else "observer"
                )
                root = (
                    CORE
                    if category == "core"
                    else OPS
                    if category == "ops"
                    else observer
                )
                evidence[category + "/" + path.relative_to(root).as_posix()] = (
                    hashlib.sha256(path.read_bytes()).hexdigest()
                )
            require(
                audit.get("evidence_sha256") == evidence,
                "bootstrap raw evidence changed or missing",
            )
            for name in ("minio_start.json", "minio_end.json"):
                path = OPS / name
                if path.exists():
                    receipt = read_object(path.read_bytes())
                    require(
                        all(
                            receipt.get(key) == expected_audit[key]
                            and type(receipt.get(key)) is type(expected_audit[key])
                            for key in (
                                "nonce",
                                "product_sha",
                                "runtime_binding_sha256",
                                "observation_id",
                            )
                        ),
                        "previous MinIO service attempt differs",
                    )
            pids = {source_pid, guardian_pid, launcher_pid}
        cpu = guardian_end.get("cpu_seconds_used")
        require(
            type(cpu) in (int, float) and math.isfinite(cpu) and cpu >= 0,
            "previous final CPU usage unavailable",
        )
        logs = dict(state["component_log_bytes"])
        for role in ("api", "worker", "beat", "observer"):
            path = CORE / (role + ".log")
            logs[role] = logs.get(role, 0) + (
                path.stat().st_size if path.exists() else 0
            )
        minio_log = OPS / "minio.log"
        logs["minio"] = logs.get("minio", 0) + (
            minio_log.stat().st_size if minio_log.exists() else 0
        )
        journal = live / "collection_observations.jsonl"
        counters = {
            "cpu_seconds_used": state["cpu_seconds_used"] + cpu,
            "component_log_bytes": logs,
            "journal_bytes_used": state["journal_bytes_used"]
            + (journal.stat().st_size if journal.exists() else 0),
        }
        validate_launch_state({**state, **counters})
        from windows_actor import process_tree

        tree = process_tree()
        require(
            not pids.intersection(tree)
            and not any(row.get("parent") in pids for row in tree.values()),
            "previous owned PID or descendant still present; no cleanup authorized",
        )
        for path in paths:
            require(
                path.resolve() == path
                and not path.is_symlink()
                and not path.is_junction()
                and path.is_file(),
                "previous runtime artifact redirected",
            )
        history = OPS / "attempt_history"
        archive = history / str(state["observation_id"])
        require_archive_path(archive, OPS)
        require(not archive.exists(), "archive target already exists")
        moves: list[tuple[Path, Path, Path]] = []
        for path in paths:
            category = (
                "core"
                if path.is_relative_to(CORE)
                else "ops"
                if path.is_relative_to(OPS)
                else "observer"
            )
            root = (
                CORE if category == "core" else OPS if category == "ops" else observer
            )
            target = archive / category / path.relative_to(root)
            require_archive_path(path, root)
            require_archive_path(target, archive)
            require(not target.exists(), "archive destination already exists")
            moves.append((path, target, root))
        require(
            len({target for _, target, _ in moves}) == len(moves),
            "archive targets overlap",
        )
        history.mkdir(exist_ok=True)
        require_archive_path(history, OPS)
        archive.mkdir(exist_ok=False)
        for _, target, _ in moves:
            require_archive_path(target.parent, archive)
            target.parent.mkdir(parents=True, exist_ok=True)
            require_archive_path(target.parent, archive)
        for path, target, root in moves:
            require_archive_path(path, root)
            require_archive_path(target, archive)
            require(not target.exists(), "archive destination already exists")
        for path, target, root in moves:
            require_archive_path(path, root)
            require_archive_path(target, archive)
            path.rename(target)
        if live.exists():
            live.rmdir()
    if transition:
        write_runtime_gate(activation)
    value = {
        "observation_id": uuid.uuid4().hex,
        "run_id": RUN_ID,
        "nonce": NONCE,
        "product_sha": PRODUCT_SHA,
        "runtime_binding_sha256": activation["runtime_binding_sha256"],
        **counters,
    }
    with (OPS / "launch_state.json").open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2)
        output.write("\n")
    read_launch_state()


def require_archive_path(path: Path, root: Path) -> None:
    """Refuse redirected roots or parents before creating an owned archive or moving evidence."""
    require(path.is_absolute() and path.is_relative_to(root), "archive path outside owned scope")
    for current in (path, *path.parents):
        require(current.resolve() == current and not current.is_symlink() and not current.is_junction(), "archive parent or target redirected")
        if current.exists():
            require(not getattr(current.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT, "archive reparse boundary refused")
            if current != path:
                require(current.is_dir(), "archive parent is not a directory")
