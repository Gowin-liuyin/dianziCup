"""认证HTTP边界：严格输入、Cookie会话及绑定CSRF，身份由服务端获取。"""

from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.api.authentication import (
    SESSION_TTL_SECONDS,
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    LoginRateLimitedError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.infrastructure.settings import ApplicationSettings

SESSION_COOKIE_NAME = "ai_intel_session"
CSRF_HEADER_NAME = "X-CSRF-Token"


class LoginRequest(BaseModel):
    """密码只以SecretStr承载；额外的租户或权限声明一律拒绝。"""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=1024)


def build_auth_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    settings: ApplicationSettings,
) -> APIRouter:
    """始终注册认证端点；真实服务未配置时明确503，不消失或回退fixture。"""
    router = APIRouter(prefix="/auth")

    @router.post("/login")
    def auth_login(request: Request, payload: LoginRequest) -> Response:
        service = service_provider()
        if service is None:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is not configured",
                True,
            )
        origin = request.headers.get("origin")
        if origin is None:
            return problem_response(request, 403, "csrf_rejected", "origin is required")
        client_key = request.client.host if request.client else "unknown"
        try:
            session_token, record = service.login(
                payload.username, payload.password.get_secret_value(), origin, client_key
            )
        except CsrfRejectionError:
            return problem_response(request, 403, "csrf_rejected", "origin not allowed")
        except LoginRateLimitedError:
            return problem_response(
                request, 429, "login_rate_limited", "too many login attempts", True
            )
        except InvalidCredentialsError:
            return problem_response(request, 401, "invalid_credentials", "invalid credentials")
        except SQLAlchemyError:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is unavailable",
                True,
            )
        response = JSONResponse(
            content={
                "user_id": record.user_id,
                "csrf_token": record.csrf_token,
                "expires_at": record.expires_at.isoformat(),
            }
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            httponly=True,
            samesite="strict",
            secure=bool(service.cookie_attributes()["secure"]),
            max_age=SESSION_TTL_SECONDS,
            path="/",
        )
        return response

    @router.get("/me")
    def auth_me(request: Request) -> Response:
        session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not session_token:
            return problem_response(request, 401, "unauthenticated", "no session cookie present")
        service = service_provider()
        if service is None:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is not configured",
                True,
            )
        try:
            principal = service.validate_session(session_token)
            scope = service.build_access_scope(session_token)
        except (SessionExpiredError, InvalidCredentialsError):
            return problem_response(request, 401, "session_expired", "session is not valid")
        except SQLAlchemyError:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is unavailable",
                True,
            )
        return JSONResponse(
            content={
                "user_id": principal.user_id,
                "tenant_id": principal.tenant_id,
                "role": principal.role.value,
                "permissions": sorted(scope.permissions),
                "permission_version": scope.permission_version,
                "data_mode": settings.data_mode,
                "app_env": settings.app_env,
                "platform_version": "0.1.0",
            }
        )

    @router.get("/csrf")
    def auth_csrf(request: Request) -> Response:
        service = service_provider()
        if service is None:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is not configured",
                True,
            )
        try:
            record = service.session_record(request.cookies.get(SESSION_COOKIE_NAME, ""))
        except (SessionExpiredError, InvalidCredentialsError):
            return problem_response(request, 401, "session_expired", "session is not valid")
        except SQLAlchemyError:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is unavailable",
                True,
            )
        return JSONResponse(
            content={"csrf_token": record.csrf_token, "header_name": CSRF_HEADER_NAME}
        )

    @router.post("/logout")
    def auth_logout(request: Request) -> Response:
        service = service_provider()
        if service is None:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is not configured",
                True,
            )
        session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
        try:
            service.validate_write_request(
                session_token,
                request.headers.get(CSRF_HEADER_NAME, ""),
                request.headers.get("origin"),
            )
            service.logout(session_token)
        except CsrfRejectionError:
            return problem_response(
                request, 403, "csrf_rejected", "csrf token and allowed origin are required"
            )
        except (SessionExpiredError, InvalidCredentialsError):
            return problem_response(request, 401, "session_expired", "session is not valid")
        except SQLAlchemyError:
            return problem_response(
                request,
                503,
                "authentication_unavailable",
                "authentication database is unavailable",
                True,
            )
        response = JSONResponse(content={"status": "logged_out"})
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="strict",
            secure=bool(service.cookie_attributes()["secure"]),
        )
        return response

    return router
