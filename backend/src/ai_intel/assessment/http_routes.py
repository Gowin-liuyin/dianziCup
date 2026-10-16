"""Cookie-authenticated assessment HTTP boundary over the existing PG service."""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.http_contracts import (
    MAX_ASSESSMENT_BODY_BYTES,
    AssessmentRequest,
    AssessmentResponse,
)
from ai_intel.assessment.rule_persistence import RulePersistenceError
from ai_intel.domain.access import READ_ASSET, CrossTenantAccessError, PermissionDeniedError
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.minio_store import ObjectStoreUnavailableError
from ai_intel.infrastructure.models.json_output import strict_json_object


class AssessmentUnavailableError(RuntimeError):
    """Required PG, authentication or content storage has not been configured."""


class AssessmentBodyTooLargeError(ValueError):
    """The streamed request exceeds the fixed HTTP byte budget."""


def build_assessment_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    content_store: ContentStorage | None,
) -> APIRouter:
    """Root mounts the router; services retain their transaction and CAS rechecks."""
    router = APIRouter()

    def authenticate(request: Request, *, write: bool) -> AssessmentService:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            raise InvalidCredentialsError("missing session")
        authentication = service_provider()
        if authentication is None or engine is None or content_store is None:
            raise AssessmentUnavailableError("assessment dependencies unavailable")
        try:
            if write:
                authentication.validate_write_request(
                    token, request.headers.get(CSRF_HEADER_NAME, ""), request.headers.get("origin")
                )
            scope = authentication.build_access_scope(token)
        except ValueError:
            raise PermissionDeniedError("invalid authentication scope") from None
        scope.requires(READ_ASSET)
        if scope.tenant_id is None:
            raise PermissionDeniedError("tenant asset scope required")
        return AssessmentService(engine, token, content_store)

    def failure(request: Request, error: Exception) -> Response:
        if isinstance(error, (SessionExpiredError, InvalidCredentialsError)):
            response = problem_response(request, 401, "session_expired", "session is not valid")
        elif isinstance(error, CsrfRejectionError):
            response = problem_response(
                request, 403, "csrf_rejected", "valid origin and CSRF required"
            )
        elif isinstance(error, PermissionDeniedError):
            response = problem_response(
                request, 403, "permission_denied", "required permission missing"
            )
        elif isinstance(error, CrossTenantAccessError):
            response = problem_response(
                request, 404, "not_found", "requested resource is not available"
            )
        elif isinstance(error, (OSError, ObjectStoreUnavailableError)):
            response = problem_response(
                request,
                503,
                "assessment_evidence_unavailable",
                "assessment evidence is unavailable",
                True,
            )
        elif isinstance(error, (RulePersistenceError, ValueError)):
            response = problem_response(
                request, 409, "assessment_inputs_invalid", "assessment inputs could not be verified"
            )
        else:
            response = problem_response(
                request, 503, "assessment_unavailable", "assessment dependencies unavailable", True
            )
        response.headers["Cache-Control"] = "no-store"
        return response

    handled = (
        SessionExpiredError,
        InvalidCredentialsError,
        CsrfRejectionError,
        PermissionDeniedError,
        CrossTenantAccessError,
        RulePersistenceError,
        SQLAlchemyError,
        AssessmentUnavailableError,
        ValueError,
        OSError,
        ObjectStoreUnavailableError,
    )

    def evaluate(service: AssessmentService, payload: AssessmentRequest) -> AssessmentResponse:
        prepared = service.prepare(
            str(payload.asset_id),
            str(payload.asset_snapshot_id),
            payload.rule_id,
            payload.rule_version,
        )
        return AssessmentResponse.from_receipt(service.commit(prepared))

    def success(receipt: AssessmentResponse) -> Response:
        return JSONResponse(
            content=receipt.model_dump(mode="json"), headers={"Cache-Control": "no-store"}
        )

    @router.post(
        "/assessments",
        response_model=AssessmentResponse,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": AssessmentRequest.model_json_schema()}},
            }
        },
    )
    async def create_assessment(request: Request) -> Response:
        try:
            service = await run_in_threadpool(authenticate, request, write=True)
        except handled as error:
            return failure(request, error)
        try:
            if request.query_params:
                raise ValueError("unsupported assessment query")
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_ASSESSMENT_BODY_BYTES:
                    raise AssessmentBodyTooLargeError("assessment body outside limit")
                body.extend(chunk)
            payload = AssessmentRequest.model_validate(
                strict_json_object(bytes(body), MAX_ASSESSMENT_BODY_BYTES, maximum_nodes=64)
            )
        except (ValidationError, ValueError, RecursionError) as error:
            oversized = isinstance(error, AssessmentBodyTooLargeError)
            response = problem_response(
                request,
                413 if oversized else 422,
                "assessment_body_too_large" if oversized else "validation_error",
                "assessment request exceeds byte limit"
                if oversized
                else "assessment request is not valid",
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        try:
            return success(await run_in_threadpool(evaluate, service, payload))
        except handled as error:
            return failure(request, error)

    @router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
    def read_assessment(request: Request, assessment_id: str) -> Response:
        try:
            service = authenticate(request, write=False)
        except handled as error:
            return failure(request, error)
        try:
            if request.query_params:
                raise ValueError("unsupported assessment query")
            identity = str(UUID(assessment_id))
        except ValueError:
            response = problem_response(
                request, 422, "validation_error", "assessment request is not valid"
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        try:
            return success(AssessmentResponse.from_receipt(service.read(identity)))
        except handled as error:
            return failure(request, error)

    return router
