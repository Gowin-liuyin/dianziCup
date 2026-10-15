"""证据图只读路由工厂；会话、隔离事务与固定错误沿用知识 API 的边界。"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError
from ai_intel.knowledge.evidence_graph import (
    EvidenceGraphReadService,
    GraphSnapshot,
    GraphSnapshotChangedError,
)


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
                reader = EvidenceGraphReadService(session, scope)
                epochs = reader.read_scope_epochs()
                candidate = reader.event_graph(event_id, max_nodes, max_edges)
                candidate_input = reader.input_sha256
                candidate_inputs = reader.read_inputs
            with Session(engine) as session, session.begin():
                session.connection(execution_options={"isolation_level": "READ COMMITTED"})
                current = lock_authenticated_scope(session.connection(), token, datetime.now(UTC))
                if current != scope:
                    raise PermissionDeniedError("graph authorization changed")
                current.requires(READ_PUBLIC)
                reader = EvidenceGraphReadService(session, current)
                if candidate_inputs is None:
                    raise GraphSnapshotChangedError("graph read inputs missing")
                reader.lock_graph_inputs(event_id, candidate_inputs)
                refreshed = reader.event_graph(event_id, max_nodes, max_edges)
                current_epochs = reader.read_scope_epochs(lock=True)
                if (
                    candidate_input is None
                    or reader.input_sha256 != candidate_input
                    or current_epochs != epochs
                    or refreshed.content_sha256 != candidate.content_sha256
                ):
                    raise GraphSnapshotChangedError("graph snapshot changed")
                return JSONResponse(content=refreshed.model_dump(mode="json"))
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
        except GraphSnapshotChangedError:
            return problem_response(
                request, 409, "graph_snapshot_changed", "graph changed before response", True
            )
        except (SQLAlchemyError, ValueError):
            return problem_response(
                request, 503, "graph_unavailable", "graph database is unavailable", True
            )

    return router
