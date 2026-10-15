"""从唯一PG事实库读取工作台投影；每层来源与历史引用都重新限制可见范围。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from typing import Literal
from uuid import UUID

from pydantic import Field, HttpUrl, ValidationError, field_validator
from sqlalchemy import Text, and_, column, exists, or_, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.api.knowledge_contracts import (
    CitationProjection,
    ClaimSummary,
    DataMode,
    EnrichmentProjection,
    EventDetailResponse,
    EventListResponse,
    EventSummary,
    EvidenceResponse,
    RevisionSummary,
)
from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.network import SENSITIVE_QUERY_KEYS
from ai_intel.knowledge.models import document_revisions, documents, evidence, text_blocks
from ai_intel.knowledge.persistence_models import (
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)

sources = table(
    "sources", column("source_id", Text), column("visibility", Text), column("tenant_id", Text)
)


class InvalidEventCursor(ValueError):
    """非法或属于其他过滤条件的continuation，不能当首页重取。"""


class KnowledgeProjectionError(ValueError):
    """保存的数据不满足公开投影合同；不能包装成成功空结果。"""


class EventFilters(StrictRecord):
    q: str = Field(default="", max_length=500)
    product: str = Field(default="", max_length=500)
    risk_type: str = Field(default="", max_length=100)
    updated_after: UtcTimestamp | None = None

    @field_validator("q", "product", "risk_type")
    @classmethod
    def valid_search_text(cls, value: str) -> str:
        """拒绝 PG text 无法表示的输入，不把客户端错误转换为服务故障。"""
        if "\x00" in value:
            raise ValueError("search text must not contain NUL")
        return value

    def fingerprint(self) -> str:
        serialized = self.model_dump_json()
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class EventCursor(StrictRecord):
    version: int = Field(strict=True, ge=1, le=1)
    first_seen_at: UtcTimestamp
    event_id: UUID
    filters_sha256: str = Field(pattern="^[0-9a-f]{64}$")


def encode_event_cursor(row: RowMapping, filters: EventFilters) -> str:
    cursor = EventCursor(
        version=1,
        first_seen_at=row["first_seen_at"],
        event_id=UUID(row["event_id"]),
        filters_sha256=filters.fingerprint(),
    )
    return base64.urlsafe_b64encode(cursor.model_dump_json().encode()).decode().rstrip("=")


def decode_event_cursor(value: str, filters: EventFilters) -> EventCursor:
    """编码只承载有界排序键；每次查询仍须独立认证并过滤SQL范围。"""
    if not 1 <= len(value) <= 2048 or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise InvalidEventCursor("invalid event cursor")
    try:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        pairs = json.loads(decoded, object_pairs_hook=lambda entries: entries)
        if not isinstance(pairs, list) or len(pairs) != 4:
            raise ValueError("invalid cursor fields")
        if any(not isinstance(pair, tuple) or len(pair) != 2 for pair in pairs):
            raise ValueError("invalid cursor object")
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("duplicate cursor key")
        cursor = EventCursor.model_validate(dict(pairs))
        if cursor.filters_sha256 != filters.fingerprint():
            raise ValueError("cursor filters changed")
        return cursor
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError) as error:
        raise InvalidEventCursor("invalid event cursor") from error


def safe_source_uri(value: str | None) -> HttpUrl | None:
    """旧记录中的凭据URI不返回前端；不猜来源根地址或对象存储路径。"""
    from urllib.parse import parse_qsl, urlsplit

    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.username
            or parsed.password
            or parsed.fragment
            or any(key.casefold() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query))
        ):
            return None
        return HttpUrl(value)
    except (ValueError, ValidationError):
        return None


class KnowledgeReadService:
    """只读服务复用已保存的版本与逐维状态，不自行推断安全或模型事实。"""

    def __init__(self, session: Session, scope: AccessScope, data_mode: DataMode) -> None:
        scope.requires(READ_PUBLIC)
        self.session = session
        self.scope = scope
        self.data_mode = data_mode

    def _visible(self, relation: FromClause) -> ColumnElement[bool]:
        visible = and_(relation.c.visibility == "public", relation.c.tenant_id.is_(None))
        if self.scope.tenant_id is not None and READ_ASSET in self.scope.permissions:
            visible = or_(
                visible,
                and_(
                    relation.c.visibility == "tenant", relation.c.tenant_id == self.scope.tenant_id
                ),
            )
        return visible

    def _revision_join(self) -> FromClause:
        return document_revisions.join(documents).join(
            sources, sources.c.source_id == documents.c.source_id
        )

    def _revision_visible(self) -> ColumnElement[bool]:
        return and_(
            self._visible(document_revisions),
            self._visible(documents),
            self._visible(sources),
            documents.c.kind != "asset_inventory",
        )

    def list_events(
        self, filters: EventFilters, cursor: str | None = None, limit: int = 20
    ) -> EventListResponse:
        if not 1 <= limit <= 100:
            raise ValueError("event page limit outside bounds")
        query = select(events).where(self._visible(events))
        if filters.q:
            identifiers = exists(
                select(event_external_ids.c.event_id).where(
                    event_external_ids.c.event_id == events.c.event_id,
                    event_external_ids.c.scope_key == events.c.scope_key,
                    event_external_ids.c.id_value.icontains(filters.q, autoescape=True),
                )
            )
            query = query.where(
                or_(events.c.title.icontains(filters.q, autoescape=True), identifiers)
            )
        if filters.risk_type:
            query = query.where(events.c.event_type == filters.risk_type)
        revision_query = (
            select(event_documents.c.event_id)
            .select_from(
                event_documents.join(
                    self._revision_join(),
                    event_documents.c.revision_id == document_revisions.c.revision_id,
                )
            )
            .where(event_documents.c.event_id == events.c.event_id, self._revision_visible())
        )
        if filters.product:
            product_query = revision_query.join(
                claims, claims.c.source_revision_id == document_revisions.c.revision_id
            ).where(
                event_documents.c.active.is_(True),
                document_revisions.c.is_current.is_(True),
                self._visible(claims),
                claims.c.is_current.is_(True),
                claims.c.predicate == "affected_product",
                claims.c.claim_origin.in_(("source_explicit", "structured_source")),
                claims.c.object_value.icontains(filters.product, autoescape=True),
            )
            query = query.where(exists(product_query))
        if filters.updated_after is not None:
            updated = revision_query.where(
                or_(
                    document_revisions.c.ingested_at > filters.updated_after,
                    document_revisions.c.created_at > filters.updated_after,
                    event_documents.c.associated_at > filters.updated_after,
                )
            )
            query = query.where(
                or_(events.c.first_seen_at > filters.updated_after, exists(updated))
            )
        if cursor is not None:
            position = decode_event_cursor(cursor, filters)
            query = query.where(
                or_(
                    events.c.first_seen_at < position.first_seen_at,
                    and_(
                        events.c.first_seen_at == position.first_seen_at,
                        events.c.event_id < str(position.event_id),
                    ),
                )
            )
        rows = list(
            self.session.execute(
                query.order_by(events.c.first_seen_at.desc(), events.c.event_id.desc()).limit(
                    limit + 1
                )
            ).mappings()
        )
        selected = rows[:limit]
        summaries = self._summaries(selected)
        return EventListResponse(
            items=tuple(summaries[row["event_id"]] for row in selected),
            next_cursor=encode_event_cursor(selected[-1], filters) if len(rows) > limit else None,
            data_mode=self.data_mode,
        )

    def _summaries(self, rows: list[RowMapping]) -> dict[str, EventSummary]:
        ids = tuple(row["event_id"] for row in rows)
        if not ids:
            return {}
        external: dict[str, list[str]] = {event_id: [] for event_id in ids}
        for event_id, value in self.session.execute(
            select(event_external_ids.c.event_id, event_external_ids.c.id_value)
            .join(events)
            .where(
                event_external_ids.c.event_id.in_(ids),
                event_external_ids.c.scope_key == events.c.scope_key,
            )
            .order_by(event_external_ids.c.id_value)
        ):
            if not isinstance(event_id, str) or not isinstance(value, str):
                raise KnowledgeProjectionError("event identifier unavailable")
            external[event_id].append(value)
        associated: dict[str, list[RowMapping]] = {event_id: [] for event_id in ids}
        query = (
            select(event_documents.c.event_id, document_revisions, documents.c.source_id)
            .select_from(
                event_documents.join(
                    self._revision_join(),
                    event_documents.c.revision_id == document_revisions.c.revision_id,
                )
            )
            .where(
                event_documents.c.event_id.in_(ids),
                event_documents.c.active.is_(True),
                self._revision_visible(),
            )
            .order_by(
                document_revisions.c.created_at.desc(),
                document_revisions.c.revision_number.desc(),
                document_revisions.c.revision_id.desc(),
            )
        )
        for revision in self.session.execute(query).mappings():
            associated[revision["event_id"]].append(revision)
        return {
            row["event_id"]: EventSummary(
                event_id=UUID(row["event_id"]),
                event_type=row["event_type"],
                title=row["title"],
                external_ids=tuple(dict.fromkeys(external[row["event_id"]])),
                primary_product_ids=(),
                first_seen_at=row["first_seen_at"],
                status=row["status"],
                source_count=len(
                    {revision["source_id"] for revision in associated[row["event_id"]]}
                ),
                latest_revision_id=(
                    UUID(associated[row["event_id"]][0]["revision_id"])
                    if associated[row["event_id"]]
                    else None
                ),
                freshness=FreshnessStatus.UNKNOWN,
            )
            for row in rows
        }

    def event_detail(self, event_id: UUID) -> EventDetailResponse:
        row = (
            self.session.execute(
                select(events).where(events.c.event_id == str(event_id), self._visible(events))
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        revisions = list(
            self.session.execute(
                select(document_revisions, documents.c.source_id, documents.c.kind)
                .select_from(
                    event_documents.join(
                        self._revision_join(),
                        event_documents.c.revision_id == document_revisions.c.revision_id,
                    )
                )
                .where(event_documents.c.event_id == str(event_id), self._revision_visible())
                .order_by(
                    document_revisions.c.created_at.desc(),
                    document_revisions.c.revision_number.desc(),
                    document_revisions.c.revision_id.desc(),
                )
            ).mappings()
        )
        revision_ids = tuple(revision["revision_id"] for revision in revisions)
        claim_rows = list(
            self.session.execute(
                select(claims)
                .where(self._visible(claims), claims.c.source_revision_id.in_(revision_ids))
                .order_by(claims.c.created_at, claims.c.claim_id)
            ).mappings()
        )
        evidence_rows = self._evidence_rows(revision_ids=revision_ids)
        evidence_by_id = {item["evidence_id"]: item for item in evidence_rows}
        claim_by_id = {item["claim_id"]: item for item in claim_rows}
        links: dict[str, list[UUID]] = {item["claim_id"]: [] for item in claim_rows}
        for claim_id, evidence_id in self.session.execute(
            select(claim_evidence.c.claim_id, claim_evidence.c.evidence_id)
            .where(claim_evidence.c.claim_id.in_(tuple(links)))
            .order_by(claim_evidence.c.evidence_id)
        ):
            if not isinstance(claim_id, str) or not isinstance(evidence_id, str):
                raise KnowledgeProjectionError("claim reference unavailable")
            if evidence_id in evidence_by_id and (
                evidence_by_id[evidence_id]["revision_id"]
                == claim_by_id[claim_id]["source_revision_id"]
            ):
                links[claim_id].append(UUID(evidence_id))
        projected_claims = tuple(
            ClaimSummary(
                claim_id=UUID(item["claim_id"]),
                predicate=item["predicate"],
                display_value=item["object_value"],
                origin=item["claim_origin"],
                status=item["claim_status"],
                source_revision_id=UUID(item["source_revision_id"]),
                evidence_ids=tuple(links[item["claim_id"]]),
            )
            for item in claim_rows
        )
        return EventDetailResponse(
            event=self._summaries([row])[str(event_id)],
            revisions=tuple(self._revision_summary(item) for item in revisions),
            claims=projected_claims,
            dimensions=self._dimensions(row, claim_rows, evidence_by_id),
            data_mode=self.data_mode,
        )

    def _revision_summary(self, row: RowMapping) -> RevisionSummary:
        return RevisionSummary(
            revision_id=UUID(row["revision_id"]),
            document_id=UUID(row["document_id"]),
            revision_number=row["revision_number"],
            source_id=UUID(row["source_id"]),
            source_published_at=row["source_published_at"],
            source_modified_at=row["source_modified_at"],
            first_observed_at=row["first_observed_at"],
            ingested_at=row["ingested_at"],
            parse_status=row["parse_status"],
            document_kind=row["kind"],
            canonical_uri=safe_source_uri(row["canonical_uri"]),
        )

    def _evidence_rows(
        self, *, revision_ids: tuple[str, ...] | None = None, evidence_id: UUID | None = None
    ) -> list[RowMapping]:
        query = (
            select(
                evidence,
                document_revisions.c.canonical_uri,
                document_revisions.c.source_published_at,
                document_revisions.c.source_modified_at,
                document_revisions.c.first_observed_at,
                document_revisions.c.ingested_at,
                document_revisions.c.is_current.label("revision_current"),
                text_blocks.c.page_number,
                text_blocks.c.json_pointer,
                text_blocks.c.start_offset.label("block_start"),
                text_blocks.c.block_text,
            )
            .select_from(
                evidence.join(
                    self._revision_join(),
                    evidence.c.revision_id == document_revisions.c.revision_id,
                ).outerjoin(
                    text_blocks,
                    and_(
                        text_blocks.c.block_id == evidence.c.block_id,
                        text_blocks.c.revision_id == evidence.c.revision_id,
                    ),
                )
            )
            .where(self._visible(evidence), self._revision_visible())
        )
        if revision_ids is not None:
            query = query.where(evidence.c.revision_id.in_(revision_ids))
        if evidence_id is not None:
            query = query.where(evidence.c.evidence_id == str(evidence_id))
        return list(self.session.execute(query).mappings())

    def read_evidence(self, evidence_id: UUID) -> EvidenceResponse:
        rows = self._evidence_rows(evidence_id=evidence_id)
        if not rows:
            raise CrossTenantAccessError("resource not found")
        return self._evidence_projection(rows[0])

    def _evidence_projection(self, row: RowMapping) -> EvidenceResponse:
        verified = row["verified_at"]
        digest = hashlib.sha256(row["quote"].encode("utf-8")).hexdigest()
        if row["block_id"] is not None and row["block_text"] is None:
            raise KnowledgeProjectionError("evidence block unavailable")
        locator: Literal["text", "pdf_page", "json_pointer", "legacy_unverified"] = (
            "legacy_unverified"
        )
        page_number = None
        pointer = None
        if row["coordinate_version"] == "fulltext_unicode_v1" and verified is not None:
            if row["block_text"] is None or row["quote_sha256"] != digest:
                raise KnowledgeProjectionError("evidence integrity unavailable")
            start = row["start_offset"] - row["block_start"]
            end = row["end_offset"] - row["block_start"]
            if (
                start < 0
                or end > len(row["block_text"])
                or row["block_text"][start:end] != row["quote"]
            ):
                raise KnowledgeProjectionError("evidence coordinates unavailable")
            page_number = row["page_number"]
            pointer = row["json_pointer"]
            locator = (
                "pdf_page"
                if page_number is not None
                else ("json_pointer" if pointer is not None else "text")
            )
        else:
            verified = None
        return EvidenceResponse(
            span_id=UUID(row["evidence_id"]),
            revision_id=UUID(row["revision_id"]),
            block_id=UUID(row["block_id"]) if row["block_id"] else None,
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            quote_text=row["quote"],
            quote_sha256=digest,
            locator_kind=locator,
            page_number=page_number,
            json_pointer=pointer,
            verified_at=verified,
            source_uri=safe_source_uri(row["canonical_uri"]),
            source_published_at=row["source_published_at"],
            source_modified_at=row["source_modified_at"],
            first_observed_at=row["first_observed_at"],
            ingested_at=row["ingested_at"],
            data_mode=self.data_mode,
        )

    def _dimensions(
        self,
        event_row: RowMapping,
        claim_rows: list[RowMapping],
        evidence_by_id: dict[str, RowMapping],
    ) -> tuple[EnrichmentProjection, ...]:
        claim_by_id = {item["claim_id"]: item for item in claim_rows}
        result = []
        rows = list(
            self.session.execute(
                select(enrichment_results)
                .where(
                    enrichment_results.c.event_id == event_row["event_id"],
                    enrichment_results.c.is_current.is_(True),
                )
                .order_by(enrichment_results.c.dimension)
            ).mappings()
        )
        for row in rows:
            for name in ("source_scope", "claim_ids", "reference_ids"):
                identifiers = row[name]
                if not isinstance(identifiers, list) or len(identifiers) > 1000:
                    raise KnowledgeProjectionError("dimension references invalid")
                for identifier in identifiers:
                    if not isinstance(identifier, str):
                        raise KnowledgeProjectionError("dimension reference invalid")
                    try:
                        UUID(identifier)
                    except ValueError:
                        raise KnowledgeProjectionError("dimension reference invalid") from None
        source_ids = {source_id for row in rows for source_id in row["source_scope"]}
        required_claims = {item for row in rows for item in row["claim_ids"]}
        required_evidence = {item for row in rows for item in row["reference_ids"]}
        for identifiers, id_column in (
            (required_claims, claims.c.claim_id),
            (required_evidence, evidence.c.evidence_id),
            (source_ids, sources.c.source_id),
        ):
            existing: set[str] = set(
                self.session.scalars(select(id_column).where(id_column.in_(identifiers)))
            )
            if identifiers - existing:
                raise KnowledgeProjectionError("dimension reference missing")
        visible_sources: set[str] = set(
            self.session.scalars(
                select(sources.c.source_id).where(
                    self._visible(sources), sources.c.source_id.in_(source_ids)
                )
            )
        )
        visible_references: dict[str, set[str]] = {}
        for name, relation, identifier_column, revision_column, required in (
            ("claim_ids", claims, claims.c.claim_id, claims.c.source_revision_id, required_claims),
            (
                "reference_ids",
                evidence,
                evidence.c.evidence_id,
                evidence.c.revision_id,
                required_evidence,
            ),
        ):
            visible_references[name] = set(
                self.session.scalars(
                    select(identifier_column)
                    .select_from(
                        relation.join(
                            self._revision_join(),
                            revision_column == document_revisions.c.revision_id,
                        )
                    )
                    .where(
                        identifier_column.in_(required),
                        self._visible(relation),
                        self._revision_visible(),
                    )
                )
            )
        for row in rows:
            if (
                any(item not in visible_references["claim_ids"] for item in row["claim_ids"])
                or any(
                    item not in visible_references["reference_ids"] for item in row["reference_ids"]
                )
                or any(item not in visible_sources for item in row["source_scope"])
            ):
                continue
            if any(item not in claim_by_id for item in row["claim_ids"]) or any(
                item not in evidence_by_id for item in row["reference_ids"]
            ):
                raise KnowledgeProjectionError("dimension reference belongs to unrelated revision")
            citations = []
            freshness = FreshnessStatus(row["freshness"] or "unknown")
            if row["event_version"] != event_row["business_version"]:
                freshness = FreshnessStatus.STALE
            if freshness == "current" and row["observed_at"] is None:
                freshness = FreshnessStatus.UNKNOWN
            for reference_id in row["reference_ids"]:
                reference = evidence_by_id[reference_id]
                projected = self._evidence_projection(reference)
                if projected.verified_at is None or projected.source_uri is None:
                    raise KnowledgeProjectionError("dimension reference unavailable")
                citations.append(
                    CitationProjection(
                        evidence_id=projected.span_id,
                        revision_id=projected.revision_id,
                        quote=projected.quote_text,
                        locator=reference["locator"],
                        source_uri=projected.source_uri,
                    )
                )
                if not reference["revision_current"]:
                    freshness = FreshnessStatus.STALE
            if any(
                not claim_by_id[item]["is_current"]
                or claim_by_id[item]["claim_status"] in {"withdrawn", "superseded"}
                or claim_by_id[item]["freshness"] == "stale"
                for item in row["claim_ids"]
            ):
                freshness = FreshnessStatus.STALE
            result.append(
                EnrichmentProjection(
                    dimension=row["dimension"],
                    status=row["status"],
                    claim_ids=tuple(UUID(item) for item in row["claim_ids"]),
                    citations=tuple(citations),
                    freshness=freshness,
                    observed_at=row["observed_at"],
                    source_version=row["source_version"],
                    error_code=row["error_code"],
                )
            )
        return tuple(result)
