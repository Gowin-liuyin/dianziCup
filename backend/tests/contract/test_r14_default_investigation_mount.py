"""The default app exposes durable investigation boundaries without simulating completion."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
@pytest.mark.parametrize("suffix", ["", "/tool-runs"])
def test_default_investigation_read_requires_current_session(prefix: str, suffix: str) -> None:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture", _env_file=None)
    )
    with TestClient(application) as client:
        response = client.get(prefix + "/investigations/" + str(uuid4()) + suffix)
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_default_openapi_retains_assessment_and_investigation_routes() -> None:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture", _env_file=None)
    )
    with TestClient(application) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/v1/investigations"]
    assert "get" in paths["/v1/investigations/{job_id}/tool-runs"]
    assert "post" in paths["/v1/investigations/{job_id}/cancel"]
    assert "post" in paths["/v1/assessments"]
    assert "/api/v1/investigations" not in paths
