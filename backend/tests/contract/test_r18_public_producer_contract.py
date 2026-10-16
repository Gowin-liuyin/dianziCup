"""The public factory exposes precisely the frozen SDK's four read HTTP paths."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_intel.api.public_extension_routes import build_public_extension_router


def test_routes_match_four_frozen_sdk_get_paths_without_new_tools():
    router = build_public_extension_router(None, "fixture", source_polling_enabled=False)
    assert [(route.path, route.methods) for route in router.routes] == [
        ("/vulns", {"GET"}),
        ("/vulns/{event_id}", {"GET"}),
        ("/sources", {"GET"}),
        ("/tasks/{task_id}", {"GET"}),
    ]
    root = Path(__file__).resolve().parents[3]
    frozen = json.loads((root / "contracts/schemas/public_api_extensions_v1.json").read_text())
    assert set(frozen["$defs"]["VulnerabilityDetailPage"]["required"]) == {
        "vulnerability",
        "advisories",
        "next_cursor",
        "mapping_limits",
        "data_mode",
    }
    assert set(frozen["$defs"]["SourcePage"]["required"]) == {"items", "next_cursor", "data_mode"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/vulns",
        "/api/v1/vulns/00000000-0000-0000-0000-000000000001",
        "/api/v1/sources",
        "/api/v1/tasks/00000000-0000-0000-0000-000000000001",
    ],
)
def test_unconfigured_factory_preserves_rfc9457_problem_contract(path):
    application = FastAPI()
    application.include_router(
        build_public_extension_router(None, "fixture", source_polling_enabled=False),
        prefix="/api/v1",
    )
    with TestClient(application) as client:
        client.cookies.set("ai_intel_session", "a" * 43)
        response = client.get(path)
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 503 and body["error"]["code"] == "not_configured"
    assert body["trace_id"] == response.headers["x-request-id"]
    assert set(body) == {"type", "title", "status", "detail", "instance", "trace_id", "error"}
