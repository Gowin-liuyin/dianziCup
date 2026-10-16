"""Real forward DDL, preserved 0022 history and integrity in a marker-owned test database."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import TypedDict
from uuid import uuid4

import pytest
from psycopg import Error as PsycopgError
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, Connection, Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool
from tests.r12_hybrid_fixtures import seed_fact
from tests.security import test_r11_r08_forward_migration_boundaries as previous_aggregate_security

from ai_intel.assets.aggregate_observations import total_result
from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.assets.aggregate_repository import AggregateServerPolicy, PostgresAggregateRepository

pytestmark = pytest.mark.real_pg
ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_forward_migrations_0023_0026_20261016"
HEAD = "0026_api_key_credentials"
NOW = datetime(2026, 10, 16, 2, 0, tzinfo=UTC)
MARKER = "recovery_forward_migrations_0023_0026_20261016:"
RAW_BYTES = b"Explicit synthetic retained raw bytes for migration 0022 to 0026.\r\n"
PWSH = (
    "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/"
    "dependencies/native/powershell/pwsh.exe"
)
NEW_TABLES = (
    "qa_conversations",
    "qa_conversation_turns",
    "graph_projection_batches",
    "graph_projection_state",
    "api_keys",
    "api_key_rate_buckets",
)


@dataclass(frozen=True)
class OwnedDatabase:
    engine: Engine
    url: URL
    database: str
    schema: str
    marker: str
    event_id: str
    old_tables: tuple[str, ...]
    old_rows: dict[str, list[str]]
    old_columns: dict[str, tuple[str, ...]]


class ReflectedShape(TypedDict):
    columns: list[dict[str, object]]
    primary_key: dict[str, object]
    unique: list[dict[str, object]]
    foreign_keys: list[dict[str, object]]
    checks: list[dict[str, object]]
    indexes: list[dict[str, object]]


def controlled_test_url() -> URL:
    result = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-Command",
            "$forwardProtected=Get-Content -LiteralPath "
            "'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
            "$forwardClear=$forwardProtected | ConvertTo-SecureString | "
            "ConvertFrom-SecureString -AsPlainText; [Console]::Write($forwardClear)",
        ],
        capture_output=True,
        timeout=15,
        check=True,
    )
    secret_key = SecretStr(json.loads(result.stdout)["TEST_DATABASE_URL"])
    url = make_url(secret_key.get_secret_value())
    if (
        url.get_backend_name() != "postgresql"
        or url.host != "127.0.0.1"
        or url.port != 25432
        or not url.database
        or not url.database.startswith("test_")
    ):
        raise RuntimeError("controlled test runtime identity rejected")
    return url.set(drivername="postgresql+psycopg")


def owned_engine(url: URL, schema: str) -> Engine:
    if not re.fullmatch(r"test_forward26_[a-f0-9]{12}(?:_rollback)?", schema):
        raise RuntimeError("owned test schema identity rejected")
    return create_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": f"-c search_path={schema},public "
            "-c statement_timeout=20000 -c lock_timeout=5000",
        },
    )


def upgrade(url: URL, schema: str, revision: str, label: str, *, fails: bool = False) -> None:
    """The child receives its DSN on stdin and exits to close every migration session."""
    configured = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=20000 -c lock_timeout=5000"}
    )
    token = SecretStr(configured.render_as_string(hide_password=False))
    password = SecretStr(url.password or "")
    argv = [
        sys.executable,
        "-c",
        "import sys\nfrom sqlalchemy import MetaData\n"
        "from ai_intel.infrastructure.database import run_migrations\n"
        "def forbidden_create_all(*arguments, **keywords):\n"
        "    raise AssertionError('production migrations cannot use business create_all')\n"
        "MetaData.create_all = forbidden_create_all\n"
        "print('business_create_all_guard_installed')\n"
        "run_migrations(sys.stdin.read(), sys.argv[1])\n",
        revision,
    ]
    started = datetime.now().astimezone().isoformat()
    result = subprocess.run(
        argv,
        input=token.get_secret_value(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        cwd=ROOT / "backend",
    )
    raw = result.stdout + result.stderr
    for value in (token.get_secret_value(), password.get_secret_value()):
        if value and value in raw:
            raise RuntimeError("migration subprocess emitted a registered credential")
    (RUN / f"{label}.log").write_text(raw, encoding="utf-8", newline="\n")
    (RUN / f"{label}.json").write_text(
        json.dumps(
            {
                "argv": argv,
                "cwd": str(ROOT / "backend"),
                "started_at": started,
                "ended_at": datetime.now().astimezone().isoformat(),
                "exit_code": result.returncode,
                "database": url.database,
                "schema": schema,
                "target_revision": revision,
                "expected_failure": fails,
                "credential_transport": "DPAPI current user; DSN only in Python memory/stdin",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    assert (result.returncode != 0) == fails, raw[-4000:]


def schema_rows(
    engine: Engine, schema: str, columns: dict[str, tuple[str, ...]]
) -> dict[str, list[str]]:
    with engine.connect() as connection:
        return {
            table: sorted(
                connection.scalars(
                    text(
                        "SELECT row_to_json(saved)::text FROM (SELECT "
                        + ",".join(f'"{column}"' for column in names)
                        + f' FROM "{schema}"."{table}") saved'
                    )
                )
            )
            for table, names in columns.items()
        }


def seed_0022_history(engine: Engine) -> str:
    fact = seed_fact(engine, RAW_BYTES.decode("ascii"))
    with engine.begin() as connection:
        for owner, tenant in (("old-owner-a", "tenant-a"), ("old-owner-b", "tenant-b")):
            connection.execute(
                text(
                    "INSERT INTO users(user_id,username,password_hash,tenant_id,role,created_at) "
                    "VALUES(:owner,:owner,'explicit-synthetic-hash',:tenant,'analyst',:now)"
                ),
                {"owner": owner, "tenant": tenant, "now": NOW},
            )
        connection.execute(
            text(
                "INSERT INTO auth_sessions(session_hash,user_id,csrf_token,issued_at,expires_at) "
                "VALUES(:digest,'old-owner-a','explicit-synthetic-csrf',:now,:expiry)"
            ),
            {"digest": "a" * 64, "now": NOW, "expiry": NOW + timedelta(days=1)},
        )
        connection.execute(
            text(
                "INSERT INTO grounded_answers(answer_id,user_id,tenant_id,question_text,response,"
                "scope_epochs,model_trace,created_at) VALUES('old-answer','old-owner-a','tenant-a',"
                "'retained question','{\"status\":\"pending\"}','{}','{}',:now)"
            ),
            {"now": NOW},
        )
        for job_id in ("old-parent-job", "old-atlas-job"):
            connection.execute(
                text(
                    "INSERT INTO job_runs(job_id,tenant_id,job_type,status,payload_sha256,"
                    "payload_ref,created_at,updated_at) VALUES(:job,'tenant-a','synthetic',"
                    "'succeeded',:digest,'pg:synthetic',:now,:now)"
                ),
                {"job": job_id, "digest": "b" * 64, "now": NOW},
            )
        connection.execute(
            text(
                "INSERT INTO enrichment_workflows(workflow_id,parent_job_id,actor_user_id,"
                "actor_session_hash,actor_tenant_id,actor_role,event_id,visibility,tenant_id,"
                "request_payload,request_sha256,rule_version,execution_policy,"
                "execution_policy_sha256,input_context,input_fingerprint,initialized_at,"
                "created_at) "
                "VALUES('old-workflow','old-parent-job','old-owner-a',:digest,'tenant-a','analyst',"
                ":event,'public',NULL,'{}',:digest,'synthetic-rule',:policy,:digest,'{}',:digest,"
                ":now,:now)"
            ),
            {
                "digest": "c" * 64,
                "event": fact["event_id"],
                "policy": '{"model_input_versions":{"prompt_version":"p1","schema_version":"s1"}}',
                "now": NOW,
            },
        )
        connection.execute(
            text(
                "INSERT INTO enrichment_job_steps(job_id,workflow_id,step_key,dimension,"
                "output_token_budget,created_at) "
                "VALUES('old-atlas-job','old-workflow','atlas','atlas',1024,:now)"
            ),
            {"now": NOW},
        )
    return fact["event_id"]


@pytest.fixture(scope="module")
def database() -> Iterator[OwnedDatabase]:
    original = controlled_test_url()
    admin = create_engine(original, poolclass=NullPool, hide_parameters=True)
    database_name = "test_forward26_" + uuid4().hex[:12]
    marker = MARKER + database_name
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        assert connection.scalar(text("SELECT current_database()")) == original.database
        assert connection.scalar(text("SELECT current_user")) == original.username
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        connection.execute(text(f"COMMENT ON DATABASE \"{database_name}\" IS '{marker}'"))
    url = original.set(database=database_name)
    engine = owned_engine(url, database_name)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == database_name
            assert connection.scalar(text("SELECT current_user")) == original.username
            connection.execute(text(f'CREATE SCHEMA "{database_name}"'))
            connection.execute(text(f"COMMENT ON SCHEMA \"{database_name}\" IS '{marker}'"))
        (RUN / "owned_database.json").write_text(
            json.dumps(
                {
                    "database": database_name,
                    "schema": database_name,
                    "marker": marker,
                    "created_at": datetime.now().astimezone().isoformat(),
                    "setup": "real Alembic",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        upgrade(url, database_name, "0022_sbom_sidecars", "upgrade_0022")
        event_id = seed_0022_history(engine)
        inspector = inspect(engine)
        old_tables = tuple(
            sorted(set(inspector.get_table_names(schema=database_name)) - {"alembic_version"})
        )
        old_columns = {
            table: tuple(
                column["name"] for column in inspector.get_columns(table, schema=database_name)
            )
            for table in old_tables
        }
        old_rows = schema_rows(engine, database_name, old_columns)
        (RUN / "history_0022_before.json").write_text(
            json.dumps(old_rows, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (RUN / "raw_content.bin").write_bytes(RAW_BYTES)
        for revision in (
            "0023_enrichment_input_audit",
            "0024_conversation_context",
            "0025_graph_projection",
            HEAD,
        ):
            upgrade(url, database_name, revision, "upgrade_" + revision[:4])
            after = schema_rows(engine, database_name, old_columns)
            assert after == old_rows
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(f'SELECT version_num FROM "{database_name}".alembic_version')
                    )
                    == revision
                )
                assert (
                    connection.scalar(
                        text("SELECT to_regclass(:identity)"),
                        {"identity": database_name + ".enrichment_job_steps"},
                    )
                    is not None
                )
            (RUN / ("history_" + revision[:4] + "_after.json")).write_text(
                json.dumps(after, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
        yield OwnedDatabase(
            engine,
            url,
            database_name,
            database_name,
            marker,
            event_id,
            old_tables,
            old_rows,
            old_columns,
        )
    finally:
        engine.dispose()
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            actual_marker = connection.scalar(
                text(
                    "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=:db"
                ),
                {"db": database_name},
            )
            assert actual_marker == marker
            sessions = connection.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname=:db"),
                {"db": database_name},
            )
            assert sessions == 0
            connection.execute(text(f'DROP DATABASE "{database_name}"'))
            remaining = connection.scalar(
                text("SELECT count(*) FROM pg_database WHERE datname=:db"), {"db": database_name}
            )
            assert remaining == 0
            (RUN / "cleanup.json").write_text(
                json.dumps(
                    {
                        "database": database_name,
                        "marker_validated": True,
                        "sessions_before_drop": sessions,
                        "databases_after_drop": remaining,
                        "schema_markers_after_drop": 0,
                        "ended_at": datetime.now().astimezone().isoformat(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
        admin.dispose()


@pytest.fixture(autouse=True)
def register_credentials(
    database: OwnedDatabase,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    register_sensitive_failure_value(SecretStr(database.url.render_as_string(hide_password=False)))
    register_sensitive_failure_value(SecretStr(database.url.password or ""))


def postgres_error_code(failure: IntegrityError) -> str:
    assert isinstance(failure.orig, PsycopgError)
    assert failure.orig.sqlstate is not None
    return failure.orig.sqlstate


def expect_rejection(engine: Engine, sql: str, parameters: Mapping[str, object], code: str) -> None:
    with pytest.raises(IntegrityError) as failure, engine.begin() as connection:
        connection.execute(text(sql), parameters)
    assert postgres_error_code(failure.value) == code


def insert_answer(
    connection: Connection, owner: str = "old-owner-a", tenant: str = "tenant-a"
) -> str:
    answer_id = str(uuid4())
    connection.execute(
        text(
            "INSERT INTO grounded_answers VALUES(:answer,:owner,:tenant,'synthetic question',"
            "'{}','{}','{}',:now)"
        ),
        {"answer": answer_id, "owner": owner, "tenant": tenant, "now": NOW},
    )
    return answer_id


def insert_conversation(
    connection: Connection, owner: str = "old-owner-a", tenant: str = "tenant-a"
) -> str:
    conversation_id = str(uuid4())
    connection.execute(
        text(
            "INSERT INTO qa_conversations VALUES(:conversation,1,:owner,:tenant,'active',0,NULL,"
            ":now,:now,NULL)"
        ),
        {"conversation": conversation_id, "owner": owner, "tenant": tenant, "now": NOW},
    )
    return conversation_id


def insert_turn(
    connection: Connection,
    conversation_id: str,
    answer_id: str,
    owner: str = "old-owner-a",
    tenant: str = "tenant-a",
    number: int = 1,
) -> str:
    turn_id = str(uuid4())
    connection.execute(
        text(
            "INSERT INTO qa_conversation_turns VALUES(:turn,1,:conversation,:owner,:tenant,"
            ":number,0,"
            ":answer,:digest,'{}',:now)"
        ),
        {
            "turn": turn_id,
            "conversation": conversation_id,
            "answer": answer_id,
            "owner": owner,
            "tenant": tenant,
            "number": number,
            "digest": "d" * 64,
            "now": NOW,
        },
    )
    return turn_id


def audit_payload(label: str = "synthetic") -> str:
    return json.dumps(
        {
            "audit_version": "r07-input-audit-1",
            "job_id": "old-atlas-job",
            "workflow_id": "old-workflow",
            "dimension": "atlas",
            "input_fingerprint": "c" * 64,
            "execution_policy_sha256": "c" * 64,
            "model_version": "fixture-model",
            "provider": "fixture-provider",
            "model_input_versions": {"prompt_version": "p1", "schema_version": "s1"},
            "input_selections": [{"label": label}],
        }
    )


AUDIT_UPDATE = (
    "UPDATE enrichment_job_steps SET input_audit_payload=CAST(:payload AS jsonb),"
    "input_audit_sha256=encode(sha256(convert_to(CAST(:payload AS jsonb)::text,'UTF8')),'hex'),"
    "model_call_reserved_at=:now,model_call_completed_at=:now,model_trace=:trace "
    "WHERE job_id='old-atlas-job'"
)
MODEL_TRACE = (
    '[{"requested_model":"fixture-model","provider":"fixture-provider",'
    '"prompt_version":"p1","schema_version":"s1"}]'
)


def test_every_0022_history_row_and_raw_hash_survives_each_forward_revision(
    database: OwnedDatabase,
) -> None:
    assert len(database.old_tables) >= 40
    for table in (
        "claims",
        "document_revisions",
        "evidence",
        "job_runs",
        "grounded_answers",
        "enrichment_workflows",
        "enrichment_job_steps",
        "auth_sessions",
    ):
        assert database.old_rows[table]
    for revision in ("0023", "0024", "0025", "0026"):
        assert json.loads((RUN / f"history_{revision}_after.json").read_text()) == database.old_rows
    raw = (RUN / "raw_content.bin").read_bytes()
    assert raw == RAW_BYTES
    with database.engine.connect() as connection:
        stored = connection.execute(
            text("SELECT content_hash,size_bytes FROM content_objects WHERE content_hash=:digest"),
            {"digest": hashlib.sha256(raw).hexdigest()},
        ).one()
    assert stored == (hashlib.sha256(raw).hexdigest(), len(raw))


def reflected_shape(engine: Engine, table: str, schema: str) -> ReflectedShape:
    inspector = inspect(engine)
    foreign_keys = [dict(row) for row in inspector.get_foreign_keys(table, schema=schema)]
    for foreign_key in foreign_keys:
        assert foreign_key.pop("referred_schema") in {schema, None}
    return {
        "columns": [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column["nullable"],
                "default": column["default"],
            }
            for column in inspector.get_columns(table, schema=schema)
        ],
        "primary_key": dict(inspector.get_pk_constraint(table, schema=schema)),
        "unique": sorted(
            [dict(row) for row in inspector.get_unique_constraints(table, schema=schema)],
            key=lambda row: str(row["name"] or ""),
        ),
        "foreign_keys": sorted(foreign_keys, key=lambda row: str(row["name"] or "")),
        "checks": sorted(
            [dict(row) for row in inspector.get_check_constraints(table, schema=schema)],
            key=lambda row: str(row["name"] or ""),
        ),
        "indexes": sorted(
            [dict(row) for row in inspector.get_indexes(table, schema=schema)],
            key=lambda row: str(row["name"] or ""),
        ),
    }


@pytest.fixture(scope="module")
def reference_schema(database: OwnedDatabase) -> str:
    schema = database.schema + "_reference"
    with database.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{database.marker}:reference'"))
        connection.execute(text(f'SET LOCAL search_path="{schema}"'))
        connection.execute(text("CREATE TABLE users(user_id TEXT PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE grounded_answers(answer_id TEXT PRIMARY KEY)"))
        for label in ("r12", "r10", "r18"):
            for statement in (RUN / f"{label}_metadata.sql").read_text().strip().split(";\n\n"):
                connection.execute(text(statement))
    return schema


@pytest.mark.parametrize("table", NEW_TABLES)
def test_columns_keys_indexes_checks_and_fk_target_columns_match_frozen_metadata(
    database: OwnedDatabase,
    reference_schema: str,
    table: str,
) -> None:
    actual = reflected_shape(database.engine, table, database.schema)
    expected = reflected_shape(database.engine, table, reference_schema)
    if table == "graph_projection_batches":
        extra = [
            row for row in actual["checks"] if row["name"] == "ck_graph_projection_payload_sha256"
        ]
        assert len(extra) == 1 and "sha256(payload)" in str(extra[0]["sqltext"])
        actual["checks"] = [row for row in actual["checks"] if row not in extra]
    assert actual == expected
    (RUN / f"reflection_{table}.json").write_text(
        json.dumps({"migration": actual, "frozen_metadata": expected}, indent=2, default=str)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_new_audit_columns_are_nullable_and_legacy_steps_remain_usable(
    database: OwnedDatabase,
) -> None:
    columns = {
        column["name"]: column
        for column in inspect(database.engine).get_columns(
            "enrichment_job_steps", schema=database.schema
        )
    }
    for name, expected_type in (("input_audit_payload", "JSONB"), ("input_audit_sha256", "TEXT")):
        assert str(columns[name]["type"]) == expected_type
        assert columns[name]["nullable"] is True and columns[name]["default"] is None
    with database.engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT input_audit_payload,input_audit_sha256 FROM enrichment_job_steps "
                "WHERE job_id='old-atlas-job'"
            )
        ).one()
        assert row == (None, None)
        connection.execute(
            text(
                "UPDATE enrichment_job_steps SET result_payload='{}',result_sha256=:digest,"
                "result_recorded_at=:now WHERE job_id='old-atlas-job'"
            ),
            {"digest": "e" * 64, "now": NOW},
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_fingerprint", "f" * 64),
        ("audit_version", "invented"),
        ("model_version", "wrong-model"),
        ("dimension", "cvss"),
        ("input_selections", []),
        ("execution_policy_sha256", None),
        ("model_input_versions", {"prompt_version": "wrong"}),
    ],
)
def test_input_audit_wrong_identity_and_missing_fields_are_rejected(
    database: OwnedDatabase,
    field: str,
    value: object,
) -> None:
    payload = json.loads(audit_payload())
    if value is None:
        del payload[field]
    else:
        payload[field] = value
    expect_rejection(
        database.engine,
        AUDIT_UPDATE,
        {"payload": json.dumps(payload), "now": NOW, "trace": MODEL_TRACE},
        "23514",
    )


def test_input_audit_null_partial_and_wrong_digest_are_rejected(database: OwnedDatabase) -> None:
    for sql, parameters in (
        (
            "UPDATE enrichment_job_steps SET input_audit_sha256=:digest "
            "WHERE job_id='old-atlas-job'",
            {"digest": "f" * 64},
        ),
        (
            "UPDATE enrichment_job_steps SET input_audit_payload=CAST(:payload AS jsonb),"
            "input_audit_sha256=:digest,model_call_reserved_at=:now,model_call_completed_at=:now,"
            "model_trace=:trace WHERE job_id='old-atlas-job'",
            {"payload": audit_payload(), "digest": "f" * 64, "now": NOW, "trace": MODEL_TRACE},
        ),
    ):
        expect_rejection(database.engine, sql, parameters, "23514")


def concurrent_codes(
    engine: Engine, statements: tuple[tuple[str, Mapping[str, object]], ...]
) -> list[str]:
    barrier = Barrier(len(statements))

    def execute(statement: tuple[str, Mapping[str, object]]) -> str:
        try:
            with engine.begin() as connection:
                barrier.wait(timeout=10)
                connection.execute(text(statement[0]), statement[1])
            return "committed"
        except IntegrityError as failure:
            return postgres_error_code(failure)

    with ThreadPoolExecutor(max_workers=len(statements)) as executor:
        return sorted(executor.map(execute, statements))


def test_concurrent_input_receipts_commit_once_and_freeze_model_trace(
    database: OwnedDatabase,
) -> None:
    statements = tuple(
        (AUDIT_UPDATE, {"payload": audit_payload(label), "now": NOW, "trace": MODEL_TRACE})
        for label in ("first", "second")
    )
    assert concurrent_codes(database.engine, statements) == ["23514", "committed"]
    for sql in (
        "UPDATE enrichment_job_steps SET input_audit_payload=NULL,input_audit_sha256=NULL "
        "WHERE job_id='old-atlas-job'",
        "UPDATE enrichment_job_steps SET model_trace='[]' WHERE job_id='old-atlas-job'",
        "DELETE FROM enrichment_job_steps WHERE job_id='old-atlas-job'",
    ):
        expect_rejection(database.engine, sql, {}, "23514")
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE enrichment_job_steps SET result_payload='{}',result_sha256=:digest,"
                "result_recorded_at=:now WHERE job_id='old-atlas-job'"
            ),
            {"digest": "e" * 64, "now": NOW},
        )


def test_unfrozen_steps_can_still_be_deleted(database: OwnedDatabase) -> None:
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO job_runs(job_id,job_type,status,payload_ref,created_at,updated_at) "
                "VALUES('unfrozen-delete','synthetic','queued','pg:synthetic',:now,:now)"
            ),
            {"now": NOW},
        )
        connection.execute(
            text(
                "INSERT INTO enrichment_job_steps(job_id,workflow_id,step_key,dimension,"
                "output_token_budget,created_at) "
                "VALUES('unfrozen-delete','old-workflow','literature','literature',1024,:now)"
            ),
            {"now": NOW},
        )
        assert (
            connection.execute(
                text("DELETE FROM enrichment_job_steps WHERE job_id='unfrozen-delete'")
            ).rowcount
            == 1
        )


def test_turn_owner_and_tenant_mismatch_reject_at_deferred_commit(database: OwnedDatabase) -> None:
    for owner, tenant in (("old-owner-b", "tenant-a"), ("old-owner-a", "tenant-b")):
        with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
            conversation_id = insert_conversation(connection)
            answer_id = insert_answer(connection)
            insert_turn(connection, conversation_id, answer_id, owner, tenant)
        assert postgres_error_code(failure.value) == "23514"


def test_active_turn_fk_and_original_grounded_answer_fk_are_not_guessed(
    database: OwnedDatabase,
) -> None:
    with database.engine.begin() as connection:
        first = insert_conversation(connection)
        second = insert_conversation(connection)
        answer_id = insert_answer(connection)
        turn = insert_turn(connection, first, answer_id)
        connection.execute(
            text(
                "UPDATE qa_conversations SET active_turn_id=:turn,version=1 "
                "WHERE conversation_id=:id"
            ),
            {"turn": turn, "id": first},
        )
    expect_rejection(
        database.engine,
        "UPDATE qa_conversations SET active_turn_id=:turn WHERE conversation_id=:id",
        {"turn": turn, "id": second},
        "23503",
    )
    with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
        insert_turn(connection, second, "missing-answer")
    assert postgres_error_code(failure.value) == "23503"


def test_turn_history_freezes_full_row_but_conversation_and_answer_lifecycle_work(
    database: OwnedDatabase,
) -> None:
    with database.engine.begin() as connection:
        conversation_id = insert_conversation(connection)
        answer_id = insert_answer(connection)
        turn_id = insert_turn(connection, conversation_id, answer_id)
        connection.execute(
            text(
                "UPDATE qa_conversations SET active_turn_id=:turn,version=1 "
                "WHERE conversation_id=:id"
            ),
            {"turn": turn_id, "id": conversation_id},
        )
        connection.execute(
            text(
                'UPDATE grounded_answers SET response=\'{"status":"terminal"}\' '
                "WHERE answer_id=:answer"
            ),
            {"answer": answer_id},
        )
        connection.execute(
            text(
                "UPDATE qa_conversations SET status='revoked',revoked_at=:now,updated_at=:now,"
                "version=2 WHERE conversation_id=:id"
            ),
            {"now": NOW, "id": conversation_id},
        )
    statements = tuple(
        (sql, {"turn": turn_id, "context": '{"tampered":true}'})
        for sql in (
            "UPDATE qa_conversation_turns SET resolved_context=CAST(:context AS jsonb) "
            "WHERE turn_id=:turn",
            "DELETE FROM qa_conversation_turns WHERE turn_id=:turn",
        )
    )
    assert concurrent_codes(database.engine, statements) == ["23514", "23514"]
    expect_rejection(
        database.engine,
        "UPDATE grounded_answers SET tenant_id='tenant-b' WHERE answer_id=:answer",
        {"answer": answer_id},
        "23514",
    )
    expect_rejection(
        database.engine,
        "UPDATE qa_conversations SET user_id='old-owner-b' WHERE conversation_id=:id",
        {"id": conversation_id},
        "23514",
    )


def test_turn_numbers_and_answer_identity_are_unique(database: OwnedDatabase) -> None:
    with database.engine.begin() as connection:
        conversation_id = insert_conversation(connection)
        answer = insert_answer(connection)
        insert_turn(connection, conversation_id, answer)
        second_answer = insert_answer(connection)
    for duplicate_answer, number in ((second_answer, 1), (answer, 2)):
        with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
            insert_turn(connection, conversation_id, duplicate_answer, number=number)
        assert postgres_error_code(failure.value) == "23505"


def test_turn_checks_reject_unknown_version_zero_number_and_bad_context(
    database: OwnedDatabase,
) -> None:
    with database.engine.begin() as connection:
        conversation_id = insert_conversation(connection)
        answer_id = insert_answer(connection)
    for version, number, digest, context in (
        (2, 1, "d" * 64, "{}"),
        (1, 0, "d" * 64, "{}"),
        (1, 1, "bad", "{}"),
        (1, 1, "d" * 64, "[]"),
    ):
        expect_rejection(
            database.engine,
            "INSERT INTO qa_conversation_turns VALUES(:turn,:version,:id,'old-owner-a',"
            "'tenant-a',:number,0,:answer,:digest,CAST(:context AS jsonb),:now)",
            {
                "turn": str(uuid4()),
                "version": version,
                "id": conversation_id,
                "number": number,
                "answer": answer_id,
                "digest": digest,
                "context": context,
                "now": NOW,
            },
            "23514",
        )


BATCH_INSERT = (
    "INSERT INTO graph_projection_batches VALUES(:batch,'synthetic-namespace','public',"
    "'synthetic-generation',:event,:sequence,:kind,:digest,:payload,:now)"
)


def batch_parameters(database: OwnedDatabase) -> dict[str, object]:
    return {
        "batch": str(uuid4()),
        "event": database.event_id,
        "sequence": 1,
        "kind": "snapshot",
        "digest": hashlib.sha256(b"synthetic batch").hexdigest(),
        "payload": b"synthetic batch",
        "now": NOW,
    }


def test_batch_hash_and_identity_constraints_and_full_immutability(database: OwnedDatabase) -> None:
    parameters = batch_parameters(database)
    with database.engine.begin() as connection:
        connection.execute(text(BATCH_INSERT), parameters)
    duplicate = {**parameters, "batch": str(uuid4())}
    expect_rejection(database.engine, BATCH_INSERT, duplicate, "23505")
    for field, value in (
        ("sequence", 0),
        ("kind", "invented"),
        ("digest", "f" * 64),
        ("payload", b"altered bytes"),
    ):
        rejected = {**parameters, "batch": str(uuid4()), "sequence": 2, field: value}
        expect_rejection(database.engine, BATCH_INSERT, rejected, "23514")
    statements = tuple(
        (sql, {"batch": parameters["batch"]})
        for sql in (
            "UPDATE graph_projection_batches SET captured_at=captured_at WHERE batch_id=:batch",
            "DELETE FROM graph_projection_batches WHERE batch_id=:batch",
        )
    )
    assert concurrent_codes(database.engine, statements) == ["23514", "23514"]


def test_batch_size_limit_and_state_checks_allow_real_mutable_watermarks(
    database: OwnedDatabase,
) -> None:
    oversized = b"x" * (8388608 + 1)
    parameters = {
        **batch_parameters(database),
        "payload": oversized,
        "digest": hashlib.sha256(oversized).hexdigest(),
        "sequence": 3,
    }
    expect_rejection(database.engine, BATCH_INSERT, parameters, "23514")
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO graph_projection_state VALUES('n','public','g','partition',"
                "'partition',"
                "NULL,'{}',:now,:now)"
            ),
            {"now": NOW},
        )
        connection.execute(
            text(
                "UPDATE graph_projection_state SET body=CAST(:body AS jsonb),updated_at=:now "
                "WHERE namespace='n'"
            ),
            {"now": NOW + timedelta(minutes=1), "body": '{"watermark":1}'},
        )
    for kind, event_id in (("invented", None), ("slot", None), ("page", "unexpected")):
        expect_rejection(
            database.engine,
            "INSERT INTO graph_projection_state VALUES('n','public','g',:key,"
            ":kind,:event,'{}',:now,:now)",
            {"key": str(uuid4()), "kind": kind, "event": event_id, "now": NOW},
            "23514",
        )


KEY_INSERT = (
    "INSERT INTO api_keys VALUES(:key,:digest,:owner,:resource,:scopes,:issued,:expires,"
    "NULL,:version)"
)


def key_parameters() -> dict[str, object]:
    key_id = str(uuid4())
    return {
        "key": key_id,
        "digest": hashlib.sha256(key_id.encode()).hexdigest(),
        "owner": "old-owner-a",
        "resource": "urn:dianzi:api:v1",
        "scopes": ["read:public"],
        "issued": NOW,
        "expires": NOW + timedelta(days=30),
        "version": 1,
    }


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("owner", "missing-owner", "23503"),
        ("digest", "bad-hash", "23514"),
        ("resource", "wrong-resource", "23514"),
        ("scopes", [], "23514"),
        ("scopes", ["write:any"], "23514"),
        ("scopes", ["read:public", "read:asset"], "23514"),
        ("scopes", ["read:public", "read:public"], "23514"),
        ("version", 0, "23514"),
        ("expires", NOW, "23514"),
        ("expires", NOW + timedelta(hours=2160, seconds=1), "23514"),
    ],
)
def test_api_key_owner_scopes_hash_resource_version_and_expiry_constraints(
    database: OwnedDatabase,
    field: str,
    value: object,
    code: str,
) -> None:
    expect_rejection(database.engine, KEY_INSERT, {**key_parameters(), field: value}, code)


def test_key_scope_positive_cases_unique_hash_and_revocation_time(database: OwnedDatabase) -> None:
    for scopes in (["read:public"], ["read:asset"], ["read:asset", "read:public"]):
        parameters = {**key_parameters(), "scopes": scopes}
        with database.engine.begin() as connection:
            connection.execute(text(KEY_INSERT), parameters)
        expect_rejection(database.engine, KEY_INSERT, {**parameters, "key": str(uuid4())}, "23505")
        expect_rejection(
            database.engine,
            "UPDATE api_keys SET revoked_at=:revoked WHERE key_id=:key",
            {"revoked": NOW - timedelta(seconds=1), "key": parameters["key"]},
            "23514",
        )


def test_expiry_limit_remains_2160_hours_across_dst(database: OwnedDatabase) -> None:
    issued = datetime(2026, 1, 1, tzinfo=UTC)
    with database.engine.begin() as connection:
        connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
        connection.execute(
            text(KEY_INSERT),
            {**key_parameters(), "issued": issued, "expires": issued + timedelta(hours=2160)},
        )
    expect_rejection(
        database.engine,
        KEY_INSERT,
        {
            **key_parameters(),
            "issued": issued,
            "expires": issued + timedelta(hours=2160, seconds=1),
        },
        "23514",
    )


def test_rate_bucket_fk_minute_operation_and_count_constraints(database: OwnedDatabase) -> None:
    parameters = key_parameters()
    with database.engine.begin() as connection:
        connection.execute(text(KEY_INSERT), parameters)
    for key, operation, window, count, code in (
        ("missing", "read", NOW, 0, "23503"),
        (parameters["key"], "write", NOW, 0, "23514"),
        (parameters["key"], "read", NOW + timedelta(seconds=1), 0, "23514"),
        (parameters["key"], "read", NOW, -1, "23514"),
        (parameters["key"], "read", NOW, 61, "23514"),
        (parameters["key"], "ask", NOW, 11, "23514"),
    ):
        expect_rejection(
            database.engine,
            "INSERT INTO api_key_rate_buckets VALUES(:key,:operation,:window,:count)",
            {"key": key, "operation": operation, "window": window, "count": count},
            code,
        )


def test_concurrent_rate_last_slot_and_failed_transaction_rollback(database: OwnedDatabase) -> None:
    parameters = key_parameters()
    with database.engine.begin() as connection:
        connection.execute(text(KEY_INSERT), parameters)
        connection.execute(
            text("INSERT INTO api_key_rate_buckets VALUES(:key,'read',:window,59)"),
            {"key": parameters["key"], "window": NOW},
        )
    statement = (
        "UPDATE api_key_rate_buckets SET request_count=request_count+1 "
        "WHERE key_id=:key AND operation='read'",
        {"key": parameters["key"]},
    )
    assert concurrent_codes(database.engine, (statement, statement)) == ["23514", "committed"]
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(
            text("UPDATE api_keys SET version=2 WHERE key_id=:key"), {"key": parameters["key"]}
        )
        connection.execute(text(statement[0]), statement[1])
    with database.engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT version FROM api_keys WHERE key_id=:key"), {"key": parameters["key"]}
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT request_count FROM api_key_rate_buckets WHERE key_id=:key"),
                {"key": parameters["key"]},
            )
            == 60
        )


def test_querying_triggers_bind_the_owned_schema_against_shadow_search_path(
    database: OwnedDatabase,
    reference_schema: str,
) -> None:
    with database.engine.connect() as connection:
        functions = connection.execute(
            text(
                "SELECT p.proname,p.proconfig FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname=:schema AND p.proname IN "
                "('qa_validate_turn_ownership','guard_enrichment_input_audit')"
            ),
            {"schema": database.schema},
        ).all()
    assert len(functions) == 2
    for _, configuration in functions:
        assert isinstance(configuration, list)
        assert any(
            isinstance(value, str) and value.startswith("search_path=" + database.schema)
            for value in configuration
        )
    with database.engine.begin() as connection:
        conversation_id = insert_conversation(connection)
        answer_id = insert_answer(connection)
        insert_turn(connection, conversation_id, answer_id)
    with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path="{reference_schema}",public'))
        connection.execute(
            text(
                f"UPDATE \"{database.schema}\".qa_conversations SET user_id='old-owner-b' "
                "WHERE conversation_id=:id"
            ),
            {"id": conversation_id},
        )
    assert postgres_error_code(failure.value) == "23514"


def test_failed_upgrade_0026_rolls_back_0023_0025_and_retries_forward(
    database: OwnedDatabase,
) -> None:
    schema = database.schema + "_rollback"
    rollback = owned_engine(database.url, schema)
    with database.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{database.marker}:rollback'"))
    try:
        upgrade(database.url, schema, "0022_sbom_sidecars", "rollback_upgrade_0022")
        with rollback.begin() as connection:
            connection.execute(text("CREATE TABLE api_keys(marker TEXT PRIMARY KEY)"))
            connection.execute(text("INSERT INTO api_keys VALUES('owned-conflict')"))
        upgrade(database.url, schema, HEAD, "rollback_expected_failure", fails=True)
        with rollback.connect() as connection:
            assert connection.scalar(
                text(f'SELECT version_num FROM "{schema}".alembic_version')
            ) == ("0022_sbom_sidecars")
            assert connection.scalar(text("SELECT marker FROM api_keys")) == "owned-conflict"
            for table in NEW_TABLES[:-2]:
                assert (
                    connection.scalar(
                        text("SELECT to_regclass(:identity)"), {"identity": schema + "." + table}
                    )
                    is None
                )
        columns = inspect(rollback).get_columns("enrichment_job_steps", schema=schema)
        assert "input_audit_payload" not in {column["name"] for column in columns}
        with rollback.begin() as connection:
            connection.execute(text("DROP TABLE api_keys"))
        upgrade(database.url, schema, HEAD, "rollback_retry_forward")
        with rollback.connect() as connection:
            assert (
                connection.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))
                == HEAD
            )
    finally:
        rollback.dispose()


def test_fresh_client_restart_and_idempotent_head_upgrade_preserve_revoked_key_history(
    database: OwnedDatabase,
) -> None:
    parameters = key_parameters()
    with database.engine.begin() as connection:
        connection.execute(text(KEY_INSERT), parameters)
        connection.execute(
            text("UPDATE api_keys SET revoked_at=:now,version=2 WHERE key_id=:key"),
            {"now": NOW, "key": parameters["key"]},
        )
        before = connection.scalar(
            text("SELECT to_jsonb(k)::text FROM api_keys k WHERE key_id=:key"),
            {"key": parameters["key"]},
        )
    database.engine.dispose()
    upgrade(database.url, database.schema, HEAD, "restart_idempotent_upgrade")
    fresh = owned_engine(database.url, database.schema)
    try:
        with fresh.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT to_jsonb(k)::text FROM api_keys k WHERE key_id=:key"),
                    {"key": parameters["key"]},
                )
                == before
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT input_audit_payload IS NOT NULL FROM enrichment_job_steps "
                        "WHERE job_id='old-atlas-job'"
                    )
                )
                is True
            )
    finally:
        fresh.dispose()


def test_production_upgrade_never_creates_tables_through_business_metadata(
    database: OwnedDatabase,
) -> None:
    for revision in ("0022", "0023", "0024", "0025", "0026"):
        assert (
            "business_create_all_guard_installed" in (RUN / f"upgrade_{revision}.log").read_text()
        )
    assert set(NEW_TABLES).issubset(
        inspect(database.engine).get_table_names(schema=database.schema)
    )


def test_input_receipt_requires_a_precreated_step(database: OwnedDatabase) -> None:
    payload = json.loads(audit_payload())
    payload.update(job_id="new-audited-step", dimension="poc")
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO job_runs(job_id,job_type,status,payload_ref,created_at,updated_at) "
                "VALUES('new-audited-step','synthetic','queued','pg:synthetic',:now,:now)"
            ),
            {"now": NOW},
        )
    with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO enrichment_job_steps(job_id,workflow_id,step_key,dimension,"
                "output_token_budget,created_at,input_audit_payload,input_audit_sha256,"
                "model_call_reserved_at,model_call_completed_at,model_trace) "
                "VALUES('new-audited-step','old-workflow','poc','poc',1024,:now,"
                "CAST(:payload AS jsonb),encode(sha256(convert_to("
                "CAST(:payload AS jsonb)::text,'UTF8')),'hex'),:now,:now,:trace)"
            ),
            {"payload": json.dumps(payload), "now": NOW, "trace": MODEL_TRACE},
        )
    assert postgres_error_code(failure.value) == "23514"
    assert isinstance(failure.value.orig, PsycopgError)
    assert "requires a precreated step" in str(failure.value.orig.diag.message_primary)


def test_physical_trigger_timing_schema_and_body_match_frozen_inputs(
    database: OwnedDatabase,
) -> None:
    with database.engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT t.tgname,c.relname,p.proname,t.tgtype,t.tgdeferrable,t.tginitdeferred,"
                "t.tgenabled,p.prosrc FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname=:schema AND p.pronamespace=n.oid AND NOT t.tgisinternal"
            ),
            {"schema": database.schema},
        ).all()
    triggers = {row[0]: tuple(row[1:]) for row in rows}
    expected = (
        (
            "enrichment_input_audit_guard",
            "enrichment_job_steps",
            "guard_enrichment_input_audit",
            23,
        ),
        (
            "enrichment_input_audit_delete_guard",
            "enrichment_job_steps",
            "prevent_enrichment_input_audit_deletion",
            11,
        ),
        ("qa_conversation_turns_immutable", "qa_conversation_turns", "prevent_qa_turn_changes", 27),
        (
            "graph_projection_batches_immutable",
            "graph_projection_batches",
            "prevent_graph_projection_batch_changes",
            27,
        ),
        *(
            (f"qa_owner_{table}", table, "qa_validate_turn_ownership", 21)
            for table in ("qa_conversation_turns", "qa_conversations", "grounded_answers")
        ),
    )
    r12_source = ast.parse((RUN / "r12_frozen.py").read_text(encoding="utf-8"))
    ownership = next(
        ast.literal_eval(node.value)
        for node in r12_source.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "OWNERSHIP_FUNCTION_DDL"
    )
    assert isinstance(ownership, str)
    r07 = (RUN / "r07_frozen.sql").read_text(encoding="utf-8")
    functions = {"guard_enrichment_input_audit": r07, "qa_validate_turn_ownership": ownership}
    guards = json.loads((RUN / "approved_guards.json").read_text(encoding="utf-8"))
    for guard in guards:
        statement = guard["statement"]
        if statement.startswith("CREATE FUNCTION"):
            functions[statement.split()[2].split("(")[0]] = statement
    for name, table, function, kind in expected:
        row = triggers[name]
        deferred = name.startswith("qa_owner_")
        assert row[:6] == (table, function, kind, deferred, deferred, "O")
        assert (
            re.sub(r"\s+", " ", str(row[6])).strip()
            == re.sub(r"\s+", " ", functions[function].split("$$")[1]).strip()
        )


@pytest.fixture()
def migrated_engine(database: OwnedDatabase) -> Engine:
    """Unchanged prior security functions receive the marker-owned production head."""
    return database.engine


@pytest.fixture()
def aggregate_record(database: OwnedDatabase) -> dict[str, object]:
    """Only the prior fixture's obsolete 0019 head guard is adapted to 0026."""
    with database.engine.connect() as connection:
        revision = connection.scalar(
            text(f'SELECT version_num FROM "{database.schema}".alembic_version')
        )
        assert revision == HEAD
    repository = PostgresAggregateRepository(database.engine)
    stored = repository.save_observation(
        total_result("hunter", "ollama", 0, previous_aggregate_security.NOW, "fixture"),
        previous_aggregate_security.SCOPE,
        AggregateServerPolicy("migration-" + uuid4().hex, "fixture", True),
        recorded_at=previous_aggregate_security.NOW,
    )
    with database.engine.connect() as connection:
        return dict(
            connection.execute(
                aggregate_observations.select().where(
                    aggregate_observations.c.observation_id == stored.observation_id
                )
            )
            .mappings()
            .one()
        )


test_previous_aggregate_field_checks = (
    previous_aggregate_security.test_production_checks_reject_invalid_safe_observation
)
test_previous_aggregate_mutation_guard = (
    previous_aggregate_security.test_production_database_rejects_aggregate_mutation
)
