"""Frozen public read projections over the existing PostgreSQL services and identities."""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError
from sqlalchemy import Text, and_, column, exists, func, or_, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from ai_intel.api.knowledge_contracts import DataMode, EnrichmentProjection
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import READ_PUBLIC, AccessScope
from ai_intel.domain.enrichment_values import (
    ArtifactReferenceValue,
    EnrichmentValue,
    LiteratureReferenceValue,
    VersionAssertionValue,
)
from ai_intel.domain.enums import ClaimOrigin, SourceCategory
from ai_intel.enrichment.contracts import (
    DIMENSION_BY_VALUE_KIND,
    CandidateEvidence,
    EvidenceBoundCandidate,
)
from ai_intel.enrichment.field_sources import FieldEvidenceError, validate_field_candidate
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.knowledge.evidence_graph import DocumentCache, EvidenceGraphReadService
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    fetch_attempts,
    scope_epochs,
    source_page_receipts,
    text_blocks,
)
from ai_intel.knowledge.persistence import publication_payload_digest
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.knowledge.revision_mode import (
    RevisionModeUnavailableError,
    homogeneous_revision_mode,
)

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
ENRICHMENT_VALUE: TypeAdapter[EnrichmentValue] = TypeAdapter(EnrichmentValue)
MAX_READ_INPUTS = 2000
sources = table(
    "sources",
    column("source_id", Text),
    column("name", Text),
    column("category", Text),
    column("visibility", Text),
    column("tenant_id", Text),
)


class PublicReadUnavailable(RuntimeError):
    """A required producer binding or verifiable projection is absent."""


class InvalidPublicCursor(ValueError):
    """The page position is malformed or no longer bound to the current read scope."""


class _Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(ge=1, le=1)
    offset: int = Field(ge=1, le=MAX_READ_INPUTS)
    binding: str = Field(pattern=r"^[a-f0-9]{64}$")


def page_position(cursor: str | None, binding: str) -> int:
    if cursor is None:
        return 0
    if not 1 <= len(cursor) <= 2048 or re.fullmatch(r"[A-Za-z0-9_-]+", cursor) is None:
        raise InvalidPublicCursor("invalid public cursor")
    try:
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        parsed = _Cursor.model_validate_json(raw)
        if parsed.binding != binding or encode_page_cursor(parsed.offset, binding) != cursor:
            raise ValueError("cursor scope changed")
        return parsed.offset
    except (ValueError, binascii.Error, UnicodeError):
        raise InvalidPublicCursor("invalid public cursor") from None


def encode_page_cursor(offset: int, binding: str) -> str:
    value = _Cursor(version=1, offset=offset, binding=binding).model_dump_json()
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def validate_page_inputs(q: str | None, limit: int, cursor: str | None) -> None:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("invalid public page limit")
    if q is not None:
        if not 1 <= len(q) <= 4096 or not q.strip() or "\0" in q:
            raise ValueError("invalid public search")
        q.encode("utf-8")
    if cursor is not None and (not 1 <= len(cursor) <= 2048 or not cursor.strip()):
        raise InvalidPublicCursor("invalid public cursor")


def classify_revision_mode(metadata: object, configured: DataMode) -> DataMode:
    """Deployment mode cannot relabel an unmarked or differently marked stored source."""
    try:
        return homogeneous_revision_mode((metadata,), configured)
    except RevisionModeUnavailableError as error:
        raise PublicReadUnavailable(str(error)) from error


def derive_source_health(observations: tuple[tuple[datetime, str], ...]) -> str:
    """Only the most recent real observation controls health; equal-time disagreement is partial."""
    if not observations:
        return "never_polled"
    if any(at.tzinfo is None for at, _ in observations):
        raise ValueError("source observation time must be aware")
    latest_at = max(at for at, _ in observations)
    states = {state for at, state in observations if at == latest_at}
    return next(iter(states)) if len(states) == 1 else "partial"


class PublicExtensionReadService:
    """Public research remains public even when the authenticated caller can read assets."""

    def __init__(
        self,
        session: Session,
        scope: AccessScope,
        data_mode: DataMode,
        source_polling_enabled: bool,
    ) -> None:
        scope.requires(READ_PUBLIC)
        self.session = session
        self.scope = scope
        self.data_mode = data_mode
        self.source_polling_enabled = source_polling_enabled
        public_scope = AccessScope(
            scope.user_id,
            scope.tenant_id,
            scope.role,
            frozenset({READ_PUBLIC}),
            scope.permission_version,
        )
        self.knowledge = KnowledgeReadService(session, public_scope, data_mode)
        self.graph = EvidenceGraphReadService(session, public_scope)

    def _binding(self, operation: str, arguments: object, inputs: object) -> str:
        epochs = list(
            self.session.execute(
                select(scope_epochs.c.scope_key, scope_epochs.c.epoch)
                .where(scope_epochs.c.scope_key == "public")
                .with_for_update(read=True)
            )
        )
        return publication_payload_digest(
            [
                operation,
                arguments,
                self.scope.user_id,
                self.scope.tenant_id,
                self.scope.role.value,
                sorted(self.scope.permissions),
                self.scope.permission_version,
                self.data_mode,
                self.source_polling_enabled,
                [tuple(row) for row in epochs],
                inputs,
            ]
        )

    def _current_rows(self, event_ids: tuple[str, ...]) -> list[RowMapping]:
        rows = list(
            self.session.execute(
                select(
                    event_documents.c.event_id,
                    document_revisions,
                    documents.c.source_id,
                    documents.c.kind,
                )
                .select_from(
                    event_documents.join(document_revisions)
                    .join(documents)
                    .join(
                        sources,
                        sources.c.source_id == documents.c.source_id,
                    )
                )
                .where(
                    event_documents.c.event_id.in_(event_ids),
                    event_documents.c.active.is_(True),
                    document_revisions.c.is_current.is_(True),
                    document_revisions.c.parse_status.in_(("parsed", "partial")),
                    documents.c.kind != "asset_inventory",
                    document_revisions.c.visibility == "public",
                    document_revisions.c.tenant_id.is_(None),
                    documents.c.visibility == "public",
                    documents.c.tenant_id.is_(None),
                    sources.c.visibility == "public",
                    sources.c.tenant_id.is_(None),
                )
                .order_by(
                    document_revisions.c.created_at.desc(),
                    document_revisions.c.revision_number.desc(),
                    documents.c.document_id,
                    document_revisions.c.revision_id,
                )
                .limit(MAX_READ_INPUTS + 1)
                .with_for_update(read=True, of=(document_revisions, documents, sources))
            ).mappings()
        )
        if len(rows) > MAX_READ_INPUTS:
            raise PublicReadUnavailable("public read inputs exceed the bounded projection")
        for row in rows:
            classify_revision_mode(row["source_metadata"], self.data_mode)
        return rows

    def _citations(self, revision_id: str) -> list[JsonValue]:
        identifiers: list[str] = list(
            self.session.scalars(
                select(evidence.c.evidence_id)
                .where(
                    evidence.c.revision_id == revision_id,
                    evidence.c.visibility == "public",
                    evidence.c.tenant_id.is_(None),
                )
                .order_by(evidence.c.start_offset, evidence.c.end_offset, evidence.c.evidence_id)
                .limit(101)
                .with_for_update(read=True)
            )
        )
        if len(identifiers) > 100:
            raise PublicReadUnavailable("one complete advisory exceeds the public citation limit")
        if not identifiers:
            raise PublicReadUnavailable("advisory evidence is not configured")
        citations: list[JsonValue] = []
        for identifier in identifiers:
            item = self.knowledge.read_evidence(UUID(identifier))
            if item.verified_at is None or item.source_uri is None:
                raise PublicReadUnavailable("advisory evidence is not verified")
            locator = self.session.scalar(
                select(evidence.c.locator).where(evidence.c.evidence_id == identifier)
            )
            citations.append(
                {
                    "evidence_id": str(item.span_id),
                    "revision_id": str(item.revision_id),
                    "quote": item.quote_text,
                    "locator": str(locator),
                    "source_uri": str(item.source_uri),
                }
            )
        return citations

    def _vulnerability(
        self,
        event_id: UUID,
        current: list[RowMapping],
    ) -> tuple[dict[str, JsonValue], list[JsonValue]]:
        if not current:
            raise PublicReadUnavailable("current normalized intelligence is not configured")
        detail = self.knowledge.event_detail(event_id)
        graph = self.graph.event_graph(event_id, 200, 400)
        graph_inputs = self.graph.read_inputs
        if graph_inputs is None:
            raise PublicReadUnavailable("graph read inputs unavailable")
        self.graph.lock_graph_inputs(event_id, graph_inputs)
        revision_ids = {row["revision_id"] for row in current}
        limits: list[JsonValue] = []
        relations: list[JsonValue] = []
        for edge in graph.edges:
            if len(edge.source_revision_ids) != 1:
                limits.append("multi_revision_relation_requires_internal_graph")
                continue
            revision_id = str(edge.source_revision_ids[0])
            if revision_id not in revision_ids or len(edge.evidence_span_ids) > 100:
                raise PublicReadUnavailable("relation evidence cannot be completely mapped")
            all_citations = self._citations(revision_id)
            selected: list[JsonValue] = [
                item
                for item in all_citations
                if isinstance(item, dict)
                and item["evidence_id"] in {str(value) for value in edge.evidence_span_ids}
            ]
            if len(selected) != len(edge.evidence_span_ids):
                raise PublicReadUnavailable("relation evidence unavailable")
            relations.append(
                {
                    "relation_id": str(edge.id),
                    "relation_type": edge.relation_type,
                    "subject_id": str(edge.subject_id),
                    "object_id": str(edge.object_id),
                    "source_revision": revision_id,
                    "citations": selected,
                    "rule_or_model_version": edge.rule_or_model_version,
                    "reason": edge.reason,
                    "status": edge.status,
                }
            )
        if len(relations) > 100 or graph.truncated:
            raise PublicReadUnavailable("event relations exceed the complete public mapping")
        if graph.gaps:
            limits.append("unsupported_relations_remain_unknown")
        dimensions: list[JsonValue] = []
        supported = {str(value) for edge in graph.edges for value in edge.supporting_claim_ids}
        for item in detail.dimensions:
            value = JSON_OBJECT.validate_json(item.model_dump_json())
            if item.status.value == "available" and not self._dimension_is_supported(
                event_id,
                item,
                supported,
                revision_ids,
            ):
                value.update(
                    status="blocked", freshness="unknown", error_code="evidence_not_qualified"
                )
                limits.append("dimension_support_requires_further_validation")
            dimensions.append(value)
        freshness = (
            "stale"
            if any(item.freshness.value == "stale" for item in detail.dimensions)
            else "unknown"
        )
        vulnerability: dict[str, JsonValue] = {
            "intel_id": str(current[0]["document_id"]),
            "event_id": str(event_id),
            "title": detail.event.title,
            "external_ids": list(detail.event.external_ids),
            "enrichments": dimensions,
            "relations": relations,
            "freshness": freshness,
        }
        return vulnerability, list(dict.fromkeys(str(value) for value in limits))

    def _dimension_is_supported(
        self,
        event_id: UUID,
        dimension: EnrichmentProjection,
        graph_claim_ids: set[str],
        revision_ids: set[str],
    ) -> bool:
        claim_ids = {str(identifier) for identifier in dimension.claim_ids}
        references = {
            (str(item.evidence_id), str(item.revision_id)) for item in dimension.citations
        }
        if (
            not claim_ids
            or not references
            or dimension.freshness.value != "current"
            or not claim_ids <= graph_claim_ids
            or any(revision_id not in revision_ids for _, revision_id in references)
        ):
            return False
        rows = (
            self.session.execute(
                select(
                    claims.c.claim_id,
                    claims.c.predicate,
                    claims.c.schema_version,
                    claims.c.value_kind,
                    claims.c.object_json,
                    claims.c.claim_origin,
                    evidence.c.evidence_id,
                    evidence.c.revision_id,
                    evidence.c.block_id,
                    evidence.c.start_offset,
                    evidence.c.end_offset,
                    evidence.c.quote,
                    evidence.c.quote_sha256,
                    text_blocks.c.start_offset.label("block_start"),
                )
                .select_from(
                    claims.join(claim_evidence)
                    .join(evidence)
                    .join(
                        text_blocks,
                        and_(
                            evidence.c.block_id == text_blocks.c.block_id,
                            evidence.c.revision_id == text_blocks.c.revision_id,
                        ),
                    )
                    .join(
                        claim_assertions,
                        and_(
                            claim_assertions.c.claim_id == claims.c.claim_id,
                            claim_assertions.c.revision_id == evidence.c.revision_id,
                            claim_assertions.c.assertion_kind == claims.c.claim_origin,
                        ),
                    )
                    .join(documents, documents.c.source_id == claim_assertions.c.source_id)
                    .join(
                        document_revisions,
                        and_(
                            document_revisions.c.revision_id == evidence.c.revision_id,
                            document_revisions.c.document_id == documents.c.document_id,
                        ),
                    )
                )
                .where(
                    claims.c.claim_id.in_(claim_ids),
                    claims.c.subject == str(event_id),
                    claims.c.source_revision_id == evidence.c.revision_id,
                    claims.c.is_current.is_(True),
                    claims.c.claim_status == "supported",
                    claims.c.condition_value == "true",
                    claims.c.freshness == "current",
                    claims.c.provenance_status == "source_verified",
                    claims.c.visibility == "public",
                    claims.c.tenant_id.is_(None),
                    evidence.c.evidence_id.in_([identifier for identifier, _ in references]),
                    evidence.c.visibility == "public",
                    evidence.c.tenant_id.is_(None),
                    evidence.c.supports_claim.is_(True),
                    evidence.c.verified_at.is_not(None),
                    evidence.c.coordinate_version == "fulltext_unicode_v1",
                    document_revisions.c.revision_id.in_(revision_ids),
                    claim_evidence.c.support_kind == "supports",
                    claim_evidence.c.validation_status == "validated",
                )
                .limit(MAX_READ_INPUTS + 1)
                .with_for_update(read=True, of=(claims, claim_assertions, claim_evidence, evidence))
            )
            .mappings()
            .all()
        )
        if len(rows) > MAX_READ_INPUTS:
            return False
        supported_claims: set[str] = set()
        supported_references: set[tuple[str, str]] = set()
        claim_rows: dict[str, list[RowMapping]] = {}
        for row in rows:
            claim_id, predicate, evidence_id, revision_id = (
                row[key] for key in ("claim_id", "predicate", "evidence_id", "revision_id")
            )
            if not all(
                isinstance(value, str) for value in (claim_id, predicate, evidence_id, revision_id)
            ):
                raise PublicReadUnavailable("dimension support identity is invalid")
            if DIMENSION_BY_VALUE_KIND.get(str(predicate)) == dimension.dimension:
                supported_claims.add(str(claim_id))
                supported_references.add((str(evidence_id), str(revision_id)))
                claim_rows.setdefault(str(claim_id), []).append(row)
        if not (claim_ids <= supported_claims and references <= supported_references):
            return False
        cache: DocumentCache = {}
        return all(
            self._claim_has_declared_support(dimension, claim_rows[identifier], cache)
            for identifier in sorted(claim_ids)
        )

    def _claim_has_declared_support(
        self,
        dimension: EnrichmentProjection,
        rows: list[RowMapping],
        cache: DocumentCache,
    ) -> bool:
        """Revalidate declared spans; normalize human origin only for the proposal contract."""
        row = rows[0]
        if row["schema_version"] != 3 or row["predicate"] != row["value_kind"]:
            return False
        documents = []
        for revision_id in sorted({str(item["revision_id"]) for item in rows}):
            loaded = self.graph._load_document(UUID(revision_id), cache)
            if loaded is None:
                return False
            documents.append(loaded[0])
        try:
            candidate_origin = ClaimOrigin(row["claim_origin"])
            if candidate_origin == ClaimOrigin.HUMAN_CONFIRMED:
                candidate_origin = ClaimOrigin.SOURCE_EXPLICIT
            value = ENRICHMENT_VALUE.validate_python(row["object_json"])
            candidate_value = value
            if isinstance(value, VersionAssertionValue):
                candidate_value = value.model_copy(update={"comparison_support": "unknown"})
            elif isinstance(value, LiteratureReferenceValue):
                candidate_value = value.model_copy(
                    update={"target_document_id": None, "target_revision_id": None}
                )
            elif isinstance(value, ArtifactReferenceValue):
                candidate_value = value.model_copy(update={"static_status": "candidate_found"})
            candidate = EvidenceBoundCandidate.model_validate(
                {
                    "dimension": dimension.dimension,
                    "value": candidate_value,
                    "origin": candidate_origin,
                    "evidence": tuple(
                        CandidateEvidence(
                            revision_id=item["revision_id"],
                            block_id=item["block_id"],
                            start_offset=item["start_offset"] - item["block_start"],
                            end_offset=item["end_offset"] - item["block_start"],
                            quote_text=item["quote"],
                            quote_sha256=item["quote_sha256"],
                        )
                        for item in rows
                    ),
                }
            )
            checked = validate_field_candidate(candidate, tuple(documents))
        except (FieldEvidenceError, ValidationError, ValueError):
            return False
        if isinstance(value, LiteratureReferenceValue):
            return (
                isinstance(checked.value, LiteratureReferenceValue)
                and checked.value.target_document_id == value.target_document_id
                and checked.value.target_revision_id == value.target_revision_id
            )
        return checked.value.kind == value.kind

    def search_vulns(
        self,
        q: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, JsonValue]:
        validate_page_inputs(q, limit, cursor)
        query = select(events).where(events.c.visibility == "public", events.c.tenant_id.is_(None))
        if q is not None:
            identifier = exists(
                select(event_external_ids.c.event_id).where(
                    event_external_ids.c.event_id == events.c.event_id,
                    event_external_ids.c.scope_key == events.c.scope_key,
                    event_external_ids.c.id_value.icontains(q, autoescape=True),
                )
            )
            query = query.where(or_(events.c.title.icontains(q, autoescape=True), identifier))
        rows = list(
            self.session.execute(
                query.order_by(events.c.first_seen_at.desc(), events.c.event_id)
                .limit(MAX_READ_INPUTS + 1)
                .with_for_update(read=True)
            ).mappings()
        )
        if len(rows) > MAX_READ_INPUTS:
            raise PublicReadUnavailable("search inputs exceed the bounded projection")
        current = self._current_rows(tuple(row["event_id"] for row in rows))
        if {row["event_id"] for row in rows} - {row["event_id"] for row in current}:
            raise PublicReadUnavailable("a matched event has no current normalized intelligence")
        binding = self._binding(
            "vulns",
            [q, limit],
            [[row["event_id"], row["business_version"]] for row in rows]
            + [[row["revision_id"], row["document_id"], row["source_metadata"]] for row in current],
        )
        offset = page_position(cursor, binding)
        if cursor is not None and offset >= len(rows):
            raise InvalidPublicCursor("cursor position is outside the current page scope")
        items: list[JsonValue] = []
        for row in rows[offset : offset + limit]:
            event_id = row["event_id"]
            value, _ = self._vulnerability(
                UUID(event_id), [item for item in current if item["event_id"] == event_id]
            )
            items.append(value)
        return {
            "items": items,
            "data_mode": self.data_mode,
            "next_cursor": encode_page_cursor(offset + limit, binding)
            if offset + limit < len(rows)
            else None,
        }

    def get_vuln(
        self,
        event_id: UUID,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, JsonValue]:
        validate_page_inputs(None, limit, cursor)
        self.knowledge.event_detail(event_id)
        current = self._current_rows((str(event_id),))
        vulnerability, limits = self._vulnerability(event_id, current)
        binding = self._binding(
            "vuln",
            [str(event_id), limit],
            [
                vulnerability,
                [[row["revision_id"], row["document_id"]] for row in current],
            ],
        )
        offset = page_position(cursor, binding)
        if cursor is not None and offset >= len(current):
            raise InvalidPublicCursor("cursor position is outside the current advisory scope")
        advisories: list[JsonValue] = []
        for row in current[offset : offset + limit]:
            if row["kind"] != "advisory":
                limits.append("non_advisory_intelligence_requires_internal_document_endpoint")
                continue
            projected = next(
                item
                for item in self.knowledge.event_detail(event_id).revisions
                if str(item.revision_id) == row["revision_id"]
            )
            if projected.canonical_uri is None:
                raise PublicReadUnavailable("advisory public URI unavailable")
            advisories.append(
                {
                    "intel_id": str(projected.document_id),
                    "revision_id": str(projected.revision_id),
                    "title": str(
                        self.session.scalar(
                            select(documents.c.title).where(
                                documents.c.document_id == row["document_id"]
                            )
                        )
                    ),
                    "source_uri": str(projected.canonical_uri),
                    "published_at": projected.source_published_at.isoformat()
                    if projected.source_published_at
                    else None,
                    "citations": self._citations(row["revision_id"]),
                }
            )
        return {
            "vulnerability": vulnerability,
            "advisories": advisories,
            "mapping_limits": list(dict.fromkeys(str(value) for value in limits)),
            "data_mode": self.data_mode,
            "next_cursor": encode_page_cursor(offset + limit, binding)
            if offset + limit < len(current)
            else None,
        }

    def list_sources(self, limit: int = 20, cursor: str | None = None) -> dict[str, JsonValue]:
        validate_page_inputs(None, limit, cursor)
        rows = list(
            self.session.execute(
                select(sources)
                .where(
                    sources.c.visibility == "public",
                    sources.c.tenant_id.is_(None),
                )
                .order_by(sources.c.source_id)
                .limit(MAX_READ_INPUTS + 1)
                .with_for_update(read=True)
            ).mappings()
        )
        if len(rows) > MAX_READ_INPUTS:
            raise PublicReadUnavailable("source inputs exceed the bounded projection")
        modes = self._current_source_modes(tuple(row["source_id"] for row in rows))
        items: list[JsonValue] = []
        configured_ids = {item.source_id for item in CATALOG_SOURCES.values()}
        for row in rows:
            source_id = row["source_id"]
            if not isinstance(source_id, str) or not 1 <= len(source_id) <= 200:
                raise PublicReadUnavailable("public source identity is invalid")
            if not isinstance(row["name"], str) or not 1 <= len(row["name"]) <= 500:
                raise PublicReadUnavailable("public source name is invalid")
            category = SourceCategory(row["category"]).value
            if source_id in modes:
                classify_revision_mode(modes[source_id], self.data_mode)
            observations = list(
                self.session.execute(
                    select(source_response_receipts)
                    .where(
                        source_response_receipts.c.source_id == source_id,
                        source_response_receipts.c.observed_at
                        == select(
                            func.max(
                                source_response_receipts.c.observed_at,
                            )
                        )
                        .where(source_response_receipts.c.source_id == source_id)
                        .scalar_subquery(),
                    )
                    .order_by(
                        source_response_receipts.c.observed_at.desc(),
                        source_response_receipts.c.receipt_id,
                    )
                    .limit(MAX_READ_INPUTS + 1)
                ).mappings()
            )
            attempts = list(
                self.session.execute(
                    select(fetch_attempts)
                    .where(
                        fetch_attempts.c.source_id == source_id,
                        fetch_attempts.c.attempted_at
                        == select(func.max(fetch_attempts.c.attempted_at))
                        .where(fetch_attempts.c.source_id == source_id)
                        .scalar_subquery(),
                    )
                    .order_by(fetch_attempts.c.attempted_at.desc())
                    .limit(MAX_READ_INPUTS + 1)
                ).mappings()
            )
            last_attempt: datetime | None = observations[0]["observed_at"] if observations else None
            if attempts and (last_attempt is None or attempts[0]["attempted_at"] > last_attempt):
                last_attempt = attempts[0]["attempted_at"]
            successes = list(
                self.session.execute(
                    select(source_page_receipts)
                    .where(
                        source_page_receipts.c.source_id == source_id,
                        source_page_receipts.c.committed_at
                        == select(func.max(source_page_receipts.c.committed_at))
                        .where(source_page_receipts.c.source_id == source_id)
                        .scalar_subquery(),
                    )
                    .order_by(source_page_receipts.c.committed_at.desc())
                    .limit(MAX_READ_INPUTS + 1)
                ).mappings()
            )
            last_success = self.session.scalar(
                select(func.max(source_page_receipts.c.committed_at)).where(
                    source_page_receipts.c.source_id == source_id,
                    source_page_receipts.c.failed_job_ids == [],
                )
            )
            health_observations: list[tuple[datetime, str]] = []
            if any(len(group) > MAX_READ_INPUTS for group in (observations, attempts, successes)):
                raise PublicReadUnavailable("source observations exceed the bounded projection")
            for observation in observations:
                outcome = observation["parse_outcome"]
                health_observations.append(
                    (
                        observation["observed_at"],
                        "failed"
                        if outcome in {"normalization_failed", "transport_failed"}
                        else "unknown",
                    )
                )
            for attempt in attempts:
                outcome = {"failed": "failed", "partial": "partial"}.get(
                    attempt["outcome"], "unknown"
                )
                health_observations.append((attempt["attempted_at"], outcome))
            for success in successes:
                health_observations.append(
                    (success["committed_at"], "partial" if success["failed_job_ids"] else "healthy")
                )
            health = derive_source_health(tuple(health_observations))
            items.append(
                {
                    "source_id": source_id,
                    "name": row["name"],
                    "category": category,
                    "enabled": self.source_polling_enabled and source_id in configured_ids,
                    "health": health,
                    "last_attempt_at": last_attempt.isoformat() if last_attempt else None,
                    "last_success_at": last_success.isoformat() if last_success else None,
                    "reason_code": "observation_support_not_qualified"
                    if health == "unknown"
                    else None,
                    "data_mode": self.data_mode,
                }
            )
        binding = self._binding("sources", [limit], items)
        offset = page_position(cursor, binding)
        if cursor is not None and offset >= len(items):
            raise InvalidPublicCursor("cursor position is outside the current source scope")
        return {
            "items": items[offset : offset + limit],
            "data_mode": self.data_mode,
            "next_cursor": encode_page_cursor(offset + limit, binding)
            if offset + limit < len(items)
            else None,
        }

    def _current_source_modes(self, source_ids: tuple[str, ...]) -> dict[str, object]:
        rows = self.session.execute(
            select(
                documents.c.source_id,
                document_revisions.c.source_metadata,
            )
            .select_from(document_revisions.join(documents))
            .where(
                documents.c.source_id.in_(source_ids),
                documents.c.visibility == "public",
                documents.c.tenant_id.is_(None),
                document_revisions.c.visibility == "public",
                document_revisions.c.tenant_id.is_(None),
                document_revisions.c.is_current.is_(True),
            )
            .limit(MAX_READ_INPUTS + 1)
            .with_for_update(read=True, of=(document_revisions, documents))
        ).all()
        if len(rows) > MAX_READ_INPUTS:
            raise PublicReadUnavailable("source read inputs exceed the bounded projection")
        result: dict[str, object] = {}
        for source_id, metadata in rows:
            if not isinstance(source_id, str):
                raise PublicReadUnavailable("source identity unavailable")
            classify_revision_mode(metadata, self.data_mode)
            result[source_id] = metadata
        return result

    def get_task_result(self, task_id: UUID) -> dict[str, JsonValue]:
        """Generic jobs cannot establish an ask/stack request type, owner and result contract."""
        raise PublicReadUnavailable(
            "public task owner and typed result producer are not configured"
        )
