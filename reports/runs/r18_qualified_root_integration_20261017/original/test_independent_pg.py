"""Original nine test functions plus independent synthetic PG negative cases; no live claims."""

import threading
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

import test_r10_evidence_graph_pg as graph_tests
from test_r04_knowledge_api_pg import seed_event, seed_source_document
from test_r18_public_read_producer_pg import (
    case,
    seed_intelligence,
    test_api_key_expiry_revoke_and_permission_are_current,
    test_long_query_reaches_pg_without_500_character_truncation,
    test_mixed_source_modes_do_not_return_fixture_as_live,
    test_old_revision_and_inactive_event_link_fail_closed,
    test_public_pg_http_projects_distinct_event_and_document_id,
    test_public_read_excludes_private_events_and_nested_evidence,
    test_read_expiry_during_response_production_is_rechecked,
    test_sources_cursor_binds_principal_query_and_acl,
    test_task_without_typed_owner_is_not_configured_and_no_secret_reflection,
)

from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService
from ai_intel.knowledge.models import document_revisions, source_cursors, source_page_receipts

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def pg_engine(isolated_test_database_url):
    original = make_url(isolated_test_database_url)
    assert original.database == "test_dianzi_r18_public_producer_review1_20261016"
    assert original.host == "127.0.0.1" and original.port == 25432
    assert original.username.startswith("test_")
    schema = "test_r18_review1_" + uuid4().hex
    base = create_engine(original, poolclass=NullPool, hide_parameters=True)
    created = False
    try:
        with base.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == original.database
            connection.exec_driver_sql('CREATE SCHEMA "' + schema + '"')
        created = True
        configured = original.update_query_dict({"options":
            f"-c search_path={schema} -c statement_timeout=12000 -c lock_timeout=4000"})
        run_migrations(configured.render_as_string(hide_password=False), "head")
        engine = create_engine(configured, poolclass=NullPool, hide_parameters=True)
        try:
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0030_revalidation_actor_bindings"
            yield engine
        finally:
            engine.dispose()
    finally:
        if created:
            with base.begin() as connection:
                connection.exec_driver_sql('DROP SCHEMA "' + schema + '" CASCADE')
        base.dispose()


def test_independent_search_full_pages_literal_query_and_epoch(pg_engine, case):
    client, _, _ = case
    event_id, document = seed_intelligence(pg_engine, title="literal %_ boundary")
    second = seed_event(pg_engine, [document["revision_id"]], title="literal %_ second")
    third = seed_event(pg_engine, [document["revision_id"]], title="literal %_ third")
    for limit in (1, 2, 100):
        page = client.get("/api/v1/vulns", params={"q": "%_", "limit": limit})
        assert page.status_code == 200, page.text
        found = []
        while True:
            value = page.json()
            found += [item["event_id"] for item in value["items"]]
            if value["next_cursor"] is None:
                break
            page = client.get("/api/v1/vulns", params={"q": "%_", "limit": limit,
                                                      "cursor": value["next_cursor"]})
            assert page.status_code == 200, page.text
        assert found == sorted([event_id, second, third]) and len(set(found)) == 3
    cursor = client.get("/api/v1/vulns", params={"limit": 1}).json()["next_cursor"]
    with pg_engine.begin() as connection:
        connection.execute(text("INSERT INTO scope_epochs(scope_key,epoch,updated_at) VALUES('public',1,now()) "
            "ON CONFLICT(scope_key) DO UPDATE SET epoch=scope_epochs.epoch+1,updated_at=now()"))
    assert client.get("/api/v1/vulns", params={"limit": 1, "cursor": cursor}).status_code == 422


def test_independent_missing_mode_fails_without_live_relabel(pg_engine, case):
    client, _, _ = case
    document = seed_source_document(pg_engine)
    event_id = seed_event(pg_engine, [document["revision_id"]])
    for path in ("/api/v1/vulns/" + event_id, "/api/v1/vulns", "/api/v1/sources"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_configured"


def insert_dimension(engine, event_id, document, *, status):
    with engine.begin() as connection:
        connection.execute(insert(enrichment_results).values(result_id=str(uuid4()),
            event_id=event_id, dimension="versions", status=status, claim_ids=[],
            reference_ids=[document["evidence_id"]], source_scope=[document["source_id"]],
            input_fingerprint="a" * 64, recorded_at=datetime.now(UTC), is_current=True,
            event_version=1, observed_at=datetime.now(UTC), freshness="current"))


def test_independent_citation_without_any_supported_claim_is_not_available(pg_engine, case):
    client, _, _ = case
    event_id, document = seed_intelligence(pg_engine)
    insert_dimension(pg_engine, event_id, document, status="available")
    response = client.get("/api/v1/vulns/" + event_id)
    assert response.status_code == 200, response.text
    dimension = response.json()["vulnerability"]["enrichments"][0]
    assert dimension["status"] == "blocked", dimension
    assert dimension["error_code"] == "evidence_not_qualified"


def test_independent_conflict_dimension_stays_conflict(pg_engine, case):
    client, _, _ = case
    event_id, document = seed_intelligence(pg_engine)
    insert_dimension(pg_engine, event_id, document, status="conflict")
    response = client.get("/api/v1/vulns/" + event_id)
    assert response.status_code == 200, response.text
    assert response.json()["vulnerability"]["enrichments"][0]["status"] == "conflict"


def test_independent_cross_source_graph_keeps_revision_ownership(pg_engine, case, tmp_path, monkeypatch):
    client, _, _ = case
    monkeypatch.setattr(graph_tests, "FIXTURE_RAW_DIRECTORY", tmp_path / "synthetic-originals")
    event_id = uuid4()
    submissions = [graph_tests.publish_fact(pg_engine, tmp_path / str(index), event_id,
                                           graph_tests.VERSION) for index in range(2)]
    graph_tests.publish_event(pg_engine, event_id, submissions)
    with pg_engine.begin() as connection:
        rows = connection.execute(select(document_revisions.c.revision_id,
            document_revisions.c.source_metadata)).all()
        for revision_id, metadata in rows:
            connection.execute(update(document_revisions).where(
                document_revisions.c.revision_id == revision_id).values(
                    source_metadata={**metadata, "data_mode": "fixture"}))
    scope = AccessScope.for_authenticated_user("synthetic-reviewer", "fixture-tenant", Role.VIEWER)
    with Session(pg_engine) as session:
        graph = EvidenceGraphReadService(session, scope).event_graph(event_id)
    assert any(len(edge.source_revision_ids) == 2 for edge in graph.edges)
    response = client.get("/api/v1/vulns/" + str(event_id))
    assert response.status_code == 200, response.text
    result = response.json()
    assert "multi_revision_relation_requires_internal_graph" in result["mapping_limits"]
    assert result["vulnerability"]["freshness"] == "unknown"
    assert {item["revision_id"] for item in result["advisories"]} == {
        item.revision_id.value for item in submissions}
    for advisory in result["advisories"]:
        assert all(citation["revision_id"] == advisory["revision_id"]
                   for citation in advisory["citations"])


def test_independent_source_acl_write_waits_for_read_lock_then_revokes(pg_engine, case):
    client, _, _ = case
    event_id, document = seed_intelligence(pg_engine)
    entered, finished = threading.Event(), threading.Event()
    errors = []
    launched = False

    def change_acl():
        try:
            with pg_engine.begin() as connection:
                entered.set()
                connection.execute(text("UPDATE sources SET visibility='tenant',tenant_id='other' "
                    "WHERE source_id=:source"), {"source": document["source_id"]})
            finished.set()
        except Exception as error:
            errors.append(type(error).__name__)

    thread = threading.Thread(target=change_acl)

    def after_cursor(connection, cursor, statement, parameters, context, executemany):
        nonlocal launched
        if not launched and "FOR SHARE OF document_revisions, documents, sources" in statement:
            launched = True
            thread.start()
            assert entered.wait(1)
            assert not finished.wait(0.15)

    event.listen(pg_engine, "after_cursor_execute", after_cursor)
    try:
        response = client.get("/api/v1/vulns/" + event_id)
    finally:
        event.remove(pg_engine, "after_cursor_execute", after_cursor)
        if launched:
            thread.join(5)
    assert launched and finished.is_set() and not errors
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/vulns/" + event_id).status_code == 503


def test_independent_newer_success_is_not_overridden_by_historical_failure(pg_engine, case):
    client, _, _ = case
    _, document = seed_intelligence(pg_engine)
    older = datetime.now(UTC) - timedelta(minutes=10)
    newer = older + timedelta(minutes=5)
    with pg_engine.begin() as connection:
        connection.execute(insert(source_response_receipts).values(receipt_id=str(uuid4()),
            job_id=str(uuid4()), attempt_count=1, response_ordinal=1, source_kind="vllm_vendor",
            source_id=document["source_id"], stream_kind="backfill", window_end=older,
            input_cursor_sha256="a" * 64, request_fingerprint_sha256="b" * 64,
            observed_at=older, parse_outcome="transport_failed", error_code="fixture_transport_error"))
        connection.execute(insert(source_cursors).values(source_id=document["source_id"],
            stream_kind="backfill", cursor_json={}, last_successful_page=1,
            generation=1, updated_at=newer))
        connection.execute(insert(source_page_receipts).values(source_id=document["source_id"],
            stream_kind="backfill", page_key="c" * 64, input_cursor={}, output_cursor={},
            revision_ids=[document["revision_id"]], failed_job_ids=[], entry_count=1,
            request_sha256="d" * 64, committed_at=newer))
    response = client.get("/api/v1/sources")
    assert response.status_code == 200, response.text
    item = next(item for item in response.json()["items"] if item["source_id"] == document["source_id"])
    assert item["last_success_at"] == newer.isoformat()
    assert item["health"] != "failed", item
