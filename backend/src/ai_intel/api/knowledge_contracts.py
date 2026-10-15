"""工作台只读投影；与已冻结API v2维度/状态保持一致。"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from ai_intel.domain.enums import ClaimOrigin, ClaimStatus, DimensionStatus, FreshnessStatus
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp

DimensionName = Literal[
    "cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure"
]
DataMode = Literal["live", "fixture"]


class CitationProjection(StrictRecord):
    """引用保留版本与定位；它的存在本身不证明支撑关系。"""

    evidence_id: UUID
    revision_id: UUID
    quote: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_uri: HttpUrl


class EnrichmentProjection(StrictRecord):
    """九维公共响应，不泄露内部job/scope字段。"""

    dimension: DimensionName
    status: DimensionStatus
    claim_ids: tuple[UUID, ...] = Field(max_length=100)
    citations: tuple[CitationProjection, ...] = Field(max_length=100)
    freshness: FreshnessStatus
    observed_at: UtcTimestamp | None
    source_version: str | None
    error_code: str | None

    @model_validator(mode="after")
    def available_requires_citations(self) -> EnrichmentProjection:
        """不能把没有来源的值当作已取得的富化结果。"""
        if self.status == DimensionStatus.AVAILABLE and not self.citations:
            raise ValueError("available enrichment requires a citation")
        return self


class EventSummary(StrictRecord):
    """列表显示保存的事件信息，不推导安全或已入侵结论。"""

    event_id: UUID
    event_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    external_ids: tuple[str, ...] = Field(max_length=100)
    primary_product_ids: tuple[UUID, ...] = Field(max_length=100)
    first_seen_at: UtcTimestamp
    status: str = Field(min_length=1, max_length=100)
    source_count: Annotated[int, Field(strict=True, ge=0)]
    latest_revision_id: UUID | None
    freshness: FreshnessStatus


class EventListResponse(StrictRecord):
    schema_version: Literal[2] = 2
    items: tuple[EventSummary, ...] = Field(max_length=100)
    next_cursor: str | None = Field(min_length=1, max_length=2048)
    data_mode: DataMode


class RevisionSummary(StrictRecord):
    """来源时间与入库时间分别保存，旧记录缺证据时保留null。"""

    revision_id: UUID
    document_id: UUID
    revision_number: int = Field(ge=1)
    source_id: UUID
    source_published_at: UtcTimestamp | None
    source_modified_at: UtcTimestamp | None
    first_observed_at: UtcTimestamp | None
    ingested_at: UtcTimestamp | None
    parse_status: Literal["pending", "parsed", "partial", "failed", "legacy_unverified"]
    document_kind: Literal[
        "advisory", "article", "paper", "repository_record", "standard", "policy"
    ]
    canonical_uri: HttpUrl | None


class ClaimSummary(StrictRecord):
    claim_id: UUID
    predicate: str = Field(min_length=1, max_length=200)
    display_value: str = Field(min_length=1, max_length=4000)
    origin: ClaimOrigin
    status: ClaimStatus
    source_revision_id: UUID | None
    evidence_ids: tuple[UUID, ...] = Field(max_length=100)


class EventDetailResponse(StrictRecord):
    schema_version: Literal[2] = 2
    event: EventSummary
    dimensions: tuple[EnrichmentProjection, ...] = Field(max_length=9)
    revisions: tuple[RevisionSummary, ...]
    claims: tuple[ClaimSummary, ...]
    data_mode: DataMode


class EvidenceResponse(StrictRecord):
    """不暴露对象存储路径；保留原文Unicode坐标与缺失时间。"""

    schema_version: Literal[2] = 2
    span_id: UUID
    revision_id: UUID
    block_id: UUID | None
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    quote_text: str = Field(min_length=1)
    quote_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    locator_kind: Literal["text", "pdf_page", "json_pointer", "legacy_unverified"]
    page_number: int | None = Field(ge=1)
    json_pointer: str | None
    verified_at: UtcTimestamp | None
    source_uri: HttpUrl | None
    source_published_at: UtcTimestamp | None
    source_modified_at: UtcTimestamp | None
    first_observed_at: UtcTimestamp | None
    ingested_at: UtcTimestamp | None
    data_mode: DataMode

    @model_validator(mode="after")
    def validate_unicode_span(self) -> EvidenceResponse:
        """倒置坐标不能通过响应验证被包装成正常引文。"""
        if self.end_offset < self.start_offset:
            raise ValueError("evidence span is inverted")
        return self
