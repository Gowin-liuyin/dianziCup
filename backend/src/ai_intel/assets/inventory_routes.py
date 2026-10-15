"""独立私有资产入口；真实PG鉴权、Origin/CSRF和业务事务在同一请求边界。"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
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
from ai_intel.api.problems import problem_response
from ai_intel.assets.inventory import (
    MAX_INVENTORY_UPLOAD_BYTES,
    AssetNameConflictError,
    InvalidAssetCursor,
    InventoryService,
)
from ai_intel.assets.inventory_contracts import AssetSnapshotRequest
from ai_intel.assets.manifest_parser import ManifestValidationError
from ai_intel.domain.access import (
    READ_ASSET,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.infrastructure.outbox import IdempotencyConflictError


class InventoryUnavailableError(RuntimeError):
    """资产PG或认证服务未配置，不使用fixture替代。"""


def build_inventory_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
) -> APIRouter:
    """供主控正式挂接；本模块不修改app，不建立另一套会话与角色权限。"""
    router = APIRouter()

    def authenticate(request: Request, *, write: bool) -> AccessScope:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            raise InvalidCredentialsError("missing session")
        authentication = service_provider()
        if authentication is None or engine is None:
            raise InventoryUnavailableError("inventory database unavailable")
        if write:
            authentication.validate_write_request(
                token,
                request.headers.get(CSRF_HEADER_NAME, ""),
                request.headers.get("origin"),
            )
        scope = authentication.build_access_scope(token)
        scope.requires(WRITE_ASSET if write else READ_ASSET)
        if not scope.tenant_id:
            raise PermissionDeniedError("tenant asset scope required")
        return scope

    def serve(
        request: Request,
        initial: AccessScope,
        operation: Callable[[InventoryService], Response],
        *,
        write: bool,
    ) -> Response:
        if engine is None:
            raise InventoryUnavailableError("inventory database unavailable")
        with Session(engine) as session, session.begin():
            if not write:
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            current = lock_authenticated_scope(
                session.connection(),
                request.cookies.get(SESSION_COOKIE_NAME, ""),
                datetime.now(UTC),
            )
            if current.user_id != initial.user_id or current.tenant_id != initial.tenant_id:
                raise PermissionDeniedError("asset authorization changed")
            current.requires(WRITE_ASSET if write else READ_ASSET)
            return operation(InventoryService(session, current))

    def failure(request: Request, error: Exception) -> Response:
        if isinstance(error, (SessionExpiredError, InvalidCredentialsError)):
            return problem_response(request, 401, "session_expired", "session is not valid")
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
        if isinstance(error, IdempotencyConflictError):
            return problem_response(
                request, 409, "idempotency_conflict", "idempotency key conflict"
            )
        if isinstance(error, AssetNameConflictError):
            return problem_response(
                request,
                409,
                "asset_name_conflict",
                "asset display name requires separate operation",
            )
        if isinstance(error, ManifestValidationError):
            status = 413 if error.code == "inventory_upload_size_limit" else 422
            return problem_response(
                request, status, error.code, "asset input is not valid at " + error.locator
            )
        if isinstance(error, (InvalidAssetCursor, ValidationError, ValueError)):
            return problem_response(request, 422, "validation_error", "asset request is not valid")
        return problem_response(
            request, 503, "inventory_unavailable", "asset database unavailable", True
        )

    handled = (
        SessionExpiredError,
        InvalidCredentialsError,
        CsrfRejectionError,
        PermissionDeniedError,
        CrossTenantAccessError,
        IdempotencyConflictError,
        AssetNameConflictError,
        ManifestValidationError,
        InvalidAssetCursor,
        ValidationError,
        ValueError,
        SQLAlchemyError,
        InventoryUnavailableError,
    )

    async def read_body(request: Request) -> bytes:
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_INVENTORY_UPLOAD_BYTES:
                raise ManifestValidationError("inventory_upload_size_limit")
            body.extend(chunk)
        if not body:
            raise ManifestValidationError("inventory_upload_size_limit")
        return bytes(body)

    @router.post("/asset-snapshots")
    async def create_snapshot(request: Request) -> Response:
        try:
            initial = authenticate(request, write=True)
            payload = AssetSnapshotRequest.model_validate(
                strict_json_object(
                    await read_body(request), MAX_INVENTORY_UPLOAD_BYTES, maximum_nodes=50000
                )
            )
            raw = json.dumps(payload.snapshot, ensure_ascii=False, separators=(",", ":")).encode()
            return serve(
                request,
                initial,
                lambda service: JSONResponse(
                    status_code=201,
                    content=service.import_manifest(
                        raw,
                        manifest_format="json_manifest_v1",
                        display_name=payload.display_name,
                        source_version=payload.source_version,
                        observed_at=payload.observed_at,
                        idempotency_key=request.headers.get("idempotency-key", ""),
                        asset_id=None if payload.asset_id is None else str(payload.asset_id),
                        request_route="asset-snapshots",
                    ).model_dump(mode="json"),
                ),
                write=True,
            )
        except handled as error:
            return failure(request, error)

    @router.post("/asset-imports")
    async def import_asset(request: Request) -> Response:
        try:
            initial = authenticate(request, write=True)
            allowed = {
                "asset_id",
                "display_name",
                "source_version",
                "observed_at",
                "manifest_format",
                "csv_column_mapping",
            }
            if not set(request.query_params) <= allowed:
                raise ValueError("unsupported upload parameter")
            raw = await read_body(request)
            mapping_text = request.query_params.get("csv_column_mapping")
            mapping: dict[str, str] | None = None
            if mapping_text is not None:
                candidate: object = json.loads(mapping_text)
                if not isinstance(candidate, dict) or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in candidate.items()
                ):
                    raise ValueError("invalid CSV mapping")
                mapping = {key: value for key, value in candidate.items()}
            identity_text = request.query_params.get("asset_id")
            identity = None if identity_text is None else str(UUID(identity_text))
            observed = datetime.fromisoformat(request.query_params.get("observed_at", ""))
            return serve(
                request,
                initial,
                lambda service: JSONResponse(
                    status_code=201,
                    content=service.import_manifest(
                        raw,
                        manifest_format=request.query_params.get("manifest_format", ""),
                        display_name=request.query_params.get("display_name", ""),
                        source_version=request.query_params.get("source_version", ""),
                        observed_at=observed,
                        idempotency_key=request.headers.get("idempotency-key", ""),
                        asset_id=identity,
                        csv_column_mapping=mapping,
                        request_route="asset-imports",
                    ).model_dump(mode="json"),
                ),
                write=True,
            )
        except handled as error:
            return failure(request, error)

    @router.get("/assets")
    def list_assets(request: Request) -> Response:
        try:
            initial = authenticate(request, write=False)
            if not set(request.query_params) <= {"cursor", "limit", "product"}:
                raise ValueError("unsupported asset query")
            return serve(
                request,
                initial,
                lambda service: JSONResponse(
                    content=service.list_assets(
                        limit=int(request.query_params.get("limit", "20")),
                        cursor=request.query_params.get("cursor"),
                        product=request.query_params.get("product", ""),
                    ).model_dump(mode="json"),
                ),
                write=False,
            )
        except handled as error:
            return failure(request, error)

    @router.get("/assets/{asset_id}")
    def get_asset(request: Request, asset_id: str) -> Response:
        try:
            initial = authenticate(request, write=False)
            identity = str(UUID(asset_id))
            return serve(
                request,
                initial,
                lambda service: JSONResponse(
                    content=service.read_asset(identity).model_dump(mode="json"),
                ),
                write=False,
            )
        except handled as error:
            return failure(request, error)

    @router.get("/assets/{asset_id}/snapshots")
    def list_snapshots(request: Request, asset_id: str) -> Response:
        try:
            initial = authenticate(request, write=False)
            identity = str(UUID(asset_id))
            if not set(request.query_params) <= {"cursor", "limit"}:
                raise ValueError("unsupported snapshot query")
            return serve(
                request,
                initial,
                lambda service: JSONResponse(
                    content=service.list_snapshots(
                        identity,
                        limit=int(request.query_params.get("limit", "20")),
                        cursor=request.query_params.get("cursor"),
                    ).model_dump(mode="json"),
                ),
                write=False,
            )
        except handled as error:
            return failure(request, error)

    @router.get("/assets/{asset_id}/snapshots/{snapshot_id}")
    def get_snapshot(request: Request, asset_id: str, snapshot_id: str) -> Response:
        try:
            initial = authenticate(request, write=False)
            identity, snapshot = str(UUID(asset_id)), str(UUID(snapshot_id))
            return serve(
                request,
                initial,
                lambda service: JSONResponse(
                    content=service.get_snapshot(identity, snapshot).model_dump(mode="json"),
                ),
                write=False,
            )
        except handled as error:
            return failure(request, error)

    return router
