"""超深合成 fixture 经共享边界进入既有模型、读取和请求错误合同。"""

import json
from dataclasses import asdict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy import create_engine

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.assets.aggregate_observations import decode_aggregate_response
from ai_intel.assets.inventory_routes import build_inventory_router
from ai_intel.domain.access import Role
from ai_intel.infrastructure.models.clients import ModelContractError, validate_structured_output
from ai_intel.infrastructure.models.generation import (
    GenerationClient,
    GenerationFailure,
    GenerationRequest,
)
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.catalog_pages import select_avid_blob
from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.repository import RepositoryFetchError
from ai_intel.investigation.graph_contracts import parse_investigation_request
from ai_intel.investigation.tool_contracts import parse_tool_call

FIXTURE_MARKER = "fixture-tokenlike-contract-secret"
DEEP_JSON = '{"marker":"' + FIXTURE_MARKER + '","nested":' + "[" * 20000 + "0"
DEEP_JSON += "]" * 20000 + "}"


def test_model_validator_keeps_one_repair_and_explicit_failure() -> None:
    with pytest.raises(ModelContractError, match="no repair available") as rejected:
        validate_structured_output(DEEP_JSON, ("ok",), "fixture-model", "fixture-prompt", 10)
    assert FIXTURE_MARKER not in str(rejected.value)
    calls: list[str] = []

    def repair(raw: str) -> str:
        calls.append(raw)
        return '{"ok":true}'

    repaired = validate_structured_output(
        DEEP_JSON, ("ok",), "fixture-model", "fixture-prompt", 10, repair
    )
    assert calls == [DEEP_JSON]
    assert repaired.structured_payload == {"ok": True}
    assert repaired.format_repair_used is True
    with pytest.raises(ModelContractError, match="invalid even after single repair"):
        validate_structured_output(
            "invalid fixture JSON",
            ("ok",),
            "fixture-model",
            "fixture-prompt",
            10,
            lambda _: DEEP_JSON,
        )


class FixtureAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


@pytest.mark.parametrize("boundary", ["wire", "output"])
def test_generation_errors_preserve_wire_and_output_classification(monkeypatch, boundary) -> None:
    client = GenerationClient("deepseek_openai", "deepseek-flash", SecretStr("fixture-key-12345"))
    payload = {
        "id": "fixture-call",
        "object": "chat.completion",
        "model": "deepseek-flash",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": DEEP_JSON},
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }
    body = DEEP_JSON.encode() if boundary == "wire" else json.dumps(payload).encode()
    calls: list[bytes] = []

    def post(url, request_body, *, protocol_headers, deadline):
        calls.append(request_body)
        return FetchResult(url, 200, "application/json", body)

    monkeypatch.setattr(client._gateway, "post_json", post)
    request = GenerationRequest(
        system_text="Fixture schema only.",
        question="Fixture question.",
        evidence_texts=(),
        prompt_version="fixture-prompt",
        schema_version="fixture-schema",
        model_version="deepseek-flash",
        max_output_tokens=100,
        allow_format_repair=False,
    )
    expected = "model_wire_invalid" if boundary == "wire" else "model_format_invalid"
    with pytest.raises(GenerationFailure) as rejected:
        client.generate(request, FixtureAnswer)
    assert rejected.value.code == expected
    assert len(rejected.value.attempts) == len(calls) == 1
    assert rejected.value.attempts[0].outcome == expected
    assert FIXTURE_MARKER not in repr(asdict(rejected.value.attempts[0]))


@pytest.mark.parametrize("reader", ["aggregate", "catalog", "avid", "releases"])
def test_readers_reject_depth_without_empty_success(reader: str) -> None:
    with pytest.raises((ValueError, RepositoryFetchError)) as rejected:
        if reader == "aggregate":
            decode_aggregate_response(
                FetchResult("https://fixture.invalid", 200, "application/json", DEEP_JSON.encode())
            )
        elif reader == "catalog":
            select_avid_blob(DEEP_JSON.encode(), {})
        elif reader == "avid":
            normalize_avid_vulnerability(DEEP_JSON.encode())
        else:
            parse_github_releases(("[" * 20000 + "0" + "]" * 20000).encode())
    assert FIXTURE_MARKER not in str(rejected.value)
    assert not isinstance(rejected.value, RecursionError)


@pytest.mark.parametrize("parser", ["investigation", "tool"])
def test_request_parsers_raise_the_existing_value_error_contract(parser: str) -> None:
    with pytest.raises(ValueError, match=r"^JSON structure outside limit$") as rejected:
        if parser == "investigation":
            parse_investigation_request(DEEP_JSON.encode())
        else:
            parse_tool_call(DEEP_JSON.encode(), 65536)
    assert FIXTURE_MARKER not in str(rejected.value)


def test_inventory_http_deep_json_returns_trusted_422_without_database_io() -> None:
    origin = "http://testserver"
    authentication = AuthenticationSessionService(InMemoryUserDirectory(), (origin,), False)
    authentication.create_precreated_user(
        "fixture-admin", "fixture-password-only", "fixture-tenant", Role.TENANT_ADMIN
    )
    token, session = authentication.login(
        "fixture-admin", "fixture-password-only", origin, "fixture-login"
    )
    engine = create_engine("sqlite://")
    application = FastAPI()
    application.include_router(build_inventory_router(lambda: authentication, engine), prefix="/v1")
    try:
        with TestClient(application) as client:
            unauthenticated = client.post("/v1/asset-snapshots", content=DEEP_JSON)
            assert unauthenticated.status_code == 401
            client.cookies.set(SESSION_COOKIE_NAME, token)
            response = client.post(
                "/v1/asset-snapshots",
                content=DEEP_JSON,
                headers={
                    "Origin": origin,
                    "X-CSRF-Token": session.csrf_token,
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 422
            assert response.headers["content-type"] == "application/problem+json"
            assert response.json()["error"]["code"] == "validation_error"
            assert FIXTURE_MARKER not in response.text
            assert "RecursionError" not in response.text
    finally:
        engine.dispose()
