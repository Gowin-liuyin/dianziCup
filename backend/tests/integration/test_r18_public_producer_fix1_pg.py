"""Import the unchanged nine author and seven reviewer Oracles with a head fixture."""

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.knowledge.models import document_revisions, source_cursors, source_page_receipts
from ai_intel.knowledge.persistence_models import claim_assertions, claims, event_documents, events

ROOT = Path(__file__).resolve().parents[3]
PROBE = (
    ROOT / "reports/runs/r18_qualified_root_integration_20261017/original/test_independent_pg.py"
)
spec = importlib.util.spec_from_file_location("r18_original_review_probe", PROBE)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)
case = probe.case
for name in (
    "test_api_key_expiry_revoke_and_permission_are_current",
    "test_long_query_reaches_pg_without_500_character_truncation",
    "test_mixed_source_modes_do_not_return_fixture_as_live",
    "test_old_revision_and_inactive_event_link_fail_closed",
    "test_public_pg_http_projects_distinct_event_and_document_id",
    "test_public_read_excludes_private_events_and_nested_evidence",
    "test_read_expiry_during_response_production_is_rechecked",
    "test_sources_cursor_binds_principal_query_and_acl",
    "test_task_without_typed_owner_is_not_configured_and_no_secret_reflection",
    "test_independent_search_full_pages_literal_query_and_epoch",
    "test_independent_missing_mode_fails_without_live_relabel",
    "test_independent_citation_without_any_supported_claim_is_not_available",
    "test_independent_conflict_dimension_stays_conflict",
    "test_independent_cross_source_graph_keeps_revision_ownership",
    "test_independent_source_acl_write_waits_for_read_lock_then_revokes",
    "test_independent_newer_success_is_not_overridden_by_historical_failure",
):
    globals()[name] = getattr(probe, name)

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def pg_engine(isolated_test_database_url):
    original = make_url(isolated_test_database_url)
    assert original.database == "test_dianzi_r18_public_producer_fix1_20261016"
    schema = "test_r18_fix1_" + uuid4().hex
    base = create_engine(original, poolclass=NullPool, hide_parameters=True)
    created = False
    try:
        with base.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == original.database
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        created = True
        configured = original.update_query_dict(
            {"options": f"-c search_path={schema} -c statement_timeout=12000 -c lock_timeout=4000"}
        )
        run_migrations(configured.render_as_string(hide_password=False), "head")
        engine = create_engine(configured, poolclass=NullPool, hide_parameters=True)
        try:
            with engine.connect() as connection:
                assert (
                    connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0031_public_task_bindings"
                )
            yield engine
        finally:
            engine.dispose()
    finally:
        if created:
            with base.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        base.dispose()


@pytest.mark.parametrize(
    "mutation",
    [
        "supported",
        "missing_claim",
        "wrong_dimension",
        "wrong_owner",
        "missing_assertion",
        "reference_mismatch",
        "old_revision",
        "conflict",
        "denied_claim",
    ],
)
def test_dimension_available_requires_its_own_current_semantic_support(
    pg_engine,
    case,
    tmp_path,
    monkeypatch,
    mutation,
):
    graph_tests = probe.graph_tests
    monkeypatch.setattr(graph_tests, "FIXTURE_RAW_DIRECTORY", tmp_path / "source-originals")
    event_id = uuid4()
    submission = graph_tests.publish_fact(
        pg_engine, tmp_path / "published", event_id, graph_tests.VERSION
    )
    graph_tests.publish_event(pg_engine, event_id, [submission])
    claim_id = submission.record.claim_id.value
    revision_id = submission.revision_id.value
    source_id = submission.source_id.value
    references = [item.evidence_id.value for item in submission.evidence_links]
    with pg_engine.begin() as connection:
        metadata = connection.scalar(
            select(document_revisions.c.source_metadata).where(
                document_revisions.c.revision_id == revision_id
            )
        )
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == revision_id)
            .values(source_metadata={**metadata, "data_mode": "fixture"})
        )
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == claim_id)
            .values(freshness="current", observed_at=datetime.now(UTC))
        )
    if mutation in {"reference_mismatch", "old_revision"}:
        other = probe.seed_source_document(pg_engine)
        with pg_engine.begin() as connection:
            connection.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == other["revision_id"])
                .values(source_metadata={"data_mode": "fixture"})
            )
            connection.execute(
                insert(event_documents).values(
                    event_id=str(event_id),
                    revision_id=other["revision_id"],
                    active=True,
                    associated_at=datetime.now(UTC),
                )
            )
        if mutation == "reference_mismatch":
            references = [other["evidence_id"]]
    with pg_engine.begin() as connection:
        if mutation == "wrong_owner":
            connection.execute(
                update(claims).where(claims.c.claim_id == claim_id).values(subject=str(uuid4()))
            )
        if mutation == "missing_assertion":
            connection.execute(
                claim_assertions.delete().where(claim_assertions.c.claim_id == claim_id)
            )
        if mutation == "old_revision":
            connection.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == revision_id)
                .values(is_current=False)
            )
        if mutation == "conflict":
            connection.execute(
                update(claims).where(claims.c.claim_id == claim_id).values(claim_status="disputed")
            )
        if mutation == "denied_claim":
            connection.execute(
                update(claims)
                .where(claims.c.claim_id == claim_id)
                .values(visibility="tenant", tenant_id="other-tenant")
            )
        version = connection.scalar(
            select(events.c.business_version).where(events.c.event_id == str(event_id))
        )
        connection.execute(
            insert(enrichment_results).values(
                result_id=str(uuid4()),
                event_id=str(event_id),
                dimension="poc" if mutation == "wrong_dimension" else "versions",
                status="available",
                claim_ids=[] if mutation == "missing_claim" else [claim_id],
                reference_ids=references,
                source_scope=[source_id],
                input_fingerprint="a" * 64,
                recorded_at=datetime.now(UTC),
                is_current=True,
                event_version=version,
                observed_at=datetime.now(UTC),
                freshness="current",
            )
        )
    response = case[0].get("/api/v1/vulns/" + str(event_id))
    assert response.status_code == 200, response.text
    dimensions = response.json()["vulnerability"]["enrichments"]
    if mutation == "supported":
        assert dimensions[0]["status"] == "available"
        assert dimensions[0]["claim_ids"] == [claim_id]
        assert {item["evidence_id"] for item in dimensions[0]["citations"]} == set(references)
    elif mutation == "denied_claim":
        assert not any(item["status"] == "available" for item in dimensions)
        assert claim_id not in response.text
    else:
        assert len(dimensions) == 1
        assert dimensions[0]["status"] == "blocked"
        assert dimensions[0]["freshness"] == "unknown"
        assert {item["evidence_id"] for item in dimensions[0]["citations"]} == set(references)


@pytest.mark.parametrize("latest", ["failed", "partial", "tie"])
def test_latest_source_status_preserves_last_success(pg_engine, case, latest):
    _, document = probe.seed_intelligence(pg_engine)
    older = datetime.now(UTC) - timedelta(minutes=10)
    newest = older if latest == "tie" else older + timedelta(minutes=5)
    with pg_engine.begin() as connection:
        connection.execute(
            insert(source_cursors).values(
                source_id=document["source_id"],
                stream_kind="backfill",
                cursor_json={},
                last_successful_page=1,
                generation=1,
                updated_at=older,
            )
        )
        connection.execute(
            insert(source_page_receipts).values(
                source_id=document["source_id"],
                stream_kind="backfill",
                page_key="a" * 64,
                input_cursor={},
                output_cursor={},
                revision_ids=[document["revision_id"]],
                failed_job_ids=[],
                entry_count=1,
                committed_at=older,
            )
        )
        if latest == "partial":
            connection.execute(
                insert(source_page_receipts).values(
                    source_id=document["source_id"],
                    stream_kind="backfill",
                    page_key="b" * 64,
                    input_cursor={},
                    output_cursor={},
                    revision_ids=[],
                    failed_job_ids=[str(uuid4())],
                    entry_count=1,
                    committed_at=newest,
                )
            )
        else:
            connection.execute(
                insert(source_response_receipts).values(
                    receipt_id=str(uuid4()),
                    job_id=str(uuid4()),
                    attempt_count=1,
                    response_ordinal=1,
                    source_kind="vllm_vendor",
                    source_id=document["source_id"],
                    stream_kind="backfill",
                    window_end=newest,
                    input_cursor_sha256="a" * 64,
                    request_fingerprint_sha256="b" * 64,
                    observed_at=newest,
                    parse_outcome="transport_failed",
                    error_code="fixture_transport_error",
                )
            )
    response = case[0].get("/api/v1/sources")
    assert response.status_code == 200, response.text
    item = next(
        item for item in response.json()["items"] if item["source_id"] == document["source_id"]
    )
    assert item["last_success_at"] == older.isoformat()
    assert item["health"] == ("partial" if latest in {"partial", "tie"} else "failed")
