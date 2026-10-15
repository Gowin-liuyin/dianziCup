"""未配置资源和伪造范围不能触发图查询，固定错误不回显内部原因。"""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.graph_routes import build_graph_router


def test_graph_requires_cookie_and_dependency_instead_of_fixture_fallback():
    app = FastAPI()
    app.include_router(build_graph_router(lambda: None, None), prefix="/v1")
    with TestClient(app) as client:
        path = f"/v1/events/{uuid4()}/graph"
        assert client.get(path).status_code == 401
        client.cookies.set(SESSION_COOKIE_NAME, "fixture-invalid-cookie")
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "graph_unavailable"
        assert "nodes" not in response.json()
        assert client.get(path, params={"scope": "public"}).status_code == 422


def test_graph_provider_failure_uses_fixed_problem_without_secret():
    def unavailable_provider():
        raise SQLAlchemyError("fixture-internal-provider-detail")

    app = FastAPI()
    app.include_router(build_graph_router(unavailable_provider, None), prefix="/v1")
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "fixture-invalid-cookie")
        response = client.get(f"/v1/events/{uuid4()}/graph")
        assert response.status_code == 503
        assert "fixture-internal-provider-detail" not in response.text
