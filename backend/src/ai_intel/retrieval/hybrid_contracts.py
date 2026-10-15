"""Internal corpus retrieval contracts; identities arrive only through AccessScope."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from ai_intel.domain.access import AccessScope
from ai_intel.infrastructure.models.semantic import E5_MODEL


class HybridRetrievalError(RuntimeError):
    """Safe failure codes distinguish unavailability from an empty corpus result."""


@dataclass(frozen=True)
class HybridQuery:
    text: str
    available_after: datetime | None = None
    available_before: datetime = field(default_factory=lambda: datetime.now(UTC))
    include_graph: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 500:
            raise ValueError("query text must contain 1..500 characters")
        if "\x00" in self.text:
            raise ValueError("query text must not contain NUL")
        try:
            self.text.encode("utf-8", errors="strict")
        except UnicodeError:
            raise ValueError("query text must be valid Unicode") from None
        for value in (self.available_after, self.available_before):
            if value is not None and (
                not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("query timestamps must be timezone aware")
        if self.available_after is not None and self.available_after > self.available_before:
            raise ValueError("query time bounds are inverted")
        if type(self.include_graph) is not bool:
            raise ValueError("include_graph must be boolean")


@dataclass(frozen=True)
class IndexGeneration:
    generation_id: str
    index_name: str
    model_version: str = E5_MODEL.model_version
    dimension: int = 384

    def require_fixed_space(self) -> None:
        if self.model_version != E5_MODEL.model_version or type(self.dimension) is not int:
            raise HybridRetrievalError("index_space_rebuild_required")
        if (
            self.dimension != 384
            or not isinstance(self.generation_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", self.generation_id) is None
        ):
            raise HybridRetrievalError("index_space_rebuild_required")


@dataclass(frozen=True)
class IndexChange:
    outbox_id: str
    scope_key: str


@dataclass(frozen=True)
class IndexReceipt:
    generation_id: str
    outbox_id: str
    scope_key: str
    indexed_epoch: int
    chunk_count: int
    replayed: bool


@dataclass(frozen=True)
class CorpusCandidate:
    chunk_id: str
    evidence_id: str
    revision_id: str
    document_id: str
    source_id: str
    event_id: str
    claim_id: str
    scope_key: str
    visibility: Literal["public", "tenant"]
    tenant_id: str | None
    available_at: datetime
    start_offset: int
    end_offset: int
    text: str
    text_sha256: str
    source_uri: str
    locator: str


@dataclass(frozen=True)
class RetrievalHit:
    candidate: CorpusCandidate
    rerank_score: float
    rrf_score: float
    exact_identifier: bool

    def __post_init__(self) -> None:
        if not math.isfinite(self.rerank_score) or not math.isfinite(self.rrf_score):
            raise ValueError("retrieval scores must be finite")


@dataclass(frozen=True)
class RetrievalTrace:
    exact_count: int
    bm25_count: int
    vector_count: int
    graph_count: int
    validated_count: int
    reranked_count: int
    exact_seconds: float
    bm25_seconds: float
    vector_seconds: float
    validation_seconds: float
    rerank_seconds: float
    total_seconds: float


@dataclass(frozen=True)
class HybridSelection:
    hits: tuple[RetrievalHit, ...]
    partial: bool
    reasons: tuple[str, ...]
    scope_epochs: tuple[tuple[str, int], ...]
    indexed_epochs: tuple[tuple[str, int | None], ...]
    embedding_model: str
    reranker_model: str
    graph_status: Literal["not_configured", "available", "not_requested"]
    trace: RetrievalTrace


class GraphCandidates(Protocol):
    """Only candidate IDs are injected; the same PG authority checks remain mandatory."""

    def retrieve(self, scope: AccessScope, query: HybridQuery) -> tuple[str, ...]: ...
