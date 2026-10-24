"""Synthetic response bytes traverse actual PG publication, metadata, API projection and replay."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r07_enrichment_inputs_pg import ADMIN
from test_r07_enrichment_publication_pg import counts, publish
from tests.r06_source_worker_fixtures import source_response

from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.enrichment.inputs import load_event_enrichment_inputs
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.ingestion.source_documents import SourceResponse, persist_source_response
from ai_intel.knowledge.models import evidence
from ai_intel.knowledge.persistence_models import claim_assertions, claims

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, tzinfo=UTC)


@pytest.mark.parametrize(
    "same_authority,expected_status", [(False, "available"), (True, "conflict")]
)
def test_two_source_scores_preserve_authority_quotes_metadata_detail_and_replay(
    catalog_engine, tmp_path, same_authority, expected_status
):
    body, _ = source_response("nvd_ollama")
    payload = json.loads(body)
    rows = payload["vulnerabilities"][0]["cve"]["metrics"]["cvssMetricV31"]
    rows[0]["source"] = "nvd@nist.gov"
    rows[0]["cvssData"]["baseScore"] = 9.8
    second = copy.deepcopy(rows[0])
    second["source"] = "nvd@nist.gov" if same_authority else "cna@example.org"
    second["cvssData"]["baseScore"] = 8.1
    rows[:] = [rows[0], second]
    raw = json.dumps(payload).encode()
    store = ContentStore(tmp_path / "synthetic-content")
    with Session(catalog_engine) as session, session.begin():
        saved = persist_source_response(
            session,
            store,
            ADMIN,
            SourceResponse(
                "nvd_ollama",
                raw,
                "https://services.nvd.nist.gov/rest/json/cves/2.0"
                "?keywordSearch=ollama&resultsPerPage=100&startIndex=0",
                NOW,
                data_mode="fixture",
            ),
            ingested_at=NOW,
        )
    event_id = UUID(saved.event_ids[0])
    with Session(catalog_engine) as session:
        loaded = load_event_enrichment_inputs(
            session, store, ADMIN, event_id, "cvss-authority-fix-1"
        )
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    cvss = next(a for a in attempts if a.dimension == "cvss")
    assert cvss.status.value == expected_status and len(cvss.candidates) == 2
    request_id = uuid4()
    first = publish(catalog_engine, loaded, attempts, request_id)
    before = counts(catalog_engine)
    replay = publish(catalog_engine, loaded, attempts, request_id, NOW + timedelta(seconds=1))
    assert [(r.result_id, r.claim_ids) for r in first] == [
        (r.result_id, r.claim_ids) for r in replay
    ]
    assert all(r.reused for r in replay) and counts(catalog_engine) == before
    with Session(catalog_engine) as session:
        stored = list(
            session.execute(select(claims).where(claims.c.predicate == "cvss_signal")).mappings()
        )
        assert len(stored) == 2
        assert {
            (r["object_json"]["authority"], r["object_json"]["base_score"]) for r in stored
        } == {
            ("nvd@nist.gov", 9.8),
            (second["source"], 8.1),
        }
        detail = KnowledgeReadService(session, ADMIN, data_mode="fixture").event_detail(event_id)
        dimension = next(d for d in detail.dimensions if d.dimension == "cvss")
        assert dimension.status == expected_status and len(dimension.claim_ids) == 2
        assert {str(r["claim_id"]) for r in stored} == {str(c) for c in dimension.claim_ids}
        for row in stored:
            assertion = (
                session.execute(
                    select(claim_assertions).where(claim_assertions.c.claim_id == row["claim_id"])
                )
                .mappings()
                .one()
            )
            assert assertion["scoring_authority"] == row["object_json"]["authority"]
            summary = next(c for c in detail.claims if str(c.claim_id) == row["claim_id"])
            assert row["object_json"]["authority"] in summary.display_value
            linked = list(
                session.execute(
                    select(evidence).where(
                        evidence.c.evidence_id.in_([str(e) for e in summary.evidence_ids])
                    )
                ).mappings()
            )
            authority_quotes = [e for e in linked if e["quote"] == row["object_json"]["authority"]]
            assert len(authority_quotes) == 1
            for quote in authority_quotes:
                assert quote["quote_sha256"] == hashlib.sha256(quote["quote"].encode()).hexdigest()
                assert quote["supports_claim"]
                assert quote["coordinate_version"] == "fulltext_unicode_v1"
        assert len(dimension.citations) >= 2
