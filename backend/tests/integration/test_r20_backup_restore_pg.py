"""Real PG16 tools and owned databases; synthetic records, no model/source live claim."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy
from pydantic import SecretStr
from reports.runs.recovery_r20_backup_restore_20261016.process_metadata import identity
from scripts.backup_restore import (
    DERIVED_TABLES,
    DatabaseTarget,
    RehearsalError,
    create_backup,
    guard_database,
    restore_backup,
    verify_backup,
)
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import document_revisions, evidence, job_runs
from ai_intel.knowledge.revisions import (
    add_text_block,
    attach_evidence_span,
    save_document_revision,
)

pytestmark = pytest.mark.real_pg
RUN = Path(__file__).resolve().parents[3] / "reports/runs/recovery_r20_backup_restore_20261016"
SCHEMA = "r20_backup_data"
DOCKER = [
    "wsl.exe",
    "-d",
    "Ubuntu-22.04",
    "-u",
    "root",
    "--exec",
    "/bin/sh",
    "-c",
    'printf "R20_DOCKER_PROC " >&2; cat /proc/$$/stat >&2; exec "$@"',
    "r20-tool-shim",
    "/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker",
    "--config",
    "/tmp/dianzi-docker-static-r01-20261014/runtime/client-config",
    "--host",
    "unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock",
    "exec",
    "-i",
    "dianzi-test-r01_20261014-postgres",
]


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def engine_for(url: URL) -> Engine:
    return create_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": str(url.query.get("options", ""))
            + " -c statement_timeout=20000 -c lock_timeout=3000",
        },
    )


class ContainerPgTools:
    """Test-only fixed parent container adapter; local PG socket needs no secret argv."""

    def __init__(self, url: URL) -> None:
        self._url = url

    @property
    def database_identity(self) -> tuple[str, int, str]:
        return self._url.host or "", self._url.port or 5432, self._url.database or ""

    def execute(self, tool: str, arguments: list[str], payload: bytes | None = None) -> bytes:
        command = [
            *DOCKER,
            "/bin/sh",
            "-c",
            'printf "R20_PG_TOOL_PROC " >&2; cat /proc/$$/stat >&2; exec "$@"',
            "r20-pg-tool",
            tool,
            "-p",
            "25432",
            "-U",
            self._url.username or "",
            *arguments,
        ]
        started = now()
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        shim_identity = identity(process.pid)
        try:
            output, errors = process.communicate(payload, timeout=75)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise RehearsalError("bounded_container_pg_tool_timed_out") from None
        linux_identities = []
        for line in errors.decode("utf-8", errors="replace").splitlines():
            if line.startswith(("R20_DOCKER_PROC ", "R20_PG_TOOL_PROC ")):
                tag, stat = line.split(" ", 1)
                linux_pid = int(stat.split(" ", 1)[0])
                fields = stat.rsplit(")", 1)[1].split()
                linux_identities.append(
                    {"role": tag, "pid": linux_pid, "birth_clock_ticks": int(fields[19])}
                )
        with (RUN / "tool_receipts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "tool": tool,
                        "started_at": started,
                        "ended_at": now(),
                        "launcher_pid": os.getpid(),
                        "wsl_shim": shim_identity,
                        "linux_processes": linux_identities,
                        "exit_code": process.returncode,
                        "fixed_container": "dianzi-test-r01_20261014-postgres",
                        "new_listener": False,
                        "argv_policy": "account field omitted; no DSN/password in argv",
                        "payload_logged": False,
                    }
                )
                + "\n"
            )
        if process.returncode:
            raise RehearsalError("bounded_container_pg_tool_failed")
        return output

    def dump(self, destination: Path, snapshot: str, excluded: tuple[str, ...]) -> None:
        payload = self.execute(
            "pg_dump",
            [
                "--dbname=" + (self._url.database or ""),
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--snapshot=" + snapshot,
                *("--exclude-table-data=" + name for name in excluded),
            ],
        )
        destination.write_bytes(payload)

    def restore(self, archive: Path) -> None:
        self.execute(
            "pg_restore",
            [
                "--dbname=" + (self._url.database or ""),
                "--single-transaction",
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
            ],
            archive.read_bytes(),
        )


@dataclass(frozen=True)
class Rehearsal:
    source: Engine
    destination: Engine
    source_target: DatabaseTarget
    destination_target: DatabaseTarget
    root: Path
    source_url: URL
    destination_url: URL


@pytest.fixture
def owned_rehearsal(
    register_sensitive_failure_value: Callable[[SecretStr], None],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Rehearsal]:
    """Only exact fresh DBs created here may be cleaned, after OID/comment/schema verification."""
    if os.environ.get("R20_REHEARSAL_AUTHORIZED") != "1":
        pytest.fail("blocked_integration: guarded R20 resource launcher required")
    original = make_url(os.environ["TEST_DATABASE_URL"]).set(drivername="postgresql+psycopg")
    register_sensitive_failure_value(SecretStr(original.render_as_string(hide_password=False)))
    if original.password:
        register_sensitive_failure_value(SecretStr(original.password))
    if (
        (original.host, original.port, original.database)
        != (
            "127.0.0.1",
            25432,
            "test_dianzi_r01_20261014",
        )
        or not original.username
        or not original.username.startswith("test_")
    ):
        pytest.fail("blocked_integration: parent identity rejected")
    identifier = uuid4().hex[:12]
    marker = "dianzi-rehearsal:r20_backup_" + identifier
    names = ("test_dianzi_r20_backup_src_" + identifier, "test_dianzi_r20_backup_dst_" + identifier)
    private_root = Path("D:/dianzi-private/r20-backup-rehearsal") / identifier
    private_root.mkdir(parents=True, mode=0o700)
    (private_root / ".rehearsal-owner").write_text(marker, encoding="utf-8")
    admin = create_engine(
        original, isolation_level="AUTOCOMMIT", poolclass=NullPool, hide_parameters=True
    )
    oids: dict[str, int] = {}
    engines: list[Engine] = []
    started = now()
    try:
        for name in names:
            with admin.connect() as connection:
                if connection.scalar(
                    text("SELECT oid FROM pg_database WHERE datname=:name"), {"name": name}
                ):
                    pytest.fail("owned database already exists; refusing reuse")
                connection.exec_driver_sql('CREATE DATABASE "' + name + '"')
                connection.exec_driver_sql(
                    'COMMENT ON DATABASE "' + name + "\" IS '" + marker + "'"
                )
                oids[name] = int(
                    connection.scalar(
                        text("SELECT oid FROM pg_database WHERE datname=:name"), {"name": name}
                    )
                )
        source_url, destination_url = (original.set(database=name) for name in names)
        source, destination = (engine_for(url) for url in (source_url, destination_url))
        engines.extend([source, destination])
        with source.begin() as connection:
            connection.exec_driver_sql('CREATE SCHEMA "' + SCHEMA + '"')
            connection.exec_driver_sql('COMMENT ON SCHEMA "' + SCHEMA + "\" IS '" + marker + "'")
            schema_oid = int(
                connection.scalar(
                    text("SELECT oid FROM pg_namespace WHERE nspname=:name"), {"name": SCHEMA}
                )
            )
        migration_url = source_url.update_query_dict(
            {"options": "-csearch_path=" + SCHEMA + ",public"}
        )

        def migration_engine(url: str) -> Engine:
            migrated = engine_for(make_url(url))
            engines.append(migrated)
            return migrated

        with monkeypatch.context() as migration_patch:
            migration_patch.setattr(sqlalchemy, "create_engine", migration_engine)
            run_migrations(migration_url.render_as_string(hide_password=False))
        source.dispose()
        destination.dispose()
        source_url = source_url.update_query_dict(
            {"options": "-csearch_path=" + SCHEMA + ",public"}
        )
        destination_url = destination_url.update_query_dict(
            {"options": "-csearch_path=" + SCHEMA + ",public"}
        )
        source, destination = (engine_for(url) for url in (source_url, destination_url))
        engines.extend([source, destination])
        common = {"host": "127.0.0.1", "port": 25432, "marker": marker, "schema_name": SCHEMA}
        yield Rehearsal(
            source,
            destination,
            DatabaseTarget(
                **common, database=names[0], database_oid=oids[names[0]], schema_oid=schema_oid
            ),
            DatabaseTarget(
                **common, database=names[1], database_oid=oids[names[1]], schema_oid=None
            ),
            private_root,
            source_url,
            destination_url,
        )
    finally:
        for engine in engines:
            engine.dispose()
        for name, oid in oids.items():
            with admin.connect() as connection:
                row = connection.execute(
                    text(
                        "SELECT oid, shobj_description(oid,'pg_database') FROM pg_database "
                        "WHERE datname=:name"
                    ),
                    {"name": name},
                ).one()
                assert tuple(row) == (oid, marker), "cleanup identity changed; refusing drop"
                sessions = int(
                    connection.scalar(
                        text("SELECT count(*) FROM pg_stat_activity WHERE datname=:name"),
                        {"name": name},
                    )
                )
                assert sessions == 0, "owned connection still active; refusing forced termination"
                connection.exec_driver_sql('DROP DATABASE "' + name + '"')
        with admin.connect() as connection:
            remaining = int(
                connection.scalar(
                    text("SELECT count(*) FROM pg_database WHERE datname = ANY(:names)"),
                    {"names": list(names)},
                )
            )
        admin.dispose()
        assert (
            private_root.resolve().parent
            == Path("D:/dianzi-private/r20-backup-rehearsal").resolve()
        )
        assert (private_root / ".rehearsal-owner").read_text() == marker
        shutil.rmtree(private_root)
        with (RUN / "resource_end.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "started_at": started,
                        "ended_at": now(),
                        "owned_databases_remaining": remaining,
                        "owned_connections_remaining": 0,
                        "owned_schemas_remaining": 0,
                        "owned_payload_directories_remaining": int(private_root.exists()),
                        "new_listeners": 0,
                        "parent_service_stopped": False,
                        "pool": "NullPool",
                        "connection_ceiling": 2,
                        "launcher_pid": os.getpid(),
                        "scope": "PG integration with synthetic business input",
                    }
                )
                + "\n"
            )


def authentication(engine: Engine) -> AuthenticationSessionService:
    return AuthenticationSessionService(
        DatabaseUserDirectory(engine),
        ("https://example.invalid",),
        False,
        state_store=PgAuthenticationStateStore(engine),
    )


def test_restore_auth_history_evidence_jobs_and_restart(owned_rehearsal: Rehearsal) -> None:
    case = owned_rehearsal
    store = ContentStore(case.root / "source_objects")
    original_a = b"synthetic original revision A"
    original_b = b"synthetic original revision B"
    initial = store.store_bytes(original_a)
    now_utc = datetime.now(UTC)
    auth = authentication(case.source)
    auth.create_precreated_user("r20-operator", "synthetic-r20-password", None, Role.SYSTEM_ADMIN)
    auth.create_precreated_user("r20-tenant", "synthetic-tenant-password", "tenant_a", Role.ANALYST)
    operator_token, _operator_session = auth.login(
        "r20-operator", "synthetic-r20-password", None, "r20-operator-client"
    )
    operator_scope = auth.build_access_scope(operator_token)
    tenant_token, _tenant_session = auth.login(
        "r20-tenant", "synthetic-tenant-password", None, "r20-tenant-client"
    )
    document_id = str(uuid4())
    source_id = str(uuid4())
    with case.source.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES (:source,'synthetic','vendor_advisory','https://example.invalid',"
                "'tenant','tenant_a',:now)"
            ),
            {"source": source_id, "now": now_utc},
        )
        connection.execute(
            text("INSERT INTO content_objects VALUES (:hash, :size, :now)"),
            {"hash": initial.content_hash, "size": initial.size_bytes, "now": now_utc},
        )
        connection.execute(
            text(
                "INSERT INTO documents(document_id,source_id,kind,title,retrieved_at,"
                "content_hash,visibility,tenant_id,schema_version) "
                "VALUES(:document,:source,'advisory','synthetic',:now,:hash,'tenant','tenant_a',1)"
            ),
            {
                "document": document_id,
                "source": source_id,
                "now": now_utc,
                "hash": initial.content_hash,
            },
        )
        connection.execute(
            insert(job_runs).values(
                job_id="synthetic-r20-job",
                tenant_id="tenant_a",
                job_type="revalidation",
                status="retry_wait",
                payload_ref="synthetic:input",
                created_at=now_utc,
                updated_at=now_utc,
                error_code="source_unavailable",
            )
        )
        connection.execute(
            text(
                "INSERT INTO hybrid_index_generations VALUES "
                "('synthetic-old-generation','synthetic-old-index',"
                "'synthetic-not-model',384,'ready',:now)"
            ),
            {"now": now_utc},
        )
    with Session(case.source) as session, session.begin():
        first = save_document_revision(
            session, store, document_id, original_a, "tenant", "tenant_a", now_utc
        )
        second = save_document_revision(
            session, store, document_id, original_b, "tenant", "tenant_a", now_utc
        )
        block = add_text_block(
            session, second.revision_id, 0, 0, len(original_b), original_b.decode()
        )
        evidence_id = attach_evidence_span(
            session,
            second.revision_id,
            0,
            len(original_b),
            "synthetic:span",
            original_b.decode(),
            True,
            "tenant",
            "tenant_a",
            now_utc,
            block,
        )
    code_version = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=RUN.parents[2], text=True
    ).strip()
    pin = create_backup(
        case.source,
        case.source_target,
        operator_scope,
        store,
        ContainerPgTools(case.source_url),
        case.root,
        case.root / "backup",
        code_version,
    )
    manifest = verify_backup(case.root / "backup", pin)
    assert manifest.tables["document_revisions"].row_count == 2
    assert manifest.tables["users"].row_count == 2
    receipt = restore_backup(
        case.destination,
        case.destination_target,
        operator_scope,
        ContainerPgTools(case.destination_url),
        case.root,
        case.root / "backup",
        case.root / "restored_objects",
        pin,
    )
    assert receipt == {"database": "verified", "content": "verified", "indexes": "rebuild_required"}
    restored_auth = authentication(case.destination)
    assert restored_auth.validate_session(tenant_token).tenant_id == "tenant_a"
    with case.destination.connect() as connection:
        assert connection.execute(
            select(document_revisions.c.revision_number, document_revisions.c.is_current).order_by(
                document_revisions.c.revision_number
            )
        ).all() == [(1, False), (2, True)]
        assert connection.execute(
            select(evidence.c.quote, evidence.c.revision_id).where(
                evidence.c.evidence_id == evidence_id
            )
        ).one() == (original_b.decode(), second.revision_id)
        assert connection.execute(select(job_runs.c.status, job_runs.c.error_code)).one() == (
            "retry_wait",
            "source_unavailable",
        )
        for table in DERIVED_TABLES:
            assert connection.scalar(text(f'SELECT count(*) FROM "{SCHEMA}"."{table}"')) == 0
    restored_store = ContentStore(case.root / "restored_objects")
    assert restored_store.read_verified(first.content_hash) == original_a
    assert restored_store.read_verified(second.content_hash) == original_b
    case.destination.dispose()
    environment = os.environ.copy()
    environment.update(
        R20_RESTART_DATABASE_URL=case.destination_url.render_as_string(hide_password=False),
        R20_RESTART_CONTENT_DIRECTORY=str(case.root / "restored_objects"),
        R20_RESTART_SESSION_TOKEN=tenant_token,
    )
    restarted = subprocess.run(
        [sys.executable, str(RUN / "restart_read.py")],
        env=environment,
        capture_output=True,
        timeout=30,
    )
    assert restarted.returncode == 0, "fresh process read failed; output intentionally not exposed"
    observed = json.loads(restarted.stdout)
    assert observed == {
        "authenticated": True,
        "history": 2,
        "evidence": 1,
        "job_status": "retry_wait",
        "objects_verified": 2,
    }
    observation_path = RUN / "rehearsal_observation.json"
    prior_counter = 2
    while observation_path.exists():
        observation_path = RUN / ("rehearsal_observation_" + str(prior_counter) + ".json")
        prior_counter += 1
    observation_path.write_text(
        json.dumps(
            {
                "observed_at": now(),
                "manifest_sha256": pin,
                "dump_sha256": manifest.dump_sha256,
                "schema_revision": manifest.schema_revision,
                "table_count": len(manifest.tables),
                "record_count": sum(value.row_count for value in manifest.tables.values()),
                "registered_object_count": len(manifest.objects),
                "restore": receipt,
                "fresh_process": observed,
                "pg_server_version": manifest.server_version,
                "production": False,
                "model_source_live": "not_run",
                "os_service_restart": "not_run; parent service belongs to another lane",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_real_wrong_oid_and_nonempty_target_guard(owned_rehearsal: Rehearsal) -> None:
    case = owned_rehearsal
    with case.destination.connect() as connection:
        guard_database(connection, case.destination_target, empty=True)
        with pytest.raises(RehearsalError, match="identity"):
            guard_database(
                connection,
                case.destination_target.model_copy(
                    update={"database_oid": case.destination_target.database_oid + 1}
                ),
                empty=True,
            )
    auth = authentication(case.source)
    auth.create_precreated_user(
        "r20-lock-operator", "synthetic-lock-password", None, Role.SYSTEM_ADMIN
    )
    session_token, _session_record = auth.login(
        "r20-lock-operator",
        "synthetic-lock-password",
        None,
        "r20-lock-client",
    )
    scope = auth.build_access_scope(session_token)
    store = ContentStore(case.root / "source_objects")
    code_version = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=RUN.parents[2],
        text=True,
    ).strip()
    pin = create_backup(
        case.source,
        case.source_target,
        scope,
        store,
        ContainerPgTools(case.source_url),
        case.root,
        case.root / "backup",
        code_version,
    )
    with case.destination.begin() as locked:
        assert (
            locked.scalar(
                text(
                    "SELECT pg_try_advisory_xact_lock("
                    "hashtextextended('dianzi-restore-rehearsal',0))"
                )
            )
            is True
        )
        with pytest.raises(RehearsalError, match="incomplete_or_degraded"):
            restore_backup(
                case.destination,
                case.destination_target,
                scope,
                ContainerPgTools(case.destination_url),
                case.root,
                case.root / "backup",
                case.root / "blocked_objects",
                pin,
            )
        assert not (case.root / "blocked_objects").exists()
        guard_database(locked, case.destination_target, empty=True)
    with case.destination.begin() as connection:
        connection.exec_driver_sql("CREATE TYPE public.owned_sentinel AS ENUM ('preserve')")
        with pytest.raises(RehearsalError, match="not_empty"):
            guard_database(connection, case.destination_target, empty=True)
        connection.exec_driver_sql("CREATE TABLE public.user_sentinel(value text)")
        connection.exec_driver_sql("INSERT INTO public.user_sentinel VALUES ('preserve')")
    with case.destination.connect() as connection:
        with pytest.raises(RehearsalError, match="not_empty"):
            guard_database(connection, case.destination_target, empty=True)
        assert connection.scalar(text("SELECT value FROM public.user_sentinel")) == "preserve"
