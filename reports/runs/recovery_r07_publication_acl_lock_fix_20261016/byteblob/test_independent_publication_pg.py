"""Independent synthetic PG negatives against the frozen publication service."""

import json
import os
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, text, update
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r07_enrichment_inputs_pg import ADMIN, seeded_event
from test_r06_source_worker_pg import handler_for, queue, run
from tests.r06_source_worker_fixtures import source_response

from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.contracts import CandidateEvidence, DimensionAttempt, EvidenceBoundCandidate
from ai_intel.enrichment.inputs import EnrichmentInputError, load_event_enrichment_inputs
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.enrichment.publication import EnrichmentPublicationError, publish_enrichment_attempts
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.ingestion.source_documents import SourceResponse, persist_source_response
from ai_intel.domain.values import Identifier
from ai_intel.knowledge.event_linking import EventIdentifier, EventRepository, EventSubmission
from ai_intel.knowledge.models import document_revisions
from ai_intel.knowledge.models import documents, evidence, job_runs, outbox_events, scope_epochs
from ai_intel.knowledge.persistence_models import claim_assertions, claim_evidence, claims, change_events, publication_receipts
import hashlib

pytest_plugins = ("tests.conftest",)
pytestmark = pytest.mark.real_pg
RAW = Path(__file__).resolve().parent
RUN_SUFFIX = os.environ.get("INDEPENDENT_REVIEW_RUN_SUFFIX", "")


def loaded_inputs(engine, tmp_path):
    store, event_id = seeded_event(engine, tmp_path)
    with Session(engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, event_id, "independent-review-1")
    return store, loaded


def all_counts(engine):
    with Session(engine) as session:
        return tuple(session.scalar(select(func.count()).select_from(table)) for table in (
            claims, claim_assertions, claim_evidence, evidence, enrichment_results,
            change_events, publication_receipts, job_runs, outbox_events, scope_epochs,
        ))


def publish(engine, loaded, attempts):
    with Session(engine) as session, session.begin():
        return publish_enrichment_attempts(session, ADMIN, loaded, attempts, request_id=uuid4(), recorded_at=loaded.documents[0].observed_at)


@pytest.mark.parametrize("revoked_parent", ["source", "document"])
def test_parent_acl_revocation_is_checked_before_object_io(catalog_engine, tmp_path, revoked_parent):
    store, loaded = loaded_inputs(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        if revoked_parent == "source":
            connection.execute(text("UPDATE sources SET visibility='tenant',tenant_id='review-secret-owner'"))
        else:
            connection.execute(update(documents).values(visibility="tenant", tenant_id="review-secret-owner"))
    reads = []

    class AuditedStore:
        def read_verified(self, digest):
            reads.append(digest)
            return store.read_verified(digest)

    with Session(catalog_engine) as session:
        try:
            load_event_enrichment_inputs(session, AuditedStore(), ADMIN, loaded.context.event_id, "independent-review-1")
        except (CrossTenantAccessError, EnrichmentInputError):
            pass
    assert reads == [], "Parent source/document ACL revoked, but object bytes were still read"


def test_failed_attempt_cannot_bypass_revoked_source_scope(catalog_engine, tmp_path):
    _, loaded = loaded_inputs(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(text("UPDATE sources SET visibility='tenant',tenant_id='review-secret-owner'"))
    failed = DimensionAttempt(dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout")
    before = all_counts(catalog_engine)
    with pytest.raises((CrossTenantAccessError, EnrichmentPublicationError, EnrichmentInputError)):
        publish(catalog_engine, loaded, (failed,))
    assert all_counts(catalog_engine) == before


def test_invalid_candidate_after_success_rolls_back_all_tables(catalog_engine, tmp_path):
    _, loaded = loaded_inputs(catalog_engine, tmp_path)
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    candidate = attempts[0].candidates[0]
    bad = candidate.model_copy(update={"origin": ClaimOrigin.MODEL_HYPOTHESIS})
    altered = attempts[0].model_copy(update={"candidates": (bad,)})
    before = all_counts(catalog_engine)
    with pytest.raises(EnrichmentPublicationError, match="verified_fields"):
        publish(catalog_engine, loaded, (attempts[1], altered))
    assert all_counts(catalog_engine) == before


def test_duplicate_context_revision_cannot_bypass_full_roster(catalog_engine, tmp_path):
    _, loaded = loaded_inputs(catalog_engine, tmp_path)
    forged = replace(loaded, context=loaded.context.model_copy(update={"revision_ids": loaded.context.revision_ids * 2}))
    failed = DimensionAttempt(dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout")
    before = all_counts(catalog_engine)
    with pytest.raises(EnrichmentPublicationError, match="roster_changed"):
        publish(catalog_engine, forged, (failed,))
    assert all_counts(catalog_engine) == before


@pytest.mark.parametrize("authority_relation,expected", [("different", "available"), ("same", "conflict")])
def test_cvss_parallel_authorities_vs_same_authority_conflict(catalog_engine, tmp_path, authority_relation, expected):
    store, loaded = loaded_inputs(catalog_engine, tmp_path)
    body = json.loads(source_response("nvd_ollama")[0])
    cve = body["vulnerabilities"][0]["cve"]
    first = {"source": "review-first@example.invalid", "type": "Primary", "cvssData": {
        "version": "3.1", "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "baseScore": 9.8}}
    second = deepcopy(first)
    second["source"] = first["source"] if authority_relation == "same" else "review-second@example.invalid"
    second["cvssData"]["vectorString"] = "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"
    second["cvssData"]["baseScore"] = 8.1
    cve["metrics"] = {"cvssMetricV31": [first, second]}
    response = SourceResponse("nvd_ollama", json.dumps(body).encode(),
        "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=20&startIndex=0",
        loaded.documents[0].observed_at + timedelta(seconds=1))
    with Session(catalog_engine) as session, session.begin():
        persist_source_response(session, store, ADMIN, response, ingested_at=response.observed_at)
    with Session(catalog_engine) as session:
        current = load_event_enrichment_inputs(session, store, ADMIN, loaded.context.event_id, "independent-review-1")
    attempts = enrich_structured_fields(current.context, current.documents)
    publish(catalog_engine, current, (attempts[0],))
    with Session(catalog_engine) as session:
        detail = KnowledgeReadService(session, ADMIN, "fixture").event_detail(current.context.event_id)
        cvss = next(item for item in detail.dimensions if item.dimension == "cvss")
        observed = {"authority_relation": authority_relation, "status": cvss.status, "new_claim_count": len(cvss.claim_ids), "source_scores": [9.8, 8.1]}
        (RAW / ("cvss_" + authority_relation + "_outcome" + RUN_SUFFIX + ".json")).write_text(json.dumps(observed, indent=2), encoding="utf-8")
        assert len(cvss.claim_ids) == 2
        assert cvss.status == expected, observed


def test_multisource_model_candidate_returns_both_exact_visible_citations(catalog_engine, tmp_path):
    store, original = loaded_inputs(catalog_engine, tmp_path)
    job_id = queue(catalog_engine, "vllm_vendor")
    assert run(catalog_engine, job_id, handler_for(store, "vllm_vendor")) in {"succeeded", "partial"}
    with Session(catalog_engine) as session, session.begin():
        revision_ids = tuple(session.scalars(select(document_revisions.c.revision_id).where(document_revisions.c.is_current.is_(True))))
        EventRepository(session, ADMIN).publish_events("independent-paired-" + str(uuid4()), original.scope,
            (EventSubmission(event_id=Identifier(value=str(original.context.event_id)), event_type="vulnerability", title="Synthetic paired review event", scope=original.scope,
                external_ids=tuple(EventIdentifier(id_type="cve", id_value=cve) for cve in original.context.external_cve_ids),
                source_revision_ids=tuple(Identifier(value=revision_id) for revision_id in revision_ids)),), original.documents[0].observed_at)
    with Session(catalog_engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, original.context.event_id, "independent-review-1")
    quotes = []
    for document in loaded.documents:
        block = next(block for block in document.blocks if block.json_pointer in {"/cve/id", "/ghsa_id"})
        start = len(block.json_pointer + ": ")
        quote = block.text[start:]
        quotes.append(CandidateEvidence(revision_id=document.revision_id, block_id=block.block_id, start_offset=start, end_offset=len(block.text), quote_text=quote, quote_sha256=hashlib.sha256(quote.encode()).hexdigest()))
    candidate = EvidenceBoundCandidate(dimension="versions", value={"kind": "version_assertion", "package_key": "synthetic-review", "ecosystem": "unknown", "scheme": "unknown", "raw_expression": "Synthetic unresolved range candidate"}, evidence=tuple(quotes), origin=ClaimOrigin.MODEL_HYPOTHESIS)
    result = publish(catalog_engine, loaded, (DimensionAttempt(dimension="versions", status=DimensionStatus.PENDING, candidates=(candidate,), source_ids=tuple(document.source_id for document in loaded.documents)),))[0]
    with Session(catalog_engine) as session:
        detail = KnowledgeReadService(session, ADMIN, "fixture").event_detail(loaded.context.event_id)
        claim = next(item for item in detail.claims if str(item.claim_id) == result.claim_ids[0])
        assert claim.origin == "model_hypothesis" and claim.status == "unverified"
        assert len(claim.evidence_ids) == 2
        actual = {KnowledgeReadService(session, ADMIN, "fixture").read_evidence(evidence_id).revision_id for evidence_id in claim.evidence_ids}
        assert actual == {quote.revision_id for quote in quotes}
        assert session.scalar(select(func.count()).select_from(claim_assertions).where(claim_assertions.c.claim_id == result.claim_ids[0])) == 2
        versions = next(item for item in detail.dimensions if item.dimension == "versions")
        assert versions.status == "pending" and not versions.claim_ids


def test_source_revision_and_publication_share_non_deadlocking_lock_order(catalog_engine, tmp_path):
    store, loaded = loaded_inputs(catalog_engine, tmp_path)
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    body = json.loads(source_response("nvd_ollama")[0])
    body["vulnerabilities"][0]["cve"]["descriptions"][0]["value"] += " Synthetic review revision."
    response = SourceResponse("nvd_ollama", json.dumps(body).encode(),
        "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=20&startIndex=0",
        loaded.documents[0].observed_at + timedelta(seconds=1))
    writer_locked = Event()
    publisher_locked = Event()

    def synchronize(connection, cursor, statement, parameters, context, executemany):
        actor = connection.info.get("review_actor")
        if actor == "writer" and "SELECT documents." in statement and "FOR UPDATE" in statement and not writer_locked.is_set():
            writer_locked.set()
            assert publisher_locked.wait(10), "publisher did not acquire scope lock"
        if actor == "publisher" and "pg_advisory_xact_lock" in statement:
            publisher_locked.set()

    def invoke(actor):
        try:
            with Session(catalog_engine) as session, session.begin():
                session.connection().info["review_actor"] = actor
                if actor == "writer":
                    persist_source_response(session, store, ADMIN, response, ingested_at=response.observed_at)
                else:
                    publish_enrichment_attempts(session, ADMIN, loaded, attempts, request_id=uuid4(), recorded_at=response.observed_at)
            return {"actor": actor, "outcome": "completed", "sqlstate": None}
        except Exception as failure:
            cause = getattr(failure, "orig", None)
            return {"actor": actor, "outcome": type(failure).__name__, "sqlstate": getattr(cause, "sqlstate", None)}

    event.listen(catalog_engine, "after_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(invoke, "writer")
            assert writer_locked.wait(10), "writer did not acquire document lock"
            publisher = pool.submit(invoke, "publisher")
            outcomes = [writer.result(timeout=25), publisher.result(timeout=25)]
    finally:
        event.remove(catalog_engine, "after_cursor_execute", synchronize)
    (RAW / ("concurrent_source_publication_outcomes" + RUN_SUFFIX + ".json")).write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
    assert all(outcome["sqlstate"] != "40P01" for outcome in outcomes), outcomes
    assert {outcome["outcome"] for outcome in outcomes} <= {"completed", "EnrichmentPublicationError"}, outcomes
