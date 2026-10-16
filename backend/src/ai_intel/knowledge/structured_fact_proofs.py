"""Read saved source reports without turning them into applicability or freshness claims."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import get_ident
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, HttpUrl, ValidationError, model_validator
from sqlalchemy import and_, event, or_, select
from sqlalchemy.engine import Connection, ExecutionContext, RowMapping
from sqlalchemy.engine.interfaces import DBAPICursor
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.api.actor_references import ActorReference, lock_actor_reference_scope
from ai_intel.api.document_read_service import sources
from ai_intel.api.knowledge_contracts import DataMode, EvidenceResponse
from ai_intel.api.knowledge_read_service import KnowledgeReadService, safe_source_uri
from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.domain.enrichment_values import CvssSignalValue
from ai_intel.domain.enums import ClaimOrigin, ClaimStatus, ConditionValue, FreshnessStatus
from ai_intel.domain.records import ClaimRecord, StrictRecord
from ai_intel.domain.values import UtcTimestamp, VisibilityScope
from ai_intel.enrichment.contracts import CandidateEvidence, EnrichmentContext, EnrichmentDocument
from ai_intel.enrichment.inputs import (
    MAX_DOCUMENT_BYTES,
    MAX_INPUT_BYTES,
    _load_document,
    _require_input_scopes,
)
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.minio_store import ObjectStoreUnavailableError
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    evidence,
    scope_epochs,
    text_blocks,
)
from ai_intel.knowledge.persistence import KnowledgeRepository
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.knowledge.revision_mode import homogeneous_revision_mode

MAX_FACTS = 8
MAX_FACT_SOURCES = 8
MAX_FACT_EVIDENCE = 8
PROOF_RULE_VERSION: Literal["r07-structured-fact-proof-1"] = "r07-structured-fact-proof-1"
REPORT_LIMITATIONS = (
    "仅证明该保存版本的来源报告此值，不证明资产适用性、风险、入侵或安全。",
    "原条件、事实状态和新鲜度独立保留；来源支持不把 unknown 变为 true/current。",
    "CVSS 数值与向量是来源报告，未独立重算评分。",
)
SUPPORTED_FACT_DIMENSIONS = {
    "cvss_signal": "cvss",
    "epss_signal": "epss",
    "kev_signal": "kev",
}
OWNER_PATHS = {
    "cvss_signal": frozenset({"/cve/id", "/cve_id", "/ghsa_id"}),
    "epss_signal": frozenset({"/response/data/0/cve"}),
    "kev_signal": frozenset({"/response/vulnerabilities/0/cveID"}),
}


class StructuredFactProofRequest(StrictRecord):
    event_id: UUID
    evidence_id: UUID
    revision_id: UUID


class SourceReportedFact(StrictRecord):
    """A source-version report keeps every original state and its primary ownership fence."""

    record: ClaimRecord
    event_id: UUID
    source_id: UUID
    document_id: UUID
    revision_id: UUID
    primary_assertion_id: UUID | None
    primary_assertion_path: Annotated[str, Field(max_length=2000)] | None
    content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_uri: HttpUrl | None
    source_version: Annotated[str, Field(max_length=200)] | None
    source_observed_at: UtcTimestamp | None
    provenance_status: Literal["source_verified", "legacy_unverified"]
    claim_is_current: Annotated[bool, Field(strict=True)]
    revision_is_current: Annotated[bool, Field(strict=True)]
    report_support: Literal["verified", "unverified"]
    supporting_evidence: tuple[EvidenceResponse, ...] = Field(default=(), max_length=8)
    missing_requirements: tuple[str, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def require_verified_source_report(self) -> SourceReportedFact:
        if self.report_support == "verified" and (
            self.record.schema_version != 3
            or self.record.predicate not in SUPPORTED_FACT_DIMENSIONS
            or self.record.claim_status != ClaimStatus.SUPPORTED
            or self.record.claim_origin
            not in {
                ClaimOrigin.SOURCE_EXPLICIT,
                ClaimOrigin.STRUCTURED_SOURCE,
                ClaimOrigin.HUMAN_CONFIRMED,
            }
            or self.record.subject not in {str(self.event_id), "event:" + str(self.event_id)}
            or self.record.freshness == FreshnessStatus.STALE
            or self.record.condition_value == ConditionValue.CONFLICT
            or self.provenance_status != "source_verified"
            or not self.claim_is_current
            or not self.revision_is_current
            or self.primary_assertion_id is None
            or not self.primary_assertion_path
            or not self.supporting_evidence
            or any(item.revision_id != self.revision_id for item in self.supporting_evidence)
        ):
            raise ValueError("verified source report requires its full original state fence")
        return self


class StructuredFactProofRead(StrictRecord):
    """Internal read projection, never a published fact or a replacement graph relation."""

    schema_version: Literal[1] = 1
    request: StructuredFactProofRequest
    status: Literal["reported", "partial", "not_found"]
    facts: tuple[SourceReportedFact, ...] = Field(default=(), max_length=8)
    missing_requirements: tuple[str, ...] = Field(default=(), max_length=64)
    conflicts: tuple[UUID, ...] = Field(default=(), max_length=8)
    scope_epochs: tuple[tuple[str, int], ...] = Field(default=(), max_length=2)
    input_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    read_rule_version: Literal["r07-structured-fact-proof-1"] = PROOF_RULE_VERSION
    data_mode: DataMode
    limitations: tuple[str, ...] = REPORT_LIMITATIONS

    @model_validator(mode="after")
    def require_reported_facts(self) -> StructuredFactProofRead:
        if self.status == "reported" and (
            not self.facts
            or self.conflicts
            or any(fact.report_support != "verified" for fact in self.facts)
        ):
            raise ValueError("reported requires bounded verified reports without conflicts")
        if self.status == "not_found" and self.facts:
            raise ValueError("not_found cannot contain reported facts")
        if any(
            fact.event_id != self.request.event_id
            or fact.revision_id != self.request.revision_id
            or (
                fact.report_support == "verified"
                and self.request.evidence_id
                not in {evidence.span_id for evidence in fact.supporting_evidence}
            )
            for fact in self.facts
        ):
            raise ValueError("fact proof identity differs from its bounded request")
        return self


class StructuredFactProofChangedError(RuntimeError):
    """Changed rows, ACL or epochs invalidate a read instead of certifying stale evidence."""


class _LinkedFactEvidence(StrictRecord):
    evidence_id: UUID
    evidence: CandidateEvidence
    support_kind: Literal["supports", "refutes", "context"]
    validation_status: Literal["validated", "unverified", "rejected"]
    supports_claim: Annotated[bool, Field(strict=True)]


def _evidence_key(span: CandidateEvidence) -> tuple[object, ...]:
    return (
        span.revision_id,
        span.block_id,
        span.start_offset,
        span.end_offset,
        span.quote_text,
        span.quote_sha256,
    )


def _verify_source_report(
    record: ClaimRecord,
    primary_document: EnrichmentDocument,
    linked_evidence: tuple[_LinkedFactEvidence, ...],
    identifiers: tuple[tuple[str, str], ...],
    primary_assertion_path: str,
) -> tuple[tuple[UUID, ...], tuple[str, ...]]:
    """Recompute one source value, requiring this claim's exact owner and qualifier spans."""
    dimension = SUPPORTED_FACT_DIMENSIONS.get(record.predicate)
    if record.predicate == "weakness":
        return (), ("cwe_owner_evidence_missing",)
    if dimension is None:
        return (), ("unsupported_typed_fact",)
    if record.claim_origin not in {
        ClaimOrigin.SOURCE_EXPLICIT,
        ClaimOrigin.STRUCTURED_SOURCE,
        ClaimOrigin.HUMAN_CONFIRMED,
    }:
        return (), ("unsupported_claim_origin",)
    if record.claim_status != ClaimStatus.SUPPORTED:
        return (), ("claim_" + record.claim_status.value,)
    owner_paths = OWNER_PATHS[record.predicate]
    owner_values = {value for kind, value in identifiers if kind in {"cve", "ghsa"}}
    blocks_by_id = {block.block_id: block for block in primary_document.blocks}
    usable = {
        _evidence_key(link.evidence): link.evidence_id
        for link in linked_evidence
        if link.support_kind == "supports"
        and link.validation_status == "validated"
        and link.supports_claim
        and link.evidence.revision_id == primary_document.revision_id
    }
    owns_event = any(
        blocks_by_id[link.evidence.block_id].json_pointer in owner_paths
        and link.evidence.quote_text in owner_values
        and _evidence_key(link.evidence) in usable
        for link in linked_evidence
        if link.evidence.block_id in blocks_by_id
    )
    if not owns_event:
        same_owner_present = any(
            block.json_pointer in owner_paths
            and any(block.text == block.json_pointer + ": " + value for value in owner_values)
            for block in primary_document.blocks
        )
        reason = "owner_evidence_missing" if same_owner_present else "source_owner_mismatch"
        return (), (reason,)
    try:
        event_id = UUID(record.subject.removeprefix("event:"))
        context = EnrichmentContext(
            event_id=event_id,
            expected_event_version=1,
            revision_ids=(primary_document.revision_id,),
            external_cve_ids=tuple(value for kind, value in identifiers if kind == "cve"),
            rule_version=PROOF_RULE_VERSION,
        )
        attempt = next(
            item
            for item in enrich_structured_fields(context, (primary_document,))
            if item.dimension == dimension
        )
    except (ValueError, ValidationError):
        return (), ("source_value_mismatch",)
    matches = tuple(
        candidate for candidate in attempt.candidates if candidate.value == record.object_value
    )
    if not matches:
        return (), ("source_value_mismatch",)
    for candidate in matches:
        keys = tuple(_evidence_key(span) for span in candidate.evidence)
        if all(key in usable for key in keys):
            primary_block = blocks_by_id.get(candidate.evidence[0].block_id)
            if primary_block is None or primary_block.json_pointer != primary_assertion_path:
                return (), ("primary_assertion_path_mismatch",)
            return tuple(usable[key] for key in keys), ()
    return (), ("qualifier_evidence_missing",)


@dataclass(frozen=True)
class _FactInputs:
    event_row: RowMapping
    claim_rows: tuple[RowMapping, ...]
    assertions: tuple[RowMapping, ...]
    links: tuple[RowMapping, ...]
    parents: tuple[RowMapping, ...]
    associations: tuple[RowMapping, ...]
    blocks: tuple[RowMapping, ...]
    dimensions: tuple[RowMapping, ...]
    identifiers: tuple[tuple[str, str], ...]
    epochs: tuple[tuple[str, int], ...]
    truncated: bool

    def fingerprint(self) -> str:
        payload = {
            "event": dict(self.event_row),
            "claims": [dict(row) for row in self.claim_rows],
            "assertions": [dict(row) for row in self.assertions],
            "links": [dict(row) for row in self.links],
            "parents": [dict(row) for row in self.parents],
            "associations": [dict(row) for row in self.associations],
            "blocks": [dict(row) for row in self.blocks],
            "dimensions": [dict(row) for row in self.dimensions],
            "identifiers": self.identifiers,
            "epochs": self.epochs,
            "truncated": self.truncated,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()


class StructuredFactProofReader:
    """Use one caller-owned connection, fixed source objects and two short authority fences.

    Object reads hold no actor/source row locks. The second transaction locks and rereads
    every used input before returning. This port never writes facts or acquires a connection.
    """

    def __init__(
        self,
        connection: Connection,
        actor_reference: ActorReference,
        access_scope: AccessScope,
        content_store: ContentStorage,
        data_mode: DataMode,
    ) -> None:
        if connection.dialect.name != "postgresql" or not isinstance(
            actor_reference, ActorReference
        ):
            raise ValueError("server actor and connected PostgreSQL reader required")
        if not isinstance(access_scope, AccessScope) or data_mode not in {"fixture", "live"}:
            raise ValueError("current server access scope and explicit data mode required")
        self.connection = connection
        self.actor_reference = actor_reference
        self.scope = access_scope
        self.content_store = content_store
        self.data_mode = data_mode
        self._owner_thread = get_ident()

    def _visible(self, relation: FromClause) -> ColumnElement[bool]:
        public = and_(relation.c.visibility == "public", relation.c.tenant_id.is_(None))
        if self.scope.tenant_id is None or READ_ASSET not in self.scope.permissions:
            return public
        return or_(
            public,
            and_(relation.c.visibility == "tenant", relation.c.tenant_id == self.scope.tenant_id),
        )

    def _authorize(self) -> None:
        try:
            current = lock_actor_reference_scope(
                self.connection, self.actor_reference, datetime.now(UTC)
            )
        except PermissionError:
            raise CrossTenantAccessError("resource_unavailable") from None
        if current != self.scope:
            raise CrossTenantAccessError("resource_unavailable")
        current.requires(READ_PUBLIC)

    def _read_inputs(self, session: Session, request: StructuredFactProofRequest) -> _FactInputs:
        event_row = (
            session.execute(
                select(events).where(
                    events.c.event_id == str(request.event_id), self._visible(events)
                )
            )
            .mappings()
            .first()
        )
        if event_row is None:
            raise CrossTenantAccessError("resource_unavailable")
        parent_join = (
            document_revisions.join(documents)
            .join(sources, sources.c.source_id == documents.c.source_id)
            .join(
                content_objects, content_objects.c.content_hash == document_revisions.c.content_hash
            )
        )
        requested_parent = session.execute(
            select(document_revisions.c.revision_id)
            .select_from(
                evidence.join(
                    parent_join, evidence.c.revision_id == document_revisions.c.revision_id
                )
            )
            .where(
                evidence.c.evidence_id == str(request.evidence_id),
                evidence.c.revision_id == str(request.revision_id),
                self._visible(evidence),
                self._visible(document_revisions),
                self._visible(documents),
                self._visible(sources),
                documents.c.kind != "asset_inventory",
            )
        ).first()
        if requested_parent is None:
            raise CrossTenantAccessError("resource_unavailable")
        rows = tuple(
            session.execute(
                select(claims)
                .join(claim_evidence, claim_evidence.c.claim_id == claims.c.claim_id)
                .join(event_documents, event_documents.c.revision_id == claims.c.source_revision_id)
                .where(
                    event_documents.c.event_id == str(request.event_id),
                    claim_evidence.c.evidence_id == str(request.evidence_id),
                    claims.c.source_revision_id == str(request.revision_id),
                    claims.c.subject.in_((str(request.event_id), "event:" + str(request.event_id))),
                    claims.c.schema_version == 3,
                    self._visible(claims),
                )
                .distinct()
                .order_by(claims.c.claim_id)
                .limit(MAX_FACTS + 1)
            ).mappings()
        )
        selected = rows[:MAX_FACTS]
        assertions: list[RowMapping] = []
        links: list[RowMapping] = []
        revision_ids = {str(request.revision_id)}
        for row in selected:
            own_assertions = tuple(
                session.execute(
                    select(claim_assertions)
                    .where(claim_assertions.c.claim_id == row["claim_id"])
                    .order_by(claim_assertions.c.assertion_id)
                    .limit(MAX_FACT_SOURCES + 1)
                ).mappings()
            )
            own_links = tuple(
                session.execute(
                    select(
                        claim_evidence.c.claim_id,
                        claim_evidence.c.support_kind,
                        claim_evidence.c.validation_status,
                        evidence,
                    )
                    .join(evidence, evidence.c.evidence_id == claim_evidence.c.evidence_id)
                    .where(claim_evidence.c.claim_id == row["claim_id"])
                    .order_by(evidence.c.evidence_id)
                    .limit(MAX_FACT_EVIDENCE + 1)
                ).mappings()
            )
            if len(own_assertions) > MAX_FACT_SOURCES or len(own_links) > MAX_FACT_EVIDENCE:
                raise ValueError("fact_proof_input_limit_exceeded")
            for link in own_links:
                if link["visibility"] == "tenant" and (
                    READ_ASSET not in self.scope.permissions
                    or link["tenant_id"] != self.scope.tenant_id
                ):
                    raise CrossTenantAccessError("resource_unavailable")
            assertions.extend(own_assertions)
            links.extend(own_links)
            revision_ids.update(item["revision_id"] for item in (*own_assertions, *own_links))
        if len(revision_ids) > MAX_FACT_SOURCES:
            raise ValueError("fact_proof_input_limit_exceeded")
        event_scope = VisibilityScope(
            visibility=event_row["visibility"], tenant_id=event_row["tenant_id"]
        )
        try:
            _require_input_scopes(session, self.scope, event_scope, tuple(sorted(revision_ids)))
        except ValueError:
            raise CrossTenantAccessError("resource_unavailable") from None
        parents = tuple(
            session.execute(
                select(
                    document_revisions,
                    documents.c.kind,
                    documents.c.source_id,
                    sources.c.category,
                    content_objects.c.size_bytes,
                )
                .select_from(parent_join)
                .where(
                    document_revisions.c.revision_id.in_(revision_ids),
                    self._visible(document_revisions),
                    self._visible(documents),
                    self._visible(sources),
                )
                .order_by(document_revisions.c.revision_id)
                .limit(MAX_FACT_SOURCES + 1)
            ).mappings()
        )
        if {row["revision_id"] for row in parents} != revision_ids:
            raise CrossTenantAccessError("resource_unavailable")
        associations = tuple(
            session.execute(
                select(event_documents)
                .where(
                    event_documents.c.event_id == str(request.event_id),
                    event_documents.c.revision_id.in_(revision_ids),
                )
                .order_by(event_documents.c.revision_id)
                .limit(MAX_FACT_SOURCES + 1)
            ).mappings()
        )
        parent_by_revision = {row["revision_id"]: row for row in parents}
        for assertion in assertions:
            if parent_by_revision[assertion["revision_id"]]["source_id"] != assertion["source_id"]:
                raise CrossTenantAccessError("resource_unavailable")
        blocks: list[RowMapping] = []
        for revision_id in sorted(revision_ids):
            blocks.extend(
                session.execute(
                    select(text_blocks)
                    .where(text_blocks.c.revision_id == revision_id)
                    .order_by(text_blocks.c.ordinal)
                    .limit(201)
                ).mappings()
            )
        dimensions = tuple(
            session.execute(
                select(enrichment_results)
                .where(
                    enrichment_results.c.event_id == str(request.event_id),
                    enrichment_results.c.is_current.is_(True),
                )
                .order_by(enrichment_results.c.dimension)
                .limit(MAX_FACTS + 1)
            ).mappings()
        )
        identifier_rows = tuple(
            session.execute(
                select(event_external_ids.c.id_type, event_external_ids.c.id_value)
                .where(
                    event_external_ids.c.event_id == str(request.event_id),
                    event_external_ids.c.scope_key == event_row["scope_key"],
                )
                .order_by(event_external_ids.c.id_type, event_external_ids.c.id_value)
                .limit(MAX_FACTS + 1)
            )
        )
        if len(identifier_rows) > MAX_FACTS:
            raise ValueError("fact_proof_input_limit_exceeded")
        identifiers: list[tuple[str, str]] = []
        for kind, value in identifier_rows:
            if not isinstance(kind, str) or not isinstance(value, str):
                raise ValueError("invalid_event_identifier")
            identifiers.append((kind, value))
        keys = ["public"]
        if self.scope.tenant_id is not None and READ_ASSET in self.scope.permissions:
            keys.append("tenant:" + self.scope.tenant_id)
        epoch_rows = tuple(
            session.execute(
                select(scope_epochs.c.scope_key, scope_epochs.c.epoch)
                .where(scope_epochs.c.scope_key.in_(keys))
                .order_by(scope_epochs.c.scope_key)
            )
        )
        epochs: list[tuple[str, int]] = []
        for key, epoch in epoch_rows:
            if not isinstance(key, str) or not isinstance(epoch, int) or isinstance(epoch, bool):
                raise ValueError("invalid_scope_epoch")
            epochs.append((key, epoch))
        return _FactInputs(
            event_row,
            selected,
            tuple(assertions),
            tuple(links),
            parents,
            associations,
            tuple(blocks),
            dimensions,
            tuple(identifiers),
            tuple(epochs),
            len(rows) > MAX_FACTS,
        )

    def _lock_inputs(
        self, session: Session, request: StructuredFactProofRequest, inputs: _FactInputs
    ) -> None:
        for relation, key, identifiers in (
            (sources, sources.c.source_id, {row["source_id"] for row in inputs.parents}),
            (documents, documents.c.document_id, {row["document_id"] for row in inputs.parents}),
            (
                document_revisions,
                document_revisions.c.revision_id,
                {row["revision_id"] for row in inputs.parents},
            ),
            (events, events.c.event_id, {str(request.event_id)}),
            (claims, claims.c.claim_id, {row["claim_id"] for row in inputs.claim_rows}),
            (
                evidence,
                evidence.c.evidence_id,
                {str(request.evidence_id), *(row["evidence_id"] for row in inputs.links)},
            ),
            (text_blocks, text_blocks.c.block_id, {row["block_id"] for row in inputs.blocks}),
            (
                claim_assertions,
                claim_assertions.c.assertion_id,
                {row["assertion_id"] for row in inputs.assertions},
            ),
            (
                enrichment_results,
                enrichment_results.c.result_id,
                {row["result_id"] for row in inputs.dimensions},
            ),
            (scope_epochs, scope_epochs.c.scope_key, {key for key, _ in inputs.epochs}),
        ):
            session.execute(
                select(key)
                .select_from(relation)
                .where(key.in_(sorted(identifiers)))
                .order_by(key)
                .with_for_update(read=True)
            ).all()
        for claim_row in inputs.claim_rows:
            locked_links = session.execute(
                select(claim_evidence.c.claim_id, claim_evidence.c.evidence_id)
                .where(claim_evidence.c.claim_id == claim_row["claim_id"])
                .order_by(claim_evidence.c.evidence_id)
                .limit(MAX_FACT_EVIDENCE + 1)
                .with_for_update(read=True)
            ).all()
            if len(locked_links) > MAX_FACT_EVIDENCE:
                raise ValueError("fact_proof_input_limit_exceeded")
        session.execute(
            select(event_documents)
            .where(
                event_documents.c.event_id == str(request.event_id),
                event_documents.c.revision_id.in_([row["revision_id"] for row in inputs.parents]),
            )
            .order_by(event_documents.c.revision_id)
            .limit(MAX_FACT_SOURCES + 1)
            .with_for_update(read=True)
        ).all()

    def _project(
        self,
        session: Session,
        request: StructuredFactProofRequest,
        inputs: _FactInputs,
        loaded: dict[str, EnrichmentDocument],
        load_errors: dict[str, str],
    ) -> StructuredFactProofRead:
        facts: list[SourceReportedFact] = []
        conflicts: list[UUID] = []
        missing = ["fact_query_truncated"] if inputs.truncated else []
        parent_by_revision = {row["revision_id"]: row for row in inputs.parents}
        active_associations = {row["revision_id"] for row in inputs.associations if row["active"]}
        blocks_by_id = {row["block_id"]: row for row in inputs.blocks}
        for row in inputs.claim_rows:
            record = KnowledgeRepository(session, self.scope).get_claim(row["claim_id"])
            primary = parent_by_revision[row["source_revision_id"]]
            own_assertions = tuple(
                item for item in inputs.assertions if item["claim_id"] == row["claim_id"]
            )
            primary_assertions = tuple(
                item for item in own_assertions if item["revision_id"] == row["source_revision_id"]
            )
            own_links = tuple(item for item in inputs.links if item["claim_id"] == row["claim_id"])
            gaps: list[str] = []
            if row["source_revision_id"] not in active_associations:
                gaps.append("event_document_withdrawn")
            if len(primary_assertions) != 1:
                gaps.append("primary_assertion_missing_or_ambiguous")
            elif isinstance(record.object_value, CvssSignalValue) and (
                primary_assertions[0]["scoring_authority"] != record.object_value.authority
            ):
                gaps.append("scoring_authority_mismatch")
            if any(item["assertion_kind"] != record.claim_origin.value for item in own_assertions):
                gaps.append("assertion_origin_mismatch")
            if row["provenance_status"] != "source_verified":
                gaps.append("source_provenance_unverified")
            if record.scope != VisibilityScope(
                visibility=inputs.event_row["visibility"], tenant_id=inputs.event_row["tenant_id"]
            ):
                gaps.append("fact_event_scope_mismatch")
            if not row["is_current"] or not primary["is_current"]:
                gaps.append("historical_fact_or_revision")
            if record.freshness == FreshnessStatus.STALE:
                gaps.append("fact_stale")
            if record.claim_status != ClaimStatus.SUPPORTED:
                gaps.append("claim_" + record.claim_status.value)
            if record.condition_value == ConditionValue.CONFLICT:
                gaps.append("condition_conflict")
                conflicts.append(UUID(row["claim_id"]))
            if record.claim_status == ClaimStatus.DISPUTED:
                conflicts.append(UUID(row["claim_id"]))
            if inputs.event_row["status"] != "active":
                gaps.append("event_not_active")
            for dimension in inputs.dimensions:
                identifiers = dimension["claim_ids"]
                if not isinstance(identifiers, list) or len(identifiers) > 1000:
                    raise ValueError("invalid_dimension_claim_references")
                if row["claim_id"] in identifiers and dimension["status"] == "conflict":
                    gaps.append("dimension_conflict")
                    conflicts.append(UUID(row["claim_id"]))
            verified_ids: tuple[UUID, ...] = ()
            projections: dict[UUID, EvidenceResponse] = {}
            document = loaded.get(row["source_revision_id"])
            if record.predicate == "weakness":
                gaps.append("cwe_owner_evidence_missing")
            elif record.predicate not in SUPPORTED_FACT_DIMENSIONS:
                gaps.append("unsupported_typed_fact")
            elif row["source_revision_id"] in load_errors:
                gaps.append(load_errors[row["source_revision_id"]])
            elif document is None:
                gaps.append("source_document_unavailable")
            if not gaps and document is not None:
                linked: list[_LinkedFactEvidence] = []
                for link in own_links:
                    block = blocks_by_id.get(link["block_id"])
                    if block is None or block["revision_id"] != link["revision_id"]:
                        gaps.append("evidence_block_unavailable")
                        break
                    declared = {item["revision_id"] for item in own_assertions}
                    if link["revision_id"] not in declared:
                        gaps.append("evidence_revision_undeclared")
                        break
                    if (
                        link["coordinate_version"] != "fulltext_unicode_v1"
                        or link["verified_at"] is None
                    ):
                        gaps.append("evidence_unverified")
                        break
                    try:
                        projection = KnowledgeReadService(
                            session, self.scope, self.data_mode
                        ).read_evidence(UUID(link["evidence_id"]))
                        span = CandidateEvidence(
                            revision_id=link["revision_id"],
                            block_id=link["block_id"],
                            start_offset=link["start_offset"] - block["start_offset"],
                            end_offset=link["end_offset"] - block["start_offset"],
                            quote_text=link["quote"],
                            quote_sha256=link["quote_sha256"],
                        )
                        linked.append(
                            _LinkedFactEvidence(
                                evidence_id=link["evidence_id"],
                                evidence=span,
                                support_kind=link["support_kind"],
                                validation_status=link["validation_status"],
                                supports_claim=link["supports_claim"],
                            )
                        )
                    except ValueError:
                        gaps.append("evidence_integrity_invalid")
                        break
                    projections[UUID(link["evidence_id"])] = projection
                if not gaps:
                    verified_ids, unmet = _verify_source_report(
                        record,
                        document,
                        tuple(linked),
                        inputs.identifiers,
                        primary_assertions[0]["json_path"],
                    )
                    gaps.extend(unmet)
                    if request.evidence_id not in verified_ids:
                        gaps.append("requested_evidence_not_supporting_report")
            facts.append(
                SourceReportedFact(
                    record=record,
                    event_id=request.event_id,
                    source_id=primary["source_id"],
                    document_id=primary["document_id"],
                    revision_id=primary["revision_id"],
                    primary_assertion_id=primary_assertions[0]["assertion_id"]
                    if len(primary_assertions) == 1
                    else None,
                    primary_assertion_path=primary_assertions[0]["json_path"]
                    if len(primary_assertions) == 1
                    else None,
                    content_sha256=primary["content_hash"],
                    source_uri=safe_source_uri(primary["canonical_uri"]),
                    source_version=document.source_version if document is not None else None,
                    source_observed_at=primary["first_observed_at"],
                    provenance_status=row["provenance_status"],
                    claim_is_current=row["is_current"],
                    revision_is_current=primary["is_current"],
                    report_support="verified" if not gaps and verified_ids else "unverified",
                    supporting_evidence=tuple(
                        projections[identifier] for identifier in verified_ids
                    )
                    if not gaps
                    else (),
                    missing_requirements=tuple(dict.fromkeys(gaps)),
                )
            )
            missing.extend(gaps)
        status: Literal["reported", "partial", "not_found"] = "not_found"
        if facts:
            status = "partial" if missing or conflicts else "reported"
        return StructuredFactProofRead(
            request=request,
            status=status,
            facts=tuple(facts),
            missing_requirements=tuple(dict.fromkeys(missing)),
            conflicts=tuple(dict.fromkeys(conflicts)),
            scope_epochs=inputs.epochs,
            input_sha256=inputs.fingerprint(),
            data_mode=self.data_mode,
        )

    def read(
        self, request: StructuredFactProofRequest, deadline_monotonic: float
    ) -> StructuredFactProofRead:
        request = StructuredFactProofRequest.model_validate(request.model_dump())
        connection = self.connection
        if (
            get_ident() != self._owner_thread
            or connection.closed
            or connection.invalidated
            or connection.in_transaction()
        ):
            raise ValueError("connected_fact_reader_unavailable")
        if not math.isfinite(deadline_monotonic) or deadline_monotonic - time.monotonic() > 5:
            raise ValueError("fact_reader_requires_original_five_second_deadline")

        def check_deadline() -> None:
            if time.monotonic() >= deadline_monotonic:
                raise TimeoutError("fact_proof_deadline_exhausted")

        def bound_statement(
            connection: Connection,
            cursor: DBAPICursor,
            statement: str,
            parameters: object,
            context: ExecutionContext,
            executemany: bool,
        ) -> None:
            check_deadline()
            milliseconds = max(1, math.floor((deadline_monotonic - time.monotonic()) * 1000))
            cursor.execute(f"SET LOCAL statement_timeout = '{milliseconds}ms'")
            cursor.execute(f"SET LOCAL lock_timeout = '{milliseconds}ms'")
            if not statement.lstrip().upper().startswith("SELECT"):
                raise ValueError("fact_reader_received_non_read_statement")

        event.listen(connection, "before_cursor_execute", bound_statement)
        try:
            connection.execution_options(isolation_level="READ COMMITTED")
            check_deadline()
            with connection.begin(), Session(bind=connection) as session:
                self._authorize()
                candidate = self._read_inputs(session, request)
                homogeneous_revision_mode(
                    tuple(row["source_metadata"] for row in candidate.parents), self.data_mode
                )
            loaded: dict[str, EnrichmentDocument] = {}
            errors: dict[str, str] = {}
            if (
                any(row["size_bytes"] > MAX_DOCUMENT_BYTES for row in candidate.parents)
                or sum(row["size_bytes"] for row in candidate.parents) > MAX_INPUT_BYTES
            ):
                errors = {
                    row["revision_id"]: "source_object_byte_limit_exceeded"
                    for row in candidate.parents
                }
            else:
                event_scope = VisibilityScope(
                    visibility=candidate.event_row["visibility"],
                    tenant_id=candidate.event_row["tenant_id"],
                )
                eligible = {
                    row["source_revision_id"]
                    for row in candidate.claim_rows
                    if row["predicate"] in SUPPORTED_FACT_DIMENSIONS
                    and row["is_current"]
                    and row["claim_status"] == "supported"
                    and row["freshness"] != "stale"
                    and any(
                        association["revision_id"] == row["source_revision_id"]
                        and association["active"]
                        for association in candidate.associations
                    )
                }
                for parent in candidate.parents:
                    if parent["revision_id"] not in eligible or not parent["is_current"]:
                        continue
                    check_deadline()
                    try:
                        with connection.begin(), Session(bind=connection) as session:
                            loaded[parent["revision_id"]] = _load_document(
                                session, self.content_store, event_scope, parent
                            )
                    except FileNotFoundError:
                        errors[parent["revision_id"]] = "source_object_missing"
                    except OSError:
                        errors[parent["revision_id"]] = "source_object_read_failed"
                    except ObjectStoreUnavailableError:
                        errors[parent["revision_id"]] = "source_object_store_unavailable"
                    except ValueError:
                        errors[parent["revision_id"]] = "source_object_or_document_invalid"
                    check_deadline()
            with connection.begin(), Session(bind=connection) as session:
                self._authorize()
                self._lock_inputs(session, request, candidate)
                current = self._read_inputs(session, request)
                homogeneous_revision_mode(
                    tuple(row["source_metadata"] for row in current.parents), self.data_mode
                )
                if current.fingerprint() != candidate.fingerprint():
                    association_only_change = (
                        replace(current, associations=candidate.associations).fingerprint()
                        == candidate.fingerprint()
                    )
                    withdrawn = any(
                        row["revision_id"] == str(request.revision_id) and not row["active"]
                        for row in current.associations
                    )
                    if not association_only_change or not withdrawn:
                        raise StructuredFactProofChangedError("fact_proof_inputs_changed")
                projected = self._project(session, request, current, loaded, errors)
                self._authorize()
                check_deadline()
                return projected
        finally:
            event.remove(connection, "before_cursor_execute", bound_statement)
