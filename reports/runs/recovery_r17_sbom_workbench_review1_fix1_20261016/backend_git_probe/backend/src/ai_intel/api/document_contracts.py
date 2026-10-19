"""资料库只读合同；覆盖范围、原始日期精度和历史版本分别表达。"""

from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from pydantic import Field, HttpUrl, field_validator, model_validator

from ai_intel.api.knowledge_contracts import DataMode, EvidenceResponse
from ai_intel.domain.enums import SourceCategory
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp
from ai_intel.infrastructure.network import SENSITIVE_QUERY_KEYS

DocumentKindFilter = Literal[
    "advisory", "article", "paper", "repository_record", "standard", "policy"
]
ContentCoverage = Literal["full_text", "abstract", "feed_excerpt", "metadata", "unknown"]
BoundedSourceText = Annotated[str, Field(min_length=1, max_length=1000)]


def validate_public_source_uri(value: HttpUrl | None) -> HttpUrl | None:
    """只返回可供用户打开的HTTPS链接，不把凭据或敏感query带进界面。"""
    if value is None:
        return None
    uri = urlsplit(str(value))
    if (
        uri.scheme != "https"
        or uri.username is not None
        or uri.password is not None
        or uri.fragment
        or any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(uri.query))
    ):
        raise ValueError("source URI is not a public HTTPS link")
    return value


class DocumentSummary(StrictRecord):
    document_id: UUID
    source_id: UUID
    revision_id: UUID
    source_name: str = Field(min_length=1, max_length=300)
    source_category: SourceCategory
    document_kind: DocumentKindFilter
    title: str = Field(min_length=1, max_length=500)
    canonical_uri: HttpUrl | None
    revision_number: int = Field(strict=True, ge=1)
    is_current: bool
    source_published_at: UtcTimestamp | None
    source_modified_at: UtcTimestamp | None
    first_observed_at: UtcTimestamp | None
    ingested_at: UtcTimestamp | None
    parse_status: Literal["pending", "parsed", "partial", "failed", "legacy_unverified"]
    content_coverage: ContentCoverage
    published_at_raw: str | None = Field(min_length=1, max_length=256)
    published_precision: Literal["instant", "calendar_date", "unknown"]

    _public_uri = field_validator("canonical_uri")(validate_public_source_uri)

    @model_validator(mode="after")
    def require_supported_date_precision(self) -> "DocumentSummary":
        """没有来源时区不能声明精确UTC时刻，日期精度不能暗中升级。"""
        if self.published_precision == "instant" and self.source_published_at is None:
            raise ValueError("instant publication requires a source timestamp")
        if self.published_precision == "calendar_date" and (
            self.source_published_at is not None or self.published_at_raw is None
        ):
            raise ValueError("calendar publication must retain only its raw date")
        return self


class DocumentListResponse(StrictRecord):
    schema_version: Literal[2] = 2
    items: tuple[DocumentSummary, ...] = Field(max_length=100)
    next_cursor: str | None = Field(min_length=1, max_length=2048)
    data_mode: DataMode


class DocumentDetailResponse(StrictRecord):
    schema_version: Literal[2] = 2
    document: DocumentSummary
    evidence: tuple[EvidenceResponse, ...] = Field(max_length=100)
    evidence_total: int = Field(strict=True, ge=0)
    next_evidence_offset: int | None = Field(strict=True, ge=1, le=2000)
    license_identifier: str | None = Field(min_length=1, max_length=256)
    license_uri: HttpUrl | None
    source_notes: tuple[BoundedSourceText, ...] = Field(max_length=20)
    data_mode: DataMode

    _public_uri = field_validator("license_uri")(validate_public_source_uri)

    @model_validator(mode="after")
    def keep_one_revision_and_mode(self) -> "DocumentDetailResponse":
        """分页也不能把别的修订、fixture片段或无效总数混入当前正文。"""
        if self.evidence_total < len(self.evidence):
            raise ValueError("document evidence count is inconsistent")
        if any(
            item.revision_id != self.document.revision_id or item.data_mode != self.data_mode
            for item in self.evidence
        ):
            raise ValueError("document evidence has different revision or data mode")
        return self


class DocumentRevisionListResponse(StrictRecord):
    schema_version: Literal[2] = 2
    items: tuple[DocumentSummary, ...] = Field(max_length=100)
    next_offset: int | None = Field(strict=True, ge=1, le=100000)
    data_mode: DataMode
