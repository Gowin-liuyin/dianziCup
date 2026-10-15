"""实际PG空schema/0006旧数据升级；每例专属schema不降级或清理共享数据。"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge import persistence_models
from ai_intel.knowledge.models import document_revisions, fetch_attempts, text_blocks

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def empty_schema_engine(isolated_test_database_url: str) -> Iterator[Engine]:
    base_engine = create_engine(isolated_test_database_url, connect_args={"connect_timeout": 5})
    schema_name = "test_r02_schema_" + uuid4().hex
    with base_engine.begin() as connection:
        actual_database, actual_user = connection.execute(
            text("SELECT current_database(), current_user")
        ).one()
        assert (
            actual_database == base_engine.url.database and actual_user == base_engine.url.username
        )
        connection.execute(CreateSchema(schema_name))
    isolated_url = make_url(isolated_test_database_url).update_query_dict(
        {"options": f"-c search_path={schema_name} -c statement_timeout=10000"}
    )
    isolated_engine = create_engine(isolated_url, connect_args={"connect_timeout": 5})
    try:
        yield isolated_engine
    finally:
        isolated_engine.dispose()
        with base_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True))
        base_engine.dispose()


@pytest.mark.parametrize("previous_revision", [None, "0006_auth_state"])
def test_empty_and_legacy_upgrade_keep_columns_and_old_claims(
    empty_schema_engine: Engine, previous_revision: str | None
) -> None:
    migration_url = empty_schema_engine.url.render_as_string(hide_password=False)
    legacy_claim_id = str(uuid4())
    legacy_time = datetime(2026, 10, 1, 12, 30, tzinfo=UTC)
    if previous_revision:
        run_migrations(migration_url, previous_revision)
        with empty_schema_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO claims (claim_id,subject,predicate,object_value,claim_status,"
                    "claim_origin,condition_value,freshness,asserted_at,visibility,created_at) "
                    "VALUES (:id,'legacy-component','affected_by','legacy text','unverified',"
                    "'source_explicit','unknown','unknown',:time,'public',:time)"
                ),
                {"id": legacy_claim_id, "time": legacy_time},
            )
    run_migrations(migration_url)
    table_names = (
        "claims",
        "claim_evidence",
        "claim_assertions",
        "claim_status_history",
        "claim_relations",
        "entities",
        "entity_aliases",
        "events",
        "event_external_ids",
        "event_documents",
        "event_operations",
        "change_events",
        "publication_receipts",
    )
    inspector = inspect(empty_schema_engine)
    for table_name in table_names:
        mapped_table = getattr(persistence_models, table_name)
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        assert actual_columns == set(mapped_table.c.keys()), table_name
    with empty_schema_engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "0013_revision_source_metadata"
        assert {column["name"] for column in inspector.get_columns("enrichment_results")} == set(
            enrichment_results.c.keys()
        )
        for mapped_table in (document_revisions, text_blocks, fetch_attempts):
            assert {column["name"] for column in inspector.get_columns(mapped_table.name)} == set(
                mapped_table.c.keys()
            )
        if previous_revision:
            old_claim = (
                connection.execute(
                    text("SELECT * FROM claims WHERE claim_id=:id"), {"id": legacy_claim_id}
                )
                .mappings()
                .one()
            )
            assert old_claim["object_value"] == "legacy text"
            assert old_claim["condition_value"] == "unknown"
            assert old_claim["asserted_at"] == legacy_time
            assert old_claim["tenant_id"] is None
            assert old_claim["schema_version"] == 1
            assert old_claim["provenance_status"] == "legacy_unverified"
            assert old_claim["object_json"] is None


def test_0011_page_receipt_history_migrates_without_inventing_request_fingerprint(
    empty_schema_engine: Engine,
) -> None:
    migration_url = empty_schema_engine.url.render_as_string(hide_password=False)
    run_migrations(migration_url, "0011_job_delivery_and_cursors")
    with empty_schema_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,visibility,created_at) "
                "VALUES ('legacy-source','legacy-source','vendor_advisory',"
                "'https://example.invalid','public',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO source_cursors(source_id,stream_kind,updated_at) "
                "VALUES ('legacy-source','live',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO source_page_receipts(source_id,stream_kind,page_key,input_cursor,"
                "output_cursor,revision_ids,failed_job_ids,entry_count,committed_at) "
                "VALUES ('legacy-source','live',:key,'{}','{}','[]','[]',0,CURRENT_TIMESTAMP)"
            ),
            {"key": "a" * 64},
        )
    run_migrations(migration_url)
    with empty_schema_engine.connect() as connection:
        old = connection.execute(
            text(
                "SELECT page_key,entry_count,request_sha256 FROM source_page_receipts "
                "WHERE source_id='legacy-source'"
            )
        ).one()
        assert old == ("a" * 64, 0, None)
    column = next(
        column
        for column in inspect(empty_schema_engine).get_columns("source_page_receipts")
        if column["name"] == "request_sha256"
    )
    assert column["nullable"] is True
