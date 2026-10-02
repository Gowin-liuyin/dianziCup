"""认证 HTTP 路由(T40 前置最小修复): login/me/csrf/logout, 复用 T06 会话服务。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InvalidCredentialsError,
    LoginRateLimitedError,
    SessionExpiredError,
)

SESSION_COOKIE_NAME = "ai_intel_session"
CSRF_HEADER_NAME = "X-CSRF-Token"


def _error_response(status_code: int, code: str, message: str, retryable: bool) -> JSONResponse:
    """统一错误体: code/message/retryable, 与 T40-A 合同核对缺口对齐。"""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "retryable": retryable}},
    )


def build_auth_router(service: AuthenticationSessionService) -> APIRouter:
    """构建 /auth 路由: 会话走 HttpOnly Cookie, CSRF 走响应体+请求头, 秘密不进前端存储。"""
    router = APIRouter(prefix="/auth")

    @router.post("/login")
    def auth_login(request: Request, payload: dict[str, Any]) -> Response:
        username = str(payload.get("username", ""))
        password = str(payload.get("password", ""))
        origin = request.headers.get("origin", "")
        client_key = request.client.host if request.client else "unknown"
        try:
            session_token, record = service.login(username, password, origin, client_key)
        except LoginRateLimitedError as error:
            return _error_response(429, "login_rate_limited", str(error), True)
        except InvalidCredentialsError as error:
            return _error_response(401, "invalid_credentials", str(error), False)
        response = JSONResponse(
            status_code=200,
            content={
                "user_id": record.user_id,
                "csrf_token": record.csrf_token,
                "expires_at": record.expires_at.isoformat(),
            },
        )
        attributes = service.cookie_attributes()
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            httponly=bool(attributes.get("httponly", True)),
            samesite="strict",
            secure=bool(attributes.get("secure", False)),
            max_age=1800,
        )
        return response

    @router.get("/me")
    def auth_me(request: Request) -> Response:
        session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not session_token:
            return _error_response(401, "unauthenticated", "no session cookie present", False)
        try:
            principal = service.validate_session(session_token)
            scope = service.build_access_scope(session_token)
        except SessionExpiredError as error:
            return _error_response(401, "session_expired", str(error), False)
        permissions = list(scope.permissions) if hasattr(scope, "permissions") else []
        return JSONResponse(
            content={
                "user_id": principal.user_id,
                "tenant_id": principal.tenant_id,
                "role": str(principal.role),
                "permissions": permissions,
            }
        )

    @router.get("/csrf")
    def auth_csrf(request: Request) -> Response:
        session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
        try:
            record = service.session_record(session_token)
        except SessionExpiredError as error:
            return _error_response(401, "session_expired", str(error), False)
        return JSONResponse(
            content={"csrf_token": record.csrf_token, "header_name": CSRF_HEADER_NAME}
        )

    @router.post("/logout")
    def auth_logout(request: Request) -> Response:
        session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
        service.logout(session_token)
        response = JSONResponse(content={"status": "logged_out"})
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    return router
