"""同步引用问答的PG生命周期；重试不重复付费，完成前重新鉴权和锁定事实epoch。"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import DateTime, cast, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.answering.contracts import GroundedAnswerFailure
from ai_intel.answering.grounding import generate_grounded_answer
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import InvalidCredentialsError, SessionExpiredError
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.api.question_contracts import (
    AnswerClaimProjection,
    QuestionAnswerResponse,
    QuestionRequest,
)
from ai_intel.domain.access import (
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.infrastructure.models.clients import ModelContractError, ModelNotConfiguredError
from ai_intel.infrastructure.models.generation import (
    AttemptMetadata,
    GenerationClient,
    GenerationFailure,
)
from ai_intel.infrastructure.models.semantic import (
    SemanticInputError,
    SemanticRuntimeError,
    SemanticTimeoutError,
)
from ai_intel.retrieval.persistence_models import grounded_answers
from ai_intel.retrieval.service import (
    EventEvidenceRetriever,
    RetrievalFailure,
    current_public_epoch,
)


class QuestionFailure(RuntimeError):
    """仅固定代码和HTTP类别交给路由；失败也保留PG调用轨迹。"""

    def __init__(self, code: str, status: int = 503) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


ANSWER_RESERVATION_SECONDS = 420


def _lock_answer_scope(session: Session, scope: AccessScope, session_token: str) -> AccessScope:
    current = lock_authenticated_scope(session.connection(), session_token, datetime.now(UTC))
    if current.user_id != scope.user_id or current.tenant_id != scope.tenant_id:
        raise CrossTenantAccessError("resource not found")
    current.requires(READ_PUBLIC)
    return current


def _expire_pending_answer(
    engine: Engine, scope: AccessScope, answer_id: UUID, session_token: str
) -> None:
    """到期仅终止原预约，不重新发送付费请求；CAS不覆盖已完成或另一预约。"""
    with Session(engine) as session, session.begin():
        _lock_answer_scope(session, scope, session_token)
        row = (
            session.execute(
                select(grounded_answers).where(
                    grounded_answers.c.answer_id == str(answer_id),
                    grounded_answers.c.user_id == scope.user_id,
                    grounded_answers.c.tenant_id == scope.tenant_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None or row["response"].get("kind") != "pending":
            return
        owner = row["model_trace"].get("reservation_id")
        expires = row["model_trace"].get("reservation_expires_at")
        if not isinstance(owner, str) or not isinstance(expires, str):
            return
        try:
            deadline = datetime.fromisoformat(expires)
        except ValueError:
            return
        if deadline.tzinfo is None or deadline > datetime.now(UTC):
            return
        session.execute(
            update(grounded_answers)
            .where(
                grounded_answers.c.answer_id == str(answer_id),
                grounded_answers.c.response["kind"].astext == "pending",
                grounded_answers.c.model_trace["reservation_id"].astext == owner,
                grounded_answers.c.model_trace["reservation_expires_at"].astext == expires,
            )
            .values(
                response={"kind": "failed", "error_code": "answer_interrupted"},
                model_trace={
                    **row["model_trace"],
                    "reservation_state": "expired",
                    "usage_status": "incomplete_interrupted",
                    "interruption_recorded_at": datetime.now(UTC).isoformat(),
                },
            )
        )


def _attempt_records(attempts: tuple[AttemptMetadata, ...]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for attempt in attempts:
        value = asdict(attempt)
        value["started_at"] = attempt.started_at.isoformat()
        value["completed_at"] = attempt.completed_at.isoformat()
        records.append(value)
    return records


def read_grounded_answer(
    engine: Engine, scope: AccessScope, answer_id: UUID, *, session_token: str
) -> QuestionAnswerResponse:
    scope.requires(READ_PUBLIC)
    _expire_pending_answer(engine, scope, answer_id, session_token)
    with Session(engine) as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        _lock_answer_scope(session, scope, session_token)
        row = (
            session.execute(
                select(grounded_answers).where(
                    grounded_answers.c.answer_id == str(answer_id),
                    grounded_answers.c.user_id == scope.user_id,
                    grounded_answers.c.tenant_id == scope.tenant_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        if row["response"].get("kind") != "completed":
            status = row["response"].get("kind")
            raise QuestionFailure(
                "answer_in_progress" if status == "pending" else "answer_failed", 409
            )
        answer = QuestionAnswerResponse.model_validate(row["response"])
        reader = KnowledgeReadService(session, scope, answer.data_mode)
        for citation in answer.citations:
            current = reader.read_evidence(citation.evidence_id)
            if (
                current.verified_at is None
                or current.source_uri != citation.source_uri
                or current.revision_id != citation.revision_id
                or citation.quote not in current.quote_text
            ):
                raise QuestionFailure("answer_evidence_integrity_unavailable")
        if row["scope_epochs"].get("public") != current_public_epoch(session):
            answer = answer.model_copy(update={"freshness": FreshnessStatus.STALE})
        return answer


class GroundedQuestionService:
    """R05限定单事件公开证据；会话/资产/历史/调查的完整能力由R12/R14接入。"""

    def __init__(
        self,
        engine: Engine,
        retriever: EventEvidenceRetriever,
        client: GenerationClient,
        *,
        data_mode: DataMode = "live",
    ) -> None:
        if data_mode not in {"live", "fixture"}:
            raise ValueError("invalid answer data mode")
        self.engine = engine
        self.retriever = retriever
        self.client = client
        self.data_mode = data_mode
        self._slot = threading.BoundedSemaphore(1)

    def ask(
        self,
        payload: QuestionRequest,
        scope_provider: Callable[[], AccessScope],
        idempotency_key: str | None = None,
        *,
        session_token: str,
    ) -> QuestionAnswerResponse:
        started = datetime.now(UTC)
        timer = time.perf_counter()
        scope = scope_provider()
        scope.requires(READ_PUBLIC)
        if (
            len(payload.event_ids) != 1
            or payload.asset_ids
            or payload.conversation_id is not None
            or payload.known_at is not None
            or payload.valid_at is not None
            or payload.mode == "investigate"
        ):
            raise QuestionFailure("question_scope_not_supported", 422)
        if idempotency_key is None or not re.fullmatch(r"[\x21-\x7e]{1,200}", idempotency_key):
            raise QuestionFailure("invalid_key", 422)
        request_digest = hashlib.sha256(
            json.dumps(payload.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        answer_id = uuid5(
            NAMESPACE_URL,
            json.dumps(["qa", scope.user_id, scope.tenant_id, idempotency_key]),
        )
        with Session(self.engine) as session:
            prior = session.execute(
                select(grounded_answers.c.model_trace).where(
                    grounded_answers.c.answer_id == str(answer_id),
                    grounded_answers.c.user_id == scope.user_id,
                    grounded_answers.c.tenant_id == scope.tenant_id,
                )
            ).scalar_one_or_none()
        if prior is not None:
            if prior.get("request_sha256") != request_digest:
                raise QuestionFailure("idempotency_conflict", 409)
            return read_grounded_answer(self.engine, scope, answer_id, session_token=session_token)
        if not self._slot.acquire(blocking=False):
            raise QuestionFailure("question_capacity_busy", 429)
        reservation_id = str(uuid4())
        reservation_deadline = started + timedelta(seconds=ANSWER_RESERVATION_SECONDS)
        trace: dict[str, object] = {
            "request_sha256": request_digest,
            "attempts": [],
            "fee": "unknown",
            "reservation_id": reservation_id,
            "reservation_expires_at": reservation_deadline.isoformat(),
            "reservation_state": "pending",
            "usage_status": "not_yet_recorded",
        }
        reserved = False
        try:
            with Session(self.engine) as session, session.begin():
                reserved_id = session.scalar(
                    pg_insert(grounded_answers)
                    .values(
                        answer_id=str(answer_id),
                        user_id=scope.user_id,
                        tenant_id=scope.tenant_id,
                        question_text=payload.question,
                        response={"kind": "pending"},
                        scope_epochs={},
                        model_trace=trace,
                        created_at=started,
                    )
                    .on_conflict_do_nothing()
                    .returning(grounded_answers.c.answer_id)
                )
                reserved = reserved_id is not None
            if not reserved:
                raise QuestionFailure("answer_in_progress", 409)
            selection = self.retriever.retrieve(scope, payload.event_ids[0], payload.question)
            trace.update(
                embedding_model=selection.embedding_model,
                reranker_model=selection.reranker_model,
                candidate_count=selection.candidate_count,
                event_id=str(selection.event_id),
            )
            draft = generate_grounded_answer(self.client, payload.question, selection.citations)
            trace["attempts"] = _attempt_records(draft.attempts)
            trace["usage_status"] = "recorded"
            current_scope = scope_provider()
            if current_scope.user_id != scope.user_id or current_scope.tenant_id != scope.tenant_id:
                raise CrossTenantAccessError("resource not found")
            with Session(self.engine) as session, session.begin():
                current_scope = _lock_answer_scope(session, current_scope, session_token)
                self.retriever.require_current(
                    session,
                    current_scope,
                    selection.event_id,
                    selection.epoch,
                    draft.citations,
                    lock_epoch=True,
                )
                completed = datetime.now(UTC)
                if completed >= reservation_deadline:
                    raise QuestionFailure("answer_lease_expired", 409)
                answer = QuestionAnswerResponse(
                    answer_id=answer_id,
                    answer_text=draft.answer_text,
                    claims=tuple(
                        AnswerClaimProjection.model_validate(claim.model_dump())
                        for claim in draft.claims
                    ),
                    citations=draft.citations,
                    limitations=draft.limitations
                    + ("本次只检索指定事件的当前公开证据，不代表全库、资产或历史研判。",)
                    + (
                        ("本事件候选达到上限或含未验证证据，检索覆盖不完整。",)
                        if selection.partial
                        else ()
                    ),
                    freshness=FreshnessStatus.UNKNOWN
                    if selection.partial
                    else FreshnessStatus.CURRENT,
                    data_mode=self.data_mode,
                    started_at=started,
                    completed_at=completed,
                    latency_milliseconds=int((time.perf_counter() - timer) * 1000),
                )
                trace["reservation_state"] = "completed"
                completed_id = session.scalar(
                    update(grounded_answers)
                    .where(
                        grounded_answers.c.answer_id == str(answer_id),
                        grounded_answers.c.response["kind"].astext == "pending",
                        grounded_answers.c.model_trace["reservation_id"].astext == reservation_id,
                        cast(
                            grounded_answers.c.model_trace["reservation_expires_at"].astext,
                            DateTime(timezone=True),
                        )
                        > func.clock_timestamp(),
                    )
                    .values(
                        response=answer.model_dump(mode="json"),
                        scope_epochs={"public": selection.epoch},
                        model_trace=trace,
                    )
                    .returning(grounded_answers.c.answer_id)
                )
                if completed_id is None:
                    raise QuestionFailure("answer_failed", 409)
            return answer
        except Exception as error:
            if isinstance(error, (GroundedAnswerFailure, GenerationFailure)):
                trace["attempts"] = _attempt_records(error.attempts)
                trace["usage_status"] = "recorded"
            if isinstance(error, (GroundedAnswerFailure, GenerationFailure, QuestionFailure)):
                code = error.code
            elif isinstance(error, RetrievalFailure):
                code = str(error)
            elif isinstance(error, SemanticInputError):
                code = "question_semantic_input_invalid"
            elif isinstance(
                error,
                (
                    ModelContractError,
                    SemanticRuntimeError,
                    SemanticTimeoutError,
                    ModelNotConfiguredError,
                ),
            ):
                code = "question_model_unavailable"
            else:
                code = "question_processing_failed"
            if not re.fullmatch(r"[a-z0-9_]{1,100}", code):
                code = "question_processing_failed"
            if reserved:
                with Session(self.engine) as session, session.begin():
                    trace["reservation_state"] = "failed"
                    failed_id = session.scalar(
                        update(grounded_answers)
                        .where(
                            grounded_answers.c.answer_id == str(answer_id),
                            grounded_answers.c.response["kind"].astext == "pending",
                            grounded_answers.c.model_trace["reservation_id"].astext
                            == reservation_id,
                        )
                        .values(response={"kind": "failed", "error_code": code}, model_trace=trace)
                        .returning(grounded_answers.c.answer_id)
                    )
                    if failed_id is None and trace["attempts"]:
                        session.execute(
                            update(grounded_answers)
                            .where(
                                grounded_answers.c.answer_id == str(answer_id),
                                grounded_answers.c.model_trace["reservation_id"].astext
                                == reservation_id,
                            )
                            .values(
                                model_trace=grounded_answers.c.model_trace.op("||")(
                                    {
                                        "attempts": trace["attempts"],
                                        "usage_status": "recorded_after_terminal",
                                        "late_attempts_recorded_at": datetime.now(UTC).isoformat(),
                                    }
                                )
                            )
                        )
            if isinstance(
                error,
                (
                    CrossTenantAccessError,
                    QuestionFailure,
                    InvalidCredentialsError,
                    SessionExpiredError,
                    PermissionDeniedError,
                ),
            ):
                raise
            raise QuestionFailure(
                code, 422 if isinstance(error, SemanticInputError) else 503
            ) from None
        finally:
            self._slot.release()
