"""证据图只读路由工厂；会话、隔离事务与固定错误沿用知识 API 的边界。"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService, GraphSnapshot


def build_graph_router(
    service_provider: Callable[[], AuthenticationSessionService | None], engine: Engine | None
) -> APIRouter:
    """由产品装配注入原会话 provider；请求不能自报租户、scope 或查询表达式。"""
    router = APIRouter()

    @router.get("/events/{event_id}/graph", response_model=GraphSnapshot)
    def event_graph(
        request: Request,
        event_id: UUID,
        max_nodes: Annotated[int, Query(ge=1, le=200)] = 200,
        max_edges: Annotated[int, Query(ge=1, le=400)] = 400,
    ) -> GraphSnapshot | Response:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            return problem_response(request, 401, "unauthenticated", "no session cookie present")
        if set(request.query_params) - {"max_nodes", "max_edges"}:
            return problem_response(request, 422, "validation_error", "request schema invalid")
        try:
            authentication = service_provider()
            if authentication is None:
                return problem_response(
                    request, 503, "graph_unavailable", "graph database is unavailable", True
                )
            scope = authentication.build_access_scope(token)
            scope.requires(READ_PUBLIC)
            if engine is None:
                return problem_response(
                    request, 503, "graph_unavailable", "graph database is unavailable", True
                )
            with Session(engine) as session:
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                return EvidenceGraphReadService(session, scope).event_graph(
                    event_id, max_nodes, max_edges
                )
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
        except (SQLAlchemyError, ValueError):
            return problem_response(
                request, 503, "graph_unavailable", "graph database is unavailable", True
            )

    return router
