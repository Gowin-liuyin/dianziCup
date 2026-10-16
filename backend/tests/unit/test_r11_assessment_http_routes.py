"""Explicit in-memory unit auth and service doubles verify only the HTTP boundary."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from tests.r11_assessment_http_fixtures import synthetic_receipt

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.assessment.http_contracts import AssessmentResponse
from ai_intel.assessment.http_routes import build_assessment_router
from ai_intel.assessment.rule_persistence import RulePersistenceError
from ai_intel.domain.access import CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.minio_store import ObjectStoreUnavailableError

ORIGIN = "http://testserver"


@pytest.fixture(scope="module")
def unit_authentication():
    service = AuthenticationSessionService(InMemoryUserDirectory(), (ORIGIN,), False)
    sessions = {}
    for label, role, tenant in [
        ("analyst", Role.ANALYST, "fixture-tenant"),
        ("viewer", Role.VIEWER, "fixture-tenant"),
        ("tenantless", Role.SYSTEM_ADMIN, None),
    ]:
        service.create_precreated_user(label, "synthetic-unit-only-password", tenant, role)
        sessions[label] = service.login(label, "synthetic-unit-only-password", ORIGIN, label)
    return service, sessions


@pytest.fixture()
def unit_client(monkeypatch, tmp_path, unit_authentication):
    authentication, sessions = unit_authentication
    receipt = synthetic_receipt()
    calls = []

    class FixtureAssessmentService:
        def __init__(self, engine, token, store):
            calls.append(("constructor", token))

        def prepare(self, *arguments):
            calls.append(("prepare", arguments))
            return receipt.prepared

        def commit(self, prepared):
            assert prepared == receipt.prepared
            calls.append(("commit", prepared.preparation_receipt_id))
            return receipt

        def read(self, identity):
            calls.append(("read", identity))
            return receipt

    monkeypatch.setattr(
        "ai_intel.assessment.http_routes.AssessmentService", FixtureAssessmentService
    )
    engine = create_engine("sqlite://")
    application = FastAPI()
    application.include_router(
        build_assessment_router(lambda: authentication, engine, ContentStore(tmp_path)),
        prefix="/v1",
    )
    with TestClient(application) as client:
        token, record = sessions["analyst"]
        client.cookies.set(SESSION_COOKIE_NAME, token)
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": record.csrf_token})
        yield client, receipt, calls, FixtureAssessmentService
    engine.dispose()


def body_for(receipt):
    return dict(
        asset_id=receipt.asset_id,
        asset_snapshot_id=receipt.asset_snapshot_id,
        rule_id=receipt.rule_id,
        rule_version=receipt.rule_version,
    )


def assert_problem(response, status, code):
    assert response.status_code == status
    assert response.headers["Content-Type"] == "application/problem+json"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["error"]["code"] == code
    assert "private-marker" not in response.text


def test_post_calls_prepare_then_commit_and_get_reads_without_private_preparation(unit_client):
    client, receipt, calls, _ = unit_client
    posted = client.post("/v1/assessments", json=body_for(receipt))
    assert posted.status_code == 200 and posted.headers["Cache-Control"] == "no-store"
    assert posted.json() == AssessmentResponse.from_receipt(receipt).model_dump(mode="json")
    assert [item[0] for item in calls] == ["constructor", "prepare", "commit"]
    assert calls[1][1] == (receipt.asset_id, receipt.asset_snapshot_id, receipt.rule_id, 1)
    read = client.get("/v1/assessments/" + receipt.assessment_id)
    assert read.status_code == 200 and read.json() == posted.json()
    assert calls[-1] == ("read", receipt.assessment_id)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"[]",
        b"{",
        b'{"rule_version":1,"rule_version":1}',
        b'{"tenant_id":"private-marker"}',
        b'{"rule_version":NaN}',
        b'{"rule_id":"\\ud800"}',
        b"[" * 1800 + b"]" * 1800,
    ],
)
def test_malformed_duplicate_or_non_object_json_is_rejected(unit_client, raw):
    client, _, calls, _ = unit_client
    assert_problem(client.post("/v1/assessments", content=raw), 422, "validation_error")
    assert not any(item[0] in {"prepare", "commit"} for item in calls)


@pytest.mark.parametrize("field", ["asset_id", "asset_snapshot_id", "rule_id", "rule_version"])
def test_missing_field_stops_before_service(unit_client, field):
    client, receipt, calls, _ = unit_client
    payload = body_for(receipt)
    del payload[field]
    assert_problem(client.post("/v1/assessments", json=payload), 422, "validation_error")
    assert not any(item[0] == "prepare" for item in calls)


@pytest.mark.parametrize(
    "field", ["tenant_id", "user_id", "role", "permissions", "prepared", "cutoff"]
)
def test_extra_identity_stops_before_service(unit_client, field):
    client, receipt, calls, _ = unit_client
    assert_problem(
        client.post("/v1/assessments", json=dict(body_for(receipt), **{field: "private-marker"})),
        422,
        "validation_error",
    )
    assert not any(item[0] == "prepare" for item in calls)


def test_exact_byte_limit_and_streamed_overflow(unit_client):
    client, receipt, calls, _ = unit_client
    raw = json.dumps(body_for(receipt)).encode()
    bounded = raw + b" " * (4096 - len(raw))
    assert client.post("/v1/assessments", content=bounded).status_code == 200
    calls.clear()
    assert_problem(
        client.post("/v1/assessments", content=iter([bounded, b" "])),
        413,
        "assessment_body_too_large",
    )
    assert not any(item[0] == "prepare" for item in calls)


def test_duplicate_key_in_otherwise_valid_request_never_reaches_prepare(unit_client):
    client, receipt, calls, _ = unit_client
    raw = json.dumps(body_for(receipt))
    duplicated = raw[:-1] + ', "rule_version": 1}'
    assert_problem(client.post("/v1/assessments", content=duplicated), 422, "validation_error")
    assert not any(item[0] == "prepare" for item in calls)


@pytest.mark.parametrize(
    "header,value",
    [
        ("Origin", "http://untrusted.invalid"),
        ("Origin", ""),
        ("X-CSRF-Token", ""),
        ("X-CSRF-Token", "private-marker"),
    ],
)
def test_origin_csrf_denial_precedes_body_and_service(unit_client, header, value):
    client, _, calls, _ = unit_client
    assert_problem(
        client.post("/v1/assessments", content=b"private-marker", headers={header: value}),
        403,
        "csrf_rejected",
    )
    assert calls == []


@pytest.mark.parametrize("actor", ["viewer", "tenantless"])
@pytest.mark.parametrize("method", ["post", "get"])
def test_read_asset_permission_and_tenant_are_required(
    unit_client, unit_authentication, actor, method
):
    client, receipt, calls, _ = unit_client
    _, sessions = unit_authentication
    token, record = sessions[actor]
    client.cookies.set(SESSION_COOKIE_NAME, token)
    client.headers["X-CSRF-Token"] = record.csrf_token
    response = (
        client.post("/v1/assessments", json=body_for(receipt))
        if method == "post"
        else client.get("/v1/assessments/" + receipt.assessment_id)
    )
    assert_problem(response, 403, "permission_denied")
    assert calls == []


@pytest.mark.parametrize("method", ["post", "get"])
def test_invalid_current_role_is_permission_denied(
    unit_client, unit_authentication, monkeypatch, method
):
    client, receipt, calls, _ = unit_client
    authentication, _ = unit_authentication

    def invalid_role(token):
        raise ValueError("private-marker invalid role")

    monkeypatch.setattr(authentication, "build_access_scope", invalid_role)
    response = (
        client.post("/v1/assessments", json=body_for(receipt))
        if method == "post"
        else client.get("/v1/assessments/" + receipt.assessment_id)
    )
    assert_problem(response, 403, "permission_denied")
    assert calls == []


@pytest.mark.parametrize(
    "error,status,code",
    [
        (CrossTenantAccessError("private-marker"), 404, "not_found"),
        (PermissionDeniedError("private-marker"), 403, "permission_denied"),
        (RulePersistenceError("private-marker"), 409, "assessment_inputs_invalid"),
        (ValueError("private-marker"), 409, "assessment_inputs_invalid"),
        (FileNotFoundError("private-marker"), 503, "assessment_evidence_unavailable"),
        (ObjectStoreUnavailableError("private-marker"), 503, "assessment_evidence_unavailable"),
        (
            OperationalError("private-marker", {}, Exception("private-marker")),
            503,
            "assessment_unavailable",
        ),
    ],
)
@pytest.mark.parametrize("operation", ["prepare", "commit", "read"])
def test_business_errors_are_fixed_and_cache_disabled(
    unit_client, monkeypatch, error, status, code, operation
):
    client, receipt, _, service = unit_client

    def rejected(*arguments):
        raise error

    monkeypatch.setattr(service, operation, rejected)
    response = (
        client.get("/v1/assessments/" + receipt.assessment_id)
        if operation == "read"
        else client.post("/v1/assessments", json=body_for(receipt))
    )
    assert_problem(response, status, code)


@pytest.mark.parametrize("configuration", ["authentication", "engine", "content_store"])
def test_missing_configuration_is_503_and_never_fixture_success(
    configuration, tmp_path, unit_authentication
):
    authentication, sessions = unit_authentication
    engine = create_engine("sqlite://")
    app = FastAPI()
    app.include_router(
        build_assessment_router(
            lambda: None if configuration == "authentication" else authentication,
            None if configuration == "engine" else engine,
            None if configuration == "content_store" else ContentStore(tmp_path),
        )
    )
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, sessions["analyst"][0])
        assert_problem(
            client.post("/assessments", content=b"private-marker"), 503, "assessment_unavailable"
        )
        assert_problem(
            client.get("/assessments/00000000-0000-0000-0000-000000000000"),
            503,
            "assessment_unavailable",
        )
        client.cookies.clear()
        assert_problem(
            client.post("/assessments", content=b"private-marker"), 401, "session_expired"
        )
    engine.dispose()


def test_get_uuid_and_query_boundary_and_openapi(unit_client):
    client, receipt, calls, _ = unit_client
    assert_problem(client.get("/v1/assessments/invalid-uuid"), 422, "validation_error")
    assert_problem(
        client.get("/v1/assessments/" + receipt.assessment_id + "?tenant_id=private-marker"),
        422,
        "validation_error",
    )
    assert_problem(
        client.post("/v1/assessments?tenant_id=private-marker", json=body_for(receipt)),
        422,
        "validation_error",
    )
    assert not any(item[0] in {"prepare", "read"} for item in calls)
    schema = client.get("/openapi.json").json()
    request = schema["paths"]["/v1/assessments"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert request["additionalProperties"] is False
    assert set(request["required"]) == {"asset_id", "asset_snapshot_id", "rule_id", "rule_version"}
    assert "prepared" not in schema["components"]["schemas"]["AssessmentResponse"]["properties"]
