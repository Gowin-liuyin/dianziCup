"""默认真实依赖装配；导入无网络，健康请求执行有界的实际探测。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from alembic.script import ScriptDirectory
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from ai_intel.api.auth_routes import build_auth_router
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    DatabaseUserDirectory,
    cookie_secure_for_environment,
)
from ai_intel.api.problems import problem_response
from ai_intel.infrastructure.database import MIGRATIONS_DIR, build_engine
from ai_intel.infrastructure.settings import ApplicationSettings, load_application_settings


def create_application(
    auth_service: AuthenticationSessionService | None = None,
    *,
    settings: ApplicationSettings | None = None,
) -> FastAPI:
    """配置真实PG目录，始终装认证；显式注入服务仅用于隔离测试。"""
    configuration = settings or load_application_settings()
    engine = build_engine(configuration) if configuration.database_url else None
    cache = None
    if configuration.redis_url:
        cache = Redis.from_url(
            configuration.redis_url.get_secret_value(),
            socket_connect_timeout=configuration.dependency_timeout_seconds,
            socket_timeout=configuration.dependency_timeout_seconds,
        )
    service = auth_service
    if service is None and engine is not None:
        service = AuthenticationSessionService(
            DatabaseUserDirectory(engine),
            configuration.allowed_origins,
            cookie_secure_for_environment(configuration.app_env),
        )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """进程只拥有自身连接池；不自动迁移或修改已有事实。"""
        try:
            yield
        finally:
            if cache is not None:
                cache.close()
            if engine is not None:
                engine.dispose()

    application = FastAPI(title="ai-intel-backend", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(configuration.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        """错误不回显Pydantic输入，身份伪造审计仅记录固定字段名。"""
        identity_fields = {"tenant_id", "user_id", "role", "permissions"}
        submitted_keys = {
            str(location)
            for detail in error.errors()
            for location in detail.get("loc", ())
            if location in identity_fields
        }
        if service is not None and submitted_keys:
            service.record_identity_spoof_attempt(dict.fromkeys(submitted_keys, ""))
        return problem_response(request, 422, "validation_error", "request schema invalid")

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        """路由错误遵循同一问题合同，保留Allow但不回显任意异常文本。"""
        code, detail = {
            404: ("not_found", "requested resource is not available"),
            405: ("method_not_allowed", "request method is not allowed"),
        }.get(error.status_code, ("http_error", "request could not be completed"))
        response = problem_response(request, error.status_code, code, detail)
        if error.headers and "Allow" in error.headers:
            response.headers["Allow"] = error.headers["Allow"]
        return response

    auth_router = build_auth_router(lambda: service, configuration)
    health_router = build_health_router(configuration, engine, cache)
    application.include_router(auth_router, prefix="/v1")
    application.include_router(health_router, prefix="/v1")
    application.include_router(auth_router, include_in_schema=False)
    application.include_router(health_router, include_in_schema=False)
    return application


def build_health_router(
    settings: ApplicationSettings, engine: Engine | None, cache: Redis | None
) -> APIRouter:
    """配置不等于就绪；PG迁移、Redis及已配置搜索均实际探测。"""
    router = APIRouter(prefix="/health")

    @router.get("/live")
    def health_live() -> dict[str, str]:
        return {"status": "live"}

    @router.get("/ready")
    def health_ready() -> JSONResponse:
        dependencies: dict[str, dict[str, str]] = {}
        dependencies["database"] = {"state": "not_configured"}
        if engine is not None:
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                    installed = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one_or_none()
                expected = ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()
                dependencies["database"] = {
                    "state": "ready" if installed == expected else "migration_required"
                }
            except SQLAlchemyError:
                dependencies["database"] = {
                    "state": "unavailable",
                    "reason": "database connection or schema unavailable",
                }
        dependencies["cache"] = {"state": "not_configured"}
        if cache is not None:
            try:
                dependencies["cache"] = {"state": "ready" if cache.ping() else "unavailable"}
            except RedisError:
                dependencies["cache"] = {
                    "state": "unavailable",
                    "reason": "cache connection unavailable",
                }
        dependencies["search"] = {"state": "not_configured"}
        if settings.opensearch_url:
            try:
                with httpx.Client(
                    timeout=settings.dependency_timeout_seconds, trust_env=False
                ) as client:
                    response = client.get(settings.opensearch_url.rstrip("/") + "/_cluster/health")
                    response.raise_for_status()
                    search = response.json()
                dependencies["search"] = {
                    "state": "ready"
                    if (
                        isinstance(search, dict)
                        and isinstance(search.get("status"), str)
                        and search["status"] in {"yellow", "green"}
                    )
                    else "unavailable"
                }
            except (httpx.HTTPError, ValueError):
                dependencies["search"] = {
                    "state": "unavailable",
                    "reason": "search connection unavailable",
                }
        core_ready = all(dependencies[name]["state"] == "ready" for name in ("database", "cache"))
        ready = core_ready and dependencies["search"]["state"] == "ready"
        if ready:
            status = "ready"
        elif core_ready:
            status = "degraded"
        else:
            status = "not_ready"
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": status,
                "reason": "all core dependencies available"
                if ready
                else "required dependencies unavailable or search degraded",
                "dependencies": dependencies,
                "data_mode": settings.data_mode,
            },
        )

    return router


app = create_application()
