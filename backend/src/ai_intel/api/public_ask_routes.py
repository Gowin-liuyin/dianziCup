"""Frozen public ask requests over the shared PG question lifecycle and current credentials."""

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ai_intel.answering.service import GroundedQuestionService, QuestionFailure
from ai_intel.api.actor_references import create_actor_reference
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.credentials import (
    ApiKeyRateLimitedError,
    AuthenticatedCredential,
    CredentialParsingError,
    InvalidApiKeyError,
    SessionCredential,
    lock_authenticated_principal,
    parse_request_credential,
)
from ai_intel.api.problems import problem_response
from ai_intel.api.public_write_adapters import MAX_PUBLIC_WRITE_BYTES, parse_public_ask_request
from ai_intel.api.question_contracts import QuestionAnswerResponse, QuestionRequest
from ai_intel.api.question_routes import build_question_service
from ai_intel.domain.access import (
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.infrastructure.settings import ApplicationSettings


def _database_now(connection: Connection) -> datetime:
    current = connection.scalar(select(func.clock_timestamp()))
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise QuestionFailure("question_database_clock_unavailable")
    return current


def _credential(request: Request) -> AuthenticatedCredential:
    session_count = sum(
        field.partition("=")[0].strip() == SESSION_COOKIE_NAME
        for header in request.headers.getlist("cookie")
        for field in header.split(";")
    )
    if session_count > 1:
        raise CredentialParsingError("ambiguous authentication")
    return parse_request_credential(
        request.headers.getlist("authorization"),
        session_cookie=request.cookies.get(SESSION_COOKIE_NAME),
        query_parameter_names=request.query_params.keys(),
    )


def _failure(request: Request, error: Exception) -> Response:
    retry_after: int | None = None
    retryable = False
    if isinstance(
        error,
        (CredentialParsingError, InvalidApiKeyError, SessionExpiredError, InvalidCredentialsError),
    ):
        status, code = 401, "unauthenticated"
    elif isinstance(error, CsrfRejectionError):
        status, code = 403, "csrf_rejected"
    elif isinstance(error, ApiKeyRateLimitedError):
        status, code, retryable = 429, "rate_limited", True
        retry_after = error.retry_after_seconds
    elif isinstance(error, PermissionDeniedError):
        status, code = 403, "permission_denied"
    elif isinstance(error, CrossTenantAccessError):
        status, code = 404, "not_found"
    elif isinstance(error, QuestionFailure):
        status = error.status
        code = "answer_failed" if error.code == "answer_lease_expired" else error.code
        retryable = status in {429, 503}
    else:
        status, code, retryable = 503, "question_database_unavailable", True
    response = problem_response(
        request, status, code, "question request could not be completed", retryable
    )
    response.headers["Cache-Control"] = "no-store"
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def build_public_ask_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    settings: ApplicationSettings,
    *,
    questions_provider: Callable[[], GroundedQuestionService | None] | None = None,
) -> APIRouter:
    """Root mounts /ask under its public prefix; only the shared service reserves quota."""
    router = APIRouter()
    questions = (
        questions_provider()
        if questions_provider is not None
        else build_question_service(engine, settings)
    )
    contract_path = (
        Path(__file__).resolve().parents[4] / "contracts/schemas/public_api_extensions_v1.json"
    )
    request_schema = json.loads(contract_path.read_text(encoding="utf-8"))["$defs"]["AskRequest"]

    def serve(
        request: Request,
        payload: QuestionRequest,
        credential: AuthenticatedCredential,
        idempotency_key: str,
    ) -> Response:
        try:
            if engine is None:
                raise QuestionFailure("question_database_unavailable")
            if isinstance(credential, SessionCredential):
                authentication = service_provider()
                if authentication is None:
                    raise QuestionFailure("question_database_unavailable")
                if (
                    len(request.headers.getlist(CSRF_HEADER_NAME)) != 1
                    or len(request.headers.getlist("origin")) != 1
                ):
                    raise CsrfRejectionError("valid origin and CSRF required")
                authentication.validate_write_request(
                    credential.token.get_secret_value(),
                    request.headers[CSRF_HEADER_NAME],
                    request.headers["origin"],
                )

            def current_scope() -> AccessScope:
                with engine.begin() as connection:
                    scope = lock_authenticated_principal(
                        connection, credential, _database_now(connection)
                    )
                    scope.requires(READ_PUBLIC)
                    return scope

            with engine.begin() as connection:
                scope = lock_authenticated_principal(
                    connection, credential, _database_now(connection)
                )
                scope.requires(READ_PUBLIC)
                actor = create_actor_reference(connection, credential, _database_now(connection))
            if questions is None:
                raise QuestionFailure("question_models_not_configured")
            answer = questions.ask(
                payload,
                current_scope,
                idempotency_key,
                session_token=actor,
                credential=credential,
            )
            return JSONResponse(
                answer.model_dump(mode="json"), headers={"Cache-Control": "no-store"}
            )
        except (
            InvalidApiKeyError,
            ApiKeyRateLimitedError,
            SessionExpiredError,
            InvalidCredentialsError,
            CsrfRejectionError,
            PermissionDeniedError,
            CrossTenantAccessError,
            QuestionFailure,
            SQLAlchemyError,
            ValueError,
        ) as error:
            return _failure(request, error)

    @router.post(
        "/ask",
        response_model=QuestionAnswerResponse,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": request_schema}},
            },
            "parameters": [
                {
                    "in": "header",
                    "name": "Idempotency-Key",
                    "required": True,
                    "schema": {"type": "string", "pattern": r"^[\x21-\x7e]{1,200}$"},
                }
            ],
        },
    )
    async def ask_question(request: Request) -> Response:
        try:
            credential = _credential(request)
        except CredentialParsingError as error:
            return _failure(request, error)
        try:
            keys = request.headers.getlist("idempotency-key")
            if len(keys) != 1 or re.fullmatch(r"[\x21-\x7e]{1,200}", keys[0]) is None:
                raise ValueError("public operation key is invalid")
            if request.query_params:
                raise ValueError("ask query parameters are unsupported")
            content_types = request.headers.getlist("content-type")
            if (
                len(content_types) != 1
                or content_types[0].partition(";")[0].strip().lower() != "application/json"
            ):
                raise ValueError("JSON content type required")
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > MAX_PUBLIC_WRITE_BYTES:
                    raise ValueError("public request exceeds byte limit")
                raw.extend(chunk)
            payload = parse_public_ask_request(bytes(raw))
        except (ValueError, RecursionError):
            response = problem_response(
                request, 422, "validation_error", "public ask request is invalid"
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        return await run_in_threadpool(serve, request, payload, credential, keys[0])

    return router
