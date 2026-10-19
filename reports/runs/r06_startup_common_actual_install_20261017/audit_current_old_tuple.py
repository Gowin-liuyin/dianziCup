"""Let Root record a fixed failed bootstrap's read-only kernel closure proof."""

from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import json
import math
import os
import re
import stat
import subprocess
from ctypes import wintypes
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import NoReturn

SCHEMA = "r06_failed_bootstrap_kernel_closure_v1"
RUN_ID = "r06_nine_script_20261016"
NONCE = "ea89c345e404475d94de02cbe67874e3"
PRODUCT_SHA = "912d8b381eaab9260ead30d68f49b88fa8078384"
LEGACY_HASH = "9e3066565a0fe45fed58574a77baee0e9492651baa3ed953a610abe2b5b5e8fd"
LEGACY_CORE = "37ffe6da1d9a258359363d42488d236b7c00ad87"
LEGACY_OPS = "81053fd680dbfb275bfcc511ae44f573340efd56"
REPOSITORY = Path(__file__).resolve().parents[3]
CORE = Path("D:/dianzi-runtime-cache/r06-f3-core-20261017")
OPS = Path("D:/dianzi-runtime-cache/r06-f3-ops-20261017")
OBSERVER = Path(
    "D:/dianzi-runtime-cache/r06-f3-tool-20261017/reports/runs/recovery_r06_incremental_observation_fix2_20261017"
)
SOURCE_RELATIVE = "reports/runs/recovery_r06_activation_prep_20261016/candidate"
PACKAGE_MANIFEST = Path("D:/dianzi/reports/runs/r06_startup_common_actual_install_20261017/old_source_manifest.json")
PACKAGE_MANIFEST_SHA256 = (
    "fe0887dd0dc92cb6f64c2cefa668dd06c8ec26dbf821a06bd8bc6d7d0700d4b1"
)
PACKAGE_SOURCE_PINS = {
    "core_source_sha": "6b86f43e34f3ab406cf8136c7106c7f340fc198d",
    "operations_source_sha": "f4187db1800188a1f302163ce8a24a19324edd6f",
}
FLAGS = {
    "root_live_authorized",
    "independent_review_ship",
    "root_budget_approved",
    "integrated_key_checks_passed",
    "actual_kernel_guardian_checked",
    "fresh_resource_binding_checked",
    "source_db_oid_binding_approved",
}
SOURCE_FIELDS = {
    "core_source_sha",
    "operations_source_sha",
    "core_source_sha256",
    "operations_sha256",
}
CORE_SOURCES = {
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
}
OPS_SOURCES = {
    "configuration.py",
    "source_entry.py",
    "guardian.py",
    "minio_segment.py",
    "stop_minio.py",
    "launch.ps1",
    "stop_owned.py",
    "windows_preflight.ps1",
    "minio_controller.py",
}
CORE_ARTIFACTS = {
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
OPS_ARTIFACTS = {
    "launch_state.json",
    "source_identity.json",
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
}
LIVE_ARTIFACTS = {
    "collection_observations.jsonl",
    "collection_latest.json",
    "collection_end.json",
    "collector_stop.request",
}


class AuditError(ValueError):
    """Carry a static failure label without exposing runtime contents or IO messages."""


class AuditArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AuditError("invalid_cli")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AuditError(label)


def object_value(value: object) -> dict[str, object]:
    require(isinstance(value, dict), "object_required")
    if not isinstance(value, dict):
        raise AuditError("object_required")
    require(all(isinstance(key, str) for key in value), "string_keys_required")
    return dict(value)


def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def checked_path(path: Path, *, file_required: bool = False) -> None:
    require(path.is_absolute(), "absolute_path_required")
    for current in (path, *path.parents):
        require(current.resolve() == current, "redirected_path")
        if current.exists() or current.is_symlink():
            attributes = current.lstat()
            require(
                not current.is_symlink()
                and not getattr(attributes, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT,
                "reparse_path",
            )
            require(current == path or current.is_dir(), "parent_not_directory")
    require(not file_required or path.is_file(), "required_file_absent")


def read_object(path: Path) -> tuple[dict[str, object], bytes]:
    checked_path(path, file_required=True)
    require(path.stat().st_size <= 65536, "metadata_size_exceeded")
    raw = path.read_bytes()
    require(len(raw) <= 65536, "metadata_size_exceeded")
    return object_value(json.loads(raw, object_pairs_hook=unique_pairs)), raw


def digest_file(path: Path) -> str:
    """Hash binary evidence without decoding, displaying or retaining log contents."""
    checked_path(path, file_required=True)
    before = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    checked_path(path, file_required=True)
    after = path.stat()
    require(
        (before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_ino, after.st_size, after.st_mtime_ns),
        "evidence_changed",
    )
    return digest


def matches(value: dict[str, object], expected: dict[str, object]) -> None:
    require(
        all(
            type(value.get(key)) is type(item) and value.get(key) == item
            for key, item in expected.items()
        ),
        "receipt_binding_differs",
    )


def positive_integer(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise AuditError("positive_identity_required")
    return value


def finite_cpu(value: object) -> float:
    if type(value) not in (int, float) or not isinstance(value, (int, float)):
        raise AuditError("final_cpu_unknown")
    require(math.isfinite(value) and value >= 0, "final_cpu_unknown")
    return float(value)


def aware_time(value: object) -> datetime:
    require(isinstance(value, str), "aware_time_required")
    if not isinstance(value, str):
        raise AuditError("aware_time_required")
    timestamp = datetime.fromisoformat(value)
    require(timestamp.tzinfo is not None, "aware_time_required")
    return timestamp


def frozen_source(commit: str, category: str, name: str) -> bytes:
    checked_path(REPOSITORY)
    result = subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:{SOURCE_RELATIVE}/{category}/{name}"],
        cwd=REPOSITORY,
        capture_output=True,
        timeout=10,
        check=False,
    )
    require(
        result.returncode == 0 and len(result.stdout) <= 131072,
        "frozen_source_unavailable",
    )
    return result.stdout


def package_source_pins() -> dict[str, object]:
    """Read only this reviewed large source map; runtime metadata retains its 64KiB limit."""
    checked_path(PACKAGE_MANIFEST, file_required=True)
    before = PACKAGE_MANIFEST.stat()
    require(before.st_size <= 262144, "package_manifest_size_exceeded")
    raw = PACKAGE_MANIFEST.read_bytes()
    checked_path(PACKAGE_MANIFEST, file_required=True)
    after = PACKAGE_MANIFEST.stat()
    require(
        (before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_ino, after.st_size, after.st_mtime_ns)
        and len(raw) == before.st_size,
        "package_manifest_changed",
    )
    require(len(raw) <= 262144, "package_manifest_size_exceeded")
    manifest = object_value(json.loads(raw, object_pairs_hook=unique_pairs))
    require(
        hashlib.sha256(raw).hexdigest() == PACKAGE_MANIFEST_SHA256,
        "package_manifest_digest_differs",
    )
    pins = {key: manifest.get(key) for key in PACKAGE_SOURCE_PINS}
    matches(pins, dict(PACKAGE_SOURCE_PINS))
    source_rows = manifest.get("source_23")
    require(
        manifest.get("product_sha") == PRODUCT_SHA
        and manifest.get("ready") is False
        and manifest.get("activated") is False
        and isinstance(source_rows, list)
        and len(source_rows) == 23,
        "package_manifest_shape_differs",
    )
    return pins


def verify_frozen_job(binding: dict[str, object]) -> dict[str, str]:
    """Pin the reviewed noninheritable Job and ordinary Windows child inheritance."""
    source_pins = {
        key: binding[key] for key in ("core_source_sha", "operations_source_sha")
    }
    if source_pins != {
        "core_source_sha": LEGACY_CORE,
        "operations_source_sha": LEGACY_OPS,
    }:
        matches(source_pins, package_source_pins())
    core_sha = binding["core_source_sha"]
    ops_sha = binding["operations_source_sha"]
    if not isinstance(core_sha, str) or not isinstance(ops_sha, str):
        raise AuditError("source_commit_required")
    raw_sources = {
        "runtime_limits.py": frozen_source(LEGACY_CORE, "core", "runtime_limits.py"),
        "guardian.py": frozen_source(LEGACY_OPS, "ops", "guardian.py"),
        "controlled_supervise.py": frozen_source(
            core_sha, "core", "controlled_supervise.py"
        ),
        "source_entry.py": frozen_source(ops_sha, "ops", "source_entry.py"),
        "windows_actor.py": frozen_source(core_sha, "core", "windows_actor.py"),
    }
    digests: dict[str, str] = {}
    for name, root in (("runtime_limits.py", CORE), ("guardian.py", OPS)):
        checked_path(root / name, file_required=True)
        installed = (root / name).read_bytes()
        require(installed == raw_sources[name], "installed_job_source_differs")
        digest = hashlib.sha256(installed).hexdigest()
        if name == "runtime_limits.py":
            frozen = object_value(object_value(binding["core_source_sha256"])[name])
            matches(frozen, {"sha256": digest, "bytes": len(installed)})
        else:
            require(
                object_value(binding["operations_sha256"])[name] == digest,
                "frozen_guardian_digest_differs",
            )
        digests[name] = digest
    trees = {name: ast.parse(raw) for name, raw in raw_sources.items()}
    job_calls = [
        node
        for node in ast.walk(trees["runtime_limits.py"])
        if isinstance(node, ast.Call)
    ]
    require(
        sum(
            ast.unparse(node.func) == "self.kernel.CreateJobObjectW"
            and [ast.unparse(arg) for arg in node.args] == ["None", "None"]
            and not node.keywords
            for node in job_calls
        )
        == 1,
        "noninheritable_job_creation_unproved",
    )
    require(
        any(
            ast.unparse(node)
            == "self.kernel.AssignProcessToJobObject(self.handle, self.kernel.GetCurrentProcess())"
            for node in job_calls
        ),
        "self_job_assignment_unproved",
    )
    require(
        any(
            isinstance(node, ast.Assign)
            and any(
                ast.unparse(target) == "limits.basic.flags" for target in node.targets
            )
            and ast.unparse(node.value) == "256 | 512 | 8192"
            for node in ast.walk(trees["runtime_limits.py"])
        ),
        "kill_on_close_mask_unproved",
    )
    forbidden = {
        "DuplicateHandle",
        "SetHandleInformation",
        "OpenJobObjectW",
        "OpenJobObjectA",
        "set_handle_inheritable",
    }
    popen_count = 0
    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            require(
                name.rsplit(".", 1)[-1] not in forbidden, "job_handle_transfer_unproved"
            )
            if name not in {
                "subprocess.Popen",
                "subprocess.check_output",
                "subprocess.run",
            }:
                continue
            popen_count += name == "subprocess.Popen"
            require(
                len(node.args) == 1 and not isinstance(node.args[0], ast.Starred),
                "popen_arguments_unproved",
            )
            keywords = {item.arg: item.value for item in node.keywords}
            require(
                None not in keywords
                and not set(keywords) & {"startupinfo", "pass_fds"},
                "popen_inheritance_unproved",
            )
            require(
                "close_fds" not in keywords
                or ast.unparse(keywords["close_fds"]) == "True",
                "popen_inheritance_unproved",
            )
            require(
                "creationflags" not in keywords
                or ast.unparse(keywords["creationflags"]) in {"0", "134217728"},
                "popen_breakaway_unproved",
            )
    require(popen_count == 3, "windows_popen_set_differs")
    for filename in ("guardian.py", "controlled_supervise.py"):
        main = next(
            (
                node
                for node in trees[filename].body
                if isinstance(node, ast.FunctionDef) and node.name == "main"
            ),
            None,
        )
        require(main is not None, "owned_main_unavailable")
        if main is None:
            raise AuditError("owned_main_unavailable")
        assignments = [
            node
            for node in main.body
            if isinstance(node, ast.Assign) and ast.unparse(node) == "job = OwnedJob()"
        ]
        spawns = [
            node
            for node in ast.walk(main)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "subprocess.Popen"
        ]
        require(
            len(assignments) == 1
            and bool(spawns)
            and all(assignments[0].lineno < node.lineno for node in spawns),
            "job_before_spawn_unproved",
        )
    return digests


def verify_installed_sources(binding: dict[str, object]) -> None:
    for root, names, field in (
        (CORE, CORE_SOURCES, "core_source_sha256"),
        (OPS, OPS_SOURCES, "operations_sha256"),
    ):
        frozen = object_value(binding[field])
        require(set(frozen) == names, "installed_source_set_differs")
        for name in sorted(names):
            path = root / name
            digest = digest_file(path)
            if root == CORE:
                row = object_value(frozen[name])
                matches(row, {"sha256": digest, "bytes": path.stat().st_size})
            else:
                require(frozen[name] == digest, "installed_operation_digest_differs")


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def process_parents() -> dict[int, int]:
    """Read Toolhelp PID ancestry without command lines, environments or signals."""
    require(os.name == "nt", "windows_required")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    require(
        snapshot not in (None, ctypes.c_void_p(-1).value),
        "process_snapshot_unavailable",
    )
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        require(
            bool(kernel.Process32FirstW(snapshot, ctypes.byref(entry))),
            "process_snapshot_unavailable",
        )
        parents: dict[int, int] = {}
        while True:
            pid = int(entry.th32ProcessID)
            require(pid not in parents, "duplicate_snapshot_pid")
            parents[pid] = int(entry.th32ParentProcessID)
            if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                require(ctypes.get_last_error() == 18, "process_snapshot_incomplete")
                return parents
    finally:
        require(bool(kernel.CloseHandle(snapshot)), "snapshot_handle_close_failed")


def require_absent(identities: set[int]) -> None:
    parents = process_parents()
    require(
        not identities.intersection(parents)
        and not identities.intersection(parents.values()),
        "owned_pid_or_descendant_present",
    )


def validate_pre_ready_diagnostics(directory: Path) -> list[dict[str, object]]:
    """Validate at most two actor identities without promoting diagnostics to authority."""
    checked_path(directory)
    require(directory.name == "pre_ready" and directory.is_dir(), "pre_ready_directory_required")
    phases = (
        "entry",
        "authorization",
        "role",
        "product_import",
        "settings",
        "service_urls",
        "engine",
        "database_session",
        "database_connect",
        "database_identity",
        "ready_publish",
    )
    fields = {
        "schema_version",
        "phase",
        "status",
        "role",
        "actual_pid",
        "creation_ticks",
        "observed_at",
    }
    directory_before = directory.stat()
    artifacts = []
    for artifact in directory.iterdir():
        artifacts.append(artifact)
        require(len(artifacts) <= 132, "pre_ready_artifact_count_exceeded")
    artifacts.sort()
    identities: dict[tuple[int, int], tuple[int, int, str | None]] = {}
    rows = []
    for path in artifacts:
        checked_path(path, file_required=True)
        match = re.fullmatch(
            r"([1-9][0-9]*)_([1-9][0-9]*)_([0-9]{2})_([a-z_]+)_(entered|completed|failed)\.json",
            path.name,
        )
        require(match is not None, "unknown_or_pending_pre_ready_artifact")
        assert match is not None
        before = path.stat()
        require(before.st_size <= 1024, "pre_ready_receipt_size_exceeded")
        raw = path.read_bytes()
        after = path.stat()
        require(
            (before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_ino, after.st_size, after.st_mtime_ns)
            and len(raw) == before.st_size,
            "pre_ready_artifact_changed",
        )
        try:
            value = object_value(json.loads(raw, object_pairs_hook=unique_pairs))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AuditError("pre_ready_json_invalid") from error
        require(set(value) == fields, "pre_ready_fields_differ")
        pid, birth, number = int(match[1]), int(match[2]), int(match[3])
        require(
            type(value["schema_version"]) is int
            and value["schema_version"] == 1
            and type(value["actual_pid"]) is int
            and value["actual_pid"] == pid
            and 0 < pid < 2**32
            and type(value["creation_ticks"]) is int
            and value["creation_ticks"] == birth
            and 0 < birth < 2**64,
            "pre_ready_integer_identity_differs",
        )
        require(
            number < len(phases)
            and phases[number] == match[4] == value["phase"]
            and value["status"] == match[5],
            "pre_ready_phase_identity_differs",
        )
        role = value["role"]
        if role is not None and not isinstance(role, str):
            raise AuditError("pre_ready_role_differs")
        require(
            role is None if number <= 2 else role in ("worker", "beat"),
            "pre_ready_role_differs",
        )
        observed_at = value["observed_at"]
        if not isinstance(observed_at, str):
            raise AuditError("pre_ready_timestamp_required")
        try:
            observed = datetime.fromisoformat(observed_at)
        except ValueError as error:
            raise AuditError("pre_ready_timestamp_invalid") from error
        require(observed.utcoffset() == timedelta(0), "pre_ready_timestamp_not_utc")
        identity = (pid, birth)
        require(
            all(
                existing_pid != pid or existing_birth == birth
                for existing_pid, existing_birth in identities
            ),
            "pre_ready_pid_birth_conflict",
        )
        count, used, known_role = identities.get(identity, (0, 0, None))
        if role is not None:
            require(known_role in (None, role), "pre_ready_actor_role_changed")
            known_role = role
        identities[identity] = (count + 1, used + len(raw), known_role)
        require(
            len(identities) <= 2 and count + 1 <= 33 and used + len(raw) <= 66 * 1024,
            "pre_ready_actor_budget_exceeded",
        )
        known_roles = [item[2] for item in identities.values() if item[2] is not None]
        require(len(known_roles) == len(set(known_roles)), "pre_ready_duplicate_actor_role")
        rows.append(
            {"name": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        )
    require(
        sum(item[1] for item in identities.values()) <= 132 * 1024,
        "pre_ready_total_budget_exceeded",
    )
    directory_after = directory.stat()
    require(
        (directory_before.st_ino, directory_before.st_mtime_ns)
        == (directory_after.st_ino, directory_after.st_mtime_ns),
        "pre_ready_directory_changed",
    )
    return rows



def evidence_paths(transition: bool) -> dict[str, Path]:
    """Select only the fixed current-attempt archive allowlist and reject partial files."""
    paths: dict[str, Path] = {}
    core_static = CORE_SOURCES | {
        "runtime_binding.json",
        "root_live_authorization.json",
        "source_budget_ledger.json",
        "control",
        "pre_ready",
    }
    ops_static = OPS_SOURCES | {
        "prepared.json",
        "activation.json",
        "attempt_history",
        "bootstrap_recovery_audit.json",
        "bootstrap_previous_runtime_binding.json",
        "beat",
        "beat.db",
        "beat.dat",
        "beat.dir",
        "beat.bak",
        "raw-unused-minio-forced",
    }
    for category, root, names, static in (
        ("core", CORE, CORE_ARTIFACTS, core_static),
        ("ops", OPS, OPS_ARTIFACTS, ops_static),
    ):
        checked_path(root)
        require(root.is_dir(), "runtime_root_absent")
        for path in root.iterdir():
            checked_path(path)
            require(
                path.name in names | static and not path.name.endswith(".pending"),
                "unknown_or_pending_runtime_artifact",
            )
            if category == "core" and path.name == "pre_ready":
                validate_pre_ready_diagnostics(path)
            if path.name in names:
                checked_path(path, file_required=True)
                paths[f"{category}/{path.name}"] = path
    control = CORE / "control"
    if control.exists():
        require(control.is_dir(), "control_directory_required")
        allowed = {
            f"{role}_{kind}.json"
            for role in ("worker", "beat")
            for kind in ("ready", "ack", "stop")
        }
        for path in control.iterdir():
            checked_path(path, file_required=True)
            require(path.name in allowed, "unknown_or_pending_control_artifact")
            paths[f"core/control/{path.name}"] = path
    checked_path(OBSERVER)
    live = OBSERVER / ("live_" + RUN_ID)
    if live.exists():
        checked_path(live)
        require(live.is_dir(), "observer_directory_required")
        for path in live.iterdir():
            checked_path(path, file_required=True)
            require(path.name in LIVE_ARTIFACTS, "unknown_or_pending_observer_artifact")
            paths[f"observer/{live.name}/{path.name}"] = path
    gate = OBSERVER / "root_live_gate.json"
    checked_path(gate)
    if gate.exists():
        paths["observer/root_live_gate.json"] = gate
    if transition:
        paths["ops/bootstrap_previous_runtime_binding.json"] = (
            OPS / "bootstrap_previous_runtime_binding.json"
        )
        paths["core/root_live_authorization.json"] = CORE / "root_live_authorization.json"
    return paths


def build_audit(candidate_hash: str) -> dict[str, object]:
    require(
        re.fullmatch("[a-f0-9]{64}", candidate_hash) is not None,
        "candidate_digest_required",
    )
    state, state_raw = read_object(OPS / "launch_state.json")
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
        "launch_state_fields_differ",
    )
    previous_hash = state["runtime_binding_sha256"]
    if (
        not isinstance(previous_hash, str)
        or re.fullmatch("[a-f0-9]{64}", previous_hash) is None
    ):
        raise AuditError("previous_binding_digest_required")
    transition = previous_hash != candidate_hash
    previous_path = OPS / "bootstrap_previous_runtime_binding.json"
    checked_path(previous_path)
    require(transition or not previous_path.exists(), "unexpected_previous_binding")
    current, current_raw = read_object(CORE / "runtime_binding.json")
    require(
        hashlib.sha256(current_raw).hexdigest() == candidate_hash,
        "candidate_binding_digest_differs",
    )
    previous, previous_raw = (
        read_object(previous_path) if transition else (current, current_raw)
    )
    require(
        hashlib.sha256(previous_raw).hexdigest() == previous_hash,
        "previous_binding_digest_differs",
    )
    if transition or previous_hash == LEGACY_HASH:
        require(previous_hash == LEGACY_HASH, "legacy_binding_digest_differs")
        matches(
            previous,
            {"core_source_sha": LEGACY_CORE, "operations_source_sha": LEGACY_OPS},
        )
    else:
        matches(previous, package_source_pins())
    matches(
        previous,
        {"run_id": RUN_ID, "nonce": NONCE, "product_sha": PRODUCT_SHA, "ready": True},
    )
    require(set(current) == set(previous), "candidate_binding_fields_differ")
    matches(
        current,
        {key: value for key, value in previous.items() if key not in SOURCE_FIELDS},
    )
    gate, gate_raw = read_object(CORE / "root_live_authorization.json")
    gate_binding = {
        key: value
        for key, value in previous.items()
        if key
        not in {
            "deployment_root",
            "operations_root",
            "core_root",
            "original_observer_scripts_sha",
            "operations_source_sha",
            "operations_sha256",
            "core_source_sha256",
            "ready",
        }
    }
    require(
        set(gate)
        == set(gate_binding) | FLAGS | {"runtime_binding_sha256", "authorized_at"},
        "legacy_gate_fields_differ",
    )
    matches(
        gate,
        {
            **gate_binding,
            **dict.fromkeys(FLAGS, True),
            "runtime_binding_sha256": previous_hash,
        },
    )
    aware_time(gate["authorized_at"])
    require(
        digest_file(CORE / "source_budget_ledger.json")
        == previous["source_job_ledger_sha256"],
        "historical_ledger_differs",
    )
    matches(
        state,
        {
            "run_id": RUN_ID,
            "nonce": NONCE,
            "product_sha": PRODUCT_SHA,
            "runtime_binding_sha256": previous_hash,
        },
    )
    observation_id = state["observation_id"]
    require(isinstance(observation_id, str), "observation_identity_required")
    if not isinstance(observation_id, str):
        raise AuditError("observation_identity_required")
    require(
        re.fullmatch("[a-f0-9]{32}", observation_id) is not None,
        "observation_identity_required",
    )
    receipt_binding = {
        key: state[key]
        for key in (
            "run_id",
            "nonce",
            "product_sha",
            "runtime_binding_sha256",
            "observation_id",
        )
    }
    source, source_raw = read_object(OPS / "source_identity.json")
    require(
        set(source) == {"run_id", "nonce", "actual_pid", "creation_ticks"},
        "source_identity_fields_differ",
    )
    matches(source, {"run_id": RUN_ID, "nonce": NONCE})
    source_pid = positive_integer(source["actual_pid"])
    source_birth = positive_integer(source["creation_ticks"])
    start, start_raw = read_object(OPS / "guardian_start.json")
    end, end_raw = read_object(OPS / "guardian_end.json")
    require(
        set(start)
        == {
            "started_at",
            "hard_deadline",
            "forced_stop_by",
            "monotonic_deadline",
            "run_id",
            "nonce",
            "guardian_pid",
            "product_sha",
            "runtime_binding_sha256",
            "observation_id",
            "launcher_pid",
            "actual_source_identity",
            "maximum_seconds",
        },
        "guardian_start_fields_differ",
    )
    require(
        set(end)
        == {
            "started_at",
            "ended_at",
            "run_id",
            "nonce",
            "reason",
            "actual_source_kernel_exit_ack",
            "product_sha",
            "runtime_binding_sha256",
            "observation_id",
            "source_job_kill_on_close_required",
            "descendant_exit_confirmation",
            "cpu_seconds_used",
            "formal_six_hour_pass",
        },
        "guardian_end_fields_differ",
    )
    matches(
        start,
        {**receipt_binding, "actual_source_identity": source, "maximum_seconds": 22500},
    )
    matches(
        end,
        {
            **receipt_binding,
            "started_at": start["started_at"],
            "actual_source_kernel_exit_ack": True,
            "source_job_kill_on_close_required": True,
            "descendant_exit_confirmation": "requires_final_actual_kernel_check",
            "formal_six_hour_pass": False,
        },
    )
    guardian_pid = positive_integer(start["guardian_pid"])
    launcher_pid = positive_integer(start["launcher_pid"])
    identities = {source_pid, guardian_pid, launcher_pid}
    require(len(identities) == 3, "source_identities_ambiguous")
    started = aware_time(start["started_at"])
    ended = aware_time(end["ended_at"])
    deadline = aware_time(start["hard_deadline"])
    parent_end = aware_time(previous["parent_deadline"])
    birth_time = datetime(1601, 1, 1, tzinfo=UTC) + timedelta(
        microseconds=source_birth // 10
    )
    require(
        started <= birth_time <= ended <= datetime.now(UTC),
        "source_birth_or_end_time_differs",
    )
    require(
        deadline == min(started + timedelta(seconds=22500), parent_end)
        and aware_time(start["forced_stop_by"]) == deadline - timedelta(seconds=15),
        "guardian_deadline_differs",
    )
    require(
        finite_cpu(state["cpu_seconds_used"]) + finite_cpu(end["cpu_seconds_used"])
        < 1200,
        "cumulative_cpu_exhausted",
    )
    logs = object_value(state["component_log_bytes"])
    require(
        set(logs) <= {"api", "worker", "beat", "observer", "minio"},
        "component_log_counter_unknown",
    )
    for role in ("api", "worker", "beat", "observer", "minio"):
        used = logs.get(role, 0)
        if type(used) is not int:
            raise AuditError("component_log_counter_unknown")
        path = (OPS if role == "minio" else CORE) / (role + ".log")
        checked_path(path)
        require(
            0 <= used
            and used + (path.stat().st_size if path.exists() else 0) < 8 * 1024**2,
            "cumulative_log_exhausted",
        )
    journal_used = state["journal_bytes_used"]
    if type(journal_used) is not int:
        raise AuditError("journal_counter_unknown")
    journal = OBSERVER / ("live_" + RUN_ID) / "collection_observations.jsonl"
    checked_path(journal)
    require(
        0 <= journal_used
        and journal_used + (journal.stat().st_size if journal.exists() else 0)
        < 16 * 1024**2 - 4 * 1024**2 - 16384,
        "journal_reserve_exhausted",
    )
    checked_path(CORE / "runtime_start.json")
    require(not (CORE / "runtime_start.json").exists(), "runtime_start_present")
    frozen_job = verify_frozen_job(previous)
    verify_installed_sources(current)
    artifacts = evidence_paths(transition)
    validated_raw = {
        "ops/launch_state.json": state_raw,
        "ops/source_identity.json": source_raw,
        "ops/guardian_start.json": start_raw,
        "ops/guardian_end.json": end_raw,
    }
    if transition:
        validated_raw.update(
            {
                "ops/bootstrap_previous_runtime_binding.json": previous_raw,
                "core/root_live_authorization.json": gate_raw,
            }
        )
    require_absent(identities)
    for name in ("minio_start.json", "minio_end.json"):
        path = OPS / name
        if path.exists():
            receipt, raw = read_object(path)
            validated_raw["ops/" + name] = raw
            matches(
                receipt,
                {
                    key: receipt_binding[key]
                    for key in (
                        "nonce",
                        "product_sha",
                        "runtime_binding_sha256",
                        "observation_id",
                    )
                },
            )
            if name == "minio_start.json":
                matches(receipt, {"run_id": RUN_ID})
    checked_path(OPS / "minio_segment.py", file_required=True)
    result = subprocess.run(
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
        capture_output=True,
        timeout=10,
        check=False,
    )
    require(result.returncode == 0, "minio_closed_scope_check_failed")
    envelope = (
        "/sys/fs/cgroup/dianzi-r01-20261014/minio-r06-envelope-"
        + NONCE
        + "-"
        + observation_id
    )
    target = envelope + "/minio-r06-nine-script-" + NONCE + "-" + observation_id
    kernel_events_check = (
        "from pathlib import Path;paths="
        + repr([envelope, target, envelope + "/owner"])
        + ";"
        "assert all(dict(line.split() for line in (Path(path)/'cgroup.events').read_text().splitlines()).get('populated')=='0' for path in paths)"
    )
    events = subprocess.run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "python3",
            "-B",
            "-c",
            kernel_events_check,
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    require(events.returncode == 0, "minio_kernel_events_not_empty")
    evidence = {name: digest_file(path) for name, path in sorted(artifacts.items())}
    require(
        all(
            evidence.get(name) == hashlib.sha256(raw).hexdigest()
            for name, raw in validated_raw.items()
        ),
        "validated_evidence_changed",
    )
    require(
        digest_file(CORE / "runtime_binding.json") == candidate_hash,
        "candidate_binding_changed",
    )
    verify_installed_sources(current)
    require_absent(identities)
    return {
        "schema": SCHEMA,
        **receipt_binding,
        "candidate_runtime_binding_sha256": candidate_hash,
        "observed_at": datetime.now(UTC)
        .astimezone(timezone(timedelta(hours=8)))
        .isoformat(),
        "actual_source_identity": source,
        "guardian_pid": guardian_pid,
        "source_launcher_pid": launcher_pid,
        "kernel_closure_basis": "frozen_noninheritable_kill_on_close_guardian_exit",
        "frozen_job_sha256": frozen_job,
        "windows_owned_job_exit_confirmed": True,
        "windows_descendants_exit_confirmed": True,
        "minio_closed_scope_checked": True,
        "evidence_sha256": evidence,
    }


def main() -> None:
    parser = AuditArgumentParser(description=__doc__)
    parser.add_argument("--candidate-runtime-binding-sha256", required=True)
    parser.add_argument("--output", action="store_true")
    arguments = parser.parse_args()
    audit = build_audit(arguments.candidate_runtime_binding_sha256)
    if arguments.output:
        target = OPS / "bootstrap_recovery_audit.json"
        checked_path(target)
        with target.open("xb") as stream:
            stream.write(
                (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode("utf-8")
            )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "verified": True,
                "audit_written": arguments.output,
                "evidence_files": len(object_value(audit["evidence_sha256"])),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        SyntaxError,
        OverflowError,
        RecursionError,
        subprocess.SubprocessError,
    ) as error:
        label = str(error) if isinstance(error, AuditError) else "audit_failed"
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "verified": False,
                    "error_type": type(error).__name__,
                    "failure_label": label,
                },
                separators=(",", ":"),
            )
        )
        raise SystemExit(1) from None
