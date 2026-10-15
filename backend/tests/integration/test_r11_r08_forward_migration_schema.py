"""Reflect production migrations and compare all new DDL against the frozen metadata."""

import json
import os
import re
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    MetaData,
    Table,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable

from ai_intel.assets.aggregate_persistence_models import (
    IMMUTABILITY_FUNCTION_DDL,
    aggregate_observations,
)
from ai_intel.assets.inventory_models import (
    ASSET_TABLES,
    CURRENT_SNAPSHOT_REQUIRED_SQL,
    SNAPSHOT_IMMUTABILITY_SQL,
)

pytestmark = pytest.mark.real_pg
TABLES = (*ASSET_TABLES, aggregate_observations)
HEAD = "0019_aggregate_observations"
RUN = Path(__file__).resolve().parents[3] / (
    "reports/runs/recovery_r11_r08_forward_migrations_20261016"
)


@pytest.fixture(scope="module")
def schema_engine():
    engine = create_engine(os.environ["TEST_DATABASE_URL"], hide_parameters=True)
    assert engine.url.database in {
        "test_dianzi_r11_r08_forward_migrations_20261016_empty",
        "test_dianzi_r11_r08_forward_migrations_20261016_fresh2",
    }
    assert engine.url.host in {"localhost", "127.0.0.1"} and engine.url.port == 25432
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == engine.url.database
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def metadata_reference_schema(schema_engine):
    """Reference DDL is test-only in a separate schema after the production upgrade."""
    schema = "migration_reference_" + uuid4().hex[:12]
    reference = MetaData()
    Table("users", reference, Column("user_id", Text, primary_key=True), schema="public")

    def referred_schema(table, target_schema, constraint, original_schema):
        return "public" if constraint.elements[0].column.table.name == "users" else schema

    tables = [
        table.to_metadata(reference, schema=schema, referred_schema_fn=referred_schema)
        for table in TABLES
    ]
    with schema_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        for table in tables:
            connection.execute(CreateTable(table))
        for table in tables:
            for constraint in table.constraints:
                if isinstance(constraint, ForeignKeyConstraint) and constraint.use_alter:
                    connection.execute(AddConstraint(constraint))
            for index in table.indexes:
                connection.execute(CreateIndex(index))
    return schema


def reflected_shape(engine, table_name, schema):
    inspector = inspect(engine)
    columns = [
        {
            "name": column["name"],
            "type": str(column["type"]),
            "nullable": column["nullable"],
            "default": column["default"],
        }
        for column in inspector.get_columns(table_name, schema=schema)
    ]
    foreign_keys = inspector.get_foreign_keys(table_name, schema=schema)
    for foreign_key in foreign_keys:
        foreign_key.pop("referred_schema")

    def sort(rows):
        return sorted(rows, key=lambda item: item["name"])

    return {
        "columns": columns,
        "primary_key": inspector.get_pk_constraint(table_name, schema=schema),
        "unique": sort(inspector.get_unique_constraints(table_name, schema=schema)),
        "foreign_keys": sort(foreign_keys),
        "checks": sort(inspector.get_check_constraints(table_name, schema=schema)),
        "indexes": sort(inspector.get_indexes(table_name, schema=schema)),
    }


@pytest.mark.parametrize("table_name", [table.name for table in TABLES])
def test_every_column_key_check_index_matches_frozen_metadata(
    schema_engine, metadata_reference_schema, table_name
):
    actual = reflected_shape(schema_engine, table_name, "public")
    expected = reflected_shape(schema_engine, table_name, metadata_reference_schema)
    suffix = schema_engine.url.database.rsplit("_", 1)[1]
    (RUN / f"reflection_{table_name}_{suffix}.json").write_text(
        json.dumps({"production": actual, "metadata_reference": expected}, indent=2, default=str),
        encoding="utf-8",
    )
    assert actual == expected
    assert all(
        foreign_key["options"].get("ondelete", "NO ACTION") == "NO ACTION"
        for foreign_key in actual["foreign_keys"]
    )


@pytest.mark.parametrize(
    "name,table,function,kind,deferred,source",
    [
        (
            "asset_snapshots_immutable",
            "asset_snapshots",
            "prevent_asset_snapshot_changes",
            27,
            False,
            SNAPSHOT_IMMUTABILITY_SQL,
        ),
        (
            "asset_current_snapshot_required",
            "assets",
            "require_asset_current_snapshot",
            21,
            True,
            CURRENT_SNAPSHOT_REQUIRED_SQL,
        ),
        (
            "r08_aggregate_observations_immutable",
            "r08_aggregate_observations",
            "r08_reject_aggregate_mutation",
            27,
            False,
            IMMUTABILITY_FUNCTION_DDL,
        ),
    ],
)
def test_exact_trigger_body_and_timing_match_frozen_metadata(
    schema_engine, name, table, function, kind, deferred, source
):
    with schema_engine.connect() as connection:
        triggers = connection.execute(
            text("""
            SELECT c.relname, p.proname, t.tgtype, t.tgdeferrable, t.tginitdeferred,
                   t.tgenabled, p.prosrc
            FROM pg_trigger t JOIN pg_class c ON t.tgrelid=c.oid
            JOIN pg_namespace n ON c.relnamespace=n.oid JOIN pg_proc p ON t.tgfoid=p.oid
            WHERE n.nspname='public' AND NOT t.tgisinternal AND t.tgname=:name
        """),
            {"name": name},
        ).all()
    assert len(triggers) == 1
    table_name, function_name, trigger_kind, deferrable, initially_deferred, enabled, body = (
        triggers[0]
    )
    assert (table_name, function_name, trigger_kind, deferrable, initially_deferred, enabled) == (
        table,
        function,
        kind,
        deferred,
        deferred,
        "O",
    )
    expected_body = source.split("$$")[1]
    assert re.sub(r"\s+", " ", body).strip() == re.sub(r"\s+", " ", expected_body).strip()


def test_upgrade_keeps_all_0016_facts_and_task_history():
    before = json.loads((RUN / "retained_before.json").read_text())
    after = json.loads((RUN / "retained_after.json").read_text())
    assert before == after and len(before) == 37
    assert all(
        before[name]["rows"] == 1
        for name in (
            "sources",
            "documents",
            "document_revisions",
            "evidence",
            "claims",
            "job_runs",
            "job_transitions",
            "job_payloads",
            "source_cursors",
        )
    )


def test_repeated_upgrade_head_is_non_destructive(schema_engine):
    from ai_intel.infrastructure.database import run_migrations

    with schema_engine.connect() as connection:
        before = connection.scalar(text("SELECT count(*) FROM asset_snapshots"))
        aggregates = connection.scalar(text("SELECT count(*) FROM r08_aggregate_observations"))
    run_migrations(schema_engine.url.render_as_string(hide_password=False))
    with schema_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        assert connection.scalar(text("SELECT count(*) FROM asset_snapshots")) == before
        assert (
            connection.scalar(text("SELECT count(*) FROM r08_aggregate_observations")) == aggregates
        )
