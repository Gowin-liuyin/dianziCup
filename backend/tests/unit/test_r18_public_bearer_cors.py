"""Configured browser origins can preflight the public Bearer API without exposing identity."""

import pytest
from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings


@pytest.mark.parametrize(
    ("origin", "expected_status"),
    [("http://localhost:5173", 200), ("https://untrusted.example", 400)],
)
def test_public_bearer_preflight_retains_exact_origin_policy(origin, expected_status):
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    with TestClient(create_application(settings=settings)) as client:
        response = client.options(
            "/api/v1/vulns",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.headers["access-control-allow-origin"] == origin
            assert "authorization" in response.headers["access-control-allow-headers"].lower()
        else:
            assert "access-control-allow-origin" not in response.headers
