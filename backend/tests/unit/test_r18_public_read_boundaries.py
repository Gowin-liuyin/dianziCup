"""Public query, cursor and stored-mode boundaries without external resources."""

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_intel.api.public_extension_reads import (
    InvalidPublicCursor,
    PublicReadUnavailable,
    classify_revision_mode,
    encode_page_cursor,
    page_position,
    validate_page_inputs,
)
from ai_intel.api.public_extension_routes import build_public_extension_router


@pytest.mark.parametrize("limit", [True, False, 0, 101, 1.0, "20"])
def test_page_limit_requires_bounded_integer(limit):
    with pytest.raises(ValueError):
        validate_page_inputs(None, limit, None)


@pytest.mark.parametrize("q", ["", " ", "a\0b", "x" * 4097, "\ud800"])
def test_search_invalid_input_is_rejected(q):
    with pytest.raises((ValueError, UnicodeError)):
        validate_page_inputs(q, 20, None)


def test_long_frozen_search_boundary_is_preserved():
    validate_page_inputs("x" * 4096, 100, None)


@pytest.mark.parametrize("cursor", ["", " ", "x" * 2049, "not+a+cursor"])
def test_cursor_invalid_shape_is_rejected(cursor):
    with pytest.raises(InvalidPublicCursor):
        page_position(cursor, "a" * 64)


def test_cursor_cannot_cross_changed_scope():
    value = encode_page_cursor(20, "a" * 64)
    assert page_position(value, "a" * 64) == 20
    with pytest.raises(InvalidPublicCursor):
        page_position(value, "b" * 64)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"version":1,"offset":1,"binding":"' + b"a" * 64 + b'","offset":2}',
        b'{"version":1,"offset":true,"binding":"' + b"a" * 64 + b'"}',
    ],
)
def test_noncanonical_duplicate_or_boolean_cursor_is_rejected(raw):
    value = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    with pytest.raises(InvalidPublicCursor):
        page_position(value, "a" * 64)


@pytest.mark.parametrize("metadata", [{}, None, {"data_mode": "fixture"}, {"data_mode": "unknown"}])
def test_live_deployment_cannot_relabel_unknown_or_fixture_sources(metadata):
    with pytest.raises(PublicReadUnavailable):
        classify_revision_mode(metadata, "live")


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/vulns?q=secret&tenant_id=private",
        "/api/v1/sources?limit=true",
        "/api/v1/sources?limit=2&limit=3",
        "/api/v1/vulns?q=",
        "/api/v1/vulns?limit=101",
        "/api/v1/vulns?cursor=",
        "/api/v1/vulns/secret",
        "/api/v1/tasks/secret",
    ],
)
def test_route_validation_does_not_echo_untrusted_query_or_path(path):
    application = FastAPI()
    application.include_router(
        build_public_extension_router(None, "fixture", source_polling_enabled=False),
        prefix="/api/v1",
    )
    with TestClient(application) as client:
        response = client.get(path)
    assert response.status_code == 422
    assert "secret" not in response.text
    assert "private" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_unconfigured_database_is_explicit_and_no_auth_is_unauthorized():
    application = FastAPI()
    application.include_router(
        build_public_extension_router(None, "fixture", source_polling_enabled=False),
        prefix="/api/v1",
    )
    with TestClient(application) as client:
        assert client.get("/api/v1/sources").status_code == 401
        client.cookies.set("ai_intel_session", "a" * 43)
        response = client.get("/api/v1/sources")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_configured"
