"""Explicit offline HTTP boundary checks; real PG behavior is tested separately."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_intel.api.recommendation_routes import MAX_REQUEST_BYTES, build_recommendation_router
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.recommendations.service import RecommendationService


@pytest.fixture
def boundary_client():
    app = FastAPI()
    app.include_router(
        build_recommendation_router(lambda: None, None, None, data_mode="fixture"), prefix="/v1"
    )
    return TestClient(app)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"spec":{"product_keys":["x"],"enabled":true,"enabled":false}}',
        b'{"spec":{"product_keys":["x"]},"spec":{"product_keys":["y"]}}',
        b'{"spec":{"product_keys":["x"],"minimum_priority":NaN}}',
        b'{"spec":{"product_keys":["\\ud800"]}}',
        b'{"spec":{"product_keys":["x"]},"tenant_id":"other"}',
        b"[]",
        b"{",
        b"\xff",
        b" " * (MAX_REQUEST_BYTES + 1),
    ],
    ids=[
        "nested_duplicate",
        "root_duplicate",
        "nonfinite",
        "surrogate",
        "body_tenant",
        "array",
        "malformed",
        "invalid_utf8",
        "body_budget",
    ],
)
def test_strict_json_never_reaches_business_or_echoes_payload(boundary_client, raw):
    response = boundary_client.post(
        "/v1/subscriptions", content=raw, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"] == {}
    assert "other" not in response.text and "NaN" not in response.text


@pytest.mark.parametrize(
    "query",
    [
        "limit=true",
        "limit=0",
        "limit=-1",
        "limit=101",
        "limit=20&limit=1",
        "tenant_id=other",
        "cursor=bad",
        "cursor=true",
    ],
)
def test_strict_list_query_is_not_an_authorization_channel(boundary_client, query):
    assert boundary_client.get("/v1/subscriptions?" + query).status_code == 400


def test_cookie_but_unconfigured_service_is_explicit_503(boundary_client):
    boundary_client.cookies.set("ai_intel_session", "fixture-invalid-cookie")
    response = boundary_client.get("/v1/subscriptions")
    assert response.status_code == 503 and response.json()["error"]["code"] == "not_configured"
    assert "fixture-invalid-cookie" not in response.text


def test_request_bound_session_is_per_request_and_expires(tmp_path):
    engine = create_engine("sqlite://")
    service = RecommendationService(
        engine, "fixture-no-pg", ContentStore(tmp_path), data_mode="fixture"
    )
    with Session(engine) as session, session.begin():
        with service.in_transaction(session) as bound:
            with bound._transaction() as actual:
                assert actual is session
            with ThreadPoolExecutor(max_workers=1) as workers:

                def wrong_thread():
                    with pytest.raises(ValueError, match="expired"), bound._transaction():
                        pytest.fail("cross-thread binding accepted")

                workers.submit(wrong_thread).result()
            assert session.in_transaction()
        with pytest.raises(ValueError, match="expired"), bound._transaction():
            pytest.fail("expired binding accepted")
    with (
        Session(engine) as session,
        pytest.raises(ValueError, match="required"),
        service.in_transaction(session),
    ):
        pytest.fail("no active transaction accepted")
    engine.dispose()
