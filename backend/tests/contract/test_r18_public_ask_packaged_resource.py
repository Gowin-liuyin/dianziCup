"""The package resource must preserve the original frozen public request definition."""

import json
from importlib.resources import files
from pathlib import Path

from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings


def test_packaged_ask_resource_matches_frozen_request_definition():
    contract = (
        Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_extensions_v1.json"
    )
    expected = json.loads(contract.read_text(encoding="utf-8"))["$defs"]["AskRequest"]
    actual = json.loads(
        files("ai_intel.api").joinpath("schemas/public_ask_request_v1.json").read_text("utf-8")
    )
    assert actual == expected


def test_default_ask_openapi_reads_the_package_resource():
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture")
    )
    operation = application.openapi()["paths"]["/api/v1/ask"]["post"]
    actual = json.loads(
        files("ai_intel.api").joinpath("schemas/public_ask_request_v1.json").read_text("utf-8")
    )
    assert operation["requestBody"]["content"]["application/json"]["schema"] == actual
    with TestClient(application) as client:
        response = client.post("/api/v1/ask", json={"question": "fixture", "mode": "library"})
        assert response.status_code == 401
