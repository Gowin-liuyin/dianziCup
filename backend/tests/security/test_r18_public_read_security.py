"""Credential ambiguity and reflection protection at the added public read boundary."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_intel.api.public_extension_routes import build_public_extension_router


@pytest.fixture()
def public_client():
    application = FastAPI()
    application.include_router(
        build_public_extension_router(None, "fixture", source_polling_enabled=False),
        prefix="/api/v1",
    )
    with TestClient(application) as client:
        yield client


def test_cookie_and_bearer_cannot_select_different_identities(public_client):
    public_client.cookies.set("ai_intel_session", "synthetic-cookie-secret")
    response = public_client.get(
        "/api/v1/sources",
        headers={"Authorization": "Bearer synthetic-bearer-secret"},
    )
    assert response.status_code == 401
    assert "synthetic" not in response.text


def test_duplicate_authorization_headers_fail_closed(public_client):
    response = public_client.get(
        "/api/v1/sources",
        headers=[
            ("Authorization", "Bearer synthetic-first-secret"),
            ("Authorization", "Bearer synthetic-second-secret"),
        ],
    )
    assert response.status_code == 401
    assert "synthetic" not in response.text


def test_query_credentials_are_rejected_without_reflection(public_client):
    response = public_client.get("/api/v1/sources?access_token=synthetic-query-secret")
    assert response.status_code == 422
    assert "synthetic" not in response.text


@pytest.mark.parametrize("path", ["/api/v1/sources", "/api/v1/vulns"])
def test_read_factory_does_not_accept_write_verbs(public_client, path):
    response = public_client.post(path, json={"tenant_id": "synthetic-spoofed-tenant"})
    assert response.status_code == 405
    assert "synthetic" not in response.text
