"""The normal application exposes public reads with the existing authentication boundary."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings


@pytest.mark.parametrize(
    "path",
    ["/vulns", "/vulns/" + str(uuid4()), "/sources", "/tasks/" + str(uuid4())],
)
def test_default_public_read_rejects_anonymous_request(path: str) -> None:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture", _env_file=None)
    )
    with TestClient(application) as client:
        response = client.get("/api/v1" + path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.headers["Cache-Control"] == "no-store"


def test_default_public_openapi_keeps_source_collection_and_public_reads() -> None:
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture", _env_file=None)
    )
    with TestClient(application) as client:
        paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/api/v1/vulns",
        "/api/v1/vulns/{event_id}",
        "/api/v1/sources",
        "/api/v1/tasks/{task_id}",
    ):
        assert "get" in paths[path]
    assert "post" in paths["/v1/sources/{source_kind}/collect"]
