"""Current PG facts feed the reviewed policy; neither quotes nor callers grant support."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import and_, func, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_models import assets
from ai_intel.domain.access import READ_ASSET, AccessScope, CrossTenantAccessError
from ai_intel.domain.enrichment_values import AtlasMappingValue, VersionAssertionValue
from ai_intel.domain.enums import ClaimOrigin, ClaimStatus, FreshnessStatus
from ai_intel.domain.values import UtcTimestamp
from ai_intel.enrichment.inputs import MAX_DOCUMENT_BYTES, MAX_INPUT_BYTES
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.evidence_graph import (
    EvidenceGraphReadService,
    GraphReadInputs,
    GraphSnapshot,
)
from ai_intel.knowledge.models import content_objects, document_revisions, documents, scope_epochs
from ai_intel.knowledge.persistence_models import claims, event_documents, events
from ai_intel.recommendations.contracts import (
    MAX_INPUT_EVENTS,
    RecommendationEventInput,
    SelectorEvidence,
)
from ai_intel.recommendations.service_contracts import (
    CandidateGap,
    RecommendationConflictError,
    RecommendationIntegrityError,
    SubscriptionRecord,
    content_sha256,
)


@dataclass(frozen=True)
class LoadedCandidates:
    events: tuple[RecommendationEventInput, ...]
    gaps: tuple[CandidateGap, ...]
    epochs: dict[str, int | None]
    facts_sha256: str
    partial: bool


def visible_clause(scope: AccessScope, relation: FromClause) -> ColumnElement[bool]:
    visible = and_(relation.c.visibility == "public", relation.c.tenant_id.is_(None))
    if scope.tenant_id is not None and READ_ASSET in scope.permissions:
        visible = or_(
            visible,
            and_(relation.c.visibility == "tenant", relation.c.tenant_id == scope.tenant_id),
        )
    return visible


def assessment_material(receipt: AssessmentReceipt) -> dict[str, object]:
    """Read clocks, receipt UUIDs and broad epochs cannot manufacture a new reminder."""
    return {
        "asset_id": receipt.asset_id,
        "snapshot_id": receipt.asset_snapshot_id,
        "rule": receipt.prepared.inputs.rule.model_dump(mode="json"),
        "status": receipt.status.value,
        "freshness": receipt.freshness.value,
        "result": None
        if receipt.rule_result is None
        else receipt.rule_result.model_dump(mode="json"),
        "missing": receipt.missing_requirements,
        "conflicts": receipt.conflicts,
        "sources": [item.model_dump(mode="json") for item in receipt.prepared.inputs.sources],
        "supports": [
            {
                "binding": item.binding.model_dump(mode="json"),
                "condition_sha256": item.condition_sha256,
                "claim_fingerprint": item.claim_fingerprint,
                "source_fingerprint": item.source_fingerprint,
                "review_fingerprint": item.review_fingerprint,
                "evidence": item.evidence.model_dump(mode="json"),
                "semantic_status": item.semantic_status,
            }
            for item in receipt.prepared.inputs.supports
        ],
    }


class CandidateLoader:
    """One authenticated Session, parent locks before publication, then a full fresh read."""

    def __init__(
        self,
        session: Session,
        scope: AccessScope,
        assessor: AssessmentService,
        store: ContentStorage,
        data_mode: Literal["live", "fixture"],
    ) -> None:
        self.session = session
        self.scope = scope
        self.assessor = assessor
        self.store = store
        self.reader = KnowledgeReadService(session, scope, data_mode)
        self.data_mode = data_mode
        self.verified_hashes: set[str] = set()
        self.verified_bytes = 0

    def validate_assets(self, subscription: SubscriptionRecord) -> tuple[dict[str, object], ...]:
        values: list[dict[str, object]] = []
        for asset_id in sorted(subscription.spec.asset_ids):
            self.scope.requires(READ_ASSET)
            row = (
                self.session.execute(
                    select(assets)
                    .where(
                        assets.c.asset_id == str(asset_id),
                        assets.c.tenant_id == self.scope.tenant_id,
                    )
                    .with_for_update(read=True)
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            asset = InventoryService(self.session, self.scope).read_asset(str(asset_id))
            if not asset.active:
                raise RecommendationConflictError("subscription_asset_inactive")
            values.append(asset.model_dump(mode="json"))
        return tuple(values)

    def _assessment_rows(
        self, subscription: SubscriptionRecord, event_ids: tuple[UUID, ...]
    ) -> tuple[RowMapping, ...]:
        if not subscription.spec.asset_ids:
            return ()
        ranked = (
            select(
                assessment_results,
                func.row_number()
                .over(
                    partition_by=(
                        assessment_results.c.asset_id,
                        assessment_results.c.event_id,
                        assessment_results.c.rule_id,
                    ),
                    order_by=(
                        assessment_results.c.created_at.desc(),
                        assessment_results.c.assessment_id.desc(),
                    ),
                )
                .label("_r15_rank"),
            )
            .where(
                assessment_results.c.tenant_id == self.scope.tenant_id,
                assessment_results.c.asset_id.in_(
                    str(value) for value in subscription.spec.asset_ids
                ),
                assessment_results.c.event_id.in_(str(value) for value in event_ids),
            )
            .subquery()
        )
        query = (
            select(ranked)
            .where(ranked.c._r15_rank == 1)
            .order_by(ranked.c.asset_id, ranked.c.event_id, ranked.c.rule_id)
            .limit(MAX_INPUT_EVENTS * 20 + 1)
        )
        rows: list[RowMapping] = []
        selected: set[tuple[str, str, str]] = set()
        for row in self.session.execute(query).mappings():
            key = (row["asset_id"], row["event_id"], row["rule_id"])
            if key not in selected:
                rows.append(row)
                selected.add(key)
        if len(rows) > MAX_INPUT_EVENTS * 20:
            raise RecommendationConflictError("assessment_input_budget_exceeded")
        return tuple(rows)

    def _lock_parents(
        self,
        event_ids: tuple[UUID, ...],
        graphs: tuple[GraphReadInputs, ...],
        assessment_rows: tuple[RowMapping, ...],
    ) -> None:
        """Precollect all sources before taking any publication/claim lock across events."""
        from ai_intel.api.document_read_service import sources

        revision_ids = {value for graph in graphs for value in graph.revision_ids}
        for row in assessment_rows:
            receipt = AssessmentReceipt.model_validate(row["result_payload"])
            revision_ids.update(item.revision_id for item in receipt.prepared.inputs.sources)
            revision_ids.update(receipt.prepared.inputs.active_revision_ids)
        revision_ids.update(
            self.session.scalars(
                select(event_documents.c.revision_id).where(
                    event_documents.c.event_id.in_(str(value) for value in event_ids)
                )
            )
        )
        source_ids: set[str] = set(
            self.session.scalars(
                select(documents.c.source_id)
                .join(
                    document_revisions, document_revisions.c.document_id == documents.c.document_id
                )
                .where(document_revisions.c.revision_id.in_(revision_ids))
            )
        )
        for source_id in sorted(source_ids):
            self.session.execute(
                select(func.pg_advisory_xact_lock(func.hashtextextended("source:" + source_id, 0)))
            )
        self.session.execute(
            select(sources.c.source_id)
            .where(sources.c.source_id.in_(source_ids))
            .order_by(sources.c.source_id)
            .with_for_update(read=True)
        ).all()
        self.session.execute(
            select(document_revisions.c.revision_id)
            .join(documents, documents.c.document_id == document_revisions.c.document_id)
            .where(document_revisions.c.revision_id.in_(revision_ids))
            .order_by(documents.c.document_id, document_revisions.c.revision_id)
            .with_for_update(read=True, of=(documents, document_revisions))
        ).all()
        for key in self._scope_keys():
            self.session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended("knowledge-publication:" + key, 0)
                    )
                )
            )
        current_sources: set[str] = set(
            self.session.scalars(
                select(documents.c.source_id)
                .join(
                    document_revisions, document_revisions.c.document_id == documents.c.document_id
                )
                .join(
                    event_documents,
                    event_documents.c.revision_id == document_revisions.c.revision_id,
                )
                .where(event_documents.c.event_id.in_(str(value) for value in event_ids))
            )
        )
        if not current_sources.issubset(source_ids):
            raise RecommendationConflictError("source_roster_changed_retry")

    def _scope_keys(self) -> tuple[str, ...]:
        keys = {"public"}
        if self.scope.tenant_id is not None and READ_ASSET in self.scope.permissions:
            keys.add("tenant:" + self.scope.tenant_id)
        return tuple(sorted(keys))

    def _epochs(self) -> dict[str, int | None]:
        rows: dict[str, int] = dict(
            self.session.execute(
                select(scope_epochs.c.scope_key, scope_epochs.c.epoch)
                .where(scope_epochs.c.scope_key.in_(self._scope_keys()))
                .order_by(scope_epochs.c.scope_key)
                .with_for_update(read=True)
            ).all()
        )
        return {key: rows.get(key) for key in self._scope_keys()}

    def revision_state(self, revision_id: str) -> tuple[dict[str, object], bool]:
        """Historical access rechecks all current parent ACLs before reading any bytes."""
        from ai_intel.api.document_read_service import sources

        row = (
            self.session.execute(
                select(
                    document_revisions,
                    documents.c.visibility.label("document_visibility"),
                    documents.c.tenant_id.label("document_tenant_id"),
                    sources.c.visibility.label("source_visibility"),
                    sources.c.tenant_id.label("source_tenant_id"),
                )
                .join(documents, documents.c.document_id == document_revisions.c.document_id)
                .join(sources, sources.c.source_id == documents.c.source_id)
                .where(document_revisions.c.revision_id == revision_id)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        for prefix in ("", "document_", "source_"):
            self.scope.enforce_visible(row[prefix + "visibility"], row[prefix + "tenant_id"])
            if row[prefix + "visibility"] == "tenant":
                self.scope.requires(READ_ASSET)
        for digest in {row["content_hash"], row["source_response_hash"]} - {None}:
            if digest in self.verified_hashes:
                continue
            size = self.session.scalar(
                select(content_objects.c.size_bytes).where(content_objects.c.content_hash == digest)
            )
            if (
                size is None
                or size > MAX_DOCUMENT_BYTES
                or self.verified_bytes + size > MAX_INPUT_BYTES
            ):
                raise RecommendationConflictError("source_blob_budget_exceeded")
            raw = self.store.read_verified(digest)
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
                raise RecommendationIntegrityError("source_blob_hash_mismatch")
            self.verified_bytes += size
            self.verified_hashes.add(digest)
        withdrawal = (
            self.session.execute(
                select(claims)
                .where(
                    claims.c.source_revision_id == revision_id,
                    claims.c.is_current.is_(True),
                    claims.c.claim_status == "supported",
                    visible_clause(self.scope, claims),
                    or_(
                        claims.c.predicate == "source_withdrawn_at",
                        and_(
                            claims.c.predicate == "source_status",
                            func.lower(claims.c.object_value).in_(("withdrawn", "rejected")),
                        ),
                    ),
                )
                .order_by(claims.c.claim_id)
            )
            .mappings()
            .all()
        )
        state = {
            "revision_id": revision_id,
            "content_hash": row["content_hash"],
            "response_hash": row["source_response_hash"],
            "current": row["is_current"],
            "parse_status": row["parse_status"],
            "first_observed_at": None
            if row["first_observed_at"] is None
            else row["first_observed_at"].isoformat(),
            "source_modified_at": None
            if row["source_modified_at"] is None
            else row["source_modified_at"].isoformat(),
            "withdrawals": [item["claim_id"] for item in withdrawal],
            "scope": [
                (row[prefix + "visibility"], row[prefix + "tenant_id"])
                for prefix in ("", "document_", "source_")
            ],
        }
        return state, bool(withdrawal)

    def _selectors(
        self, event_id: UUID, graph: GraphSnapshot, cutoff: datetime
    ) -> tuple[
        tuple[SelectorEvidence, ...],
        tuple[CandidateGap, ...],
        tuple[dict[str, object], ...],
        tuple[datetime, ...],
        tuple[datetime, ...],
    ]:
        selectors: list[SelectorEvidence] = []
        gaps: list[CandidateGap] = []
        revisions: dict[str, dict[str, object]] = {}
        observations: list[datetime] = []
        modifications: list[datetime] = []
        for edge in graph.edges:
            if edge.relation_type not in {"affects_component_version", "mapped_atlas"}:
                continue
            if len(edge.evidence_span_ids) > 8:
                gaps.append(
                    CandidateGap(event_id=event_id, code="selector_evidence_budget_exceeded")
                )
                continue
            citations: list[CitationProjection] = []
            unsupported = False
            for evidence_id in edge.evidence_span_ids:
                span = self.reader.read_evidence(evidence_id)
                state, withdrawn = self.revision_state(str(span.revision_id))
                revisions[str(span.revision_id)] = state
                if (
                    withdrawn
                    or not state["current"]
                    or state["parse_status"] not in {"parsed", "partial"}
                ):
                    gaps.append(
                        CandidateGap(
                            event_id=event_id,
                            code="source_withdrawn" if withdrawn else "claim_not_current",
                        )
                    )
                    unsupported = True
                if (
                    span.verified_at is None
                    or span.source_uri is None
                    or span.first_observed_at is None
                    or span.first_observed_at > cutoff
                ):
                    gaps.append(CandidateGap(event_id=event_id, code="source_time_unavailable"))
                    unsupported = True
                else:
                    observations.append(span.first_observed_at)
                    if span.source_modified_at is not None:
                        modifications.append(span.source_modified_at)
                    citations.append(
                        CitationProjection(
                            evidence_id=span.span_id,
                            revision_id=span.revision_id,
                            quote=span.quote_text,
                            locator=f"{span.locator_kind}:{span.start_offset}:{span.end_offset}",
                            source_uri=span.source_uri,
                        )
                    )
            if unsupported:
                continue
            for claim_id in edge.supporting_claim_ids:
                row = (
                    self.session.execute(
                        select(claims).where(
                            claims.c.claim_id == str(claim_id),
                            claims.c.subject == str(event_id),
                            visible_clause(self.scope, claims),
                        )
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    raise RecommendationIntegrityError("graph_claim_binding_unavailable")
                if (
                    not row["is_current"]
                    or row["freshness"] != "current"
                    or row["observed_at"] is None
                    or row["created_at"] > cutoff
                    or row["observed_at"] > cutoff
                ):
                    gaps.append(CandidateGap(event_id=event_id, code="claim_not_current"))
                    continue
                if (
                    row["claim_status"] != "supported"
                    or row["provenance_status"] != "source_verified"
                    or row["claim_origin"] == "model_hypothesis"
                ):
                    raise RecommendationIntegrityError("graph_claim_support_mismatch")
                kind: Literal["product", "risk_topic"]
                if edge.relation_type == "affects_component_version":
                    value = VersionAssertionValue.model_validate(row["object_json"])
                    kind, key = "product", value.ecosystem + ":" + value.package_key
                else:
                    atlas = AtlasMappingValue.model_validate(row["object_json"])
                    kind, key = "risk_topic", atlas.technique_id
                observations.extend((row["created_at"], row["observed_at"]))
                selectors.append(
                    SelectorEvidence(
                        selector_kind=kind,
                        selector_value=key,
                        claim_id=str(claim_id),
                        claim_status=ClaimStatus.SUPPORTED,
                        claim_origin=ClaimOrigin(row["claim_origin"]),
                        support_kind="supports",
                        validation_status="validated",
                        citations=tuple(citations),
                    )
                )
        return (
            tuple(selectors),
            tuple(gaps),
            tuple(revisions[key] for key in sorted(revisions)),
            tuple(observations),
            tuple(modifications),
        )

    def load(
        self, subscription: SubscriptionRecord, event_ids: tuple[UUID, ...], cutoff: datetime
    ) -> LoadedCandidates:
        if len(event_ids) > MAX_INPUT_EVENTS or len(set(event_ids)) != len(event_ids):
            raise ValueError("event_input_budget_or_identity_invalid")
        if not subscription.spec.enabled:
            return LoadedCandidates((), (), {}, content_sha256({"disabled": True}), False)
        asset_values = self.validate_assets(subscription)
        asset_observations = tuple(
            TypeAdapter(UtcTimestamp).validate_python(value["updated_at"]) for value in asset_values
        )
        assessment_rows = self._assessment_rows(subscription, event_ids)
        graph_inputs: list[GraphReadInputs] = []
        initial_graphs: dict[UUID, str] = {}
        for event_id in event_ids:
            graph_reader = EvidenceGraphReadService(self.session, self.scope)
            graph_reader.event_graph(event_id)
            if graph_reader.read_inputs is None or graph_reader.input_sha256 is None:
                raise RecommendationIntegrityError("graph_read_fence_unavailable")
            graph_inputs.append(graph_reader.read_inputs)
            initial_graphs[event_id] = graph_reader.input_sha256
        self._lock_parents(event_ids, tuple(graph_inputs), assessment_rows)
        self.session.execute(
            select(events.c.event_id)
            .where(
                events.c.event_id.in_(str(value) for value in event_ids),
                visible_clause(self.scope, events),
            )
            .order_by(events.c.event_id)
            .with_for_update(read=True)
        ).all()
        for graph_input in graph_inputs:
            if not any(
                (
                    graph_input.source_ids,
                    graph_input.document_ids,
                    graph_input.revision_ids,
                    graph_input.claim_ids,
                    graph_input.evidence_ids,
                    graph_input.block_ids,
                    graph_input.assertion_ids,
                    graph_input.support_pairs,
                )
            ):
                continue
            EvidenceGraphReadService(self.session, self.scope).lock_graph_inputs(
                graph_input.event_id, graph_input
            )
        epochs = self._epochs()
        results: list[RecommendationEventInput] = []
        gaps: list[CandidateGap] = []
        fingerprints: dict[str, object] = {}
        for event_id in event_ids:
            graph_reader = EvidenceGraphReadService(self.session, self.scope)
            graph = graph_reader.event_graph(event_id)
            if graph_reader.input_sha256 != initial_graphs[event_id]:
                raise RecommendationConflictError("graph_inputs_changed_retry")
            row = (
                self.session.execute(
                    select(events).where(
                        events.c.event_id == str(event_id), visible_clause(self.scope, events)
                    )
                )
                .mappings()
                .one()
            )
            if row["status"] != "active":
                gaps.append(CandidateGap(event_id=event_id, code="event_not_active"))
                fingerprints[str(event_id)] = {
                    "status": row["status"],
                    "graph": graph_reader.input_sha256,
                }
                continue
            selectors, selector_gaps, revision_states, observations, modifications = (
                self._selectors(event_id, graph, cutoff)
            )
            gaps.extend(selector_gaps)
            if graph.truncated:
                gaps.append(CandidateGap(event_id=event_id, code="graph_partial"))
            receipts: list[AssessmentReceipt] = []
            receipt_times: list[datetime] = []
            for assessment in assessment_rows:
                if assessment["event_id"] != str(event_id):
                    continue
                receipt = self.assessor._read_result(self.session, self.scope, assessment)
                if receipt.freshness != FreshnessStatus.CURRENT or receipt.created_at > cutoff:
                    gaps.append(
                        CandidateGap(
                            event_id=event_id,
                            asset_id=UUID(receipt.asset_id),
                            code="assessment_not_current",
                        )
                    )
                else:
                    receipts.append(receipt)
                    receipt_times.append(receipt.created_at)
                    if receipt.status.value in {"insufficient_evidence", "conflicting_evidence"}:
                        gaps.append(
                            CandidateGap(
                                event_id=event_id,
                                asset_id=UUID(receipt.asset_id),
                                code="consequence_selector_unavailable",
                            )
                        )
            if len(receipts) > 20:
                raise RecommendationConflictError("event_assessment_budget_exceeded")
            for asset_id in subscription.spec.asset_ids:
                if not any(receipt.asset_id == str(asset_id) for receipt in receipts):
                    gaps.append(
                        CandidateGap(
                            event_id=event_id, asset_id=asset_id, code="assessment_unavailable"
                        )
                    )
            if not selectors and not receipts:
                gaps.append(CandidateGap(event_id=event_id, code="no_current_semantic_support"))
            material = content_sha256(
                {
                    "selectors": [item.model_dump(mode="json") for item in selectors],
                    "sources": revision_states,
                    "assessments": [assessment_material(item) for item in receipts],
                    "assets": asset_values,
                }
            )
            fingerprints[str(event_id)] = {
                "material": material,
                "graph_inputs": graph_reader.input_sha256,
                "assessments": [item.input_digest for item in receipts],
            }
            available_times = (*observations, *receipt_times, *asset_observations)
            if not available_times:
                continue
            observed_at = max(available_times)
            if observed_at > cutoff:
                gaps.append(CandidateGap(event_id=event_id, code="assessment_not_current"))
                continue
            results.append(
                RecommendationEventInput(
                    event_id=str(event_id),
                    material_version=material,
                    observed_at=observed_at,
                    source_changed_at=max(modifications) if modifications else None,
                    valid_from=observed_at,
                    status_at_cutoff=ClaimStatus.SUPPORTED,
                    freshness_at_cutoff=FreshnessStatus.CURRENT,
                    current_status=ClaimStatus.SUPPORTED,
                    current_freshness=FreshnessStatus.CURRENT,
                    current_state_checked_at=datetime.now(UTC),
                    selectors=selectors,
                    assessments=tuple(receipts),
                )
            )
        return LoadedCandidates(
            tuple(results),
            tuple(dict.fromkeys(gaps)),
            epochs,
            content_sha256(fingerprints),
            any(gap.code == "graph_partial" for gap in gaps),
        )
