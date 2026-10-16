"""Cookie/CSRF investigations expose PG status and bounded, owner-scoped operation receipts."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai_intel.api.actor_references import actor_reference_from_payload
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.credentials import SessionCredential
from ai_intel.api.problems import problem_response
from ai_intel.domain.access import (
    READ_ASSET,
    READ_PUBLIC,
    WRITE_ASSET,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.investigation.graph_contracts import (
    InvestigationRequest,
    WorkflowBudget,
    WorkflowResult,
    parse_investigation_request,
)
from ai_intel.investigation.runtime import build_investigation_service
from ai_intel.investigation.workflow_service import (
    JOB_TYPE,
    WorkflowChangedError,
    investigation_operations,
    investigation_workflows,
)
from ai_intel.knowledge.models import job_runs
from ai_intel.workers.jobs import cancel_job_with_scope

JobStatus = Literal[
    "queued",
    "running",
    "retry_wait",
    "waiting_approval",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "blocked",
]


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    job_id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    result_ref: str | None
    elapsed_milliseconds: float = Field(ge=0)
    result: WorkflowResult | None = None


class InvestigationOperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    operation_key: str
    kind: Literal["tool", "model", "node"]
    role: str
    status: Literal["reserved", "succeeded", "failed", "partial"]
    request_sha256: str
    tool_name: str | None
    model_version: str | None
    prompt_version: str | None
    policy_version: str
    cost_status: Literal["unknown"]
    input_bytes: int = Field(ge=0)
    output_bytes: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    created_at: datetime
    completed_at: datetime | None


class InvestigationOperationPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    items: tuple[InvestigationOperationResponse, ...]
    next_cursor: str | None


def build_investigation_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    settings: ApplicationSettings,
    *,
    checkpoint_schema: str = "dianzi_investigation_checkpoints",
) -> APIRouter:
    """Mount on /v1 and its compatibility alias; no request sets actor, budget or thread."""
    router = APIRouter()

    def authenticate(request: Request, *, write: bool) -> SessionCredential:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token or request.headers.get("authorization"):
            raise InvalidCredentialsError("session is not valid")
        authentication = service_provider()
        if authentication is None or engine is None:
            raise RuntimeError("investigation dependency unavailable")
        if write:
            authentication.validate_write_request(
                token, request.headers.get(CSRF_HEADER_NAME, ""), request.headers.get("origin")
            )
        authentication.build_access_scope(token).requires(READ_PUBLIC)
        return SessionCredential(SecretStr(token))

    def failure(request: Request, error: Exception) -> Response:
        if isinstance(error, (SessionExpiredError, InvalidCredentialsError)):
            return problem_response(request, 401, "session_expired", "session is not valid")
        if isinstance(error, CsrfRejectionError):
            return problem_response(request, 403, "csrf_rejected", "valid origin and CSRF required")
        if isinstance(error, CrossTenantAccessError):
            return problem_response(request, 404, "not_found", "resource is not available")
        if isinstance(error, PermissionDeniedError):
            return problem_response(
                request, 403, "permission_denied", "required permission missing"
            )
        if isinstance(error, IdempotencyConflictError):
            return problem_response(request, 409, "idempotency_conflict", "request key conflicts")
        if isinstance(error, WorkflowChangedError):
            return problem_response(request, 409, "workflow_changed", "workflow inputs changed")
        if isinstance(error, ValueError):
            return problem_response(
                request, 422, "invalid_investigation", "invalid investigation input"
            )
        return problem_response(
            request, 503, "investigation_unavailable", "investigation unavailable", True
        )

    def authorized_job(
        session: Session, credential: SessionCredential, job_id: UUID
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        session.connection().exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
        session.connection().exec_driver_sql("SET LOCAL lock_timeout = '5000ms'")
        scope = lock_authenticated_scope(
            session.connection(), credential.token.get_secret_value(), now
        )
        scope.requires(READ_PUBLIC)
        row = (
            session.execute(
                select(
                    job_runs,
                    investigation_workflows.c.actor_reference.label("workflow_actor_reference"),
                    investigation_workflows.c.input_json.label("workflow_input_json"),
                )
                .join(
                    investigation_workflows, investigation_workflows.c.job_id == job_runs.c.job_id
                )
                .where(
                    job_runs.c.job_id == str(job_id),
                    job_runs.c.job_type == JOB_TYPE,
                    job_runs.c.tenant_id.is_not_distinct_from(scope.tenant_id),
                    investigation_workflows.c.owner_user_id == scope.user_id,
                    investigation_workflows.c.tenant_id.is_not_distinct_from(scope.tenant_id),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        reference = actor_reference_from_payload(row["workflow_actor_reference"])
        original_scope = lock_authenticated_scope(
            session.connection(), reference, datetime.now(UTC)
        )
        if original_scope != scope:
            raise PermissionDeniedError("investigation authorization changed")
        payload = row["workflow_input_json"]
        if not isinstance(payload, dict) or not isinstance(payload.get("request"), dict):
            raise WorkflowChangedError("investigation input changed")
        if payload["request"].get("asset_id") is not None:
            scope.requires(READ_ASSET)
        session.execute(
            select(job_runs.c.job_id).where(job_runs.c.job_id == str(job_id)).with_for_update()
        ).one()
        current = (
            session.execute(select(job_runs).where(job_runs.c.job_id == str(job_id)))
            .mappings()
            .one()
        )
        return {**dict(row), **dict(current)}

    def response(
        row: dict[str, object], result: WorkflowResult | None = None
    ) -> InvestigationResponse:
        created = row["created_at"]
        completed = row["finished_at"] or datetime.now(UTC)
        if not isinstance(created, datetime) or not isinstance(completed, datetime):
            raise ValueError("invalid job timing")
        return InvestigationResponse.model_validate(
            {
                "job_id": UUID(str(row["job_id"])),
                "status": row["status"],
                "created_at": created,
                "updated_at": row["updated_at"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "error_code": row["error_code"],
                "result_ref": row["result_ref"],
                "elapsed_milliseconds": max(0.0, (completed - created).total_seconds() * 1000),
                "result": result,
            }
        )

    def create_authenticated_investigation(
        request: Request, payload: InvestigationRequest
    ) -> InvestigationResponse | Response:
        try:
            actor = authenticate(request, write=True)
            key = request.headers.get("idempotency-key", "")
            if not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", key):
                raise ValueError("idempotency key required")
            if engine is None:
                raise RuntimeError("investigation database unavailable")
            service = build_investigation_service(
                engine, settings, actor, checkpoint_schema=checkpoint_schema
            )
            job_id = service.enqueue(payload, WorkflowBudget(), idempotency_key=key)
            with Session(engine) as session, session.begin():
                return response(authorized_job(session, actor, job_id))
        except (PermissionError, ValueError, RuntimeError, SQLAlchemyError) as error:
            return failure(request, error)

    @router.post(
        "/investigations",
        response_model=InvestigationResponse,
        status_code=202,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "$id": "urn:dianzi:investigation-request:1",
                            **InvestigationRequest.model_json_schema(),
                        }
                    }
                },
            }
        },
    )
    async def enqueue_investigation(request: Request) -> InvestigationResponse | Response:
        try:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 65536:
                    raise ValueError("investigation input too large")
                body.extend(chunk)
            payload = parse_investigation_request(bytes(body))
            return await run_in_threadpool(create_authenticated_investigation, request, payload)
        except (PermissionError, ValueError, RuntimeError, SQLAlchemyError) as error:
            return failure(request, error)

    @router.get("/investigations/{job_id}", response_model=InvestigationResponse)
    def read_investigation(request: Request, job_id: UUID) -> InvestigationResponse | Response:
        try:
            actor = authenticate(request, write=False)
            if engine is None:
                raise RuntimeError("investigation database unavailable")
            with Session(engine) as session, session.begin():
                row = authorized_job(session, actor, job_id)
            result = None
            if row["status"] not in {"queued", "retry_wait", "cancelled", "blocked"}:
                stored_actor = row["workflow_actor_reference"]
                if not isinstance(stored_actor, dict):
                    raise WorkflowChangedError("investigation actor changed")
                service = build_investigation_service(
                    engine,
                    settings,
                    actor_reference_from_payload(stored_actor),
                    checkpoint_schema=checkpoint_schema,
                )
                result = service.read_result(job_id)
            return response(row, result)
        except (PermissionError, ValueError, RuntimeError, SQLAlchemyError) as error:
            return failure(request, error)

    @router.get("/investigations/{job_id}/tool-runs", response_model=InvestigationOperationPage)
    def read_operations(
        request: Request,
        job_id: UUID,
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None, min_length=1, max_length=200),
    ) -> InvestigationOperationPage | Response:
        try:
            actor = authenticate(request, write=False)
            if engine is None:
                raise RuntimeError("investigation database unavailable")
            with Session(engine) as session, session.begin():
                authorized_job(session, actor, job_id)
                query = select(investigation_operations).where(
                    investigation_operations.c.job_id == str(job_id)
                )
                if cursor is not None:
                    query = query.where(investigation_operations.c.operation_key > cursor)
                rows = (
                    session.execute(
                        query.order_by(investigation_operations.c.operation_key).limit(limit + 1)
                    )
                    .mappings()
                    .all()
                )
                items = tuple(
                    InvestigationOperationResponse.model_validate(
                        {field: row[field] for field in InvestigationOperationResponse.model_fields}
                    )
                    for row in rows[:limit]
                )
                return InvestigationOperationPage(
                    items=items, next_cursor=items[-1].operation_key if len(rows) > limit else None
                )
        except (PermissionError, ValueError, RuntimeError, SQLAlchemyError) as error:
            return failure(request, error)

    @router.post("/investigations/{job_id}/cancel", response_model=InvestigationResponse)
    def cancel_investigation(request: Request, job_id: UUID) -> InvestigationResponse | Response:
        try:
            actor = authenticate(request, write=True)
            if engine is None:
                raise RuntimeError("investigation database unavailable")
            with Session(engine) as session, session.begin():
                row = authorized_job(session, actor, job_id)
                scope = lock_authenticated_scope(
                    session.connection(), actor.token.get_secret_value(), datetime.now(UTC)
                )
                scope.requires(WRITE_ASSET)
                if row["status"] != "cancelled":
                    cancel_job_with_scope(session, str(job_id), scope, datetime.now(UTC))
                return response(authorized_job(session, actor, job_id))
        except (PermissionError, ValueError, RuntimeError, SQLAlchemyError) as error:
            return failure(request, error)

    return router
