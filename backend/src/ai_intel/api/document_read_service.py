"""公开资料的当前、历史和证据投影；PG仍是唯一事实来源。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from sqlalchemy import Text, and_, column, func, or_, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from ai_intel.api.document_contracts import (
    ContentCoverage,
    DocumentDetailResponse,
    DocumentKindFilter,
    DocumentListResponse,
    DocumentRevisionListResponse,
    DocumentSummary,
    validate_public_source_uri,
)
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.domain.enums import SourceCategory
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp
from ai_intel.knowledge.models import document_revisions, documents

sources = table(
    "sources",
    column("source_id", Text),
    column("name", Text),
    column("category", Text),
    column("visibility", Text),
    column("tenant_id", Text),
)


class InvalidDocumentCursor(ValueError):
    """排序游标无效或过滤条件改变，不能静默回到首页。"""


class DocumentFilters(StrictRecord):
    q: str = Field(default="", max_length=500)
    document_kind: DocumentKindFilter | None = None
    source_category: SourceCategory | None = None

    @field_validator("q")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("search text must not contain NUL")
        return value

    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class DocumentCursor(StrictRecord):
    version: int = Field(strict=True, ge=1, le=1)
    ingested_at: UtcTimestamp
    document_id: UUID
    filters_sha256: str = Field(pattern="^[0-9a-f]{64}$")


def encode_document_cursor(
    ingested_at: datetime, document_id: UUID, filters: DocumentFilters
) -> str:
    cursor = DocumentCursor(
        version=1,
        ingested_at=ingested_at,
        document_id=document_id,
        filters_sha256=filters.fingerprint(),
    )
    return base64.urlsafe_b64encode(cursor.model_dump_json().encode()).decode().rstrip("=")


def decode_document_cursor(value: str, filters: DocumentFilters) -> DocumentCursor:
    if not 1 <= len(value) <= 2048 or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise InvalidDocumentCursor("invalid document cursor")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        pairs = json.loads(raw, object_pairs_hook=lambda entries: entries)
        if (
            not isinstance(pairs, list)
            or len(pairs) != 4
            or any(not isinstance(pair, tuple) or len(pair) != 2 for pair in pairs)
            or len({key for key, _ in pairs}) != len(pairs)
        ):
            raise ValueError("invalid cursor fields")
        cursor = DocumentCursor.model_validate(dict(pairs))
        if cursor.filters_sha256 != filters.fingerprint():
            raise ValueError("cursor filters changed")
        return cursor
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError) as error:
        raise InvalidDocumentCursor("invalid document cursor") from error


class _DocumentMetadata(BaseModel):
    """只投影已约定字段；来源的任意JSON/HTML不直接暴露给界面。"""

    model_config = ConfigDict(extra="ignore", strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content_coverage: ContentCoverage = "unknown"
    published_at_raw: str | None = Field(default=None, min_length=1, max_length=256)
    published_precision: Literal["instant", "calendar_date", "unknown"] | None = None
    license_identifier: str | None = Field(default=None, min_length=1, max_length=256)
    license_uri: HttpUrl | None = None
    source_notes: tuple[str, ...] = Field(default=(), max_length=20)

    @field_validator("source_notes", mode="before")
    @classmethod
    def read_json_notes(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("source_notes")
    @classmethod
    def bound_notes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not 1 <= len(note) <= 1000 or "\x00" in note for note in value):
            raise ValueError("source notes invalid")
        return value

    _public_license = field_validator("license_uri")(validate_public_source_uri)


class DocumentReadService:
    """资料不强制转换为漏洞事件；历史始终按选定修订读取。"""

    def __init__(self, session: Session, scope: AccessScope, data_mode: DataMode) -> None:
        scope.requires(READ_PUBLIC)
        self.session = session
        self.scope = scope
        self.data_mode = data_mode

    @staticmethod
    def _visible() -> ColumnElement[bool]:
        return and_(
            documents.c.visibility == "public",
            documents.c.tenant_id.is_(None),
            document_revisions.c.visibility == "public",
            document_revisions.c.tenant_id.is_(None),
            sources.c.visibility == "public",
            sources.c.tenant_id.is_(None),
            documents.c.kind != "asset_inventory",
        )

    @staticmethod
    def _rows_query() -> Select[tuple[object, ...]]:
        return select(
            document_revisions,
            documents.c.source_id,
            documents.c.kind,
            documents.c.title.label("current_title"),
            sources.c.name.label("source_name"),
            sources.c.category.label("source_category"),
        ).select_from(
            document_revisions.join(documents).join(
                sources, sources.c.source_id == documents.c.source_id
            )
        )

    def _summary(self, row: RowMapping) -> DocumentSummary:
        metadata = _DocumentMetadata.model_validate(row["source_metadata"])
        title = metadata.title
        if title is None:
            title = row["current_title"] if row["is_current"] else "历史标题未记录"
        return DocumentSummary(
            document_id=row["document_id"],
            source_id=row["source_id"],
            revision_id=row["revision_id"],
            source_name=row["source_name"],
            source_category=row["source_category"],
            document_kind=row["kind"],
            title=title,
            canonical_uri=row["canonical_uri"],
            revision_number=row["revision_number"],
            is_current=row["is_current"],
            source_published_at=row["source_published_at"],
            source_modified_at=row["source_modified_at"],
            first_observed_at=row["first_observed_at"],
            ingested_at=row["ingested_at"],
            parse_status=row["parse_status"],
            content_coverage=metadata.content_coverage,
            published_at_raw=metadata.published_at_raw,
            published_precision=metadata.published_precision
            or ("instant" if row["source_published_at"] is not None else "unknown"),
        )

    def list_documents(
        self, filters: DocumentFilters, cursor: str | None = None, limit: int = 20
    ) -> DocumentListResponse:
        if not 1 <= limit <= 100:
            raise ValueError("document page limit outside bounds")
        order_time = func.coalesce(
            document_revisions.c.ingested_at, document_revisions.c.created_at
        )
        query = self._rows_query().where(self._visible(), document_revisions.c.is_current.is_(True))
        if filters.q:
            title = func.coalesce(
                document_revisions.c.source_metadata["title"].astext, documents.c.title
            )
            query = query.where(title.icontains(filters.q, autoescape=True))
        if filters.document_kind is not None:
            query = query.where(documents.c.kind == filters.document_kind)
        if filters.source_category is not None:
            query = query.where(sources.c.category == filters.source_category.value)
        if cursor is not None:
            position = decode_document_cursor(cursor, filters)
            query = query.where(
                or_(
                    order_time < position.ingested_at,
                    and_(
                        order_time == position.ingested_at,
                        documents.c.document_id > str(position.document_id),
                    ),
                )
            )
        rows = list(
            self.session.execute(
                query.order_by(order_time.desc(), documents.c.document_id).limit(limit + 1)
            ).mappings()
        )
        selected = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = selected[-1]
            next_cursor = encode_document_cursor(
                last["ingested_at"] or last["created_at"], UUID(last["document_id"]), filters
            )
        return DocumentListResponse(
            items=tuple(self._summary(row) for row in selected),
            next_cursor=next_cursor,
            data_mode=self.data_mode,
        )

    def document_detail(
        self,
        document_id: UUID,
        revision_id: UUID | None = None,
        evidence_offset: int = 0,
        evidence_limit: int = 100,
    ) -> DocumentDetailResponse:
        if not 0 <= evidence_offset <= 2000 or not 1 <= evidence_limit <= 100:
            raise ValueError("evidence page outside bounds")
        query = self._rows_query().where(
            self._visible(), documents.c.document_id == str(document_id)
        )
        query = query.where(
            document_revisions.c.revision_id == str(revision_id)
            if revision_id is not None
            else document_revisions.c.is_current.is_(True)
        )
        row = self.session.execute(query).mappings().one_or_none()
        if row is None:
            raise CrossTenantAccessError("resource not found")
        metadata = _DocumentMetadata.model_validate(row["source_metadata"])
        items, total = KnowledgeReadService(
            self.session, self.scope, self.data_mode
        ).read_public_revision_evidence(UUID(row["revision_id"]), evidence_offset, evidence_limit)
        if total > 2000:
            raise ValueError("document evidence exceeds supported source bounds")
        notes = metadata.source_notes
        if metadata.title is None and not row["is_current"]:
            notes = (*notes[:19], "该历史修订未保存标题；未使用当前标题替代。")
        if total == 0:
            notes = (*notes[:19], "没有可展示的公开证据正文；未将空结果解释为不存在风险。")
        return DocumentDetailResponse(
            document=self._summary(row),
            evidence=items,
            evidence_total=total,
            next_evidence_offset=(
                evidence_offset + len(items) if evidence_offset + len(items) < total else None
            ),
            license_identifier=metadata.license_identifier,
            license_uri=metadata.license_uri,
            source_notes=notes,
            data_mode=self.data_mode,
        )

    def list_revisions(
        self, document_id: UUID, offset: int = 0, limit: int = 20
    ) -> DocumentRevisionListResponse:
        if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
            raise ValueError("revision page outside bounds")
        query = self._rows_query().where(
            self._visible(), documents.c.document_id == str(document_id)
        )
        if self.session.execute(query.limit(1)).first() is None:
            raise CrossTenantAccessError("resource not found")
        rows = list(
            self.session.execute(
                query.order_by(document_revisions.c.revision_number.desc())
                .offset(offset)
                .limit(limit + 1)
            ).mappings()
        )
        return DocumentRevisionListResponse(
            items=tuple(self._summary(row) for row in rows[:limit]),
            next_offset=offset + limit if len(rows) > limit else None,
            data_mode=self.data_mode,
        )
