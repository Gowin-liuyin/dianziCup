"""Bounded explicit-event PG bundles with gaps; no corpus/model/rule/history fallback."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from ai_intel.answering.conversation_context import (
    SLOT_WORDS,
    scope_fingerprint,
    validate_context_integrity,
)
from ai_intel.answering.conversation_contracts import (
    AssetSnapshotReference,
    BundleGap,
    ConversationFailure,
    EvidenceBinding,
    GapSlot,
    GapState,
    QueryScopeWatch,
    QuestionEvidenceBundle,
    ResolvedQuestionContext,
)
from ai_intel.api.knowledge_contracts import CitationProjection, DataMode
from ai_intel.api.knowledge_read_service import KnowledgeReadService, sources
from ai_intel.domain.access import AccessScope, CrossTenantAccessError
from ai_intel.knowledge.models import document_revisions, documents, evidence, scope_epochs
from ai_intel.knowledge.persistence_models import claim_evidence, claims, event_documents, events
from ai_intel.retrieval.hybrid import (
    authorized_scope_keys,
    candidates_from_rows,
    lock_candidate_authorities,
    read_scope_epochs,
    visible_clause,
)

MAX_BINDINGS = 100
MAX_CITATIONS = 20


def _rows_query(scope: AccessScope, context: ResolvedQuestionContext) -> Select[tuple[object, ...]]:
    withdrawal = claims.alias("bundle_source_withdrawal")
    withdrawn = exists(
        select(withdrawal.c.claim_id).where(
            withdrawal.c.source_revision_id == document_revisions.c.revision_id,
            withdrawal.c.is_current.is_(True),
            withdrawal.c.claim_status == "supported",
            visible_clause(scope, withdrawal),
            or_(
                withdrawal.c.predicate == "source_withdrawn_at",
                (withdrawal.c.predicate == "source_status")
                & func.lower(withdrawal.c.object_value).in_(("withdrawn", "rejected")),
            ),
        )
    )
    available = func.greatest(
        evidence.c.created_at,
        evidence.c.verified_at,
        document_revisions.c.created_at,
        document_revisions.c.first_observed_at,
        document_revisions.c.ingested_at,
        documents.c.retrieved_at,
        claims.c.created_at,
        claims.c.asserted_at,
        events.c.first_seen_at,
        event_documents.c.associated_at,
    )
    authorities = (events, evidence, document_revisions, documents, sources, claims)
    fields = [
        evidence.c.evidence_id,
        document_revisions.c.revision_id,
        documents.c.document_id,
        documents.c.source_id,
        events.c.event_id,
        claims.c.claim_id,
        evidence.c.quote,
        evidence.c.locator,
        available.label("available_at"),
        claims.c.subject,
        claims.c.predicate,
        claims.c.claim_status,
        claims.c.condition_value,
        claims.c.object_value,
        claims.c.object_json,
        claim_evidence.c.support_kind,
        claim_evidence.c.validation_status,
        evidence.c.verified_at,
        evidence.c.coordinate_version,
        document_revisions.c.parse_status,
        withdrawn.label("source_withdrawn"),
    ]
    for relation in authorities:
        fields.extend(
            (
                relation.c.visibility.label(relation.name + "_visibility"),
                relation.c.tenant_id.label(relation.name + "_tenant"),
            )
        )
    return (
        select(*fields)
        .select_from(
            evidence.join(document_revisions)
            .join(documents)
            .join(sources, sources.c.source_id == documents.c.source_id)
            .join(
                event_documents, event_documents.c.revision_id == document_revisions.c.revision_id
            )
            .join(events, events.c.event_id == event_documents.c.event_id)
            .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
            .join(claims, claims.c.claim_id == claim_evidence.c.claim_id)
        )
        .where(
            *(visible_clause(scope, relation) for relation in authorities),
            events.c.event_id.in_(tuple(map(str, context.event_ids))),
            events.c.status == "active",
            event_documents.c.active.is_(True),
            document_revisions.c.is_current.is_(True),
            document_revisions.c.parse_status.in_(("parsed", "partial")),
            documents.c.kind != "asset_inventory",
            claims.c.source_revision_id == document_revisions.c.revision_id,
            claims.c.is_current.is_(True),
            claims.c.freshness == "current",
            available <= context.requested_at,
        )
        .order_by(claims.c.claim_id, evidence.c.evidence_id)
        .limit(MAX_BINDINGS + 1)
    )


def _input_digest(rows: list[RowMapping]) -> str:
    return hashlib.sha256(
        json.dumps(
            [dict(row) for row in rows],
            default=str,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def build_question_evidence(
    session: Session,
    scope: AccessScope,
    context: ResolvedQuestionContext,
    *,
    data_mode: DataMode,
    asset_references: tuple[AssetSnapshotReference, ...] = (),
) -> QuestionEvidenceBundle:
    """Caller holds authentication/conversation locks; root repeats this before answer commit.

    This slice supplies explicit-event authoritative facts, not unfiltered corpus recall.
    Empty, conflict, unavailable temporal/rule/graph seams stay explicit and watched.
    """
    if session.connection().get_isolation_level() != "READ COMMITTED":
        raise ConversationFailure("bundle_fresh_read_required", 503)
    if scope_fingerprint(scope) != context.scope_sha256:
        raise CrossTenantAccessError("resource not found")
    validate_context_integrity(context)
    if context.requested_at > datetime.now(UTC):
        raise ConversationFailure("future_context_time", 422)
    epochs = read_scope_epochs(session, scope)
    gaps: list[BundleGap] = []

    def gap(slot: GapSlot, code: str, state: GapState = "unknown", required: bool = True) -> None:
        item = BundleGap(slot=slot, reason_code=code, state=state, required=required)
        if item not in gaps:
            gaps.append(item)

    historical = context.known_at is not None or context.valid_at is not None
    if context.clarification_code is not None:
        gap("retrieval", context.clarification_code)
    if historical:
        gap("history", "temporal_bundle_not_configured", "not_configured")
    if context.mode == "investigate":
        gap("investigation", "investigation_not_configured", "not_configured")
    if not context.event_ids:
        gap("retrieval", "corpus_retrieval_not_configured", "not_configured")
    if context.asset_ids and asset_references != context.asset_snapshot_refs:
        gap("impact", "asset_snapshot_changed")
    rows: list[RowMapping] = []
    if not historical and context.event_ids and context.clarification_code is None:
        observed = list(session.execute(_rows_query(scope, context)).mappings())
        lockable = [
            row
            for row in observed[:MAX_BINDINGS]
            if row["verified_at"] is not None and row["coordinate_version"] == "fulltext_unicode_v1"
        ]
        candidates = candidates_from_rows(session, scope, lockable)
        lock_candidate_authorities(session, scope, candidates)
        rows = list(session.execute(_rows_query(scope, context)).mappings())
        if _input_digest(rows) != _input_digest(observed):
            gap("facts", "bundle_inputs_changed", "partial")
            rows = []
        if len(rows) > MAX_BINDINGS:
            gap("facts", "bundle_binding_limit", "partial")
            rows = rows[:MAX_BINDINGS]
    final_epochs = read_scope_epochs(session, scope, lock=True)
    if final_epochs != epochs:
        gap("facts", "scope_changed_during_bundle", "partial")
        rows = []
    existing_epoch_keys: set[str] = set(
        session.scalars(
            select(scope_epochs.c.scope_key).where(
                scope_epochs.c.scope_key.in_(authorized_scope_keys(scope))
            )
        )
    )
    if existing_epoch_keys != set(final_epochs):
        gap("facts", "scope_epoch_not_initialized", "partial")
    reader = KnowledgeReadService(session, scope, data_mode)
    citations: dict[UUID, CitationProjection] = {}
    bindings: list[EvidenceBinding] = []
    for row in rows:
        if row["source_withdrawn"]:
            gap("facts", "source_withdrawn")
            continue
        if row["claim_status"] in {"withdrawn", "superseded"}:
            gap("facts", "claim_no_longer_supported")
            continue
        if row["verified_at"] is None or row["coordinate_version"] != "fulltext_unicode_v1":
            gap("facts", "evidence_not_verified")
            continue
        identifier = UUID(row["evidence_id"])
        projection = reader.read_evidence(identifier)
        if projection.verified_at is None or projection.source_uri is None:
            raise ConversationFailure("bundle_evidence_integrity_unavailable", 503)
        if identifier not in citations and len(citations) >= MAX_CITATIONS:
            gap("facts", "bundle_citation_limit", "partial")
            continue
        citations[identifier] = CitationProjection(
            evidence_id=identifier,
            revision_id=projection.revision_id,
            quote=projection.quote_text,
            locator=row["locator"],
            source_uri=projection.source_uri,
        )
        bindings.append(
            EvidenceBinding(
                claim_id=UUID(row["claim_id"]),
                evidence_id=identifier,
                revision_id=projection.revision_id,
                subject=row["subject"],
                predicate=row["predicate"],
                claim_status=row["claim_status"],
                support_kind=row["support_kind"],
                validation_status=row["validation_status"],
            )
        )
        if (
            row["claim_status"] == "disputed"
            or row["support_kind"] == "refutes"
            or row["condition_value"] == "conflict"
        ):
            gap("facts", "conflicting_evidence", "conflict", required=False)
        if row["claim_status"] == "unverified" or row["validation_status"] != "validated":
            gap("facts", "support_not_validated")
        if row["parse_status"] == "partial":
            gap("facts", "source_parse_partial", "partial", required=False)
    if not any(
        item.claim_status == "supported"
        and item.support_kind == "supports"
        and item.validation_status == "validated"
        for item in bindings
    ):
        gap("facts", "no_current_supported_evidence")
    requested_slots = {
        slot for slot, pattern, _word in SLOT_WORDS if pattern.search(context.question)
    }
    supported_rows = [
        row
        for row in rows
        if not row["source_withdrawn"]
        and row["claim_status"] == "supported"
        and row["support_kind"] == "supports"
        and row["validation_status"] == "validated"
        and UUID(row["evidence_id"]) in citations
    ]
    predicates = {row["predicate"] for row in supported_rows}
    if "version" in requested_slots and not predicates.intersection(
        {"affected_versions", "version_range", "version_assertion", "fixed_version"}
    ):
        gap("version", "required_version_evidence_missing")
    if "fix" in requested_slots and not predicates.intersection(
        {"fixed_version", "fix_version", "remediation", "mitigation"}
    ):
        has_action = any(
            row["predicate"] == "version_assertion"
            and isinstance(row["object_json"], dict)
            and (row["object_json"].get("vendor_fix") or row["object_json"].get("mitigations"))
            for row in supported_rows
        )
        if not has_action:
            gap("fix", "required_fix_evidence_missing")
    if "mechanism" in requested_slots and not predicates.intersection(
        {"risk_mechanism", "atlas_mapping", "risk_summary"}
    ):
        gap("mechanism", "required_mechanism_evidence_missing")
    if context.asset_ids or "impact" in requested_slots:
        gap("impact", "assessment_not_configured", "not_configured")
    if "standard" in requested_slots:
        gap("standard", "standard_relation_not_configured", "not_configured")
    if {"version", "impact", "fix"} <= requested_slots:
        gap("impact", "version_impact_fix_path_not_configured", "not_configured")
    watch = QueryScopeWatch(
        event_ids=context.event_ids,
        asset_ids=context.asset_ids,
        known_at=context.known_at,
        valid_at=context.valid_at,
        query_sha256=context.context_sha256,
        scope_epochs=tuple(sorted(final_epochs.items())),
    )
    return QuestionEvidenceBundle(
        context_sha256=context.context_sha256,
        citations=tuple(citations.values()),
        bindings=tuple(bindings),
        paths=(),
        gaps=tuple(gaps),
        scope_watch=watch,
        input_sha256=_input_digest(rows),
        constructed_at=datetime.now(UTC),
        partial=bool(gaps),
        data_mode=data_mode,
    )
