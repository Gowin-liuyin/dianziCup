"""Resolve bounded references and reserve owner-scoped PG turns without model calls."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.answering.conversation_contracts import (
    AssetSnapshotReference,
    ClarificationCode,
    ConversationFailure,
    ConversationTurn,
    DerivedRetrievalQuery,
    EventReference,
    QuerySlot,
    QuestionEvidenceBundle,
    ResolvedQuestionContext,
    TurnHistoryEvent,
)
from ai_intel.answering.conversation_models import qa_conversation_turns, qa_conversations
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.api.question_contracts import QuestionAnswerResponse, QuestionRequest
from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_models import assets
from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.knowledge.persistence_models import event_external_ids, events
from ai_intel.retrieval.hybrid import EXACT_ID, visible_clause
from ai_intel.retrieval.persistence_models import grounded_answers

RESERVATION_SECONDS = 420
PRONOUN = re.compile(
    r"它|他们|它们|该问题|这个问题|\b(?:it|its|they|their|former|latter)\b", re.IGNORECASE
)
OTHER_REFERENCE = re.compile(
    r"另一个|另外一个|前者|后者|\b(?:another|other|former|latter)\b", re.IGNORECASE
)
SLOT_WORDS: tuple[tuple[QuerySlot, re.Pattern[str], str], ...] = (
    ("version", re.compile(r"版本|\bversions?\b", re.IGNORECASE), "version"),
    ("impact", re.compile(r"影响|\b(?:impact|affected)\b", re.IGNORECASE), "impact"),
    ("fix", re.compile(r"修复|缓解|\b(?:fix|remediat|mitigat)", re.IGNORECASE), "fix"),
    ("mechanism", re.compile(r"机制|\bmechanism\b", re.IGNORECASE), "mechanism"),
    ("standard", re.compile(r"标准|条款|政策|\b(?:standard|policy)\b", re.IGNORECASE), "standard"),
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def scope_fingerprint(scope: AccessScope) -> str:
    return _digest(
        [
            scope.user_id,
            scope.tenant_id,
            scope.role.value,
            sorted(scope.permissions),
            scope.permission_version,
        ]
    )


def validate_context_integrity(context: ResolvedQuestionContext) -> None:
    """Every consumer verifies the saved canonical digest before using context identity."""
    if (
        _digest(context.model_dump(mode="json", exclude={"context_sha256"}))
        != context.context_sha256
    ):
        raise ConversationFailure("context_integrity_unavailable", 503)


def resolve_question_context(
    payload: QuestionRequest,
    *,
    conversation_id: UUID,
    base_version: int,
    scope: AccessScope,
    event_references: tuple[EventReference, ...],
    asset_references: tuple[AssetSnapshotReference, ...] = (),
    prior: ResolvedQuestionContext | None = None,
    reference_turn_ids: tuple[UUID, ...] = (),
    now: datetime,
) -> ResolvedQuestionContext:
    """Trusted PG references supply identity; ambiguity never produces a wider query."""
    payload = QuestionRequest.model_validate(payload.model_dump())
    if now.tzinfo is None or base_version < 0:
        raise ValueError("context time/version invalid")
    selected_events = payload.event_ids or (() if prior is None else prior.event_ids)
    selected_assets = payload.asset_ids or (() if prior is None else prior.asset_ids)
    known_at = (
        payload.known_at
        if payload.known_at is not None
        else (None if prior is None else prior.known_at)
    )
    valid_at = (
        payload.valid_at
        if payload.valid_at is not None
        else (None if prior is None else prior.valid_at)
    )
    clarification: ClarificationCode | None = None
    if prior is not None and (
        (payload.event_ids and not set(payload.event_ids) <= set(prior.event_ids))
        or (payload.asset_ids and not set(payload.asset_ids) <= set(prior.asset_ids))
    ):
        clarification = "scope_expansion_requires_new_conversation"
    if prior is not None and (
        (prior.known_at is not None and known_at != prior.known_at)
        or (prior.valid_at is not None and valid_at != prior.valid_at)
    ):
        clarification = "time_scope_disjoint"
    if known_at is not None and known_at > now:
        clarification = "future_knowledge_time"
    if any(item.recorded_at > now for item in asset_references):
        clarification = "future_knowledge_time"
    by_id = {item.event_id: item for item in event_references}
    if not set(selected_events) <= by_id.keys():
        raise CrossTenantAccessError("resource not found")
    if not set(selected_assets) <= {item.asset_id for item in asset_references}:
        raise CrossTenantAccessError("resource not found")
    identifiers_in_question = {
        identifier.upper() for identifier in EXACT_ID.findall(payload.question)
    }
    if (
        not selected_events
        and not selected_assets
        and not identifiers_in_question
        and (PRONOUN.search(payload.question) or OTHER_REFERENCE.search(payload.question))
    ):
        clarification = "reference_ambiguous"
    if prior is not None and not payload.event_ids:
        known_identifiers = {
            identifier.upper()
            for event_id in selected_events
            for identifier in by_id[event_id].identifiers
        }
        if identifiers_in_question:
            if not identifiers_in_question <= known_identifiers:
                clarification = "reference_ambiguous"
            else:
                selected_events = tuple(
                    event_id
                    for event_id in selected_events
                    if identifiers_in_question.intersection(
                        identifier.upper() for identifier in by_id[event_id].identifiers
                    )
                )
        elif OTHER_REFERENCE.search(payload.question):
            clarification = "reference_ambiguous"
    if (
        prior is not None
        and not payload.event_ids
        and len(selected_events) > 1
        and PRONOUN.search(payload.question)
    ):
        clarification = "reference_ambiguous"
    queries: list[DerivedRetrievalQuery] = []
    is_followup = prior is not None and not payload.event_ids and bool(selected_events)
    if clarification is None and len(payload.question) <= 500 and not is_followup:
        queries.append(
            DerivedRetrievalQuery(
                text=payload.question,
                source="question",
                slot="facts",
                reference_ids=selected_events,
            )
        )
    elif clarification is None:
        identifiers = tuple(
            identifier for event_id in selected_events for identifier in by_id[event_id].identifiers
        )
        if len(selected_events) != 1 or not identifiers:
            clarification = "bounded_query_required"
        elif is_followup and len(payload.question) + len(identifiers[0]) + 1 <= 500:
            queries.append(
                DerivedRetrievalQuery(
                    text=identifiers[0] + " " + payload.question,
                    source="resolved_event_reference",
                    slot="facts",
                    reference_ids=selected_events,
                )
            )
        else:
            for slot, pattern, word in SLOT_WORDS:
                if pattern.search(payload.question):
                    queries.append(
                        DerivedRetrievalQuery(
                            text=identifiers[0] + " " + word,
                            source="resolved_event_reference",
                            slot=slot,
                            reference_ids=selected_events,
                        )
                    )
            if not queries or len(queries) > 3:
                queries.clear()
                clarification = "bounded_query_required"
    context = ResolvedQuestionContext(
        conversation_id=conversation_id,
        base_version=base_version,
        question=payload.question,
        mode=payload.mode,
        event_ids=selected_events,
        asset_ids=selected_assets,
        asset_snapshot_refs=tuple(
            item for item in asset_references if item.asset_id in selected_assets
        ),
        reference_turn_ids=reference_turn_ids,
        known_at=known_at,
        valid_at=valid_at,
        requested_at=now,
        retrieval_queries=tuple(queries),
        clarification_code=clarification,
        scope_sha256=scope_fingerprint(scope),
        context_sha256="0" * 64,
    )
    return context.model_copy(
        update={
            "context_sha256": _digest(context.model_dump(mode="json", exclude={"context_sha256"}))
        }
    )


def _owner(scope: AccessScope, table: FromClause) -> ColumnElement[bool]:
    return and_(
        table.c.user_id == scope.user_id, table.c.tenant_id.is_not_distinct_from(scope.tenant_id)
    )


class ConversationContextService:
    """PG lifecycle only; root commits validated completed answers through the narrow ack seam."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _authenticate(session: Session, scope: AccessScope, token: str) -> AccessScope:
        current = lock_authenticated_scope(session.connection(), token, datetime.now(UTC))
        if current != scope:
            raise CrossTenantAccessError("resource not found")
        current.requires(READ_PUBLIC)
        return current

    @staticmethod
    def _conversation(session: Session, scope: AccessScope, conversation_id: UUID) -> RowMapping:
        row = (
            session.execute(
                select(qa_conversations)
                .where(
                    qa_conversations.c.conversation_id == conversation_id,
                    _owner(scope, qa_conversations),
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        if row["status"] != "active":
            raise ConversationFailure("conversation_revoked")
        return row

    @staticmethod
    def _references(
        session: Session,
        scope: AccessScope,
        event_ids: tuple[UUID, ...],
        asset_ids: tuple[UUID, ...],
        *,
        lock_events: bool = True,
    ) -> tuple[tuple[EventReference, ...], tuple[AssetSnapshotReference, ...]]:
        """Bundle defers event locks to the shared source/document/event authority fence."""
        query = (
            select(events)
            .where(
                events.c.event_id.in_(tuple(map(str, event_ids))),
                visible_clause(scope, events),
            )
            .order_by(events.c.event_id)
        )
        if lock_events:
            query = query.with_for_update(read=True)
        rows = session.execute(query).mappings().all()
        if {row["event_id"] for row in rows} != set(map(str, event_ids)):
            raise CrossTenantAccessError("resource not found")
        if any(row["status"] != "active" for row in rows):
            raise ConversationFailure("reference_no_longer_visible", 422)
        references = []
        for row in rows:
            identifiers: tuple[str, ...] = tuple(
                session.scalars(
                    select(event_external_ids.c.id_value)
                    .where(
                        event_external_ids.c.event_id == row["event_id"],
                        event_external_ids.c.scope_key == row["scope_key"],
                    )
                    .order_by(event_external_ids.c.id_type, event_external_ids.c.id_value)
                    .limit(20)
                )
            )
            references.append(
                EventReference(
                    event_id=UUID(row["event_id"]),
                    identifiers=identifiers,
                    business_version=row["business_version"],
                )
            )
        asset_refs: list[AssetSnapshotReference] = []
        inventory = InventoryService(session, scope)
        for asset_id in sorted(asset_ids):
            session.execute(
                select(assets.c.asset_id)
                .where(
                    assets.c.asset_id == str(asset_id),
                    assets.c.tenant_id == scope.tenant_id,
                    assets.c.active.is_(True),
                )
                .with_for_update(read=True)
            ).all()
            snapshot = inventory.read_asset(str(asset_id)).snapshot
            asset_refs.append(
                AssetSnapshotReference(
                    asset_id=asset_id,
                    snapshot_id=UUID(snapshot.snapshot_id),
                    recorded_at=snapshot.recorded_at,
                    snapshot_sha256=snapshot.snapshot_sha256,
                )
            )
        return tuple(references), tuple(asset_refs)

    @staticmethod
    def _turn(
        session: Session, scope: AccessScope, turn_id: UUID, *, replayed: bool
    ) -> ConversationTurn:
        row = (
            session.execute(
                select(
                    qa_conversation_turns,
                    grounded_answers.c.model_trace,
                    grounded_answers.c.response,
                    grounded_answers.c.question_text,
                )
                .join(
                    grounded_answers,
                    grounded_answers.c.answer_id == qa_conversation_turns.c.answer_id,
                )
                .where(
                    qa_conversation_turns.c.turn_id == turn_id,
                    _owner(scope, qa_conversation_turns),
                    _owner(scope, grounded_answers),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        try:
            context = ResolvedQuestionContext.model_validate_json(
                json.dumps(row["resolved_context"])
            )
        except ValueError:
            raise ConversationFailure("context_integrity_unavailable", 503) from None
        validate_context_integrity(context)
        if (
            context.context_sha256 != row["context_sha256"]
            or context.conversation_id != row["conversation_id"]
            or context.base_version != row["base_conversation_version"]
            or context.question != row["question_text"]
        ):
            raise ConversationFailure("context_integrity_unavailable", 503)
        trace = row["model_trace"]
        return ConversationTurn(
            conversation_id=row["conversation_id"],
            conversation_version=row["base_conversation_version"] + 1,
            turn_id=row["turn_id"],
            turn_number=row["turn_number"],
            answer_id=UUID(row["answer_id"]),
            reservation_id=UUID(trace["reservation_id"]),
            reservation_expires_at=datetime.fromisoformat(trace["reservation_expires_at"]),
            state=trace["conversation_state"],
            context=context,
            history=tuple(
                TurnHistoryEvent.model_validate_json(json.dumps(item))
                for item in trace["conversation_history"]
            ),
            replayed=replayed,
        )

    @staticmethod
    def _authorize_turn_references(
        session: Session, scope: AccessScope, turn: ConversationTurn
    ) -> ConversationTurn:
        """Current ACL governs historical identity; current eligibility never rewrites context."""
        if turn.context.asset_ids:
            scope.requires(READ_ASSET)
        event_rows = session.execute(
            select(events.c.event_id, events.c.status)
            .where(
                events.c.event_id.in_(tuple(map(str, turn.context.event_ids))),
                visible_clause(scope, events),
            )
            .order_by(events.c.event_id)
            .with_for_update(read=True)
        ).all()
        if {row.event_id for row in event_rows} != set(map(str, turn.context.event_ids)):
            raise CrossTenantAccessError("resource not found")
        asset_rows = session.execute(
            select(assets.c.asset_id, assets.c.active, assets.c.current_snapshot_id)
            .where(
                assets.c.asset_id.in_(tuple(map(str, turn.context.asset_ids))),
                assets.c.tenant_id == scope.tenant_id,
            )
            .order_by(assets.c.asset_id)
            .with_for_update(read=True)
        ).all()
        if {row.asset_id for row in asset_rows} != set(map(str, turn.context.asset_ids)):
            raise CrossTenantAccessError("resource not found")
        snapshot_ids = {
            str(item.asset_id): str(item.snapshot_id) for item in turn.context.asset_snapshot_refs
        }
        stale = any(row.status != "active" for row in event_rows) or any(
            not row.active or row.current_snapshot_id != snapshot_ids.get(row.asset_id)
            for row in asset_rows
        )
        return turn.model_copy(update={"reference_freshness": "stale" if stale else "unknown"})

    def _recover_expired_active_turn(
        self, scope: AccessScope, conversation_id: UUID, *, session_token: str
    ) -> None:
        """Commit lease recovery before a separate request can fail CAS, ACL or clarification."""
        with Session(self.engine) as session, session.begin():
            self._authenticate(session, scope, session_token)
            row = (
                session.execute(
                    select(qa_conversations)
                    .where(
                        qa_conversations.c.conversation_id == conversation_id,
                        _owner(scope, qa_conversations),
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is not None and row["status"] == "active" and row["active_turn_id"] is not None:
                active = self._turn(session, scope, row["active_turn_id"], replayed=False)
                self._expire(session, scope, active)

    def admit(
        self,
        payload: QuestionRequest,
        scope: AccessScope,
        idempotency_key: str,
        *,
        conversation_version: int | None,
        session_token: str,
    ) -> ConversationTurn:
        if (
            not isinstance(idempotency_key, str)
            or re.fullmatch(r"[\x21-\x7e]{1,200}", idempotency_key) is None
        ):
            raise ConversationFailure("invalid_key", 422)
        if payload.conversation_id is not None and (
            type(conversation_version) is not int or conversation_version < 0
        ):
            raise ConversationFailure("conversation_version_required", 422)
        if payload.conversation_id is None and conversation_version is not None:
            raise ConversationFailure("unexpected_conversation_version", 422)
        request_sha = _digest(
            [payload.model_dump(mode="json"), conversation_version, "r12-context-1"]
        )
        answer_id = uuid5(
            NAMESPACE_URL, json.dumps(["qa", scope.user_id, scope.tenant_id, idempotency_key])
        )
        turn_id = uuid5(NAMESPACE_URL, "qa-turn:" + str(answer_id))
        conversation_id = payload.conversation_id or uuid5(
            NAMESPACE_URL, "qa-conversation:" + str(answer_id)
        )
        self._recover_expired_active_turn(scope, conversation_id, session_token=session_token)
        now = datetime.now(UTC)
        with Session(self.engine) as session, session.begin():
            self._authenticate(session, scope, session_token)
            prior_answer = session.execute(
                select(grounded_answers.c.model_trace).where(
                    grounded_answers.c.answer_id == str(answer_id), _owner(scope, grounded_answers)
                )
            ).scalar_one_or_none()
            if prior_answer is not None:
                if prior_answer.get("request_sha256") != request_sha:
                    raise ConversationFailure("idempotency_conflict")
                prior_turn = self._turn(session, scope, turn_id, replayed=True)
                self._conversation(session, scope, prior_turn.conversation_id)
                return self._authorize_turn_references(
                    session, scope, self._turn(session, scope, turn_id, replayed=True)
                )
            if payload.conversation_id is None:
                session.execute(
                    pg_insert(qa_conversations)
                    .values(
                        conversation_id=conversation_id,
                        schema_version=1,
                        user_id=scope.user_id,
                        tenant_id=scope.tenant_id,
                        status="active",
                        version=0,
                        active_turn_id=None,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing()
                )
            conversation = self._conversation(session, scope, conversation_id)
            concurrent_prior = session.scalar(
                select(grounded_answers.c.model_trace).where(
                    grounded_answers.c.answer_id == str(answer_id), _owner(scope, grounded_answers)
                )
            )
            if concurrent_prior is not None:
                if concurrent_prior.get("request_sha256") != request_sha:
                    raise ConversationFailure("idempotency_conflict")
                return self._authorize_turn_references(
                    session, scope, self._turn(session, scope, turn_id, replayed=True)
                )
            if conversation["active_turn_id"] is not None:
                active = self._turn(session, scope, conversation["active_turn_id"], replayed=False)
                if active.state == "pending":
                    raise ConversationFailure("conversation_turn_in_progress")
            if (
                payload.conversation_id is not None
                and conversation["version"] != conversation_version
            ):
                raise ConversationFailure("conversation_version_conflict")
            prior_row = (
                session.execute(
                    select(qa_conversation_turns.c.turn_id)
                    .join(
                        grounded_answers,
                        grounded_answers.c.answer_id == qa_conversation_turns.c.answer_id,
                    )
                    .where(
                        qa_conversation_turns.c.conversation_id == conversation_id,
                        _owner(scope, qa_conversation_turns),
                        _owner(scope, grounded_answers),
                        grounded_answers.c.response["kind"].astext == "completed",
                        grounded_answers.c.model_trace["conversation_state"].astext == "completed",
                    )
                    .order_by(qa_conversation_turns.c.turn_number.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            prior_turn = (
                None
                if prior_row is None
                else self._authorize_turn_references(
                    session,
                    scope,
                    self._turn(session, scope, prior_row["turn_id"], replayed=False),
                )
            )
            prior = None if prior_turn is None else prior_turn.context
            event_ids = payload.event_ids or (() if prior is None else prior.event_ids)
            asset_ids = payload.asset_ids or (() if prior is None else prior.asset_ids)
            event_refs, asset_refs = self._references(session, scope, event_ids, asset_ids)
            context = resolve_question_context(
                payload,
                conversation_id=conversation_id,
                base_version=conversation["version"],
                scope=scope,
                event_references=event_refs,
                asset_references=asset_refs,
                prior=prior,
                reference_turn_ids=() if prior_row is None else (prior_row["turn_id"],),
                now=now,
            )
            if context.clarification_code is not None:
                raise ConversationFailure(context.clarification_code, 422)
            reservation_id = uuid4()
            history = TurnHistoryEvent(state="pending", occurred_at=now)
            trace = {
                "request_sha256": request_sha,
                "reservation_id": str(reservation_id),
                "reservation_expires_at": (
                    now + timedelta(seconds=RESERVATION_SECONDS)
                ).isoformat(),
                "reservation_state": "pending",
                "conversation_state": "pending",
                "conversation_history": [history.model_dump(mode="json")],
                "attempts": [],
                "fee": "unknown",
                "usage_status": "not_yet_recorded",
            }
            session.execute(
                pg_insert(grounded_answers).values(
                    answer_id=str(answer_id),
                    user_id=scope.user_id,
                    tenant_id=scope.tenant_id,
                    question_text=payload.question,
                    response={"kind": "pending"},
                    scope_epochs={},
                    model_trace=trace,
                    created_at=now,
                )
            )
            number = (
                session.scalar(
                    select(func.max(qa_conversation_turns.c.turn_number)).where(
                        qa_conversation_turns.c.conversation_id == conversation_id
                    )
                )
                or 0
            ) + 1
            session.execute(
                qa_conversation_turns.insert().values(
                    turn_id=turn_id,
                    schema_version=1,
                    conversation_id=conversation_id,
                    user_id=scope.user_id,
                    tenant_id=scope.tenant_id,
                    turn_number=number,
                    base_conversation_version=conversation["version"],
                    answer_id=str(answer_id),
                    context_sha256=context.context_sha256,
                    resolved_context=context.model_dump(mode="json"),
                    admitted_at=now,
                )
            )
            session.execute(
                update(qa_conversations)
                .where(qa_conversations.c.conversation_id == conversation_id)
                .values(active_turn_id=turn_id, version=conversation["version"] + 1, updated_at=now)
            )
            return self._turn(session, scope, turn_id, replayed=False)

    def read_turn(
        self, scope: AccessScope, turn_id: UUID, *, session_token: str
    ) -> ConversationTurn:
        with Session(self.engine) as session, session.begin():
            self._authenticate(session, scope, session_token)
            turn = self._turn(session, scope, turn_id, replayed=False)
            self._conversation(session, scope, turn.conversation_id)
            turn = self._turn(session, scope, turn_id, replayed=False)
            turn = self._expire(session, scope, turn)
            return self._authorize_turn_references(session, scope, turn)

    def read_history(
        self, scope: AccessScope, turn_id: UUID, *, session_token: str
    ) -> tuple[TurnHistoryEvent, ...]:
        """Read owner workflow history after conversation revoke, without evidence text."""
        with Session(self.engine) as session, session.begin():
            self._authenticate(session, scope, session_token)
            return self._turn(session, scope, turn_id, replayed=False).history

    def read_bundle(
        self, scope: AccessScope, turn_id: UUID, *, session_token: str, data_mode: DataMode
    ) -> QuestionEvidenceBundle:
        """No generation: authenticate and lock the active conversation before PG assembly."""
        from ai_intel.answering.evidence_bundle import build_question_evidence

        with Session(self.engine) as session, session.begin():
            self._authenticate(session, scope, session_token)
            turn = self._turn(session, scope, turn_id, replayed=False)
            conversation = self._conversation(session, scope, turn.conversation_id)
            turn = self._turn(session, scope, turn_id, replayed=False)
            turn = self._expire(session, scope, turn)
            if turn.state == "pending" and conversation["active_turn_id"] == turn_id:
                _events, asset_refs = self._references(
                    session,
                    scope,
                    turn.context.event_ids,
                    turn.context.asset_ids,
                    lock_events=False,
                )
                return build_question_evidence(
                    session, scope, turn.context, data_mode=data_mode, asset_references=asset_refs
                )
        raise ConversationFailure("turn_reservation_conflict")

    def _expire(
        self, session: Session, scope: AccessScope, turn: ConversationTurn
    ) -> ConversationTurn:
        if turn.state == "pending" and turn.reservation_expires_at <= datetime.now(UTC):
            self._terminal(session, scope, turn, "expired", "answer_interrupted")
            return self._turn(session, scope, turn.turn_id, replayed=turn.replayed)
        return turn

    def acknowledge_completed_turn(
        self,
        session: Session,
        scope: AccessScope,
        turn_id: UUID,
        *,
        reservation_id: UUID,
        session_token: str,
    ) -> ConversationTurn:
        """Root invokes inside its validated-answer commit; this method never writes an answer."""
        self._authenticate(session, scope, session_token)
        turn = self._turn(session, scope, turn_id, replayed=False)
        conversation = self._conversation(session, scope, turn.conversation_id)
        if (
            turn.state != "pending"
            or turn.reservation_id != reservation_id
            or conversation["active_turn_id"] != turn_id
        ):
            raise ConversationFailure("turn_reservation_conflict")
        if turn.reservation_expires_at <= datetime.now(UTC):
            raise ConversationFailure("answer_lease_expired")
        row: dict[str, object] = session.execute(
            select(grounded_answers.c.response).where(
                grounded_answers.c.answer_id == str(turn.answer_id), _owner(scope, grounded_answers)
            )
        ).scalar_one()
        answer = QuestionAnswerResponse.model_validate(row)
        if answer.answer_id != turn.answer_id:
            raise ConversationFailure("answer_identity_mismatch")
        self._terminal(session, scope, turn, "completed", None)
        return self._turn(session, scope, turn_id, replayed=False)

    @staticmethod
    def _terminal(
        session: Session,
        scope: AccessScope,
        turn: ConversationTurn,
        state: Literal["completed", "failed", "cancelled", "expired"],
        code: str | None,
    ) -> None:
        now = datetime.now(UTC)
        trace: dict[str, object] | None = session.scalar(
            select(grounded_answers.c.model_trace).where(
                grounded_answers.c.answer_id == str(turn.answer_id), _owner(scope, grounded_answers)
            )
        )
        if trace is None:
            raise ConversationFailure("turn_reservation_unavailable", 503)
        event = TurnHistoryEvent(state=state, occurred_at=now, reason_code=code)
        trace = {
            **trace,
            "conversation_state": state,
            "reservation_state": state,
            "conversation_history": [
                *(item.model_dump(mode="json") for item in turn.history),
                event.model_dump(mode="json"),
            ],
        }
        values = {"model_trace": trace}
        if state != "completed":
            values["response"] = {"kind": "failed", "error_code": code}
        changed = session.execute(
            update(grounded_answers)
            .where(
                grounded_answers.c.answer_id == str(turn.answer_id),
                _owner(scope, grounded_answers),
                grounded_answers.c.model_trace["reservation_id"].astext == str(turn.reservation_id),
                grounded_answers.c.model_trace["conversation_state"].astext == "pending",
                grounded_answers.c.response["kind"].astext
                == ("completed" if state == "completed" else "pending"),
            )
            .values(**values)
            .returning(grounded_answers.c.answer_id)
        ).scalar_one_or_none()
        if changed is None:
            raise ConversationFailure("turn_reservation_conflict")
        session.execute(
            update(qa_conversations)
            .where(
                qa_conversations.c.conversation_id == turn.conversation_id,
                _owner(scope, qa_conversations),
                qa_conversations.c.active_turn_id == turn.turn_id,
            )
            .values(active_turn_id=None, updated_at=now)
        )

    def fail_turn(
        self,
        scope: AccessScope,
        turn_id: UUID,
        *,
        reservation_id: UUID,
        reason_code: str,
        session_token: str,
    ) -> ConversationTurn:
        with Session(self.engine) as session, session.begin():
            self._authenticate(session, scope, session_token)
            turn = self._turn(session, scope, turn_id, replayed=False)
            conversation = self._conversation(session, scope, turn.conversation_id)
            if (
                turn.state != "pending"
                or turn.reservation_id != reservation_id
                or conversation["active_turn_id"] != turn_id
            ):
                raise ConversationFailure("turn_reservation_conflict")
            self._terminal(session, scope, turn, "failed", reason_code)
            return self._turn(session, scope, turn_id, replayed=False)

    def revoke(self, scope: AccessScope, conversation_id: UUID, *, session_token: str) -> None:
        with Session(self.engine) as session, session.begin():
            self._authenticate(session, scope, session_token)
            conversation = self._conversation(session, scope, conversation_id)
            if conversation["active_turn_id"] is not None:
                turn = self._turn(session, scope, conversation["active_turn_id"], replayed=False)
                self._terminal(session, scope, turn, "cancelled", "conversation_revoked")
            now = datetime.now(UTC)
            session.execute(
                update(qa_conversations)
                .where(
                    qa_conversations.c.conversation_id == conversation_id,
                    _owner(scope, qa_conversations),
                )
                .values(
                    status="revoked",
                    revoked_at=now,
                    updated_at=now,
                    version=conversation["version"] + 1,
                )
            )
