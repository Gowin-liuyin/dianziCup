"""The default application uses the actual assessment boundary under both API prefixes."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_default_assessment_routes_reject_anonymous_requests(prefix: str, method: str) -> None:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture", _env_file=None)
    )
    path = prefix + "/assessments"
    if method == "GET":
        path += "/" + str(uuid4())
    payload = {
        "asset_id": str(uuid4()),
        "asset_snapshot_id": str(uuid4()),
        "rule_id": "fixture-rule",
        "rule_version": 1,
    }
    with TestClient(application) as client:
        response = client.request(method, path, json=payload if method == "POST" else None)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"


def test_assessment_openapi_uses_canonical_prefix_and_retains_recommendations() -> None:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture", _env_file=None)
    )
    with TestClient(application) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/v1/assessments"]
    assert "get" in paths["/v1/assessments/{assessment_id}"]
    assert "/api/v1/assessments" not in paths
    assert "/api/v1/assessments/{assessment_id}" not in paths
    assert "post" in paths["/v1/subscriptions"]
    assert "post" in paths["/v1/questions"]
