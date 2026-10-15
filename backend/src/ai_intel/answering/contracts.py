"""Bounded model candidates and internal results, without an API or persistence contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.infrastructure.models.generation import AttemptMetadata

MAX_CLAIMS = 20
MAX_CITATIONS = 20
LINE_SEPARATORS = frozenset("\r\n\v\f\x85\u2028\u2029")


def validate_answer_text(value: str) -> str:
    """Preserve exact characters while rejecting hidden lines and invalid UTF-8."""
    if not value.strip() or any(character in LINE_SEPARATORS for character in value):
        raise ValueError("answer text must be a nonempty single line")
    if "\0" in value:
        raise ValueError("answer text contains a forbidden character")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("answer text must be valid UTF-8") from None
    return value


class AnswerClaim(BaseModel):
    """Facts require source identities; suggestions are separately verified and displayed."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    text: str = Field(min_length=1, max_length=2048)
    kind: Literal["source_fact", "rule_result", "project_suggestion"]
    support_ids: tuple[UUID, ...] = Field(max_length=MAX_CITATIONS)

    _valid_text = field_validator("text")(validate_answer_text)

    @model_validator(mode="after")
    def validate_supports(self) -> AnswerClaim:
        if self.kind != "project_suggestion" and not self.support_ids:
            raise ValueError("a factual claim requires support")
        if len(set(self.support_ids)) != len(self.support_ids):
            raise ValueError("claim supports must be unique")
        return self


class CitationCandidate(BaseModel):
    """The model selects an exact quote, never source identity or locator metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    evidence_id: UUID
    quote: str = Field(min_length=1, max_length=2048)

    _valid_quote = field_validator("quote")(validate_answer_text)


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    claims: tuple[AnswerClaim, ...] = Field(min_length=1, max_length=MAX_CLAIMS)
    citations: tuple[CitationCandidate, ...] = Field(max_length=MAX_CITATIONS)


class ClaimVerdict(BaseModel):
    """An explicit verdict for a server-assigned claim index, including factual safeguards."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    claim_index: int = Field(ge=1, le=MAX_CLAIMS)
    verdict: Literal["supported", "unsupported", "unknown"]
    numbers_match: bool
    states_preserved: bool
    suggestion_only: bool


class SupportVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    verdicts: tuple[ClaimVerdict, ...] = Field(min_length=1, max_length=MAX_CLAIMS)


@dataclass(frozen=True)
class GroundedAnswerDraft:
    answer_text: str
    claims: tuple[AnswerClaim, ...]
    citations: tuple[CitationProjection, ...]
    limitations: tuple[str, ...]
    attempts: tuple[AttemptMetadata, ...]


class GroundedAnswerFailure(RuntimeError):
    """Only a fixed error code and actual call metadata escape failure boundaries."""

    def __init__(self, code: str, attempts: tuple[AttemptMetadata, ...] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.attempts = attempts
