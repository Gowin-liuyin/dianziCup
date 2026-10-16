"""Internal typed conversation and PG evidence projections; no public API expansion."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_intel.api.knowledge_contracts import CitationProjection, DataMode
from ai_intel.domain.values import UtcTimestamp


class ConversationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


QuerySlot = Literal["facts", "version", "impact", "fix", "mechanism", "standard"]
GapSlot = Literal[
    "facts",
    "version",
    "impact",
    "fix",
    "mechanism",
    "standard",
    "history",
    "investigation",
    "retrieval",
]
GapState = Literal["unknown", "conflict", "unsupported", "not_configured", "partial"]


class EventReference(ConversationRecord):
    event_id: UUID
    identifiers: tuple[str, ...] = Field(max_length=20)
    business_version: int = Field(ge=1)


class AssetSnapshotReference(ConversationRecord):
    asset_id: UUID
    snapshot_id: UUID
    recorded_at: UtcTimestamp
    snapshot_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class DerivedRetrievalQuery(ConversationRecord):
    text: str = Field(min_length=1, max_length=500)
    source: Literal["question", "resolved_event_reference"]
    slot: Literal["facts", "version", "impact", "fix", "mechanism", "standard"]
    reference_ids: tuple[UUID, ...] = Field(max_length=20)


ClarificationCode = Literal[
    "reference_ambiguous",
    "scope_expansion_requires_new_conversation",
    "time_scope_disjoint",
    "future_knowledge_time",
    "bounded_query_required",
    "reference_no_longer_visible",
]


class ResolvedQuestionContext(ConversationRecord):
    schema_version: Literal[1] = 1
    conversation_id: UUID
    base_version: int = Field(ge=0)
    question: str = Field(min_length=1, max_length=4096)
    mode: Literal["auto", "library", "investigate"]
    event_ids: tuple[UUID, ...] = Field(max_length=20)
    asset_ids: tuple[UUID, ...] = Field(max_length=20)
    asset_snapshot_refs: tuple[AssetSnapshotReference, ...] = Field(max_length=20)
    reference_turn_ids: tuple[UUID, ...] = Field(max_length=4)
    known_at: UtcTimestamp | None
    valid_at: UtcTimestamp | None
    requested_at: UtcTimestamp
    retrieval_queries: tuple[DerivedRetrievalQuery, ...] = Field(max_length=3)
    clarification_code: ClarificationCode | None
    scope_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    context_sha256: str = Field(pattern="^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_context(self) -> ResolvedQuestionContext:
        if any(
            len(values) != len(set(values))
            for values in (self.event_ids, self.asset_ids, self.reference_turn_ids)
        ):
            raise ValueError("context references must be unique")
        if self.clarification_code is not None and self.retrieval_queries:
            raise ValueError("clarification cannot authorize retrieval")
        if any(
            not set(query.reference_ids) <= set(self.event_ids) for query in self.retrieval_queries
        ):
            raise ValueError("query reference is outside resolved scope")
        if any(item.asset_id not in self.asset_ids for item in self.asset_snapshot_refs):
            raise ValueError("snapshot is outside resolved scope")
        return self


class TurnHistoryEvent(ConversationRecord):
    state: Literal["pending", "completed", "failed", "cancelled", "expired"]
    occurred_at: UtcTimestamp
    reason_code: str | None = Field(default=None, pattern="^[a-z0-9_]{1,100}$")


class ConversationTurn(ConversationRecord):
    conversation_id: UUID
    conversation_version: int = Field(ge=1)
    turn_id: UUID
    turn_number: int = Field(ge=1)
    answer_id: UUID
    reservation_id: UUID
    reservation_expires_at: UtcTimestamp
    state: Literal["pending", "completed", "failed", "cancelled", "expired"]
    context: ResolvedQuestionContext
    history: tuple[TurnHistoryEvent, ...] = Field(min_length=1, max_length=3)
    replayed: bool
    reference_freshness: Literal["unknown", "stale"] = "unknown"

    @model_validator(mode="after")
    def validate_history(self) -> ConversationTurn:
        if self.history[0].state != "pending" or self.history[-1].state != self.state:
            raise ValueError("turn history does not match current state")
        if len(self.history) > 2 or any(item.state == "pending" for item in self.history[1:]):
            raise ValueError("turn history has an invalid transition")
        if any(
            right.occurred_at < left.occurred_at
            for left, right in zip(self.history, self.history[1:], strict=False)
        ):
            raise ValueError("turn history time is inverted")
        return self


class GenerationBudgetProof(ConversationRecord):
    """A server counter's proof, not an inference from unknown provider token usage."""

    approved_model: str = Field(min_length=1, max_length=200)
    counter_version: str | None = Field(min_length=1, max_length=100)
    input_tokens: tuple[int, int] | None

    @model_validator(mode="after")
    def validate_counts(self) -> GenerationBudgetProof:
        if self.input_tokens is not None and any(value < 0 for value in self.input_tokens):
            raise ValueError("token counts must be nonnegative")
        return self

    @property
    def decision(
        self,
    ) -> Literal["within_budget", "blocked_token_budget", "token_budget_exhausted"]:
        if self.counter_version is None or self.input_tokens is None:
            return "blocked_token_budget"
        if any(type(value) is not int or value < 0 for value in self.input_tokens):
            return "blocked_token_budget"
        if sum(self.input_tokens) + 6144 > 16384:
            return "token_budget_exhausted"
        return "within_budget"


class BundleGap(ConversationRecord):
    slot: Literal[
        "facts",
        "version",
        "impact",
        "fix",
        "mechanism",
        "standard",
        "history",
        "investigation",
        "retrieval",
    ]
    reason_code: str = Field(pattern="^[a-z0-9_]{1,100}$")
    state: Literal["unknown", "conflict", "unsupported", "not_configured", "partial"]
    required: bool


class EvidenceBinding(ConversationRecord):
    claim_id: UUID
    evidence_id: UUID
    revision_id: UUID
    subject: str = Field(min_length=1, max_length=4000)
    predicate: str = Field(min_length=1, max_length=200)
    claim_status: Literal["supported", "disputed", "unverified", "superseded", "withdrawn"]
    support_kind: Literal["supports", "refutes", "context"]
    validation_status: str = Field(min_length=1, max_length=100)


class AnswerEvidencePath(ConversationRecord):
    path_id: UUID
    slot: Literal["version_impact_fix", "mechanism_standard"]
    edge_ids: tuple[UUID, ...] = Field(min_length=2, max_length=3)
    node_ids: tuple[UUID, ...] = Field(min_length=3, max_length=4)
    claim_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    evidence_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    revision_ids: tuple[UUID, ...] = Field(min_length=2, max_length=20)
    rule_version: str = Field(min_length=1, max_length=100)


class QueryScopeWatch(ConversationRecord):
    event_ids: tuple[UUID, ...] = Field(max_length=20)
    asset_ids: tuple[UUID, ...] = Field(max_length=20)
    known_at: UtcTimestamp | None
    valid_at: UtcTimestamp | None
    query_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    scope_epochs: tuple[tuple[str, int], ...]


class QuestionEvidenceBundle(ConversationRecord):
    schema_version: Literal[1] = 1
    context_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    citations: tuple[CitationProjection, ...] = Field(max_length=20)
    bindings: tuple[EvidenceBinding, ...] = Field(max_length=100)
    paths: tuple[AnswerEvidencePath, ...] = Field(max_length=8)
    gaps: tuple[BundleGap, ...] = Field(max_length=20)
    scope_watch: QueryScopeWatch
    input_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    constructed_at: UtcTimestamp
    partial: bool
    data_mode: DataMode
    generation_status: Literal["not_run"] = "not_run"

    @model_validator(mode="after")
    def validate_evidence_references(self) -> QuestionEvidenceBundle:
        evidence_ids = {item.evidence_id for item in self.citations}
        if len(evidence_ids) != len(self.citations):
            raise ValueError("bundle citations must be unique")
        if any(item.evidence_id not in evidence_ids for item in self.bindings):
            raise ValueError("binding has no citation")
        if any(not set(path.evidence_ids) <= evidence_ids for path in self.paths):
            raise ValueError("path has no complete evidence")
        if self.gaps and not self.partial:
            raise ValueError("gaps require partial")
        return self


class ConversationFailure(RuntimeError):
    """A fixed safe code; no request text, source facts, or credentials in exceptions."""

    def __init__(self, code: str, status: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
