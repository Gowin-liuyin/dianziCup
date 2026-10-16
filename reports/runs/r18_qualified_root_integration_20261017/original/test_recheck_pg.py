"""Unchanged original 28 functions and independent support/observation negative cases."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

import test_r18_public_producer_fix1_pg as fixed_tests
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import document_revisions, evidence, fetch_attempts, source_cursors, source_page_receipts
from ai_intel.knowledge.persistence_models import claims, events

PROBE_SHA = "208d41385e757c0d5410f6bca8d63a90859f629d7f6673ffe48412b22bb069b8"
assert hashlib.sha256(fixed_tests.PROBE.read_bytes()).hexdigest() == PROBE_SHA
case = fixed_tests.case
for name in dir(fixed_tests):
    if name.startswith("test_"):
        globals()[name] = getattr(fixed_tests, name)
pytestmark = pytest.mark.real_pg


@pytest.fixture()
def pg_engine(isolated_test_database_url):
    original = make_url(isolated_test_database_url)
    assert original.database == "test_dianzi_r18_public_producer_review1_fix1_20261016"
    assert original.host == "127.0.0.1" and original.port == 25432
    assert original.username.startswith("test_")
    schema = "test_r18_review1_fix1_" + uuid4().hex
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
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "0030_revalidation_actor_bindings")
            yield engine
        finally:
            engine.dispose()
    finally:
        if created:
            with base.begin() as connection:
                connection.exec_driver_sql('DROP SCHEMA "' + schema + '" CASCADE')
        base.dispose()


@pytest.mark.parametrize("mutation", ["mitigation_only", "claim_unknown", "unsupported_link"])
def test_independent_declared_citations_qualify_the_actual_version_dimension(
    pg_engine, case, tmp_path, monkeypatch, mutation
):
    graph_tests = fixed_tests.probe.graph_tests
    monkeypatch.setattr(graph_tests, "FIXTURE_RAW_DIRECTORY", tmp_path / "synthetic-originals")
    event_id = uuid4()
    submission = graph_tests.publish_fact(pg_engine, tmp_path / "source", event_id, graph_tests.VERSION)
    graph_tests.publish_event(pg_engine, event_id, [submission])
    revision_id = submission.revision_id.value
    claim_id = submission.record.claim_id.value
    all_references = [item.evidence_id.value for item in submission.evidence_links]
    assert len(all_references) == 3
    references = [all_references[-1]] if mutation == "mitigation_only" else all_references
    with pg_engine.begin() as connection:
        metadata = connection.scalar(select(document_revisions.c.source_metadata).where(
            document_revisions.c.revision_id == revision_id))
        connection.execute(update(document_revisions).where(
            document_revisions.c.revision_id == revision_id).values(
                source_metadata={**metadata, "data_mode": "fixture"}))
        connection.execute(update(claims).where(claims.c.claim_id == claim_id).values(
            freshness="unknown" if mutation == "claim_unknown" else "current",
            observed_at=datetime.now(UTC)))
        if mutation == "unsupported_link":
            connection.execute(update(evidence).where(
                evidence.c.evidence_id == all_references[-1]).values(supports_claim=False))
        version = connection.scalar(select(events.c.business_version).where(
            events.c.event_id == str(event_id)))
        connection.execute(insert(enrichment_results).values(result_id=str(uuid4()),
            event_id=str(event_id), dimension="versions", status="available",
            claim_ids=[claim_id], reference_ids=references, source_scope=[submission.source_id.value],
            input_fingerprint="a" * 64, recorded_at=datetime.now(UTC), is_current=True,
            event_version=version, observed_at=datetime.now(UTC), freshness="current"))
    response = case[0].get("/api/v1/vulns/" + str(event_id))
    assert response.status_code == 200, response.text
    dimension = response.json()["vulnerability"]["enrichments"][0]
    assert {item["evidence_id"] for item in dimension["citations"]} == set(references)
    if mutation == "mitigation_only":
        assert dimension["citations"][0]["quote"].startswith("Mitigation:")
        assert ">=1.0,<1.4.2" not in dimension["citations"][0]["quote"]
    assert dimension["status"] == "blocked", dimension
    assert dimension["freshness"] == "unknown"


@pytest.mark.parametrize("latest", ["failed", "partial", "succeeded"])
def test_independent_newer_fetch_observation_controls_health_without_erasing_success(pg_engine, case, latest):
    _, document = fixed_tests.probe.seed_intelligence(pg_engine)
    older = datetime.now(UTC) - timedelta(minutes=10)
    newer = older + timedelta(minutes=5)
    with pg_engine.begin() as connection:
        connection.execute(insert(source_cursors).values(source_id=document["source_id"],
            stream_kind="backfill", cursor_json={}, last_successful_page=1, generation=1,
            updated_at=older))
        connection.execute(insert(source_page_receipts).values(source_id=document["source_id"],
            stream_kind="backfill", page_key="a" * 64, input_cursor={}, output_cursor={},
            revision_ids=[document["revision_id"]], failed_job_ids=[], entry_count=1,
            committed_at=older))
        connection.execute(insert(fetch_attempts).values(attempt_id=str(uuid4()),
            source_id=document["source_id"], attempted_at=newer, outcome=latest,
            http_status=503 if latest == "failed" else 200, new_event_count=0))
    response = case[0].get("/api/v1/sources")
    assert response.status_code == 200, response.text
    source = next(item for item in response.json()["items"] if item["source_id"] == document["source_id"])
    assert source["last_success_at"] == older.isoformat()
    assert source["last_attempt_at"] == newer.isoformat()
    assert source["health"] == ("unknown" if latest == "succeeded" else latest)
