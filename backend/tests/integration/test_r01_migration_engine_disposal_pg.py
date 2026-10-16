"""真实迁移连接释放与失败事务回滚，仅操作带 nonce/OID 的新自有测试库。"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy
from alembic.runtime.migration import MigrationContext
from pydantic import SecretStr
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, Connection, Engine, make_url
from sqlalchemy.pool import NullPool

from ai_intel.infrastructure import database as database_module
from ai_intel.infrastructure.database import (
    build_engine,
    current_migration_revision,
    run_migrations,
)
from ai_intel.infrastructure.settings import ApplicationSettings

pytestmark = pytest.mark.real_pg
RUN = (
    Path(__file__).resolve().parents[3] / "reports/runs/r01_migration_engine_disposal_fix_20261017"
)
PWSH = (
    "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/"
    "dependencies/native/powershell/pwsh.exe"
)
HEAD = "0030_revalidation_actor_bindings"


def emit_record(record: dict[str, object]) -> None:
    payload = {"at": datetime.now().astimezone().isoformat(), **record}
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / "pg_lifecycle.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(payload, sort_keys=True) + "\n")


def load_parent_url() -> URL:
    result = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-Command",
            "$disposalProtected=Get-Content -LiteralPath "
            "'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
            "$disposalClear=$disposalProtected | ConvertTo-SecureString | "
            "ConvertFrom-SecureString -AsPlainText; [Console]::Write($disposalClear)",
        ],
        capture_output=True,
        timeout=12,
        check=True,
    )
    secret_key = SecretStr(json.loads(result.stdout)["TEST_DATABASE_URL"])
    url = make_url(secret_key.get_secret_value())
    if (
        url.get_backend_name() != "postgresql"
        or url.host != "127.0.0.1"
        or url.port != 25432
        or url.database != "test_dianzi_r01_20261014"
        or url.username != "test_dianzi_r01"
    ):
        raise RuntimeError("authorized parent PostgreSQL identity rejected")
    return url.set(drivername="postgresql+psycopg")


def record_connection(
    connection: Connection,
    label: str,
    *,
    record: Callable[[dict[str, object]], None] = emit_record,
) -> int:
    database, username, backend_pid, schema = connection.execute(
        text("SELECT current_database(), current_user, pg_backend_pid(), current_schema()")
    ).one()
    if not isinstance(backend_pid, int):
        raise RuntimeError("PostgreSQL backend PID must be an integer")
    record(
        {
            "event": "connection_identity",
            "label": label,
            "database": database,
            "username": username,
            "backend_pid": backend_pid,
            "schema": schema,
        }
    )
    return backend_pid


@dataclass
class OwnedDatabase:
    parent: Engine
    target_url: URL
    database: str
    schema: str
    marker: str
    oid: int | None
    engines: list[Engine] = field(default_factory=list)
    reporting_errors: list[OSError] = field(default_factory=list)

    def record(self, payload: dict[str, object]) -> None:
        """报告 IO 失败延迟到资源清理后报告，不从 dispose 回调替换业务异常。"""
        try:
            emit_record(payload)
        except OSError as error:
            self.reporting_errors.append(error)

    def sessions(self, label: str) -> list[dict[str, object]]:
        with self.parent.connect() as control:
            record_connection(control, "parent_control:" + label, record=self.record)
            rows = control.execute(
                text(
                    "SELECT pid, usename, application_name, state "
                    "FROM pg_stat_activity WHERE datname=:database ORDER BY pid"
                ),
                {"database": self.database},
            ).mappings()
            sessions = [dict(row) for row in rows]
        self.record({"event": "target_sessions", "label": label, "sessions": sessions})
        return sessions


@pytest.fixture()
def owned_database() -> Iterator[OwnedDatabase]:
    parent_url = load_parent_url()
    parent = create_engine(
        parent_url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=10000"},
    )
    nonce = uuid4().hex[:12]
    database = "test_r01_dispose_" + nonce
    schema = "test_r01_dispose_" + nonce
    marker = "r01_migration_engine_disposal_fix_20261017:" + nonce
    assert re.fullmatch(r"test_r01_dispose_[a-f0-9]{12}", database)
    target_url = parent_url.set(database=database).update_query_dict(
        {
            "application_name": "r01_disposal_owned",
            "connect_timeout": "5",
            "options": f"-c search_path={schema} -c statement_timeout=10000 -c lock_timeout=3000",
        }
    )
    owned = OwnedDatabase(parent, target_url, database, schema, marker, None)
    created_oid: int | None = None
    try:
        with parent.connect() as control:
            record_connection(control, "parent_guard", record=owned.record)
            identity = control.execute(text("SELECT current_database(), current_user")).one()
            assert tuple(identity) == ("test_dianzi_r01_20261014", "test_dianzi_r01")
            superuser: object = control.execute(
                text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")
            ).scalar_one()
            owned.record({"event": "parent_guard", "superuser": superuser})
            assert (
                control.execute(
                    text("SELECT oid FROM pg_database WHERE datname=:database"),
                    {"database": database},
                ).scalar_one_or_none()
                is None
            )
            control.exec_driver_sql(f'CREATE DATABASE "{database}"')
            created_oid = control.execute(
                text("SELECT oid FROM pg_database WHERE datname=:database"), {"database": database}
            ).scalar_one()
            control.exec_driver_sql(f"COMMENT ON DATABASE \"{database}\" IS '{marker}'")
        owned.oid = created_oid
        owned.record(
            {
                "event": "owned_database",
                "nonce": nonce,
                "database": database,
                "oid": created_oid,
                "schema": schema,
                "marker": marker,
            }
        )
        setup_engine = create_engine(target_url, poolclass=NullPool, hide_parameters=True)
        owned.engines.append(setup_engine)
        with setup_engine.begin() as connection:
            record_connection(connection, "schema_setup", record=owned.record)
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        setup_engine.dispose()
        yield owned
    finally:
        dropped = False
        try:
            owned.record({"event": "cleanup_begin", "database": database, "oid": created_oid})
            for engine in owned.engines:
                engine.dispose()
            assert owned.sessions("cleanup_before_drop") == []
            if created_oid is not None:
                with parent.connect() as control:
                    record_connection(control, "parent_cleanup", record=owned.record)
                    row = control.execute(
                        text(
                            "SELECT oid, shobj_description(oid, 'pg_database') "
                            "FROM pg_database WHERE datname=:database"
                        ),
                        {"database": database},
                    ).one()
                    assert tuple(row) == (created_oid, marker)
                    control.exec_driver_sql(f'DROP DATABASE "{database}"')
                    assert (
                        control.execute(
                            text("SELECT oid FROM pg_database WHERE datname=:database"),
                            {"database": database},
                        ).scalar_one_or_none()
                        is None
                    )
                    dropped = True
        finally:
            parent.dispose()
            owned.record({"event": "cleanup_end", "database": database, "dropped": dropped})
        if owned.reporting_errors:
            raise RuntimeError(
                f"PostgreSQL test report writes failed: {len(owned.reporting_errors)}"
            ) from owned.reporting_errors[0]


def trace_owned_engine(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedDatabase,
    label: str,
    *,
    revision_lookup: bool = False,
) -> list[int]:
    actual_create_engine = sqlalchemy.create_engine
    pids: list[int] = []

    def create_migration_engine(url: str) -> Engine:
        engine = actual_create_engine(url)
        owned.engines.append(engine)

        def connected(connection: Connection) -> None:
            pids.append(record_connection(connection, label, record=owned.record))
            connection.commit()

        def disposed(engine: Engine) -> None:
            owned.record({"event": "owned_engine_disposed", "label": label})

        event.listen(engine, "engine_connect", connected)
        event.listen(engine, "engine_disposed", disposed)
        return engine

    module = database_module if revision_lookup else sqlalchemy
    monkeypatch.setattr(module, "create_engine", create_migration_engine)
    return pids


def test_head_migration_and_two_product_engines_leave_no_target_sessions(
    owned_database: OwnedDatabase,
    monkeypatch: pytest.MonkeyPatch,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    owned = owned_database
    register_sensitive_failure_value(
        SecretStr(owned.target_url.render_as_string(hide_password=False))
    )
    register_sensitive_failure_value(SecretStr(owned.target_url.password or ""))
    assert owned.sessions("before_head") == []
    with monkeypatch.context() as revision_patch:
        pids = trace_owned_engine(revision_patch, owned, "revision_missing", revision_lookup=True)
        assert (
            current_migration_revision(owned.target_url.render_as_string(hide_password=False))
            is None
        )
        assert len(pids) == 1
    assert owned.sessions("after_missing_revision") == []
    with monkeypatch.context() as migration_patch:
        pids = trace_owned_engine(migration_patch, owned, "head_migration")
        run_migrations(owned.target_url.render_as_string(hide_password=False), "head")
    assert len(pids) == 1
    assert owned.sessions("after_head") == []
    with monkeypatch.context() as revision_patch:
        pids = trace_owned_engine(revision_patch, owned, "revision_head", revision_lookup=True)
        assert (
            current_migration_revision(owned.target_url.render_as_string(hide_password=False))
            == HEAD
        )
        assert len(pids) == 1
    assert owned.sessions("after_head_revision") == []
    settings = ApplicationSettings(
        app_env="test",
        database_url=SecretStr(owned.target_url.render_as_string(hide_password=False)),
        dependency_timeout_seconds=3,
    )
    engines = [build_engine(settings), build_engine(settings)]
    owned.engines.extend(engines)
    connections: list[Connection] = []
    try:
        product_pids: list[int] = []
        for position, engine in enumerate(engines):
            connection = engine.connect()
            connections.append(connection)
            product_pids.append(
                record_connection(connection, f"product_{position + 1}", record=owned.record)
            )
        assert (
            connections[0]
            .execute(text(f'SELECT version_num FROM "{owned.schema}".alembic_version'))
            .scalar_one()
            == HEAD
        )
        sessions = owned.sessions("two_product_connections")
        assert len(sessions) == 2
        assert {row["pid"] for row in sessions} == set(product_pids)
    finally:
        for connection in connections:
            connection.close()
        for engine in engines:
            engine.dispose()
        owned.record({"event": "product_engines_disposed", "count": len(engines)})
    assert owned.sessions("after_product_disposal") == []


def test_migration_failure_rolls_back_and_disposes_without_replacing_exception(
    owned_database: OwnedDatabase,
    monkeypatch: pytest.MonkeyPatch,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    owned = owned_database
    register_sensitive_failure_value(
        SecretStr(owned.target_url.render_as_string(hide_password=False))
    )
    register_sensitive_failure_value(SecretStr(owned.target_url.password or ""))
    run_migrations(owned.target_url.render_as_string(hide_password=False), HEAD)
    failure = RuntimeError("explicit synthetic rollback probe")
    assert owned.sessions("before_failed_migration") == []
    pids = trace_owned_engine(monkeypatch, owned, "failed_migration")

    def failed_migration(context: MigrationContext, **arguments: object) -> None:
        assert context.bind is not None
        context.bind.exec_driver_sql("CREATE TABLE r01_rollback_probe (id integer)")
        owned.record({"event": "rollback_probe_created_inside_transaction"})
        raise failure

    monkeypatch.setattr(MigrationContext, "run_migrations", failed_migration)
    with pytest.raises(RuntimeError) as caught:
        run_migrations(owned.target_url.render_as_string(hide_password=False), "head")
    assert caught.value is failure
    assert len(pids) == 1
    assert owned.sessions("after_failed_migration") == []
    verification_engine = create_engine(owned.target_url, poolclass=NullPool, hide_parameters=True)
    owned.engines.append(verification_engine)
    try:
        with verification_engine.connect() as connection:
            record_connection(connection, "rollback_verification", record=owned.record)
            assert (
                connection.execute(text("SELECT to_regclass('r01_rollback_probe')")).scalar_one()
                is None
            )
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == HEAD
            )
    finally:
        verification_engine.dispose()
    owned.record({"event": "rollback_verified", "original_exception_preserved": True})
