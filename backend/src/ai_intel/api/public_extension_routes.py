"""Request-bound public read routes using the current credential and rate-limit services."""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import JsonValue
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.credentials import (
    ApiKeyCredential,
    ApiKeyRateLimitedError,
    CredentialParsingError,
    InvalidApiKeyError,
    consume_api_key_rate_limit,
    lock_authenticated_principal,
    parse_request_credential,
)
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.api.problems import problem_response
from ai_intel.api.public_extension_reads import (
    JSON_OBJECT,
    InvalidPublicCursor,
    PublicExtensionReadService,
    PublicReadUnavailable,
    validate_page_inputs,
)
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError
from ai_intel.knowledge.evidence_graph import GraphSnapshotChangedError
from ai_intel.knowledge.persistence import publication_payload_digest


def _public_problem(request: Request, status: int, code: str, retryable: bool = False) -> Response:
    original = problem_response(
        request, status, code, "public read could not be completed", retryable
    )
    value = JSON_OBJECT.validate_json(bytes(original.body))
    route = request.scope.get("route")
    value["instance"] = str(getattr(route, "path", "/api/v1"))
    return JSONResponse(
        value,
        status_code=status,
        media_type="application/problem+json",
        headers={"X-Request-ID": str(value["trace_id"]), "Cache-Control": "no-store"},
    )


def _page_parameters(request: Request, *, search: bool) -> tuple[str | None, int, str | None]:
    allowed = {"q", "limit", "cursor"} if search else {"limit", "cursor"}
    if set(request.query_params) - allowed:
        raise ValueError("unsupported query parameters")
    if any(len(request.query_params.getlist(name)) != 1 for name in request.query_params):
        raise ValueError("duplicate query parameters")
    raw_limit = request.query_params.get("limit", "20")
    if re.fullmatch(r"[1-9][0-9]{0,2}", raw_limit) is None:
        raise ValueError("invalid page limit")
    q = request.query_params.get("q") if search else None
    cursor = request.query_params.get("cursor")
    limit = int(raw_limit)
    validate_page_inputs(q, limit, cursor)
    return q, limit, cursor


def _event_uuid(value: str) -> UUID:
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("canonical UUID required")
    return parsed


def build_public_extension_router(
    engine: Engine | None,
    data_mode: DataMode,
    *,
    source_polling_enabled: bool,
) -> APIRouter:
    """Root mounts this factory under /api/v1; it does not configure a second auth service."""
    router = APIRouter()

    def serve(
        request: Request,
        operation: Callable[[PublicExtensionReadService], dict[str, JsonValue]],
    ) -> Response:
        try:
            credential = parse_request_credential(
                request.headers.getlist("authorization"),
                session_cookie=request.cookies.get(SESSION_COOKIE_NAME),
                query_parameter_names=request.query_params.keys(),
            )
            if engine is None:
                raise PublicReadUnavailable("public database producer is not configured")
            with Session(engine) as session, session.begin():
                connection = session.connection()
                if isinstance(credential, ApiKeyCredential):
                    scope = consume_api_key_rate_limit(connection, credential, datetime.now(UTC))
                else:
                    scope = lock_authenticated_principal(connection, credential, datetime.now(UTC))
                scope.requires(READ_PUBLIC)
                reader = PublicExtensionReadService(
                    session, scope, data_mode, source_polling_enabled
                )
                result = operation(reader)
                refreshed_scope = lock_authenticated_principal(
                    connection, credential, datetime.now(UTC)
                )
                if refreshed_scope != scope:
                    raise PermissionDeniedError("public read identity changed")
                refreshed = operation(reader)
                if publication_payload_digest(refreshed) != publication_payload_digest(result):
                    raise GraphSnapshotChangedError("public read changed before response")
                if lock_authenticated_principal(connection, credential, datetime.now(UTC)) != scope:
                    raise PermissionDeniedError("public read identity changed")
                return JSONResponse(refreshed, headers={"Cache-Control": "no-store"})
        except (CredentialParsingError, InvalidApiKeyError, SessionExpiredError):
            return _public_problem(request, 401, "unauthenticated")
        except ApiKeyRateLimitedError as error:
            response = _public_problem(request, 429, "rate_limited", True)
            response.headers["Retry-After"] = str(error.retry_after_seconds)
            return response
        except PermissionDeniedError:
            return _public_problem(request, 403, "permission_denied")
        except CrossTenantAccessError:
            return _public_problem(request, 404, "not_found")
        except InvalidPublicCursor:
            return _public_problem(request, 422, "invalid_cursor")
        except GraphSnapshotChangedError:
            return _public_problem(request, 409, "read_snapshot_changed", True)
        except PublicReadUnavailable:
            return _public_problem(request, 503, "not_configured")
        except (SQLAlchemyError, ValueError):
            return _public_problem(request, 503, "public_read_unavailable", True)

    @router.get("/vulns")
    def search_vulns(request: Request) -> Response:
        try:
            q, limit, cursor = _page_parameters(request, search=True)
        except (ValueError, UnicodeError):
            return _public_problem(request, 422, "validation_error")
        return serve(request, lambda reader: reader.search_vulns(q, limit, cursor))

    @router.get("/vulns/{event_id}")
    def get_vuln(request: Request, event_id: str) -> Response:
        try:
            identifier = _event_uuid(event_id)
            _, limit, cursor = _page_parameters(request, search=False)
        except (ValueError, UnicodeError):
            return _public_problem(request, 422, "validation_error")
        return serve(request, lambda reader: reader.get_vuln(identifier, limit, cursor))

    @router.get("/sources")
    def list_sources(request: Request) -> Response:
        try:
            _, limit, cursor = _page_parameters(request, search=False)
        except (ValueError, UnicodeError):
            return _public_problem(request, 422, "validation_error")
        return serve(request, lambda reader: reader.list_sources(limit, cursor))

    @router.get("/tasks/{task_id}")
    def get_task_result(request: Request, task_id: str) -> Response:
        try:
            identifier = _event_uuid(task_id)
            if request.query_params:
                raise ValueError("task result query parameters are unsupported")
        except ValueError:
            return _public_problem(request, 422, "validation_error")
        return serve(request, lambda reader: reader.get_task_result(identifier))

    return router
