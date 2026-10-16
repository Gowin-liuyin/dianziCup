"""公开资料GET入口，同一PG事务内复鉴权并读取固定修订。"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import ValidationError
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
from ai_intel.api.document_contracts import (
    DocumentDetailResponse,
    DocumentKindFilter,
    DocumentListResponse,
    DocumentRevisionListResponse,
)
from ai_intel.api.document_read_service import (
    DocumentFilters,
    DocumentReadService,
    InvalidDocumentCursor,
)
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.api.problems import problem_response
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError
from ai_intel.domain.enums import SourceCategory

DocumentResponse = TypeVar(
    "DocumentResponse", DocumentListResponse, DocumentDetailResponse, DocumentRevisionListResponse
)


def build_document_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    data_mode: DataMode,
) -> APIRouter:
    router = APIRouter()

    def serve(
        request: Request, operation: Callable[[DocumentReadService], DocumentResponse]
    ) -> DocumentResponse | Response:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            return problem_response(request, 401, "unauthenticated", "no session cookie present")
        authentication = service_provider()
        if authentication is None or engine is None:
            return problem_response(
                request, 503, "document_unavailable", "document database is unavailable", True
            )
        try:
            initial = authentication.build_access_scope(token)
            initial.requires(READ_PUBLIC)
            with Session(engine) as session:
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                current = lock_authenticated_scope(session.connection(), token, datetime.now(UTC))
                if current.user_id != initial.user_id or current.tenant_id != initial.tenant_id:
                    raise PermissionDeniedError("document authorization changed")
                current.requires(READ_PUBLIC)
                return operation(
                    DocumentReadService(session, current, data_mode, require_expected_mode=False)
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
        except InvalidDocumentCursor:
            return problem_response(request, 422, "invalid_cursor", "document cursor is not valid")
        except (SQLAlchemyError, ValueError):
            return problem_response(
                request, 503, "document_unavailable", "document database is unavailable", True
            )

    @router.get("/documents", response_model=DocumentListResponse)
    def list_documents(
        request: Request,
        q: Annotated[str, Query(max_length=500)] = "",
        document_kind: DocumentKindFilter | None = None,
        source_category: SourceCategory | None = None,
        cursor: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> DocumentListResponse | Response:
        try:
            filters = DocumentFilters(
                q=q, document_kind=document_kind, source_category=source_category
            )
        except ValidationError:
            return problem_response(request, 422, "validation_error", "request schema invalid")
        return serve(request, lambda reader: reader.list_documents(filters, cursor, limit))

    @router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
    def document_detail(
        request: Request,
        document_id: UUID,
        revision_id: UUID | None = None,
        evidence_offset: Annotated[int, Query(ge=0, le=2000)] = 0,
        evidence_limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> DocumentDetailResponse | Response:
        return serve(
            request,
            lambda reader: reader.document_detail(
                document_id, revision_id, evidence_offset, evidence_limit
            ),
        )

    @router.get("/documents/{document_id}/revisions", response_model=DocumentRevisionListResponse)
    def document_revisions(
        request: Request,
        document_id: UUID,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> DocumentRevisionListResponse | Response:
        return serve(request, lambda reader: reader.list_revisions(document_id, offset, limit))

    return router
