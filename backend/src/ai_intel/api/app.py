"""最小 API 应用入口与健康检查路由。

职责: 装配 FastAPI 应用并暴露健康检查端点。健康端点必须如实反映依赖就绪状态,
不得在外部依赖未接入时谎报 ready。
"""

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from ai_intel.api.authentication import AuthenticationSessionService


def create_application(auth_service: AuthenticationSessionService | None = None) -> FastAPI:
    """构建 FastAPI 应用: 健康检查路由 + 可选认证路由(T40 前置最小修复)。"""
    application = FastAPI(title="ai-intel-backend", version="0.1.0")
    application.include_router(build_health_router())
    if auth_service is not None:
        from ai_intel.api.auth_routes import build_auth_router

        application.include_router(build_auth_router(auth_service))
    return application


def build_health_router() -> APIRouter:
    """返回存活/就绪检查路由, 便于应用装配与单测复用。"""
    router = APIRouter(prefix="/health")

    @router.get("/live")
    def health_live() -> dict[str, str]:
        """进程存活探针: 仅表示进程可响应, 不表示依赖可用。"""
        return {"status": "live"}

    @router.get("/ready")
    def health_ready() -> JSONResponse:
        """依赖就绪探针: 外部依赖未配置接入时如实返回 not_ready 与原因。"""
        readiness = {
            "status": "not_ready",
            "reason": (
                "external dependencies not configured (database/cache/search 由 T03/T05 接入)"
            ),
        }
        return JSONResponse(status_code=503, content=readiness)

    return router


app = create_application()
