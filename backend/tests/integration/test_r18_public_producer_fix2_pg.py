"""Unchanged original 28 and reviewer six, with this run's isolated head fixture."""

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import document_revisions
from ai_intel.knowledge.persistence_models import claims, events

ROOT = Path(__file__).resolve().parents[3]
PROBE = ROOT / "reports/runs/r18_qualified_root_integration_20261017/original/test_recheck_pg.py"
spec = importlib.util.spec_from_file_location("r18_fix1_independent_recheck", PROBE)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)
case = probe.case
for name in dir(probe):
    if name.startswith("test_"):
        globals()[name] = getattr(probe, name)
pytestmark = pytest.mark.real_pg


@pytest.fixture()
def pg_engine(isolated_test_database_url):
    original = make_url(isolated_test_database_url)
    assert original.database == "test_dianzi_r18_public_producer_fix2_20261016"
    assert (original.host, original.port) == ("127.0.0.1", 25432)
    assert original.username.startswith("test_")
    schema = "test_r18_fix2_" + uuid4().hex
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
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "0031_public_task_bindings"
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
    "declared", ["complete", "expression_only", "missing_fix", "missing_mitigation"]
)
def test_public_version_requires_the_declared_proof_of_every_typed_field(
    pg_engine, case, tmp_path, monkeypatch, declared
):
    graph_tests = probe.fixed_tests.probe.graph_tests
    monkeypatch.setattr(graph_tests, "FIXTURE_RAW_DIRECTORY", tmp_path / "synthetic-originals")
    event_id = uuid4()
    submission = graph_tests.publish_fact(
        pg_engine, tmp_path / "source", event_id, graph_tests.VERSION
    )
    graph_tests.publish_event(pg_engine, event_id, [submission])
    revision_id, claim_id = submission.revision_id.value, submission.record.claim_id.value
    all_references = [item.evidence_id.value for item in submission.evidence_links]
    assert len(all_references) == 3
    references = {
        "complete": all_references,
        "expression_only": all_references[:1],
        "missing_fix": [all_references[0], all_references[2]],
        "missing_mitigation": all_references[:2],
    }[declared]
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
        version = connection.scalar(
            select(events.c.business_version).where(events.c.event_id == str(event_id))
        )
        connection.execute(
            insert(enrichment_results).values(
                result_id=str(uuid4()),
                event_id=str(event_id),
                dimension="versions",
                status="available",
                claim_ids=[claim_id],
                reference_ids=references,
                source_scope=[submission.source_id.value],
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
    dimension = response.json()["vulnerability"]["enrichments"][0]
    assert dimension["claim_ids"] == [claim_id]
    assert {item["evidence_id"] for item in dimension["citations"]} == set(references)
    assert dimension["status"] == ("available" if declared == "complete" else "blocked")
    assert dimension["freshness"] == ("current" if declared == "complete" else "unknown")
    if declared != "complete":
        assert dimension["error_code"] == "evidence_not_qualified"
