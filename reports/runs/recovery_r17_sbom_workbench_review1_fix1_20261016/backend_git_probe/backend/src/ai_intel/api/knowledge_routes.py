"""认证的知识只读HTTP入口；失败使用固定problem，不回显数据库异常。"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.knowledge_contracts import (
    DataMode,
    EventDetailResponse,
    EventListResponse,
    EvidenceResponse,
)
from ai_intel.api.knowledge_read_service import (
    EventFilters,
    InvalidEventCursor,
    KnowledgeReadService,
)
from ai_intel.api.problems import problem_response
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError

KnowledgeResponse = TypeVar(
    "KnowledgeResponse", EventListResponse, EventDetailResponse, EvidenceResponse
)


def build_knowledge_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    data_mode: DataMode,
) -> APIRouter:
    """同一会话构造范围；查询不接受客户端tenant/权限或任意排序表达式。"""
    router = APIRouter()

    def serve(
        request: Request, operation: Callable[[KnowledgeReadService], KnowledgeResponse]
    ) -> KnowledgeResponse | Response:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            return problem_response(request, 401, "unauthenticated", "no session cookie present")
        authentication = service_provider()
        if authentication is None:
            return problem_response(
                request, 503, "knowledge_unavailable", "knowledge database is unavailable", True
            )
        try:
            scope = authentication.build_access_scope(token)
            scope.requires(READ_PUBLIC)
            if engine is None:
                return problem_response(
                    request, 503, "knowledge_unavailable", "knowledge database is unavailable", True
                )
            with Session(engine) as session:
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                reader = KnowledgeReadService(session, scope, data_mode)
                return operation(reader)
        except (SessionExpiredError, InvalidCredentialsError):
            return problem_response(request, 401, "session_expired", "session is not valid")
        except PermissionDeniedError:
            return problem_response(
                request, 403, "permission_denied", "required permission missing"
            )
        except CrossTenantAccessError:
            return problem_response(
                request, 404, "not_found", "requested resource is not available"
            )
        except InvalidEventCursor:
            return problem_response(request, 422, "invalid_cursor", "event cursor is not valid")
        except (SQLAlchemyError, ValueError):
            return problem_response(
                request, 503, "knowledge_unavailable", "knowledge database is unavailable", True
            )

    @router.get("/events", response_model=EventListResponse)
    def list_events(
        request: Request,
        q: Annotated[str, Query(max_length=500)] = "",
        product: Annotated[str, Query(max_length=500)] = "",
        risk_type: Annotated[str, Query(max_length=100)] = "",
        updated_after: Annotated[datetime | None, Query()] = None,
        cursor: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> EventListResponse | Response:
        try:
            filters = EventFilters(
                q=q, product=product, risk_type=risk_type, updated_after=updated_after
            )
        except ValidationError:
            return problem_response(request, 422, "validation_error", "request schema invalid")
        return serve(request, lambda reader: reader.list_events(filters, cursor, limit))

    @router.get("/events/{event_id}", response_model=EventDetailResponse)
    def event_detail(request: Request, event_id: UUID) -> EventDetailResponse | Response:
        return serve(request, lambda reader: reader.event_detail(event_id))

    @router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
    def read_evidence(request: Request, evidence_id: UUID) -> EvidenceResponse | Response:
        return serve(request, lambda reader: reader.read_evidence(evidence_id))

    return router
