"""Authenticated durable enrichment requests perform no model or source IO in HTTP handlers."""

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.enrichment_contracts import EnrichmentEnqueueResponse, EnrichmentWorkflowResponse
from ai_intel.api.problems import problem_response
from ai_intel.domain.access import (
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.enrichment.job_contracts import EventEnrichmentRequest
from ai_intel.enrichment.job_service import EnrichmentJobService, EnrichmentWorkflowError
from ai_intel.infrastructure.outbox import IdempotencyConflictError


def build_enrichment_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    enrichment: EnrichmentJobService | None,
) -> APIRouter:
    """The same transaction binds current authentication, scope and idempotent scheduling."""
    router = APIRouter()

    def authenticate(request: Request, *, write: bool) -> AccessScope:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            raise InvalidCredentialsError("missing session")
        authentication = service_provider()
        if authentication is None or engine is None or enrichment is None:
            raise RuntimeError("enrichment database unavailable")
        if write:
            authentication.validate_write_request(
                token, request.headers.get(CSRF_HEADER_NAME, ""), request.headers.get("origin")
            )
        scope = authentication.build_access_scope(token)
        scope.requires(READ_PUBLIC)
        return scope

    def lock_scope(session: Session, request: Request, initial: AccessScope) -> AccessScope:
        current = lock_authenticated_scope(
            session.connection(), request.cookies.get(SESSION_COOKIE_NAME, ""), datetime.now(UTC)
        )
        if current != initial:
            raise PermissionDeniedError("enrichment authorization changed")
        return current

    def failure(request: Request, error: Exception) -> Response:
        if isinstance(error, (InvalidCredentialsError, SessionExpiredError)):
            return problem_response(request, 401, "unauthenticated", "session is not valid")
        if isinstance(error, CsrfRejectionError):
            return problem_response(request, 403, "csrf_rejected", "valid origin and CSRF required")
        if isinstance(error, PermissionDeniedError):
            return problem_response(
                request, 403, "permission_denied", "required permission missing"
            )
        if isinstance(error, CrossTenantAccessError):
            return problem_response(request, 404, "not_found", "workflow is not available")
        if isinstance(error, IdempotencyConflictError):
            return problem_response(
                request, 409, "idempotency_conflict", "request key already used"
            )
        if (
            isinstance(error, EnrichmentWorkflowError)
            and error.status in {403, 404, 409, 503}
            and re.fullmatch(r"[a-z0-9_]{1,100}", error.code)
        ):
            return problem_response(
                request,
                error.status,
                error.code,
                "enrichment request could not be completed",
                error.status == 503,
            )
        return problem_response(
            request, 503, "enrichment_unavailable", "enrichment database is unavailable", True
        )

    @router.post(
        "/events/{event_id}/enrichment-jobs",
        status_code=202,
        response_model=EnrichmentEnqueueResponse,
    )
    def enqueue_enrichment(
        request: Request,
        event_id: UUID,
        payload: EventEnrichmentRequest,
    ) -> EnrichmentEnqueueResponse | Response:
        try:
            scope = authenticate(request, write=True)
            key = request.headers.get("idempotency-key")
            if key is None or re.fullmatch(r"[\x21-\x7e]{1,200}", key) is None:
                return problem_response(request, 422, "invalid_key", "invalid idempotency key")
            if engine is None or enrichment is None:
                raise RuntimeError("enrichment database unavailable")
            with Session(engine) as session, session.begin():
                scope = lock_scope(session, request, scope)
                receipt = enrichment.enqueue(
                    session,
                    scope,
                    event_id,
                    payload,
                    actor_session_hash=hashlib.sha256(
                        request.cookies.get(SESSION_COOKIE_NAME, "").encode("utf-8")
                    ).hexdigest(),
                    idempotency_key=key,
                    created_at=datetime.now(UTC),
                )
                return EnrichmentEnqueueResponse(
                    workflow_id=receipt.workflow_id,
                    parent_job_id=receipt.parent_job_id,
                    reused=receipt.reused,
                )
        except (
            InvalidCredentialsError,
            SessionExpiredError,
            CsrfRejectionError,
            PermissionDeniedError,
            CrossTenantAccessError,
            IdempotencyConflictError,
            EnrichmentWorkflowError,
            SQLAlchemyError,
            ValueError,
            RuntimeError,
        ) as error:
            return failure(request, error)

    @router.get("/enrichment-workflows/{workflow_id}", response_model=EnrichmentWorkflowResponse)
    def read_enrichment(
        request: Request, workflow_id: UUID
    ) -> EnrichmentWorkflowResponse | Response:
        try:
            scope = authenticate(request, write=False)
            if engine is None or enrichment is None:
                raise RuntimeError("enrichment database unavailable")
            with Session(engine) as session, session.begin():
                scope = lock_scope(session, request, scope)
                view = enrichment.read_workflow(
                    session,
                    scope,
                    workflow_id,
                    actor_session_hash=hashlib.sha256(
                        request.cookies.get(SESSION_COOKIE_NAME, "").encode("utf-8")
                    ).hexdigest(),
                    at=datetime.now(UTC),
                )
                return EnrichmentWorkflowResponse.model_validate(view, from_attributes=True)
        except (
            InvalidCredentialsError,
            SessionExpiredError,
            PermissionDeniedError,
            CrossTenantAccessError,
            EnrichmentWorkflowError,
            SQLAlchemyError,
            ValueError,
            RuntimeError,
        ) as error:
            return failure(request, error)

    return router
