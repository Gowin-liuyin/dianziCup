"""固定公开来源调度与 PG 任务查询；认证身份不来自业务请求。"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.ingestion.source_jobs import (
    SOURCE_JOB_TYPE,
    SourceKind,
    SourcePageRequest,
    enqueue_source_page,
)
from ai_intel.knowledge.models import job_runs


class SourceCollectionRequest(BaseModel):
    """观察截止标识不是上游快照保证；重试同幂等键必须复用同一请求。"""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    window_end: AwareDatetime
    stream_kind: Literal["live", "backfill"] = "backfill"
    max_pages: int = Field(default=20, ge=1, le=20)

    @field_validator("window_end", mode="before")
    @classmethod
    def parse_iso_window(cls, value: object) -> object:
        """FastAPI 已解码 JSON；只对 ISO 字符串显式解析，不接受 epoch 数值。"""
        if isinstance(value, str):
            if len(value) > 64:
                raise ValueError("invalid source window")
            return datetime.fromisoformat(value)
        return value


class SourceJobResponse(BaseModel):
    """仅暴露内部 PG 标识与固定状态，不返回输入或任何秘密配置。"""

    job_id: UUID
    status: str
    attempt_count: int
    error_code: str | None
    result_ref: str | None
    created_at: datetime
    finished_at: datetime | None


def build_source_router(
    service_provider: Callable[[], AuthenticationSessionService | None], engine: Engine | None
) -> APIRouter:
    """管理员调度只处理两固定来源；读写失败均返回脱敏 problem。"""
    router = APIRouter()

    def authenticate(request: Request, *, write: bool) -> AccessScope:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            raise InvalidCredentialsError("missing session")
        authentication = service_provider()
        if authentication is None or engine is None:
            raise RuntimeError("source database unavailable")
        if write:
            authentication.validate_write_request(
                token,
                request.headers.get(CSRF_HEADER_NAME, ""),
                request.headers.get("origin"),
            )
        scope = authentication.build_access_scope(token)
        if scope.role != Role.SYSTEM_ADMIN or scope.tenant_id is not None:
            raise PermissionDeniedError("public source administration required")
        return scope

    def failure(request: Request, error: Exception) -> Response:
        if isinstance(error, (SessionExpiredError, InvalidCredentialsError)):
            return problem_response(request, 401, "unauthenticated", "session is not valid")
        if isinstance(error, CsrfRejectionError):
            return problem_response(request, 403, "csrf_rejected", "valid origin and CSRF required")
        if isinstance(error, PermissionDeniedError):
            return problem_response(
                request, 403, "permission_denied", "source administrator required"
            )
        if isinstance(error, IdempotencyConflictError):
            return problem_response(
                request, 409, "idempotency_conflict", "request key already used"
            )
        return problem_response(
            request, 503, "source_unavailable", "source database unavailable", True
        )

    def read_job(session: Session, job_id: UUID) -> SourceJobResponse | None:
        row = (
            session.execute(
                select(job_runs).where(
                    job_runs.c.job_id == str(job_id),
                    job_runs.c.job_type == SOURCE_JOB_TYPE,
                    job_runs.c.tenant_id.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return SourceJobResponse.model_validate(dict(row))

    @router.post(
        "/sources/{source_kind}/collect", status_code=202, response_model=SourceJobResponse
    )
    def collect_source(
        request: Request, source_kind: SourceKind, payload: SourceCollectionRequest
    ) -> SourceJobResponse | Response:
        at = datetime.now(UTC)
        if payload.window_end > at:
            return problem_response(request, 422, "invalid_window", "future source window denied")
        key = request.headers.get("idempotency-key")
        if key is not None and (not key.strip() or len(key) > 200 or not key.isascii()):
            return problem_response(request, 422, "invalid_key", "invalid idempotency key")
        try:
            scope = authenticate(request, write=True)
            if engine is None:
                raise RuntimeError("source database unavailable")
            with Session(engine) as session, session.begin():
                ensure_source_registration(session, scope, source_kind, at)
                job_id = enqueue_source_page(
                    session,
                    SourcePageRequest(
                        source_kind=source_kind,
                        stream_kind=payload.stream_kind,
                        window_end=payload.window_end,
                        remaining_pages=payload.max_pages,
                    ),
                    at,
                    idempotency_key=key,
                )
                response = read_job(session, UUID(job_id))
                if response is None:
                    raise RuntimeError("source job missing")
            return response
        except (
            InvalidCredentialsError,
            SessionExpiredError,
            CsrfRejectionError,
            PermissionDeniedError,
            IdempotencyConflictError,
            SQLAlchemyError,
            RuntimeError,
            ValueError,
        ) as error:
            return failure(request, error)

    @router.get("/jobs/{job_id}", response_model=SourceJobResponse)
    def source_job(request: Request, job_id: UUID) -> SourceJobResponse | Response:
        try:
            authenticate(request, write=False)
            if engine is None:
                raise RuntimeError("source database unavailable")
            with Session(engine) as session:
                response = read_job(session, job_id)
            if response is None:
                return problem_response(request, 404, "not_found", "job is not available")
            return response
        except (
            InvalidCredentialsError,
            SessionExpiredError,
            PermissionDeniedError,
            SQLAlchemyError,
            RuntimeError,
            ValueError,
        ) as error:
            return failure(request, error)

    return router
