"""当前 PostgreSQL 事实的有界证据图快照；不发布事实，也不维护另一份图真值。"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, ValidationError
from sqlalchemy import Text, and_, column, literal, or_, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.domain.enrichment_values import (
    ArtifactReferenceValue,
    AtlasMappingValue,
    LiteratureReferenceValue,
    VersionAssertionValue,
)
from ai_intel.domain.enums import ClaimOrigin
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.contracts import (
    CandidateEvidence,
    EnrichmentBlock,
    EnrichmentDocument,
    EvidenceBoundCandidate,
)
from ai_intel.enrichment.field_sources import (
    FieldEvidenceError,
    is_atlas_taxonomy,
    validate_field_candidate,
)
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    scope_epochs,
    text_blocks,
)
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)

GRAPH_RULE_VERSION: Literal["r10-graph-1.1.0"] = "r10-graph-1.1.0"
MAX_SUPPORT_ROWS = 2000
RelationType = Literal[
    "same_event",
    "affects_component_version",
    "mapped_atlas",
    "related_paper",
    "remediated_by",
    "component_version_vulnerability",
]
RELATION_TYPES: tuple[RelationType, ...] = (
    "same_event",
    "affects_component_version",
    "mapped_atlas",
    "related_paper",
    "remediated_by",
    "component_version_vulnerability",
)
sources = table(
    "sources",
    column("source_id", Text),
    column("visibility", Text),
    column("tenant_id", Text),
    column("category", Text),
)
GraphValue = (
    VersionAssertionValue
    | AtlasMappingValue
    | LiteratureReferenceValue
    | ArtifactReferenceValue
    | str
)
DocumentCache = dict[UUID, tuple[EnrichmentDocument, VisibilityScope] | None]


class GraphSnapshotChangedError(RuntimeError):
    """候选图在返回围栏前失效；不能把旧快照包装成当前结果。"""


class GraphNode(StrictRecord):
    id: UUID
    kind: Literal["event", "source_revision", "component_version", "atlas", "paper", "remediation"]
    label: str = Field(min_length=1, max_length=2500)
    scope: VisibilityScope


class GraphEdge(StrictRecord):
    id: UUID
    relation_type: RelationType
    subject_id: UUID
    object_id: UUID
    scope: VisibilityScope
    source_revision_ids: tuple[UUID, ...] = Field(min_length=1, max_length=MAX_SUPPORT_ROWS)
    evidence_span_ids: tuple[UUID, ...] = Field(min_length=1, max_length=MAX_SUPPORT_ROWS)
    supporting_claim_ids: tuple[UUID, ...] = Field(min_length=1, max_length=MAX_SUPPORT_ROWS)
    rule_or_model_version: Literal["r10-graph-1.1.0"] = GRAPH_RULE_VERSION
    reason: str = Field(min_length=1, max_length=2500)
    status: Literal["supported"] = "supported"


class GraphGap(StrictRecord):
    relation_type: RelationType
    status: Literal["unknown"] = "unknown"
    reason: Literal["no_current_supported_relation", "truncated"]


class GraphSnapshot(StrictRecord):
    schema_version: Literal[1] = 1
    event_id: UUID
    business_version: int = Field(strict=True, ge=1)
    rule_version: Literal["r10-graph-1.1.0"] = GRAPH_RULE_VERSION
    nodes: tuple[GraphNode, ...] = Field(min_length=1, max_length=200)
    edges: tuple[GraphEdge, ...] = Field(max_length=400)
    truncated: bool
    gaps: tuple[GraphGap, ...]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _identity(kind: str, scope: VisibilityScope, value: object) -> UUID:
    serialized = json.dumps(
        [kind, scope.model_dump(mode="json"), value],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return uuid5(NAMESPACE_URL, serialized)


def _scope_of(row: RowMapping, prefixes: tuple[str, ...]) -> VisibilityScope:
    tenants = {
        row[prefix + "tenant"] for prefix in prefixes if row[prefix + "visibility"] == "tenant"
    }
    if len(tenants) > 1:
        raise ValueError("incompatible graph scopes")
    if tenants:
        return VisibilityScope(visibility="tenant", tenant_id=tenants.pop())
    return VisibilityScope(visibility="public")


def _scope_columns(relation: FromClause, prefix: str) -> tuple[ColumnElement[object], ...]:
    return (
        relation.c.visibility.label(prefix + "visibility"),
        relation.c.tenant_id.label(prefix + "tenant"),
    )


def _verified_span(row: RowMapping) -> bool:
    quote = row["quote"]
    block = row["block_text"]
    start = row["start_offset"] - row["block_start"]
    end = row["end_offset"] - row["block_start"]
    return (
        0 <= start < end <= len(block)
        and block[start:end] == quote
        and hashlib.sha256(quote.encode()).hexdigest() == row["quote_sha256"]
        and hashlib.sha256(block.encode()).hexdigest() == row["text_sha256"]
    )


def _narrow_scope(scopes: tuple[VisibilityScope, ...]) -> VisibilityScope:
    private = {scope.tenant_id for scope in scopes if scope.visibility == "tenant"}
    if len(private) > 1:
        raise ValueError("incompatible graph scopes")
    return (
        VisibilityScope(visibility="tenant", tenant_id=private.pop())
        if private
        else VisibilityScope(visibility="public")
    )


def _has_identifier(identifier: str, quote: str) -> bool:
    return (
        re.search(r"(?<![\w.+-])" + re.escape(identifier) + r"(?![\w.+-])", quote, re.IGNORECASE)
        is not None
    )


class EvidenceGraphReadService:
    """认证范围内投影固定六类关系；语义支持只读取 PG 已核验的发布记录。"""

    def __init__(self, session: Session, scope: AccessScope) -> None:
        scope.requires(READ_PUBLIC)
        self.session = session
        self.scope = scope
        self.input_sha256: str | None = None

    def _visible(self, relation: FromClause) -> ColumnElement[bool]:
        public = and_(relation.c.visibility == "public", relation.c.tenant_id.is_(None))
        if self.scope.tenant_id is None or READ_ASSET not in self.scope.permissions:
            return public
        return or_(
            public,
            and_(relation.c.visibility == "tenant", relation.c.tenant_id == self.scope.tenant_id),
        )

    def _revision_join(self) -> FromClause:
        return document_revisions.join(documents).join(
            sources, sources.c.source_id == documents.c.source_id
        )

    def _current_revision(self) -> ColumnElement[bool]:
        return and_(
            self._visible(document_revisions),
            self._visible(documents),
            self._visible(sources),
            document_revisions.c.is_current.is_(True),
            document_revisions.c.parse_status.in_(("parsed", "partial")),
            documents.c.kind != "asset_inventory",
        )

    def _support_rows(self, event_id: UUID) -> list[RowMapping]:
        joined = (
            event_documents.join(
                self._revision_join(),
                event_documents.c.revision_id == document_revisions.c.revision_id,
            )
            .join(claims, claims.c.source_revision_id == document_revisions.c.revision_id)
            .join(
                claim_assertions,
                and_(
                    claim_assertions.c.claim_id == claims.c.claim_id,
                    claim_assertions.c.revision_id == document_revisions.c.revision_id,
                    claim_assertions.c.source_id == sources.c.source_id,
                    claim_assertions.c.assertion_kind == claims.c.claim_origin,
                ),
            )
            .join(claim_evidence, claim_evidence.c.claim_id == claims.c.claim_id)
            .join(
                evidence,
                and_(
                    claim_evidence.c.evidence_id == evidence.c.evidence_id,
                    evidence.c.revision_id == document_revisions.c.revision_id,
                ),
            )
            .join(
                text_blocks,
                and_(
                    evidence.c.block_id == text_blocks.c.block_id,
                    evidence.c.revision_id == text_blocks.c.revision_id,
                ),
            )
        )
        query = (
            select(
                claims.c.claim_id,
                claims.c.schema_version,
                claims.c.predicate,
                claims.c.value_kind,
                claims.c.object_json,
                claims.c.object_value,
                claim_assertions.c.json_path.label("assertion_path"),
                document_revisions.c.revision_id,
                documents.c.document_id,
                documents.c.title,
                evidence.c.evidence_id,
                evidence.c.quote,
                evidence.c.quote_sha256,
                evidence.c.start_offset,
                evidence.c.end_offset,
                evidence.c.block_id,
                text_blocks.c.start_offset.label("block_start"),
                text_blocks.c.block_text,
                text_blocks.c.text_sha256,
                text_blocks.c.json_pointer,
                *_scope_columns(claims, "claim_"),
                *_scope_columns(document_revisions, "revision_"),
                *_scope_columns(documents, "document_"),
                *_scope_columns(sources, "source_"),
                *_scope_columns(evidence, "evidence_"),
            )
            .select_from(joined)
            .where(
                event_documents.c.event_id == str(event_id),
                event_documents.c.active.is_(True),
                self._current_revision(),
                self._visible(claims),
                self._visible(evidence),
                claims.c.subject == str(event_id),
                claims.c.is_current.is_(True),
                claims.c.claim_status == "supported",
                claims.c.condition_value == "true",
                claims.c.freshness != "stale",
                claims.c.provenance_status == "source_verified",
                claims.c.claim_origin.in_(
                    ("source_explicit", "structured_source", "rule_derived", "human_confirmed")
                ),
                claim_evidence.c.support_kind == "supports",
                claim_evidence.c.validation_status == "validated",
                evidence.c.supports_claim.is_(True),
                evidence.c.coordinate_version == "fulltext_unicode_v1",
                evidence.c.verified_at.is_not(None),
            )
            .distinct()
            .order_by(claims.c.claim_id, evidence.c.evidence_id)
            .limit(MAX_SUPPORT_ROWS + 1)
        )
        return list(self.session.execute(query).mappings())

    def read_scope_epochs(self, *, lock: bool = False) -> tuple[tuple[str, int], ...]:
        keys = ["public"]
        if self.scope.tenant_id is not None and READ_ASSET in self.scope.permissions:
            keys.append("tenant:" + self.scope.tenant_id)
        query = (
            select(scope_epochs.c.scope_key, scope_epochs.c.epoch)
            .where(scope_epochs.c.scope_key.in_(keys))
            .order_by(scope_epochs.c.scope_key)
        )
        if lock:
            query = query.with_for_update(read=True)
        result: list[tuple[str, int]] = []
        for key, epoch in self.session.execute(query):
            if not isinstance(key, str) or not isinstance(epoch, int) or isinstance(epoch, bool):
                raise ValueError("scope epoch invalid")
            result.append((key, epoch))
        return tuple(result)

    def lock_graph_inputs(self, event_id: UUID) -> None:
        """先锁事实父链，再由调用者取 epoch 锁；不在持 epoch 时倒序取父锁。"""
        if (
            self.session.scalar(
                select(events.c.event_id).where(
                    events.c.event_id == str(event_id), self._visible(events)
                )
            )
            is None
        ):
            raise CrossTenantAccessError("resource not found")
        revisions: list[str] = list(
            self.session.scalars(
                select(event_documents.c.revision_id)
                .where(event_documents.c.event_id == str(event_id))
                .order_by(event_documents.c.revision_id)
                .limit(MAX_SUPPORT_ROWS + 1)
            )
        )
        claim_rows = list(
            self.session.execute(
                select(claims.c.claim_id, claims.c.object_json)
                .where(claims.c.subject == str(event_id))
                .order_by(claims.c.claim_id)
                .limit(MAX_SUPPORT_ROWS + 1)
            )
        )
        if len(revisions) > MAX_SUPPORT_ROWS or len(claim_rows) > MAX_SUPPORT_ROWS:
            raise GraphSnapshotChangedError("graph inputs exceed validity fence")
        revision_ids = set(revisions)
        for _claim_id, value in claim_rows:
            if (
                isinstance(value, dict)
                and value.get("kind") == "literature_reference"
                and value.get("target_revision_id") is not None
            ):
                revision_ids.add(str(UUID(value["target_revision_id"])))
        parents = list(
            self.session.execute(
                select(
                    document_revisions.c.revision_id, documents.c.document_id, documents.c.source_id
                )
                .select_from(document_revisions.join(documents))
                .where(document_revisions.c.revision_id.in_(revision_ids))
            )
        )
        for relation, key, identifiers in (
            (sources, sources.c.source_id, {item.source_id for item in parents}),
            (documents, documents.c.document_id, {item.document_id for item in parents}),
            (document_revisions, document_revisions.c.revision_id, revision_ids),
            (events, events.c.event_id, {str(event_id)}),
            (claims, claims.c.claim_id, {item.claim_id for item in claim_rows}),
        ):
            self.session.execute(
                select(key)
                .select_from(relation)
                .where(key.in_(identifiers))
                .order_by(key)
                .with_for_update(read=True)
            ).all()
        evidence_ids: tuple[str, ...] = tuple(
            self.session.scalars(
                select(evidence.c.evidence_id)
                .where(evidence.c.revision_id.in_(revision_ids))
                .order_by(evidence.c.evidence_id)
                .limit(MAX_SUPPORT_ROWS + 1)
            )
        )
        if len(evidence_ids) > MAX_SUPPORT_ROWS:
            raise GraphSnapshotChangedError("graph evidence exceeds validity fence")
        self.session.execute(
            select(evidence.c.evidence_id)
            .where(evidence.c.evidence_id.in_(evidence_ids))
            .order_by(evidence.c.evidence_id)
            .with_for_update(read=True)
        ).all()
        block_ids: tuple[str, ...] = tuple(
            self.session.scalars(
                select(text_blocks.c.block_id)
                .where(text_blocks.c.revision_id.in_(revision_ids))
                .order_by(text_blocks.c.block_id)
                .limit(MAX_SUPPORT_ROWS + 1)
            )
        )
        if len(block_ids) > MAX_SUPPORT_ROWS:
            raise GraphSnapshotChangedError("graph blocks exceed validity fence")
        self.session.execute(
            select(text_blocks.c.block_id)
            .where(text_blocks.c.block_id.in_(block_ids))
            .order_by(text_blocks.c.block_id)
            .with_for_update(read=True)
        ).all()
        for relation, key in (
            (event_documents, event_documents.c.revision_id),
            (claim_assertions, claim_assertions.c.assertion_id),
            (claim_evidence, claim_evidence.c.evidence_id),
        ):
            predicate = (
                relation.c.event_id == str(event_id)
                if relation is event_documents
                else relation.c.claim_id.in_({item.claim_id for item in claim_rows})
            )
            self.session.execute(
                select(key).where(predicate).order_by(key).with_for_update(read=True)
            ).all()

    def _load_document(
        self, revision_id: UUID, cache: DocumentCache
    ) -> tuple[EnrichmentDocument, VisibilityScope] | None:
        if revision_id in cache:
            return cache[revision_id]
        row = (
            self.session.execute(
                select(
                    document_revisions,
                    documents.c.kind,
                    documents.c.document_id,
                    documents.c.source_id,
                    sources.c.category,
                    *_scope_columns(document_revisions, "revision_"),
                    *_scope_columns(documents, "document_"),
                    *_scope_columns(sources, "source_"),
                )
                .select_from(self._revision_join())
                .where(
                    document_revisions.c.revision_id == str(revision_id), self._current_revision()
                )
            )
            .mappings()
            .first()
        )
        cache[revision_id] = None
        if row is None:
            return None
        from ai_intel.api.knowledge_read_service import safe_source_uri

        uri = safe_source_uri(row["canonical_uri"])
        if uri is None:
            return None
        blocks = list(
            self.session.execute(
                select(text_blocks)
                .where(text_blocks.c.revision_id == str(revision_id))
                .order_by(text_blocks.c.ordinal)
                .limit(201)
            ).mappings()
        )
        if not blocks or len(blocks) > 200:
            return None
        metadata = row["source_metadata"]
        try:
            document = EnrichmentDocument.model_validate(
                {
                    "revision_id": revision_id,
                    "document_id": row["document_id"],
                    "source_id": row["source_id"],
                    "document_kind": row["kind"],
                    "source_category": row["category"],
                    "canonical_uri": uri,
                    "source_record_id": metadata.get("source_record_id", str(uri)),
                    "content_sha256": row["content_hash"],
                    "blocks": tuple(
                        EnrichmentBlock(
                            block_id=item["block_id"],
                            start_offset=item["start_offset"],
                            text=item["block_text"],
                            text_sha256=item["text_sha256"],
                            json_pointer=item["json_pointer"],
                            page_number=item["page_number"],
                        )
                        for item in blocks
                    ),
                    "blocks_complete": metadata.get(
                        "blocks_complete", row["parse_status"] == "parsed"
                    ),
                    "content_coverage": metadata.get("content_coverage", "unknown"),
                    "source_version": metadata.get("source_version"),
                    "observed_at": row["first_observed_at"],
                }
            )
        except ValidationError:
            return None
        result = (document, _scope_of(row, ("revision_", "document_", "source_")))
        cache[revision_id] = result
        return result

    def _event_bound(
        self,
        rows: tuple[RowMapping, ...],
        all_rows: tuple[RowMapping, ...],
        identifiers: tuple[str, ...],
    ) -> bool:
        if identifiers:
            return any(
                _has_identifier(identifier, row["quote"])
                for identifier in identifiers
                for row in rows
            )
        same_revision = tuple(
            row for row in all_rows if row["revision_id"] == rows[0]["revision_id"]
        )
        products = tuple(
            row["object_value"]
            for row in same_revision
            if row["predicate"] == "affected_product" and row["object_value"] == row["quote"]
        )
        excerpts = tuple(
            row["object_value"]
            for row in same_revision
            if row["predicate"] == "source_excerpt" and row["object_value"] == row["quote"]
        )
        return any(
            _has_identifier(product, excerpt)
            and re.search(
                r"vulnerab|affected|security|injection|受影响|漏洞|安全|注入",
                excerpt,
                re.IGNORECASE,
            )
            for product in products
            for excerpt in excerpts
        )

    def _validated_support(
        self,
        rows: tuple[RowMapping, ...],
        all_rows: tuple[RowMapping, ...],
        identifiers: tuple[str, ...],
        cache: DocumentCache,
        event_id: UUID,
    ) -> tuple[GraphValue, tuple[RowMapping, ...], VisibilityScope] | None:
        row = rows[0]
        scope = _narrow_scope(
            tuple(
                _scope_of(item, ("claim_", "revision_", "document_", "source_", "evidence_"))
                for item in rows
            )
        )
        if row["schema_version"] != 3:
            return (
                (row["object_value"], rows, scope)
                if self._event_bound(rows, all_rows, identifiers)
                and any(row["object_value"] in item["quote"] for item in rows)
                else None
            )
        if row["predicate"] != row["value_kind"]:
            raise ValueError("graph fact value disagrees with predicate")
        value: GraphValue
        candidate_value: (
            VersionAssertionValue
            | AtlasMappingValue
            | LiteratureReferenceValue
            | ArtifactReferenceValue
        )
        if row["predicate"] == "version_assertion":
            value = VersionAssertionValue.model_validate(row["object_json"])
            candidate_value = value.model_copy(update={"comparison_support": "unknown"})
            dimension: Literal["versions", "atlas", "literature", "poc"] = "versions"
        elif row["predicate"] == "atlas_mapping":
            value = AtlasMappingValue.model_validate(row["object_json"])
            candidate_value = value
            dimension = "atlas"
        elif row["predicate"] == "literature_reference":
            value = LiteratureReferenceValue.model_validate(row["object_json"])
            candidate_value = value.model_copy(
                update={"target_document_id": None, "target_revision_id": None}
            )
            dimension = "literature"
        elif row["predicate"] == "artifact_reference":
            value = ArtifactReferenceValue.model_validate(row["object_json"])
            candidate_value = value.model_copy(update={"static_status": "candidate_found"})
            dimension = "poc"
        else:
            return None
        if identifiers:
            core = ""
            if isinstance(value, VersionAssertionValue):
                core = value.raw_expression
            elif isinstance(value, AtlasMappingValue):
                core = value.mechanism
            elif isinstance(value, LiteratureReferenceValue):
                core = value.support_summary
            owner_paths = {"/id", "/ghsa_id", "/cve/id", "/cveMetadata/cveId"}
            field_binding = any(
                item["revision_id"] == row["revision_id"]
                and item["json_pointer"] in owner_paths
                and item["assertion_path"] == item["json_pointer"]
                and item["quote"].strip().casefold()
                in {identifier.casefold() for identifier in identifiers}
                for item in all_rows
            )
            artifact_binding = isinstance(value, ArtifactReferenceValue) and any(
                str(value.uri) in item["quote"]
                and value.title in item["quote"]
                and any(_has_identifier(identifier, item["quote"]) for identifier in identifiers)
                for item in rows
            )
            if (
                not field_binding
                and not artifact_binding
                and not any(_has_identifier(identifier, core) for identifier in identifiers)
            ):
                return None
        elif not self._event_bound(rows, all_rows, identifiers):
            return None
        loaded = self._load_document(UUID(row["revision_id"]), cache)
        if loaded is None or len(rows) > 20:
            return None
        selected = [loaded[0]]
        proof = list(rows)
        scopes = [scope, loaded[1]]
        if isinstance(value, LiteratureReferenceValue) and value.target_revision_id is not None:
            target = self._load_document(value.target_revision_id, cache)
            if target is None or target[0].document_id != value.target_document_id:
                return None
            selected.append(target[0])
            scopes.append(target[1])
        if isinstance(value, AtlasMappingValue):
            taxonomy_ids: tuple[str, ...] = tuple(
                self.session.scalars(
                    select(document_revisions.c.revision_id)
                    .select_from(
                        event_documents.join(
                            self._revision_join(),
                            event_documents.c.revision_id == document_revisions.c.revision_id,
                        )
                    )
                    .where(
                        event_documents.c.event_id == str(event_id),
                        event_documents.c.active.is_(True),
                        self._current_revision(),
                        document_revisions.c.canonical_uri.in_(
                            (
                                f"https://raw.githubusercontent.com/mitre/atlas-data/{value.taxonomy_version}/dist/ATLAS.yaml",
                                f"https://github.com/mitre/atlas-data/blob/{value.taxonomy_version}/dist/ATLAS.yaml",
                            )
                        ),
                    )
                    .limit(2)
                )
            )
            if len(taxonomy_ids) != 1:
                return None
            taxonomy = self._load_document(UUID(taxonomy_ids[0]), cache)
            if taxonomy is None or not is_atlas_taxonomy(taxonomy[0]):
                return None
            selected.append(taxonomy[0])
            scopes.append(taxonomy[1])
            taxonomy_rows = list(
                self.session.execute(
                    select(
                        literal(row["claim_id"]).label("claim_id"),
                        evidence.c.revision_id,
                        evidence.c.evidence_id,
                        evidence.c.block_id,
                        evidence.c.quote,
                        evidence.c.quote_sha256,
                        evidence.c.start_offset,
                        evidence.c.end_offset,
                        text_blocks.c.start_offset.label("block_start"),
                        text_blocks.c.block_text,
                        text_blocks.c.text_sha256,
                        *_scope_columns(evidence, "evidence_"),
                    )
                    .select_from(
                        evidence.join(
                            text_blocks,
                            and_(
                                evidence.c.block_id == text_blocks.c.block_id,
                                evidence.c.revision_id == text_blocks.c.revision_id,
                            ),
                        )
                    )
                    .where(
                        evidence.c.revision_id == taxonomy_ids[0],
                        self._visible(evidence),
                        evidence.c.coordinate_version == "fulltext_unicode_v1",
                        evidence.c.verified_at.is_not(None),
                        evidence.c.quote.contains(value.technique_id, autoescape=True),
                    )
                    .order_by(evidence.c.evidence_id)
                    .limit(21)
                ).mappings()
            )
            taxonomy_rows = [item for item in taxonomy_rows if _verified_span(item)]
            if not taxonomy_rows or len(rows) + len(taxonomy_rows) > 20:
                return None
            proof.extend(taxonomy_rows)
            scopes.extend(_scope_of(item, ("evidence_",)) for item in taxonomy_rows)
        try:
            candidate = EvidenceBoundCandidate(
                dimension=dimension,
                value=candidate_value,
                origin=ClaimOrigin.SOURCE_EXPLICIT,
                evidence=tuple(
                    CandidateEvidence(
                        revision_id=item["revision_id"],
                        block_id=item["block_id"],
                        start_offset=item["start_offset"] - item["block_start"],
                        end_offset=item["end_offset"] - item["block_start"],
                        quote_text=item["quote"],
                        quote_sha256=item["quote_sha256"],
                    )
                    for item in proof
                ),
            )
            checked = validate_field_candidate(candidate, tuple(selected))
        except (FieldEvidenceError, ValidationError):
            return None
        if isinstance(value, LiteratureReferenceValue) and (
            not isinstance(checked.value, LiteratureReferenceValue)
            or checked.value.target_document_id != value.target_document_id
            or checked.value.target_revision_id != value.target_revision_id
        ):
            return None
        return value, tuple(proof), _narrow_scope(tuple(scopes))

    def _paper_scope(
        self,
        value: LiteratureReferenceValue,
        cache: DocumentCache,
    ) -> VisibilityScope | None:
        if value.target_document_id is None or value.reference_kind != "paper":
            return None
        if value.relation == "background":
            return None
        if value.target_revision_id is None:
            return None
        target = self._load_document(value.target_revision_id, cache)
        if (
            target is None
            or target[0].document_id != value.target_document_id
            or target[0].document_kind != "paper"
        ):
            return None
        return target[1]

    def event_graph(
        self, event_id: UUID, max_nodes: int = 200, max_edges: int = 400
    ) -> GraphSnapshot:
        """调用方需使用一致性读事务；上限和两跳结构固定，不接受任意图/SQL 查询。"""
        if (
            not isinstance(event_id, UUID)
            or type(max_nodes) is not int
            or type(max_edges) is not int
            or not 1 <= max_nodes <= 200
            or not 1 <= max_edges <= 400
        ):
            raise ValueError("graph request outside bounds")
        event = (
            self.session.execute(
                select(events).where(events.c.event_id == str(event_id), self._visible(events))
            )
            .mappings()
            .first()
        )
        if event is None:
            raise CrossTenantAccessError("resource not found")
        event_scope = VisibilityScope(visibility=event["visibility"], tenant_id=event["tenant_id"])
        root = GraphNode(id=event_id, kind="event", label=event["title"], scope=event_scope)
        nodes = {root.id: root}
        edges: dict[UUID, GraphEdge] = {}
        rows = self._support_rows(event_id) if event["status"] == "active" else []
        truncated = len(rows) > MAX_SUPPORT_ROWS
        valid_rows = tuple(row for row in rows[:MAX_SUPPORT_ROWS] if _verified_span(row))
        grouped: dict[str, list[RowMapping]] = {}
        for row in valid_rows:
            grouped.setdefault(row["claim_id"], []).append(row)
        identifiers: tuple[str, ...] = tuple(
            self.session.scalars(
                select(event_external_ids.c.id_value).where(
                    event_external_ids.c.event_id == str(event_id),
                    event_external_ids.c.scope_key == event["scope_key"],
                )
            )
        )
        document_cache: DocumentCache = {}
        proof_rows: tuple[RowMapping, ...] = ()
        claim_rows: tuple[RowMapping, ...] = ()
        proof_inputs: list[object] = []

        def add_edge(
            relation_type: RelationType,
            subject: GraphNode,
            target: GraphNode,
            scope: VisibilityScope,
            row: RowMapping,
            reason: str,
        ) -> None:
            identity: list[object] = [str(subject.id), str(target.id)]
            if relation_type != "same_event":
                identity.extend((row["predicate"], row["object_json"], reason))
            edge_id = _identity(relation_type, scope, identity)
            nodes[subject.id] = subject
            nodes[target.id] = target
            previous = edges.get(edge_id)
            supporting_rows = claim_rows if relation_type == "same_event" else proof_rows
            revision_ids = {UUID(item["revision_id"]) for item in supporting_rows}
            evidence_ids = {UUID(item["evidence_id"]) for item in supporting_rows}
            claim_ids = {UUID(row["claim_id"])}
            if previous:
                revision_ids.update(previous.source_revision_ids)
                evidence_ids.update(previous.evidence_span_ids)
                claim_ids.update(previous.supporting_claim_ids)
            edges[edge_id] = GraphEdge(
                id=edge_id,
                relation_type=relation_type,
                subject_id=subject.id,
                object_id=target.id,
                scope=scope,
                source_revision_ids=tuple(sorted(revision_ids)),
                evidence_span_ids=tuple(sorted(evidence_ids)),
                supporting_claim_ids=tuple(sorted(claim_ids)),
                reason=reason,
            )

        for group in grouped.values():
            claim_rows = tuple(group)
            support = self._validated_support(
                claim_rows, valid_rows, identifiers, document_cache, event_id
            )
            proof_inputs.append(
                [
                    group[0]["claim_id"],
                    None if support is None else [dict(item) for item in support[1]],
                ]
            )
            if support is None:
                continue
            value, proof_rows, scope = support
            scope = _narrow_scope((scope, event_scope))
            row = group[0]
            revision = GraphNode(
                id=_identity("source_revision", scope, row["revision_id"]),
                kind="source_revision",
                label=row["title"],
                scope=scope,
            )
            add_edge(
                "same_event", root, revision, scope, row, "当前事件的已发布来源关联及已核验支持事实"
            )
            if event["event_type"] != "vulnerability" or row["schema_version"] != 3:
                continue
            if isinstance(value, VersionAssertionValue):
                version = value
                if (
                    version.comparison_support != "supported"
                    or version.scheme == "unknown"
                    or not (version.intervals or version.explicit_versions)
                ):
                    continue
                identity = version.model_dump(
                    mode="json", exclude={"vendor_fix", "mitigations", "limitations"}
                )
                component = GraphNode(
                    id=_identity("component_version", scope, identity),
                    kind="component_version",
                    label=f"{version.ecosystem}:{version.package_key} {version.raw_expression}",
                    scope=scope,
                )
                add_edge(
                    "affects_component_version", root, component, scope, row, version.raw_expression
                )
                add_edge(
                    "component_version_vulnerability",
                    component,
                    root,
                    scope,
                    row,
                    version.raw_expression,
                )
                actions = [("vendor_fix", version.vendor_fix)] if version.vendor_fix else []
                actions.extend(("mitigation", action) for action in version.mitigations)
                for action_kind, action in actions:
                    remediation = GraphNode(
                        id=_identity("remediation", scope, [identity, action_kind, action]),
                        kind="remediation",
                        label=f"{action_kind}: {action}",
                        scope=scope,
                    )
                    add_edge("remediated_by", root, remediation, scope, row, action)
            elif isinstance(value, AtlasMappingValue):
                atlas = value
                technique = GraphNode(
                    id=_identity("atlas", scope, [atlas.technique_id, atlas.taxonomy_version]),
                    kind="atlas",
                    label=f"{atlas.technique_id} ({atlas.taxonomy_version})",
                    scope=scope,
                )
                add_edge("mapped_atlas", root, technique, scope, row, atlas.mechanism)
            elif isinstance(value, LiteratureReferenceValue):
                literature = value
                target_scope = self._paper_scope(literature, document_cache)
                if target_scope is None:
                    continue
                if target_scope.visibility == "tenant":
                    scope = target_scope
                paper = GraphNode(
                    id=_identity(
                        "paper",
                        scope,
                        [str(literature.target_document_id), str(literature.target_revision_id)],
                    ),
                    kind="paper",
                    label=literature.title,
                    scope=scope,
                )
                add_edge("related_paper", root, paper, scope, row, literature.support_summary)

        selected_nodes = {root.id: root}
        selected_edges: list[GraphEdge] = []
        for edge in sorted(edges.values(), key=lambda item: (item.relation_type, item.id)):
            additional = {edge.subject_id, edge.object_id} - selected_nodes.keys()
            if (
                len(selected_edges) >= max_edges
                or len(selected_nodes) + len(additional) > max_nodes
            ):
                truncated = True
                continue
            selected_edges.append(edge)
            for node_id in additional:
                selected_nodes[node_id] = nodes[node_id]
        present = {edge.relation_type for edge in selected_edges}
        gaps = tuple(
            GraphGap(
                relation_type=kind,
                reason="truncated" if truncated else "no_current_supported_relation",
            )
            for kind in sorted(RELATION_TYPES)
            if kind not in present
        )
        payload = {
            "schema_version": 1,
            "event_id": str(event_id),
            "business_version": event["business_version"],
            "rule_version": GRAPH_RULE_VERSION,
            "nodes": [
                node.model_dump(mode="json")
                for node in sorted(selected_nodes.values(), key=lambda node: node.id)
            ],
            "edges": [edge.model_dump(mode="json") for edge in selected_edges],
            "truncated": truncated,
            "gaps": [gap.model_dump(mode="json") for gap in gaps],
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        input_state = {
            "event": dict(event),
            "rows": [dict(item) for item in rows],
            "identifiers": sorted(identifiers),
            "proofs": proof_inputs,
            "documents": [
                [
                    str(key),
                    None
                    if value is None
                    else [value[0].model_dump(mode="json"), value[1].model_dump(mode="json")],
                ]
                for key, value in sorted(document_cache.items())
            ],
        }
        self.input_sha256 = hashlib.sha256(
            json.dumps(
                input_state, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
            ).encode()
        ).hexdigest()
        return GraphSnapshot.model_validate(
            {**payload, "content_sha256": hashlib.sha256(serialized.encode()).hexdigest()}
        )
