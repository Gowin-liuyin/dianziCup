"""与公共v2一致的问答投影；尚未支持的范围由R05服务显式拒绝。"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ai_intel.api.knowledge_contracts import CitationProjection, DataMode
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp


class QuestionRequest(StrictRecord):
    question: str = Field(min_length=1, max_length=4096, strict=True)
    conversation_id: UUID | None = None
    asset_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    event_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    mode: Literal["auto", "library", "investigate"]
    known_at: UtcTimestamp | None = None
    valid_at: UtcTimestamp | None = None

    @model_validator(mode="after")
    def validate_question_boundary(self) -> QuestionRequest:
        if not self.question.strip() or "\0" in self.question:
            raise ValueError("question must be nonempty text")
        try:
            self.question.encode("utf-8")
        except UnicodeError:
            raise ValueError("question must be valid UTF-8") from None
        return self


class AnswerClaimProjection(StrictRecord):
    text: str = Field(min_length=1)
    kind: Literal["source_fact", "rule_result", "project_suggestion"]
    support_ids: tuple[UUID, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def facts_require_support(self) -> AnswerClaimProjection:
        if self.kind != "project_suggestion" and not self.support_ids:
            raise ValueError("facts require support")
        return self


class QuestionAnswerResponse(StrictRecord):
    kind: Literal["completed"] = "completed"
    answer_id: UUID
    answer_text: str = Field(min_length=1)
    claims: tuple[AnswerClaimProjection, ...] = Field(max_length=100)
    citations: tuple[CitationProjection, ...] = Field(max_length=100)
    limitations: tuple[Annotated[str, Field(min_length=1)], ...] = Field(max_length=100)
    freshness: FreshnessStatus
    data_mode: DataMode
    started_at: UtcTimestamp
    completed_at: UtcTimestamp
    latency_milliseconds: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_completed_answer(self) -> QuestionAnswerResponse:
        citation_ids = [citation.evidence_id for citation in self.citations]
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("answer citations must be unique")
        if any(set(claim.support_ids) - set(citation_ids) for claim in self.claims):
            raise ValueError("answer support is not present in citations")
        if self.completed_at < self.started_at:
            raise ValueError("answer completion precedes start")
        return self
