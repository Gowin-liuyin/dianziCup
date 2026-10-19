"""Validate the single reviewed run before secrets, product imports or owned actors are used."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.engine import Connection

PRODUCT_ROOT = Path("D:\\wt\\r06-product-912-runtime-20261017")
TOOL_ROOT = Path("D:/dianzi-runtime-cache/r06-f3-tool-20261017")
OPERATIONS_ROOT = Path("D:/dianzi-runtime-cache/r06-f3-ops-20261017")
CORE_ROOT = Path("D:/dianzi-runtime-cache/r06-f3-core-20261017")
PRODUCT_SHA = "912d8b381eaab9260ead30d68f49b88fa8078384"
TOOL_SHA = "a1919643b715026938c12faa07ea15b4bd7deb89"
OBSERVER_SHA = "a1919643b715026938c12faa07ea15b4bd7deb89"
OBSERVER_RELATIVE = "reports/runs/recovery_r06_incremental_observation_fix2_20261017"
CORE_SOURCE_RELATIVE = "reports/runs/recovery_r06_activation_prep_20261016/candidate/core"
OPERATIONS_SOURCE_RELATIVE = "reports/runs/recovery_r06_activation_prep_20261016/candidate/ops"
RUN_ID = "r06_nine_script_20261016"
NONCE = "ea89c345e404475d94de02cbe67874e3"
CONTROL_MARKER_OWNER = "recovery_root:nonce:" + NONCE
QUEUE = "r06_nine_script_20261016"
REDIS_PREFIX = "r06-nine-script-20261016:"
DATABASE = "test_dianzi_r06_912_20261017_f15191e6ea74"
SCHEMA = "0030_revalidation_actor_bindings"
PARENT_END = datetime.fromisoformat("2026-10-17T21:49:15+08:00")
FLAGS = (
    "root_live_authorized",
    "independent_review_ship",
    "root_budget_approved",
    "integrated_key_checks_passed",
    "actual_kernel_guardian_checked",
    "fresh_resource_binding_checked",
    "source_db_oid_binding_approved",
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
OPERATIONS_NAMES = (
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
STATIC_GATE: dict[str, object] = {
    "run_id": RUN_ID,
    "nonce": NONCE,
    "product_sha": PRODUCT_SHA,
    "tool_sha": TOOL_SHA,
    "controller_source_sha": "87faa9e7ac48c17ac974cc2300d1bf03e8989d09",
    "maximum_seconds": 21600,
    "shutdown_seconds": 900,
    "source_job_cap": 450,
    "prestop": 410,
    "solo_maximum_row_bound": 418,
    "wire_https_cap": 35100,
    "model_requests_permitted": 0,
    "paid_provider_requests_permitted": 0,
    "source_database": DATABASE,
    "source_schema": SCHEMA,
    "redis_database": 15,
    "redis_prefix": REDIS_PREFIX,
    "redis_queue": QUEUE,
    "parent_deadline": PARENT_END.isoformat(),
    "actual_wire_count": "unknown",
    "source_cost": "unknown",
    "formal_six_hour_pass": False,
    "product_root": str(PRODUCT_ROOT),
}
STATIC_BINDING = {
    **STATIC_GATE,
    "deployment_root": str(TOOL_ROOT),
    "operations_root": str(OPERATIONS_ROOT),
    "core_root": str(CORE_ROOT),
    "original_observer_scripts_sha": OBSERVER_SHA,
}
DYNAMIC_FIELDS = {
    "source_database_oid",
    "source_database_marker_sha256",
    "core_source_sha",
    "operations_source_sha",
    "operations_sha256",
    "core_source_sha256",
    "ready",
    "source_job_ledger_offset",
    "source_job_ledger_sha256",
}
PREPARED_FIELDS = {
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
MARKER_FIELDS = {
    "project",
    "kind",
    "run_id",
    "owner",
    "product_sha",
    "maximum_seconds",
    "queue",
    "redis_prefix",
    "created_at",
}


def object_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("run binding JSON object required")
    return {key: item for key, item in value.items()}


def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate run binding JSON key")
        value[key] = item
    return value


def read_object(raw: bytes) -> dict[str, object]:
    if len(raw) > 65536:
        raise ValueError("run binding JSON exceeds bound")
    return object_value(json.loads(raw, object_pairs_hook=unique_pairs))


def require_digest(value: object, length: int) -> str:
    if not isinstance(value, str) or re.fullmatch(f"[a-f0-9]{{{length}}}", value) is None:
        raise ValueError("exact frozen run digest required")
    return value


def require_static(value: dict[str, object], expected: dict[str, object]) -> None:
    for key, item in expected.items():
        if type(value.get(key)) is not type(item) or value.get(key) != item:
            raise ValueError("fixed run identity or budget differs: " + key)


def validate_binding(value: dict[str, object], *, require_ready: bool) -> None:
    if set(value) != set(STATIC_BINDING) | DYNAMIC_FIELDS:
        raise ValueError("run binding fields missing or unknown")
    require_static(value, STATIC_BINDING)
    if type(value["ready"]) is not bool or (require_ready and value["ready"] is not True):
        raise ValueError("actual run binding is not ready")
    oid = value["source_database_oid"]
    marker = value["source_database_marker_sha256"]
    if marker is not None:
        require_digest(marker, 64)
    if oid is not None:
        if not isinstance(oid, str) or not oid.isascii() or not oid.isdigit() or int(oid) <= 0:
            raise ValueError("actual source database OID required")
        if oid == "3680428":
            raise ValueError("old source database is protected")
    if (oid is None or marker is None) and (value["ready"] is not False or require_ready):
        raise ValueError("marked database actual identity is unknown")
    for key in ("core_source_sha", "operations_source_sha"):
        if value[key] is None and value["ready"] is False and not require_ready:
            continue
        require_digest(value[key], 40)
    offset = value["source_job_ledger_offset"]
    ledger_hash = value["source_job_ledger_sha256"]
    if ledger_hash is not None:
        require_digest(ledger_hash, 64)
    if offset is not None and (type(offset) is not int or not 11 <= offset <= 450):
        raise ValueError("fixed historical source ledger offset required")
    if (offset is None or ledger_hash is None) and (value["ready"] is not False or require_ready):
        raise ValueError("historical source budget is not proven")
    operations = object_value(value["operations_sha256"])
    core = object_value(value["core_source_sha256"])
    if set(operations) != set(OPERATIONS_NAMES) or set(core) != set(CORE_NAMES):
        raise ValueError("exact nine operations and eleven core freeze required")
    for digest in operations.values():
        require_digest(digest, 64)
    if (
        operations["minio_controller.py"]
        != "8d2f69c369bff148698d8382bc39c761bb70a5848e920de58e176710f6fd1ce7"
    ):
        raise ValueError("final reviewed controller differs")
    for entry in core.values():
        row = object_value(entry)
        if set(row) != {"sha256", "bytes"} or type(row["bytes"]) is not int or row["bytes"] <= 0:
            raise ValueError("core frozen hash and byte count required")
        require_digest(row["sha256"], 64)


def aware_created_at(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError("root actual aware timestamp required")
    observed = datetime.fromisoformat(value)
    if observed.utcoffset() != timedelta(hours=8):
        raise ValueError("root actual timestamp must be aware +08")


def validate_database_snapshot(
    binding: dict[str, object], name: object, oid: object, marker: object, schema: object
) -> None:
    if (
        name != DATABASE
        or type(oid) is not str
        or oid != binding["source_database_oid"]
        or schema != SCHEMA
    ):
        raise ValueError("actual database name, OID or schema differs")
    if not isinstance(marker, str):
        raise ValueError("actual marked database COMMENT unavailable")
    if hashlib.sha256(marker.encode()).hexdigest() != binding["source_database_marker_sha256"]:
        raise ValueError("actual database COMMENT digest differs")
    content = read_object(marker.encode())
    if set(content) != MARKER_FIELDS:
        raise ValueError("database COMMENT fields missing or unknown")
    require_static(
        content,
        {
            "project": "dianzi",
            "kind": "isolated_live_source_observation",
            "run_id": RUN_ID,
            "owner": CONTROL_MARKER_OWNER,
            "product_sha": PRODUCT_SHA,
            "maximum_seconds": 21600,
            "queue": QUEUE,
            "redis_prefix": REDIS_PREFIX,
        },
    )
    aware_created_at(content["created_at"])


def validate_service_urls(database_url: object, redis_url: object) -> None:
    for value, schemes, port, path in (
        (database_url, {"postgresql", "postgresql+psycopg"}, 25432, "/" + DATABASE),
        (redis_url, {"redis"}, 26379, "/15"),
    ):
        if not isinstance(value, str):
            raise ValueError("bound local database and Redis URLs required")
        try:
            url = urlsplit(value)
            valid = (
                url.scheme in schemes
                and url.hostname in {"127.0.0.1", "localhost"}
                and url.port == port
                and url.path == path
                and not url.query
                and not url.fragment
            )
        except ValueError:
            raise ValueError("bound local database and Redis URL identity differs") from None
        if not valid:
            raise ValueError("bound local database and Redis URL identity differs")


def cumulative_source_jobs(current_jobs: object, binding: dict[str, object]) -> int:
    offset = binding.get("source_job_ledger_offset")
    if type(current_jobs) is not int or current_jobs < 0 or type(offset) is not int or offset < 11:
        raise ValueError("current count or historical source budget is unknown")
    return current_jobs + offset


def validate_source_ledger(raw: bytes) -> int:
    value = read_object(raw)
    fields = {
        "run_id",
        "nonce",
        "source_database",
        "source_database_oid",
        "observed_at",
        "accounting_mode",
        "source_job_ledger_offset",
        "job_ids",
        "initial_job_ids",
        "initial_count",
        "initial_receipt_sha256",
        "pg_snapshot_sha256",
    }
    if set(value) != fields:
        raise ValueError("source ledger fields missing or unknown")
    require_static(
        value,
        {
            "run_id": RUN_ID,
            "nonce": NONCE,
            "source_database": "test_dianzi_r06_catalog_live_8a_20261016",
            "source_database_oid": "3680428",
            "initial_count": 11,
        },
    )
    aware_created_at(value["observed_at"])
    for key in ("initial_receipt_sha256", "pg_snapshot_sha256"):
        require_digest(value[key], 64)
    collections: list[set[str]] = []
    for key in ("job_ids", "initial_job_ids"):
        entries = value[key]
        if not isinstance(entries, list) or len(entries) > 450:
            raise ValueError("bounded source job digest collection required")
        digests = [require_digest(item, 64) for item in entries]
        if len(digests) != len(set(digests)):
            raise ValueError("duplicate source job digest")
        collections.append(set(digests))
    current, initial = collections
    if value["accounting_mode"] == "exact_union":
        if len(initial) != 11 or not initial <= current:
            raise ValueError("initial eleven membership proof differs")
        offset = len(current | initial)
    elif value["accounting_mode"] == "conservative_sum":
        offset = len(current) + 11
    else:
        raise ValueError("historical source accounting is unknown")
    if (
        type(value["source_job_ledger_offset"]) is not int
        or value["source_job_ledger_offset"] != offset
    ):
        raise ValueError("frozen cumulative source ledger count differs")
    if not 11 <= offset <= 450:
        raise ValueError("historical source ledger exceeds the approved budget")
    return offset


def require_cumulative_producer_slot(engine: Engine, binding: dict[str, object]) -> None:
    import os

    from celery.exceptions import WorkerShutdown
    from owned_stop_watcher import owned_control_path, read_stop_request
    from sqlalchemy import text
    from task_fence import request_owned_worker_stop

    if read_stop_request("worker"):
        raise WorkerShutdown(0)
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout=3000"))
            count = connection.scalar(
                text("select count(*) from job_runs where job_type='collect_public_source_page'")
            )
        admitted = cumulative_source_jobs(count, binding) < 410
    except Exception as error:
        path = owned_control_path("worker", "ready").parent / (
            f"cumulative_fence_failure_{os.getpid()}.json"
        )
        with path.open("xb") as output:
            output.write(
                json.dumps(
                    {
                        "actual_pid": os.getpid(),
                        "observed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                        "phase": "cumulative_source_slot_pg_read",
                        "error_type": type(error).__name__,
                        "details": "withheld",
                    }
                ).encode()
                + b"\n"
            )
        request_owned_worker_stop()
        raise WorkerShutdown(70) from None
    if not admitted or read_stop_request("worker"):
        request_owned_worker_stop()
        raise WorkerShutdown(0)


def verify_database_connection(connection: Connection, binding: dict[str, object]) -> None:
    from sqlalchemy import text

    row = (
        connection.execute(
            text(
                "select current_database() database_name, oid::text database_oid, "
                "shobj_description(oid,'pg_database') database_marker "
                "from pg_database where datname=current_database()"
            )
        )
        .mappings()
        .one()
    )
    schema: object = connection.execute(
        text("select version_num from alembic_version")
    ).scalar_one()
    validate_database_snapshot(
        binding, row["database_name"], row["database_oid"], row["database_marker"], schema
    )


def validate_observer_gate(value: dict[str, object]) -> None:
    expected: dict[str, object] = {
        "root_live_authorized": True,
        "product_sha": PRODUCT_SHA,
        "observer_sha": TOOL_SHA,
        "product_root": str(PRODUCT_ROOT),
        "run_id": RUN_ID,
        "segment_id": "segment_" + NONCE,
        "supervisor_limits_verified": True,
        "maximum_seconds": 21600,
        "postgres_port": 25432,
        "redis_port": 26379,
        "opensearch_port": 29200,
        "source_scope": [
            "nvd_ollama",
            "vllm_vendor",
            "osv_ollama",
            "avid_community",
            "ollama_releases",
            "trailofbits_blog",
            "arxiv_security",
            "nist_ai_rmf",
            "cac_generative_ai",
        ],
    }
    if set(value) != set(expected) | {"started_at"}:
        raise ValueError("owned observer gate fields differ")
    require_static(value, expected)
    aware_created_at(value["started_at"])


def verify_tool_status() -> None:
    """Read committed outputs before their append-only journal; tmp files are unpublished."""
    gate_relative = OBSERVER_RELATIVE + "/root_live_gate.json"
    live_relative = OBSERVER_RELATIVE + "/live_" + RUN_ID
    tracked = subprocess.check_output(
        ["git", "ls-files", "--", gate_relative, live_relative], cwd=TOOL_ROOT
    )
    if tracked:
        raise ValueError("owned observer gate or output path is already tracked")
    raw_status = subprocess.check_output(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"], cwd=TOOL_ROOT
    )
    if not raw_status:
        return
    entries = raw_status.decode().rstrip("\0").split("\0")
    output_names = {
        "collection_observations.jsonl",
        "collection_latest.json",
        "collection_end.json",
        "collection_latest.json.tmp",
        "collection_end.json.tmp",
        "collector_stop.request",
    }
    paths = []
    for entry in entries:
        if not entry.startswith("?? "):
            raise ValueError("tracked tool source differs")
        relative = entry[3:]
        if relative != gate_relative and (
            not relative.startswith(live_relative + "/")
            or relative.removeprefix(live_relative + "/") not in output_names
        ):
            raise ValueError("unknown untracked tool item refuses runtime")
        path = TOOL_ROOT / relative
        if path.resolve() != path or path.is_symlink() or path.is_junction():
            raise ValueError("owned observer output redirected")
        paths.append(path)
    gate = TOOL_ROOT / gate_relative
    validate_observer_gate(read_object(gate.read_bytes()))
    journal = TOOL_ROOT / live_relative / "collection_observations.jsonl"
    published: dict[Path, bytes] = {}
    for path in paths:
        if path in (gate, journal):
            continue
        try:
            if path.stat().st_size > 1024**2 + 8192:
                raise ValueError("owned observer output exceeds original bound")
            if path.suffix == ".tmp":
                continue
            published[path] = path.read_bytes()
        except FileNotFoundError:
            if path.suffix != ".tmp":
                raise
    records: dict[str, dict[str, object]] = {}
    previous_hash = "0" * 64
    sequence = 0
    if journal.exists():
        for attempt in range(2):
            if attempt and datetime.now(PARENT_END.tzinfo) >= PARENT_END:
                raise ValueError("owned observer shared parent deadline expired")
            if journal.resolve() != journal or journal.is_symlink() or journal.is_junction():
                raise ValueError("owned observer output redirected")
            if journal.stat().st_size > 16 * 1024**2:
                raise ValueError("owned observer journal exceeds original cap")
            journal_bytes = journal.read_bytes()
            if len(journal_bytes) > 16 * 1024**2:
                raise ValueError("owned observer journal exceeds original cap")
            if not journal_bytes or journal_bytes.endswith(b"\n"):
                break
            if attempt:
                raise ValueError("owned observer journal is incomplete")
            remaining = (PARENT_END - datetime.now(PARENT_END.tzinfo)).total_seconds()
            if remaining <= 0:
                raise ValueError("owned observer shared parent deadline expired")
            time.sleep(min(0.01, remaining))
        for line in journal_bytes.splitlines():
            value = object_value(json.loads(line, object_pairs_hook=unique_pairs))
            require_static(
                value,
                {
                    "product_sha": PRODUCT_SHA,
                    "observer_sha": TOOL_SHA,
                    "run_id": RUN_ID,
                    "segment_id": "segment_" + NONCE,
                },
            )
            payload_fields = {
                "snapshot": {"observation"},
                "delta": {"changes"},
                "heartbeat": set(),
                "terminal": {"observation", "reason"},
            }
            kind = value.get("kind")
            required = {
                "schema",
                "observation_schema",
                "recorded_at",
                "seq",
                "kind",
                "observed_at",
                "product_sha",
                "observer_sha",
                "run_id",
                "segment_id",
                "continuity_gap",
                "state_sha256",
                "previous_record_sha256",
                "record_sha256",
            }
            if (
                not isinstance(kind, str)
                or kind not in payload_fields
                or set(value) != required | payload_fields[kind]
            ):
                raise ValueError("owned observer journal fields differ")
            require_static(
                value,
                {
                    "schema": "r06-observation-v2",
                    "observation_schema": "pg-safe-projection-v1",
                    "seq": sequence + 1,
                    "previous_record_sha256": previous_hash,
                    "continuity_gap": False,
                },
            )
            digest = require_digest(value["record_sha256"], 64)
            payload = {key: item for key, item in value.items() if key != "record_sha256"}
            encoded = (
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode()
            if hashlib.sha256(encoded).hexdigest() != digest:
                raise ValueError("owned observer journal record hash differs")
            records[digest] = value
            previous_hash = digest
            sequence += 1
    for path, content in published.items():
        if path.name == "collector_stop.request":
            if content != b"owned producers stopped or failed closed\n":
                raise ValueError("owned observer stop marker differs")
            continue
        if len(content) > 1024**2 + 8192:
            raise ValueError("owned observer output exceeds original bound")
        value = object_value(json.loads(content, object_pairs_hook=unique_pairs))
        digest = require_digest(value.get("record_sha256"), 64)
        if digest not in records:
            raise ValueError("owned observer output is not linked to this nonce journal")
        record = records[digest]
        if path.name.startswith("collection_end"):
            expected = {
                key: record[key]
                for key in (
                    "schema",
                    "observation_schema",
                    "product_sha",
                    "observer_sha",
                    "run_id",
                    "segment_id",
                    "reason",
                    "state_sha256",
                    "record_sha256",
                )
            }
            expected.update(
                ended_at=record["recorded_at"],
                last_pg_observed_at=record["observed_at"],
                sequence=record["seq"],
                formal_pass=False,
                continuous_window_claim=False,
            )
            if set(value) != set(expected):
                raise ValueError("owned observer terminal fields differ")
            require_static(value, expected)
        else:
            if set(value) != {
                "schema",
                "observation_schema",
                "sequence",
                "record_sha256",
                "observation",
            }:
                raise ValueError("owned observer latest fields differ")
            require_static(
                value,
                {
                    "schema": record["schema"],
                    "observation_schema": record["observation_schema"],
                    "sequence": record["seq"],
                },
            )
            observation = object_value(value["observation"])
            encoded = (
                json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode()
            if hashlib.sha256(encoded).hexdigest() != record["state_sha256"]:
                raise ValueError("owned observer latest state hash differs")


def verify_frozen_files(binding: dict[str, object], prepared: dict[str, object]) -> None:
    for directory, sha, require_clean in (
        (PRODUCT_ROOT, PRODUCT_SHA, True),
        (TOOL_ROOT, TOOL_SHA, False),
    ):
        if directory.resolve() != directory or directory.is_symlink() or directory.is_junction():
            raise ValueError("fixed checkout path redirected")
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=directory, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=directory, text=True
        ).strip()
        if actual != sha or (require_clean and status):
            raise ValueError("fixed clean product or tool checkout differs")
    verify_tool_status()
    for directory, names, source_sha, relative, sized in (
        (
            OPERATIONS_ROOT,
            OPERATIONS_NAMES,
            binding["operations_source_sha"],
            OPERATIONS_SOURCE_RELATIVE,
            False,
        ),
        (CORE_ROOT, CORE_NAMES, binding["core_source_sha"], CORE_SOURCE_RELATIVE, True),
    ):
        if directory.resolve() != directory or directory.is_symlink() or directory.is_junction():
            raise ValueError("fixed runtime script path redirected")
        hashes = object_value(binding["core_source_sha256" if sized else "operations_sha256"])
        for name in names:
            path = directory / name
            if path.is_symlink() or path.is_junction():
                raise ValueError("fixed runtime script redirected")
            raw = path.read_bytes()
            expected = hashes[name]
            if sized:
                entry = object_value(expected)
                if len(raw) != entry["bytes"]:
                    raise ValueError("core runtime byte count differs")
                expected = entry["sha256"]
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("frozen runtime script hash differs")
            blob = subprocess.check_output(
                ["git", "show", f"{source_sha}:{relative}/{name}"], cwd=TOOL_ROOT
            )
            if raw != blob:
                raise ValueError("frozen runtime script Git blob differs")
            if not sized:
                git_blobs = object_value(prepared["operations_git_blobs"])
                digest = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                if digest != git_blobs[name]:
                    raise ValueError("prepared operations Git blob identity differs")
    for name in ("observe.py", "observation_log.py", "pg_snapshot.py"):
        relative = OBSERVER_RELATIVE + "/" + name
        expected = subprocess.check_output(
            ["git", "show", OBSERVER_SHA + ":" + relative], cwd=TOOL_ROOT
        )
        if (TOOL_ROOT / relative).read_bytes() != expected:
            raise ValueError("original observer changed")


def validate_prepared(prepared: dict[str, object], binding: dict[str, object]) -> None:
    if set(prepared) != PREPARED_FIELDS or prepared["ready"] is not True:
        raise ValueError("exact prepared source identity is not ready")
    for key in set(binding) & set(prepared):
        if type(binding[key]) is not type(prepared[key]) or binding[key] != prepared[key]:
            raise ValueError("prepared and core run binding differ: " + key)
    if (
        type(prepared["maximum_total_seconds"]) is not int
        or prepared["maximum_total_seconds"] != 22500
    ):
        raise ValueError("prepared total deadline budget differs")
    blobs = object_value(prepared["operations_git_blobs"])
    if set(blobs) != set(OPERATIONS_NAMES):
        raise ValueError("prepared nine operations Git blob set differs")
    for digest in blobs.values():
        require_digest(digest, 40)
    aware_created_at(prepared["prepared_at"])


def verify_live_binding() -> dict[str, object]:
    gate_path = Path(__file__).resolve().parent / "root_live_authorization.json"
    if not gate_path.is_file():
        raise RuntimeError("root reviewed fixed run authorization required")
    gate = read_object(gate_path.read_bytes())
    gate_fields = (
        set(STATIC_GATE)
        | set(FLAGS)
        | {
            "source_database_oid",
            "source_database_marker_sha256",
            "core_source_sha",
            "runtime_binding_sha256",
            "authorized_at",
            "source_job_ledger_offset",
            "source_job_ledger_sha256",
        }
    )
    if set(gate) != gate_fields or any(gate.get(flag) is not True for flag in FLAGS):
        raise RuntimeError("root seven gates or exact runtime authorization fields differ")
    require_static(gate, STATIC_GATE)
    aware_created_at(gate["authorized_at"])
    raw = (CORE_ROOT / "runtime_binding.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != gate["runtime_binding_sha256"]:
        raise ValueError("root frozen runtime binding digest differs")
    binding = read_object(raw)
    validate_binding(binding, require_ready=True)
    for key in (
        "source_database_oid",
        "source_database_marker_sha256",
        "core_source_sha",
        "source_job_ledger_offset",
        "source_job_ledger_sha256",
    ):
        if gate[key] != binding[key]:
            raise ValueError("root gate and runtime binding identity differ")
    if Path(__file__).resolve().parent != CORE_ROOT:
        raise ValueError("entry is outside the single fixed core runtime")
    prepared = read_object((OPERATIONS_ROOT / "prepared.json").read_bytes())
    validate_prepared(prepared, binding)
    verify_frozen_files(binding, prepared)
    ledger = (CORE_ROOT / "source_budget_ledger.json").read_bytes()
    if hashlib.sha256(ledger).hexdigest() != binding["source_job_ledger_sha256"]:
        raise ValueError("root frozen source ledger digest differs")
    if validate_source_ledger(ledger) != binding["source_job_ledger_offset"]:
        raise ValueError("binding and actual source ledger offset differ")
    return binding


def require_start_window(observed_at: datetime) -> None:
    if observed_at.tzinfo is None or (PARENT_END - observed_at).total_seconds() < 22500:
        raise ValueError("full source and cleanup window does not fit parent deadline")
