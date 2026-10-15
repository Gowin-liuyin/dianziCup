"""Frozen internal seams for bounded enrichment; candidates never publish themselves."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from ai_intel.domain.enrichment_values import CveId, DimensionName, EnrichmentValue
from ai_intel.domain.enums import (
    ClaimOrigin,
    DimensionStatus,
    DocumentKind,
    FreshnessStatus,
    SourceCategory,
)
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp

DIMENSION_BY_VALUE_KIND: dict[str, DimensionName] = {
    "cvss_signal": "cvss",
    "epss_signal": "epss",
    "kev_signal": "kev",
    "weakness": "cwe",
    "atlas_mapping": "atlas",
    "version_assertion": "versions",
    "literature_reference": "literature",
    "artifact_reference": "poc",
    "exposure_aggregate": "exposure",
}
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class EnrichmentContext(StrictRecord):
    """The service derives visible active revisions and supported IDs from PostgreSQL."""

    event_id: UUID
    expected_event_version: Annotated[int, Field(strict=True, ge=1)]
    revision_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    external_cve_ids: tuple[CveId, ...] = Field(default=(), max_length=20)
    rule_version: Annotated[str, Field(min_length=1, max_length=200)]


class EnrichmentBlock(StrictRecord):
    """Offsets here identify the block in the immutable revision's normalized text."""

    block_id: UUID
    start_offset: Annotated[int, Field(strict=True, ge=0)]
    text: Annotated[str, Field(min_length=1, max_length=20000)]
    text_sha256: Hash
    json_pointer: Annotated[str, Field(max_length=2000)] | None = None
    page_number: Annotated[int, Field(strict=True, ge=1)] | None = None

    @model_validator(mode="after")
    def verify_block_hash(self) -> EnrichmentBlock:
        if hashlib.sha256(self.text.encode()).hexdigest() != self.text_sha256:
            raise ValueError("enrichment block hash mismatch")
        return self


class EnrichmentDocument(StrictRecord):
    revision_id: UUID
    document_id: UUID
    source_id: UUID
    document_kind: DocumentKind
    source_category: SourceCategory
    canonical_uri: HttpUrl
    source_record_id: Annotated[str, Field(min_length=1, max_length=1000)]
    content_sha256: Hash
    blocks: tuple[EnrichmentBlock, ...] = Field(min_length=1, max_length=200)
    blocks_complete: bool = Field(strict=True)
    content_coverage: Literal["full_text", "metadata_only", "excerpt", "unknown"]
    source_version: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    observed_at: UtcTimestamp | None = None
    json_payload: Annotated[bytes, Field(strict=True, max_length=2097152)] | None = None

    @model_validator(mode="after")
    def verify_bounded_document_input(self) -> EnrichmentDocument:
        if len({block.block_id for block in self.blocks}) != len(self.blocks):
            raise ValueError("enrichment document has repeated blocks")
        if sum(len(block.text) for block in self.blocks) > 200000:
            raise ValueError("enrichment document text limit exceeded")
        if self.json_payload is not None and (
            hashlib.sha256(self.json_payload).hexdigest() != self.content_sha256
        ):
            raise ValueError("enrichment JSON payload hash mismatch")
        return self


class CandidateEvidence(StrictRecord):
    """Quote coordinates are relative to the named block; publication adds block.start_offset."""

    revision_id: UUID
    block_id: UUID
    start_offset: Annotated[int, Field(strict=True, ge=0)]
    end_offset: Annotated[int, Field(strict=True, ge=1)]
    quote_text: Annotated[str, Field(min_length=1, max_length=2000)]
    quote_sha256: Hash

    @model_validator(mode="after")
    def verify_quote_shape(self) -> CandidateEvidence:
        if self.end_offset - self.start_offset != len(self.quote_text):
            raise ValueError("candidate quote length mismatch")
        if hashlib.sha256(self.quote_text.encode()).hexdigest() != self.quote_sha256:
            raise ValueError("candidate quote hash mismatch")
        return self


class EvidenceBoundCandidate(StrictRecord):
    """A typed proposal still needs block identity, field and semantic support validation."""

    dimension: DimensionName
    value: EnrichmentValue
    evidence: tuple[CandidateEvidence, ...] = Field(min_length=1, max_length=20)
    origin: Literal[
        ClaimOrigin.SOURCE_EXPLICIT,
        ClaimOrigin.STRUCTURED_SOURCE,
        ClaimOrigin.RULE_DERIVED,
        ClaimOrigin.MODEL_HYPOTHESIS,
    ]
    limitations: tuple[Annotated[str, Field(min_length=1, max_length=2000)], ...] = Field(
        default=(), max_length=20
    )

    @model_validator(mode="after")
    def verify_dimension_value(self) -> EvidenceBoundCandidate:
        if DIMENSION_BY_VALUE_KIND[self.value.kind] != self.dimension:
            raise ValueError("candidate dimension does not match typed value")
        return self


class DimensionAttempt(StrictRecord):
    """Attempts preserve partial failures; final PG publication validates every candidate again."""

    dimension: DimensionName
    status: DimensionStatus
    candidates: tuple[EvidenceBoundCandidate, ...] = Field(default=(), max_length=100)
    source_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    searched_at: UtcTimestamp | None = None
    observed_at: UtcTimestamp | None = None
    source_version: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN
    error_code: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,120}$")] | None = None

    @model_validator(mode="after")
    def verify_attempt_state(self) -> DimensionAttempt:
        if any(candidate.dimension != self.dimension for candidate in self.candidates):
            raise ValueError("attempt contains another dimension")
        if self.status in {DimensionStatus.AVAILABLE, DimensionStatus.CONFLICT}:
            minimum = 2 if self.status == DimensionStatus.CONFLICT else 1
            if len(self.candidates) < minimum:
                raise ValueError("available or conflicting attempt requires candidates")
            if self.status == DimensionStatus.CONFLICT and (
                len({candidate.value.model_dump_json() for candidate in self.candidates}) < 2
            ):
                raise ValueError("identical values do not establish a conflict")
        elif self.status != DimensionStatus.PENDING and self.candidates:
            raise ValueError("unavailable attempt cannot carry proposed facts")
        if self.status == DimensionStatus.NOT_FOUND and (
            self.searched_at is None or not self.source_ids
        ):
            raise ValueError("not_found requires explicit searched time and source scope")
        if self.status in {DimensionStatus.FAILED, DimensionStatus.BLOCKED} and not self.error_code:
            raise ValueError("failed or blocked attempt requires a reason")
        if self.freshness == FreshnessStatus.CURRENT and self.observed_at is None:
            raise ValueError("current freshness requires an observed time")
        return self
