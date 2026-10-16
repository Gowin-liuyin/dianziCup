"""Default application exposes both prefixes through the shared cookie-only factory."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings

PUBLIC_ROUTES = (
    ("GET", "/subscriptions"),
    ("POST", "/subscriptions"),
    ("GET", "/subscriptions/{subscription_id}"),
    ("PATCH", "/subscriptions/{subscription_id}"),
    ("POST", "/subscriptions/{subscription_id}/generate"),
    ("GET", "/subscriptions/{subscription_id}/recommendations"),
    ("POST", "/recommendations/{recommendation_id}/read"),
    ("GET", "/subscriptions/{subscription_id}/reports"),
    ("POST", "/reports"),
    ("GET", "/reports/{report_id}"),
    ("GET", "/reports/{report_id}/export"),
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture")
    )
    with TestClient(application) as opened:
        yield opened


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
@pytest.mark.parametrize("method,path", PUBLIC_ROUTES)
def test_default_recommendation_routes_authenticate_before_business(
    client: TestClient, prefix: str, method: str, path: str
) -> None:
    endpoint = path.format(
        subscription_id=str(uuid4()), report_id=str(uuid4()), recommendation_id=str(uuid4())
    )
    params = (
        {"subscription_id": str(uuid4())}
        if path.startswith("/reports/{") or path.endswith("/read")
        else None
    )
    payload: dict[str, object] = {}
    if method == "POST" and path == "/subscriptions":
        payload = {"spec": {"product_keys": ["PyPI:alpha"]}}
    elif method == "PATCH":
        payload = {"expected_version": 1, "enabled": False}
    elif method == "POST" and path == "/reports":
        payload = {
            "subscription_id": str(uuid4()),
            "generation_id": str(uuid4()),
            "frequency": "day",
        }
    response = client.request(
        method, prefix + endpoint, params=params, json=payload if method != "GET" else None
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"
    assert response.headers["content-type"].startswith("application/problem+json")


def test_default_openapi_exposes_only_canonical_recommendation_paths(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for method, path in PUBLIC_ROUTES:
        assert method.lower() in paths["/v1" + path]
        assert "/api/v1" + path not in paths
