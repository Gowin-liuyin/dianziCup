"""Real forward-migrated schema, authoritative references, and unchanged old rows."""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.r12_hybrid_fixtures import seed_fact

from ai_intel.infrastructure.database import run_migrations
from ai_intel.retrieval.hybrid_schema import hybrid_metadata

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def production_engine(isolated_test_database_url: str) -> Iterator[Engine]:
    run_migrations(isolated_test_database_url)
    engine = create_engine(isolated_test_database_url, hide_parameters=True)
    try:
        yield engine
    finally:
        engine.dispose()


def test_all_hybrid_tables_exist_after_normal_forward_upgrade(production_engine: Engine) -> None:
    names = set(inspect(production_engine).get_table_names())
    assert set(hybrid_metadata.tables).issubset(names)


def test_production_columns_match_the_existing_indexer(production_engine: Engine) -> None:
    inspector = inspect(production_engine)
    for name, table in hybrid_metadata.tables.items():
        actual = {column["name"]: column for column in inspector.get_columns(name)}
        assert set(actual) == set(table.columns.keys())
        for column in table.columns:
            assert actual[column.name]["nullable"] == column.nullable
        assert set(inspector.get_pk_constraint(name)["constrained_columns"]) == {
            column.name for column in table.primary_key.columns
        }
    vector_column = next(
        column for column in inspector.get_columns("hybrid_chunks") if column["name"] == "embedding"
    )
    assert vector_column["type"].dim == 384


def test_projection_references_authoritative_pg_rows(production_engine: Engine) -> None:
    inspector = inspect(production_engine)
    references = {
        tuple(item["constrained_columns"]): item["referred_table"]
        for item in inspector.get_foreign_keys("hybrid_chunks")
    }
    for column, table in (
        ("evidence_id", "evidence"),
        ("revision_id", "document_revisions"),
        ("document_id", "documents"),
        ("source_id", "sources"),
        ("event_id", "events"),
        ("claim_id", "claims"),
    ):
        assert references[(column,)] == table
    for table in ("hybrid_index_watermarks", "hybrid_index_receipts"):
        assert any(
            item["constrained_columns"] == ["outbox_id"]
            and item["referred_table"] == "outbox_events"
            for item in inspector.get_foreign_keys(table)
        )


@pytest.mark.parametrize("dimension,state", [(383, "ready"), (384, "invented")])
def test_invalid_generation_cannot_be_persisted(
    production_engine: Engine, dimension: int, state: str
) -> None:
    with pytest.raises(IntegrityError), production_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO hybrid_index_generations VALUES "
                "('invalid-generation','dianzi_test_invalid','synthetic-model',:dimension,:state,:now)"
            ),
            {"dimension": dimension, "state": state, "now": datetime.now(UTC)},
        )


@pytest.mark.parametrize("table", ["hybrid_index_watermarks", "hybrid_index_receipts"])
def test_missing_outbox_cannot_advance_projection(production_engine: Engine, table: str) -> None:
    with production_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO hybrid_index_generations VALUES "
                "('missing-outbox','dianzi_test_missing_outbox',"
                "'synthetic-model',384,'ready',:now) "
                "ON CONFLICT DO NOTHING"
            ),
            {"now": datetime.now(UTC)},
        )
    with pytest.raises(IntegrityError), production_engine.begin() as connection:
        if table == "hybrid_index_watermarks":
            connection.execute(
                text(
                    "INSERT INTO hybrid_index_watermarks VALUES "
                    "('missing-outbox','public',1,'absent',:now)"
                ),
                {"now": datetime.now(UTC)},
            )
        else:
            connection.execute(
                text(
                    "INSERT INTO hybrid_index_receipts VALUES "
                    "('missing-outbox','absent','public',1,0,:digest,:now)"
                ),
                {"digest": "a" * 64, "now": datetime.now(UTC)},
            )


def test_forward_upgrade_preserves_all_0019_rows(
    isolated_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = create_engine(isolated_test_database_url, hide_parameters=True)
    schema = "test_r12_history_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    configured = base.url.update_query_dict({"options": f"-c search_path={schema},public"})
    migration_url = base.url.update_query_dict({"options": f"-c search_path={schema}"})
    engine = create_engine(configured, hide_parameters=True)

    def forbidden_create_all(*arguments, **keywords):
        raise AssertionError("normal forward upgrade must not use create_all")

    monkeypatch.setattr(MetaData, "create_all", forbidden_create_all)
    try:
        run_migrations(
            migration_url.render_as_string(hide_password=False), "0019_aggregate_observations"
        )
        seed_fact(engine, "Synthetic retained history fact for production migration")
        old_tables = sorted(
            set(inspect(engine).get_table_names(schema=schema)) - {"alembic_version"}
        )
        assert not set(hybrid_metadata.tables).intersection(old_tables)

        def rows():
            with engine.connect() as connection:
                return {
                    table: sorted(
                        connection.execute(
                            text(f'SELECT to_jsonb(t)::text FROM "{table}" t')
                        ).scalars()
                    )
                    for table in old_tables
                }

        before = rows()
        assert before["claims"] and before["evidence"] and before["document_revisions"]
        run_migrations(migration_url.render_as_string(hide_password=False))
        assert rows() == before
        assert set(hybrid_metadata.tables).issubset(inspect(engine).get_table_names(schema=schema))
    finally:
        engine.dispose()
        assert schema.startswith("test_r12_history_") and schema.isidentifier()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()
