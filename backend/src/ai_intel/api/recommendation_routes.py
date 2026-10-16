"""Cookie-only recommendation v1 router; root owns prefix mounting and migrations."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.api.recommendation_contracts import (
    CreateReport,
    CreateSubscription,
    GenerateRecommendations,
    GenerationResponse,
    ReplaceSubscription,
    SetSubscriptionEnabled,
    SubscriptionPatch,
    public_uuid,
)
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.recommendations.mutation_receipts import idempotency_key_digest, perform_mutation
from ai_intel.recommendations.service import RecommendationCursorError, RecommendationService
from ai_intel.recommendations.service_contracts import (
    RecommendationConflictError,
    RecommendationIntegrityError,
    RecommendationPage,
    RecommendationRecord,
    ReportPage,
    ReportReceipt,
    SubscriptionPage,
    SubscriptionRecord,
    canonical_json_bytes,
)

MAX_REQUEST_BYTES = 128 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
PATHS = (
    ("GET", "/subscriptions", "list_subscriptions", SubscriptionPage),
    ("POST", "/subscriptions", "create_subscription", SubscriptionRecord),
    ("GET", "/subscriptions/{subscription_id}", "read_subscription", SubscriptionRecord),
    ("PATCH", "/subscriptions/{subscription_id}", "patch_subscription", SubscriptionRecord),
    ("POST", "/subscriptions/{subscription_id}/generate", "generate", GenerationResponse),
    (
        "GET",
        "/subscriptions/{subscription_id}/recommendations",
        "list_recommendations",
        RecommendationPage,
    ),
    ("POST", "/recommendations/{recommendation_id}/read", "mark_read", RecommendationRecord),
    ("GET", "/subscriptions/{subscription_id}/reports", "list_reports", ReportPage),
    ("POST", "/reports", "create_report", ReportReceipt),
    ("GET", "/reports/{report_id}", "read_report", ReportReceipt),
    ("GET", "/reports/{report_id}/export", "export_report", ReportReceipt),
)


class RecommendationInputError(ValueError):
    """Only boundary errors use 400; stored content failures remain dependency failures."""


@dataclass(frozen=True)
class PageQuery:
    limit: int = 20
    cursor: UUID | None = None
    subscription_id: UUID | None = None


def identifier(value: str | None) -> UUID:
    try:
        if value is None:
            raise ValueError("missing identifier")
        return public_uuid(value)
    except ValueError:
        raise RecommendationInputError("invalid_identifier") from None


def read_query(request: Request, operation: str) -> PageQuery:
    allowed = {"limit", "cursor"} if operation.startswith("list_") else set()
    if operation in {"mark_read", "read_report", "export_report"}:
        allowed = {"subscription_id"}
    entries = request.query_params.multi_items()
    keys = [key for key, _ in entries]
    if len(keys) != len(set(keys)) or set(keys) - allowed:
        raise RecommendationInputError("invalid_query")
    raw_limit = request.query_params.get("limit", "20")
    if re.fullmatch(r"[0-9]{1,3}", raw_limit) is None or not 1 <= int(raw_limit) <= 100:
        raise RecommendationInputError("invalid_page_limit")
    cursor = request.query_params.get("cursor")
    return PageQuery(
        limit=int(raw_limit),
        cursor=identifier(cursor) if cursor is not None else None,
        subscription_id=identifier(request.query_params.get("subscription_id"))
        if "subscription_id" in allowed
        else None,
    )


async def read_body(request: Request) -> dict[str, object]:
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > MAX_REQUEST_BYTES:
            raise RecommendationInputError("request_body_exceeds_budget")
    if not raw:
        return {}
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise RecommendationInputError("json_content_type_required")
    try:
        return strict_json_object(bytes(raw), MAX_REQUEST_BYTES)
    except (ValueError, UnicodeError, RecursionError):
        raise RecommendationInputError("invalid_json_body") from None


def decode_payload(operation: str, raw: dict[str, object]) -> BaseModel | None:
    try:
        encoded = canonical_json_bytes(raw)
        if operation == "create_subscription":
            return CreateSubscription.model_validate_json(encoded)
        if operation == "patch_subscription":
            return TypeAdapter(SubscriptionPatch).validate_json(encoded)
        if operation == "generate":
            return GenerateRecommendations.model_validate_json(encoded)
        if operation == "create_report":
            return CreateReport.model_validate_json(encoded)
        if raw:
            raise RecommendationInputError("unexpected_body")
        return None
    except ValidationError:
        raise RecommendationInputError("request_schema_invalid") from None


def locked_csrf(session: Session, token: str, csrf: str) -> None:
    expected = session.scalar(
        select(auth_sessions.c.csrf_token).where(
            auth_sessions.c.session_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
        )
    )
    if (
        not isinstance(expected, str)
        or not csrf.isascii()
        or not hmac.compare_digest(expected, csrf)
    ):
        raise CsrfRejectionError("csrf token mismatch")


def request_effects(
    service: RecommendationService,
    operation: str,
    payload: BaseModel | None,
    subscription_id: UUID | None,
    resource_id: UUID | None,
) -> tuple[Callable[[], BaseModel], Callable[[dict[str, object]], BaseModel]]:
    """Specific server callbacks preserve locators and re-read current ACL on replay."""
    if operation == "create_subscription" and isinstance(payload, CreateSubscription):

        def replay_subscription(saved: dict[str, object]) -> BaseModel:
            record = SubscriptionRecord.model_validate(saved)
            return service.read_subscription(record.subscription_id)

        return lambda: service.create_subscription(
            payload.spec.internal_spec()
        ), replay_subscription
    if subscription_id is None:
        raise RecommendationIntegrityError("mutation_subscription_binding_missing")
    if operation in {"replace_subscription", "set_enabled"}:

        def replay_patch(saved: dict[str, object]) -> BaseModel:
            record = SubscriptionRecord.model_validate(saved)
            if record.subscription_id != subscription_id:
                raise RecommendationIntegrityError("mutation_target_mismatch")
            return service.read_subscription(subscription_id)

        if isinstance(payload, ReplaceSubscription):
            return lambda: service.replace_subscription(
                subscription_id,
                expected_version=payload.expected_version,
                spec=payload.spec.internal_spec(),
            ), replay_patch
        if isinstance(payload, SetSubscriptionEnabled):
            return lambda: service.set_enabled(
                subscription_id,
                expected_version=payload.expected_version,
                enabled=payload.enabled,
            ), replay_patch
    if operation == "generate" and isinstance(payload, GenerateRecommendations):

        def replay_generation(saved: dict[str, object]) -> BaseModel:
            original = GenerationResponse.model_validate(saved)
            current = GenerationResponse.from_receipt(
                service.read_generation(subscription_id, original.generation_id)
            )
            if (
                set(current.recommendation_ids) != set(original.recommendation_ids)
                or current.model_copy(
                    update={
                        "reused": original.reused,
                        "recommendation_ids": original.recommendation_ids,
                    }
                )
                != original
            ):
                raise RecommendationIntegrityError("mutation_generation_binding_mismatch")
            return current.model_copy(update={"recommendation_ids": original.recommendation_ids})

        return lambda: GenerationResponse.from_receipt(
            service.generate_current(subscription_id, max_candidates=payload.max_candidates)
        ), replay_generation
    if operation == "mark_read" and resource_id is not None:

        def replay_read(saved: dict[str, object]) -> BaseModel:
            original = RecommendationRecord.model_validate(saved)
            if (
                original.recommendation_id != resource_id
                or original.content.key.subscription_id != str(subscription_id)
            ):
                raise RecommendationIntegrityError("mutation_target_mismatch")
            return service.mark_read(subscription_id, resource_id, _mark_read=False)

        return lambda: service.mark_read(subscription_id, resource_id), replay_read
    if operation == "create_report" and isinstance(payload, CreateReport):

        def replay_report(saved: dict[str, object]) -> BaseModel:
            original = ReportReceipt.model_validate(saved)
            if (
                original.content.report.subscription_id != str(subscription_id)
                or original.content.generation_id != payload.generation_id
            ):
                raise RecommendationIntegrityError("mutation_target_mismatch")
            return service.read_report(subscription_id, original.report_id).model_copy(
                update={"reused": True}
            )

        return lambda: service.create_report(
            subscription_id,
            payload.generation_id,
            frequency=payload.frequency,
            max_items=payload.max_items,
        ), replay_report
    raise RecommendationIntegrityError("mutation_operation_mismatch")


def build_recommendation_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    content_store: ContentStorage | None,
    *,
    data_mode: str = "live",
) -> APIRouter:
    """Root mounts this unprefixed factory under /v1 and /api/v1 using existing providers."""
    if data_mode not in {"live", "fixture"}:
        raise ValueError("invalid_data_mode")
    router = APIRouter()

    def failure(request: Request, error: Exception) -> Response:
        if isinstance(error, (InvalidCredentialsError, SessionExpiredError)):
            response = problem_response(request, 401, "session_expired", "session is not valid")
            response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, samesite="strict")
            return response
        if isinstance(error, CsrfRejectionError):
            return problem_response(request, 403, "csrf_rejected", "valid origin and CSRF required")
        if isinstance(error, PermissionDeniedError):
            return problem_response(
                request, 403, "permission_denied", "required permission missing"
            )
        if isinstance(error, CrossTenantAccessError):
            return problem_response(
                request, 404, "not_found", "requested resource is not available"
            )
        if isinstance(error, RecommendationConflictError):
            return problem_response(
                request, 409, "recommendation_conflict", "request conflicts with current state"
            )
        if isinstance(error, RecommendationInputError | RecommendationCursorError):
            return problem_response(request, 400, "invalid_input", "request schema invalid")
        return problem_response(
            request, 503, "not_configured", "recommendation service is unavailable", True
        )

    def execute(
        request: Request,
        operation: str,
        payload: BaseModel | None,
        query: PageQuery,
    ) -> Response:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            raise InvalidCredentialsError("missing session")
        authentication = service_provider()
        if authentication is None or engine is None or content_store is None:
            raise RecommendationIntegrityError("service_not_configured")
        write = request.method in {"POST", "PATCH"}
        if write:
            authentication.validate_write_request(
                token, request.headers.get(CSRF_HEADER_NAME, ""), request.headers.get("origin")
            )
        preliminary = authentication.build_access_scope(token)
        preliminary.requires(READ_PUBLIC)
        service = RecommendationService(
            engine, token, content_store, data_mode="fixture" if data_mode == "fixture" else "live"
        )
        subscription_id = query.subscription_id
        if "subscription_id" in request.path_params:
            subscription_id = identifier(str(request.path_params["subscription_id"]))
        if isinstance(payload, CreateReport):
            subscription_id = payload.subscription_id
        resource_id = None
        for field in ("recommendation_id", "report_id"):
            if field in request.path_params:
                resource_id = identifier(str(request.path_params[field]))
        with Session(engine) as session, session.begin(), service.in_transaction(session) as bound:
            current = bound._scope(session)
            if current != preliminary:
                raise PermissionDeniedError("authorization_changed")
            status_code = 200
            if write:
                locked_csrf(session, token, request.headers.get(CSRF_HEADER_NAME, ""))
                receipt_operation = operation
                if operation == "patch_subscription":
                    receipt_operation = "replace_subscription"
                target = "subscriptions" if subscription_id is None else str(subscription_id)
                if resource_id is not None:
                    target += ":" + str(resource_id)
                effect, replay = request_effects(
                    bound, receipt_operation, payload, subscription_id, resource_id
                )
                key = request.headers.get("idempotency-key")
                if len(request.headers.getlist("idempotency-key")) != 1:
                    raise RecommendationInputError("invalid_idempotency_key")
                try:
                    idempotency_key_digest(key)
                except ValueError:
                    raise RecommendationInputError("invalid_idempotency_key") from None
                if key is None:
                    raise RecommendationInputError("invalid_idempotency_key")
                status_code = 201 if operation == "create_subscription" else 200
                content, status_code = perform_mutation(
                    session,
                    current,
                    operation=receipt_operation,
                    target_locator=target,
                    key=key,
                    request_payload=payload.model_dump(mode="json") if payload else {},
                    status_code=status_code,
                    effect=lambda: effect().model_dump(mode="json"),
                    replay=lambda saved: replay(saved).model_dump(mode="json"),
                )
                if bound._scope(session) != current:
                    raise PermissionDeniedError("authorization_changed")
                locked_csrf(session, token, request.headers.get(CSRF_HEADER_NAME, ""))
            else:
                result: BaseModel
                if operation == "list_subscriptions":
                    result = bound.list_subscriptions(limit=query.limit, cursor=query.cursor)
                elif subscription_id is None:
                    raise RecommendationInputError("subscription_required")
                elif operation == "read_subscription":
                    result = bound.read_subscription(subscription_id)
                elif operation == "list_recommendations":
                    result = bound.list_recommendations(
                        subscription_id, limit=query.limit, cursor=query.cursor
                    )
                elif operation == "list_reports":
                    result = bound.list_reports(
                        subscription_id, limit=query.limit, cursor=query.cursor
                    )
                elif resource_id is not None:
                    result = bound.read_report(subscription_id, resource_id)
                else:
                    raise RecommendationInputError("resource_required")
                content = result.model_dump(mode="json")
            encoded = canonical_json_bytes(content)
            if len(encoded) > MAX_RESPONSE_BYTES:
                raise RecommendationIntegrityError("response_budget_exceeded")
            headers = {"Cache-Control": "no-store"}
            if operation == "export_report" and resource_id is not None:
                headers["Content-Disposition"] = f'attachment; filename="report-{resource_id}.json"'
            return Response(
                encoded, status_code=status_code, media_type="application/json", headers=headers
            )

    def endpoint(operation: str) -> Callable[[Request], object]:
        async def handle(request: Request) -> Response:
            try:
                query = read_query(request, operation)
                raw = await read_body(request) if request.method in {"POST", "PATCH"} else {}
                payload = decode_payload(operation, raw)
                return await run_in_threadpool(execute, request, operation, payload, query)
            except (
                RecommendationInputError,
                RecommendationCursorError,
                RecommendationConflictError,
                RecommendationIntegrityError,
                InvalidCredentialsError,
                SessionExpiredError,
                CsrfRejectionError,
                PermissionDeniedError,
                CrossTenantAccessError,
                SQLAlchemyError,
                ValueError,
                OSError,
            ) as error:
                return failure(request, error)

        return handle

    for method, path, operation, response_model in PATHS:
        router.add_api_route(
            path,
            endpoint(operation),
            methods=[method],
            name=operation,
            response_model=response_model,
        )
    return router
