"""Real PG authority bundles, explicit gaps and empty watches; no semantic or generated live."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session
from tests.r12_conversation_fixtures import context_identity as context_identity
from tests.r12_conversation_fixtures import conversation_database as conversation_database
from tests.r12_hybrid_fixtures import record_change, seed_fact

from ai_intel.answering import evidence_bundle
from ai_intel.answering.conversation_context import ConversationContextService
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import ClaimOrigin, ClaimStatus, ConditionValue, FreshnessStatus
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.knowledge.models import evidence
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import claim_evidence, claims

pytestmark = pytest.mark.real_pg


def bundle(identity, *, events=(), question="Describe current facts", known_at=None, valid_at=None):
    engine, _auth, scope, token, _login = identity
    service = ConversationContextService(engine)
    turn = service.admit(
        QuestionRequest(
            question=question,
            event_ids=events,
            mode="library",
            known_at=known_at,
            valid_at=valid_at,
        ),
        scope,
        uuid4().hex,
        conversation_version=None,
        session_token=token,
    )
    return service.read_bundle(scope, turn.turn_id, session_token=token, data_mode="fixture")


def public_epochs(engine):
    record_change(engine)
    record_change(engine, "tenant:tenant-a")


def legal_publication(
    engine, source, *, predicate="source_verified", value="synthetic", key=None, on_connection=None
):
    now = datetime.now(UTC)
    record = ClaimRecord(
        claim_id=Identifier(value=str(uuid4())),
        subject="synthetic component",
        predicate=predicate,
        object_value=value,
        claim_status=ClaimStatus.SUPPORTED,
        claim_origin=ClaimOrigin.SOURCE_EXPLICIT,
        condition_value=ConditionValue.TRUE,
        freshness=FreshnessStatus.CURRENT,
        asserted_at=now,
        observed_at=now,
        scope=VisibilityScope(visibility="public", tenant_id=None),
    )
    submission = ClaimSubmission(
        record=record,
        source_id=Identifier(value=source["source_id"]),
        revision_id=Identifier(value=source["revision_id"]),
        json_path="/synthetic",
        evidence_links=(
            EvidenceLink(
                evidence_id=Identifier(value=source["evidence_id"]),
                support_kind="supports",
                validation_status="validated",
            ),
        ),
    )
    publisher = AccessScope.for_authenticated_user("synthetic-publisher", None, Role.SYSTEM_ADMIN)
    with Session(engine) as session, session.begin():
        if on_connection is not None:
            on_connection(session)
        return KnowledgeRepository(session, publisher).publish(
            key or uuid4().hex, record.scope, (submission,), created_at=now
        )


def test_pg_single_event_bundle_keeps_permanent_span_and_watch(context_identity):
    engine = context_identity[0]
    fact = seed_fact(engine, "A synthetic source directly reports a fact.")
    public_epochs(engine)
    result = bundle(context_identity, events=(UUID(fact["event_id"]),))
    assert result.citations[0].evidence_id == UUID(fact["evidence_id"])
    assert result.bindings[0].claim_id == UUID(fact["claim_id"])
    assert result.partial is False and result.generation_status == "not_run"
    assert dict(result.scope_watch.scope_epochs) == {"public": 1, "tenant:tenant-a": 1}


def test_pg_event_scope_does_not_admit_other_event(context_identity):
    engine = context_identity[0]
    allowed = seed_fact(engine, "Allowed synthetic fact.")
    other = seed_fact(engine, "Another public fact outside the selected event.")
    public_epochs(engine)
    result = bundle(context_identity, events=(UUID(allowed["event_id"]),))
    assert {citation.evidence_id for citation in result.citations} == {UUID(allowed["evidence_id"])}
    assert UUID(other["evidence_id"]) not in {citation.evidence_id for citation in result.citations}


@pytest.mark.parametrize("historical_field", ["known_at", "valid_at"])
def test_pg_history_never_substitutes_current_evidence(context_identity, historical_field):
    engine = context_identity[0]
    fact = seed_fact(engine, "A current synthetic fact that cannot prove a historical answer.")
    public_epochs(engine)
    result = bundle(
        context_identity,
        events=(UUID(fact["event_id"]),),
        **{historical_field: datetime.now(UTC) - timedelta(days=10)},
    )
    assert result.citations == () and result.paths == ()
    assert "temporal_bundle_not_configured" in {gap.reason_code for gap in result.gaps}
    assert result.partial


def test_pg_future_claim_availability_is_not_in_bundle(context_identity):
    engine = context_identity[0]
    fact = seed_fact(
        engine, "A synthetic future fact.", available_at=datetime.now(UTC) + timedelta(days=1)
    )
    public_epochs(engine)
    result = bundle(context_identity, events=(UUID(fact["event_id"]),))
    assert result.citations == ()
    assert "no_current_supported_evidence" in {gap.reason_code for gap in result.gaps}


def test_pg_dispute_and_refute_are_preserved(context_identity):
    engine = context_identity[0]
    fact = seed_fact(engine, "A synthetic disputed statement.")
    with engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == fact["claim_id"])
            .values(claim_status="disputed")
        )
        connection.execute(
            update(claim_evidence)
            .where(claim_evidence.c.claim_id == fact["claim_id"])
            .values(support_kind="refutes")
        )
    public_epochs(engine)
    result = bundle(context_identity, events=(UUID(fact["event_id"]),))
    assert result.bindings[0].claim_status == "disputed"
    assert result.bindings[0].support_kind == "refutes"
    assert "conflicting_evidence" in {gap.reason_code for gap in result.gaps}
    assert result.partial


def test_pg_unverified_support_does_not_become_supported_answer(context_identity):
    engine = context_identity[0]
    fact = seed_fact(engine, "An existence-verified quote with unverified support.")
    with engine.begin() as connection:
        connection.execute(
            update(claim_evidence)
            .where(claim_evidence.c.claim_id == fact["claim_id"])
            .values(validation_status="unverified")
        )
    public_epochs(engine)
    result = bundle(context_identity, events=(UUID(fact["event_id"]),))
    assert result.bindings[0].validation_status == "unverified"
    assert {"support_not_validated", "no_current_supported_evidence"} <= {
        gap.reason_code for gap in result.gaps
    }


def test_pg_legal_source_withdrawal_removes_all_old_quotes(context_identity):
    engine = context_identity[0]
    fact = seed_fact(engine, "Synthetic source contains a withdrawal statement.")
    public_epochs(engine)
    receipt = legal_publication(engine, fact, predicate="source_status", value="withdrawn")
    assert receipt.epoch == 2
    result = bundle(context_identity, events=(UUID(fact["event_id"]),))
    assert result.citations == () and result.bindings == ()
    assert "source_withdrawn" in {gap.reason_code for gap in result.gaps}


def test_pg_required_paths_and_slots_are_explicit_gaps(context_identity):
    engine = context_identity[0]
    fact = seed_fact(engine, "Synthetic component name, without versions or mitigation.")
    public_epochs(engine)
    result = bundle(
        context_identity, events=(UUID(fact["event_id"]),), question="版本影响修复与机制标准"
    )
    reasons = {gap.reason_code for gap in result.gaps}
    assert {
        "assessment_not_configured",
        "standard_relation_not_configured",
        "version_impact_fix_path_not_configured",
        "required_version_evidence_missing",
        "required_fix_evidence_missing",
        "required_mechanism_evidence_missing",
    } <= reasons
    assert result.paths == () and result.partial


def test_pg_empty_unbound_query_has_scope_watch_and_no_false_clean(context_identity):
    public_epochs(context_identity[0])
    result = bundle(context_identity)
    assert result.citations == () and result.partial
    assert len(result.scope_watch.query_sha256) == 64
    assert dict(result.scope_watch.scope_epochs)["public"] == 1
    assert "corpus_retrieval_not_configured" in {gap.reason_code for gap in result.gaps}


def test_pg_legal_publication_after_final_rows_invalidates_bundle(context_identity, monkeypatch):
    engine = context_identity[0]
    fact = seed_fact(engine, "Synthetic source fact for a legal publication window.")
    public_epochs(engine)
    original = evidence_bundle.read_scope_epochs
    receipts = []

    def publish_before_final_epoch(session, scope, *, lock=False):
        if lock:
            receipts.append(legal_publication(engine, fact))
        return original(session, scope, lock=lock)

    monkeypatch.setattr(evidence_bundle, "read_scope_epochs", publish_before_final_epoch)
    result = bundle(context_identity, events=(UUID(fact["event_id"]),))
    assert receipts[0].epoch == 2
    assert result.citations == () and result.partial
    assert "scope_changed_during_bundle" in {gap.reason_code for gap in result.gaps}


def test_pg_quote_integrity_failure_is_not_an_empty_success(context_identity):
    engine = context_identity[0]
    fact = seed_fact(engine, "Synthetic exact quote.")
    with engine.begin() as connection:
        connection.execute(
            update(evidence)
            .where(evidence.c.evidence_id == fact["evidence_id"])
            .values(quote="Synthetic forged quote.")
        )
    public_epochs(engine)
    with pytest.raises(
        Exception, match=r"evidence integrity|evidence coordinates|evidence_integrity"
    ):
        bundle(context_identity, events=(UUID(fact["event_id"]),))
