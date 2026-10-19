"""Real authority publication commits inside both final retrieval check windows."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from test_t30_hybrid_retrieval import PUBLIC, corpus, index_fact_set
from tests.r12_hybrid_fixtures import NOW, seed_fact

import ai_intel.retrieval.hybrid as hybrid
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.knowledge.models import scope_epochs
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import claims, claim_evidence, publication_receipts
from ai_intel.retrieval.hybrid_contracts import HybridQuery

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize("phase", ["after_final_epoch_read", "after_final_candidate_read"])
@pytest.mark.parametrize("withdraw", [False, True], ids=["new_supported_fact", "supported_source_withdrawal"])
def test_legal_publication_must_invalidate_final_selection(corpus, monkeypatch, phase: str, withdraw: bool) -> None:
    engine, indexer, retriever = corpus
    target = seed_fact(engine, "prompt injection risk. The source status is withdrawn.")
    unpublished = seed_fact(engine, "prompt injection newly confirmed synthetic risk")
    with engine.begin() as connection:
        connection.execute(delete(claim_evidence).where(claim_evidence.c.claim_id == unpublished["claim_id"]))
        connection.execute(delete(claims).where(claims.c.claim_id == unpublished["claim_id"]))
    index_fact_set(engine, indexer)
    authority_scope = AccessScope.for_authenticated_user("review-authority-publisher", None, Role.SYSTEM_ADMIN)
    public_scope = VisibilityScope(visibility="public", tenant_id=None)
    source = target if withdraw else unpublished
    submission = ClaimSubmission(
        record=ClaimRecord.model_validate(dict(schema_version=2, claim_id={"value": str(uuid4())}, subject=source["event_id"], predicate="source_status" if withdraw else "risk_description", object_value="withdrawn" if withdraw else "prompt injection newly confirmed synthetic risk", claim_status="supported", claim_origin="source_explicit", condition_value="true", freshness="current", asserted_at=NOW, observed_at=NOW, scope=public_scope.model_dump())),
        source_id=Identifier(value=source["source_id"]),
        revision_id=Identifier(value=source["revision_id"]),
        json_path="synthetic source status" if withdraw else "synthetic risk description",
        evidence_links=(EvidenceLink(evidence_id=Identifier(value=source["evidence_id"]), support_kind="supports", validation_status="validated"),),
    )
    published = []
    with engine.connect() as connection:
        before_epoch = connection.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public"))
        before_count = connection.scalar(select(func.count()).select_from(claims))

    def publish() -> None:
        with Session(engine) as session, session.begin():
            receipt = KnowledgeRepository(session, authority_scope).publish("review-window-" + str(uuid4()), public_scope, (submission,), created_at=NOW)
        published.append(receipt)

    if phase == "after_final_epoch_read":
        original = hybrid.read_scope_epochs
        reads = 0

        def after_epoch_read(session, scope, *, lock=False):
            nonlocal reads
            result = original(session, scope, lock=lock)
            reads += 1
            if reads == 2:
                publish()
            return result

        monkeypatch.setattr(hybrid, "read_scope_epochs", after_epoch_read)
    else:
        original_candidates = hybrid.candidates_from_rows
        reads = 0

        def after_candidates_read(session, scope, rows):
            nonlocal reads
            result = original_candidates(session, scope, rows)
            reads += 1
            if reads == 3:
                publish()
            return result

        monkeypatch.setattr(hybrid, "candidates_from_rows", after_candidates_read)
    result = retriever.retrieve(PUBLIC, HybridQuery("prompt injection", include_graph=False))
    with engine.connect() as connection:
        after_epoch = connection.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public"))
        after_count = connection.scalar(select(func.count()).select_from(claims))
        saved_receipt = connection.scalar(select(publication_receipts.c.epoch).where(publication_receipts.c.receipt_id == published[0].receipt_id))
        new_status = connection.execute(select(claims.c.claim_status, claims.c.provenance_status).where(claims.c.claim_id == submission.record.claim_id.value)).one()
    print(json.dumps(dict(probe="legal_KnowledgeRepository_publish", phase=phase, withdrawal=withdraw, before=dict(epoch=before_epoch, claims=before_count), after=dict(epoch=after_epoch, claims=after_count, publication_receipt_epoch=saved_receipt, claim_status=new_status[0], provenance_status=new_status[1]), result=dict(epoch=dict(result.scope_epochs)["public"], indexed_epoch=dict(result.indexed_epochs)["public"], partial=result.partial, reasons=result.reasons, returned_event_ids=[hit.candidate.event_id for hit in result.hits], returned_evidence_ids=[hit.candidate.evidence_id for hit in result.hits]), target=target, unpublished=unpublished)))
    assert before_epoch == 1 and after_epoch == saved_receipt == 2 and len(published) == 1
    assert after_count == before_count + 1 and new_status == ("supported", "source_verified")
    assert result.partial and not result.hits and "scope_changed_during_retrieval" in result.reasons
