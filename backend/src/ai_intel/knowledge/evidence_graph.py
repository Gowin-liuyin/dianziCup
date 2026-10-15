"""当前 PostgreSQL 事实的有界证据图快照；不发布事实，也不维护另一份图真值。"""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field
from sqlalchemy import Text, and_, column, or_, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.domain.enrichment_values import (
    AtlasMappingValue,
    LiteratureReferenceValue,
    VersionAssertionValue,
)
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import VisibilityScope
from ai_intel.knowledge.models import document_revisions, documents, evidence, text_blocks
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    events,
)

GRAPH_RULE_VERSION: Literal["r10-graph-1.0.0"] = "r10-graph-1.0.0"
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
    "sources", column("source_id", Text), column("visibility", Text), column("tenant_id", Text)
)


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
    rule_or_model_version: Literal["r10-graph-1.0.0"] = GRAPH_RULE_VERSION
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
    rule_version: Literal["r10-graph-1.0.0"] = GRAPH_RULE_VERSION
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


class EvidenceGraphReadService:
    """认证范围内投影固定六类关系；语义支持只读取 PG 已核验的发布记录。"""

    def __init__(self, session: Session, scope: AccessScope) -> None:
        scope.requires(READ_PUBLIC)
        self.session = session
        self.scope = scope

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
                document_revisions.c.revision_id,
                documents.c.title,
                evidence.c.evidence_id,
                evidence.c.quote,
                evidence.c.quote_sha256,
                evidence.c.start_offset,
                evidence.c.end_offset,
                text_blocks.c.start_offset.label("block_start"),
                text_blocks.c.block_text,
                text_blocks.c.text_sha256,
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
                    ("source_explicit", "structured_source", "human_confirmed")
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

    def _paper_scope(self, value: LiteratureReferenceValue) -> VisibilityScope | None:
        if value.target_document_id is None or value.reference_kind != "paper":
            return None
        if value.relation == "background":
            return None
        row = (
            self.session.execute(
                select(
                    *_scope_columns(document_revisions, "revision_"),
                    *_scope_columns(documents, "document_"),
                    *_scope_columns(sources, "source_"),
                )
                .select_from(self._revision_join())
                .where(
                    document_revisions.c.revision_id == str(value.target_revision_id),
                    document_revisions.c.document_id == str(value.target_document_id),
                    documents.c.kind == "paper",
                    self._current_revision(),
                )
            )
            .mappings()
            .first()
        )
        return _scope_of(row, ("revision_", "document_", "source_")) if row is not None else None

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
            revision_ids = {UUID(row["revision_id"])}
            evidence_ids = {UUID(row["evidence_id"])}
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

        for row in rows[:MAX_SUPPORT_ROWS]:
            if not _verified_span(row):
                continue
            scope = _scope_of(row, ("claim_", "revision_", "document_", "source_", "evidence_"))
            if event_scope.visibility == "tenant":
                scope = event_scope
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
            value = row["object_json"]
            if row["predicate"] != row["value_kind"]:
                raise ValueError("graph fact value disagrees with predicate")
            if row["predicate"] == "version_assertion":
                version = VersionAssertionValue.model_validate(value)
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
            elif row["predicate"] == "atlas_mapping":
                atlas = AtlasMappingValue.model_validate(value)
                technique = GraphNode(
                    id=_identity("atlas", scope, [atlas.technique_id, atlas.taxonomy_version]),
                    kind="atlas",
                    label=f"{atlas.technique_id} ({atlas.taxonomy_version})",
                    scope=scope,
                )
                add_edge("mapped_atlas", root, technique, scope, row, atlas.mechanism)
            elif row["predicate"] == "literature_reference":
                literature = LiteratureReferenceValue.model_validate(value)
                target_scope = self._paper_scope(literature)
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
        return GraphSnapshot.model_validate(
            {**payload, "content_sha256": hashlib.sha256(serialized.encode()).hexdigest()}
        )
