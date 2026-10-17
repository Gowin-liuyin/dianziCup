"""Raw public ask wire boundaries reuse the frozen parser; no real models or DB are used."""

import json

import pytest
from test_public_ask_routes import PAYLOAD, assert_problem
from test_public_ask_routes import public_ask_case as public_ask_case

from ai_intel.api.public_write_adapters import MAX_PUBLIC_WRITE_BYTES


@pytest.mark.parametrize(
    "raw",
    [
        b'{"question":"fixture", "question":"duplicate", "mode":"library"}',
        b'{"question":"fixture", "mode":"library", "event_ids":[], "event_ids":[]}',
        b'{"question":NaN,"mode":"library"}',
        b"[]",
        b'{"question":"\xff", "mode":"library"}',
        b"{",
    ],
)
def test_raw_duplicate_non_json_or_invalid_utf8_is_rejected(public_ask_case, raw):
    headers = {**public_ask_case["key_headers"], "Content-Type": "application/json"}
    response = public_ask_case["client"].post("/ask", content=raw, headers=headers)
    assert_problem(response, 422, "validation_error")
    assert public_ask_case["state"]["auth_calls"] == []


def test_deeply_nested_json_is_a_validation_error_before_authentication(public_ask_case):
    raw = b'{"question":' + b"[" * 20000 + b"0" + b"]" * 20000 + b',"mode":"library"}'
    assert len(raw) < MAX_PUBLIC_WRITE_BYTES
    response = public_ask_case["client"].post(
        "/ask",
        content=raw,
        headers={**public_ask_case["key_headers"], "Content-Type": "application/json"},
    )
    assert_problem(response, 422, "validation_error")
    assert public_ask_case["state"]["auth_calls"] == []


@pytest.mark.parametrize(
    "updates",
    [
        {"tenant_id": "foreign-tenant"},
        {"user_id": "foreign-owner"},
        {"role": "system_admin"},
        {"scopes": ["read:asset"]},
        {"actor_reference": {"tenant_id": "foreign-tenant"}},
        {"data_mode": "live"},
        {"event_ids": ["00000000000000000000000000000001"]},
        {"conversation_id": None},
        {"known_at": None},
        {"valid_at": "2026-10-17 00:00:00+00:00"},
        {"known_at": "2026-10-17T00:00:00"},
        {"question": " "},
    ],
)
def test_strict_public_dto_rejects_authority_and_non_public_spellings(public_ask_case, updates):
    response = public_ask_case["client"].post(
        "/ask", json={**PAYLOAD, **updates}, headers=public_ask_case["key_headers"]
    )
    assert_problem(response, 422, "validation_error")
    assert "foreign-" not in response.text and "system_admin" not in response.text
    assert public_ask_case["state"]["service_calls"] == []


@pytest.mark.parametrize("key", [None, "", "two words", "x" * 201])
def test_missing_or_invalid_idempotency_key_stops_before_auth_and_service(public_ask_case, key):
    headers = dict(public_ask_case["key_headers"])
    if key is None:
        headers.pop("Idempotency-Key")
    else:
        headers["Idempotency-Key"] = key
    assert_problem(
        public_ask_case["client"].post("/ask", json=PAYLOAD, headers=headers),
        422,
        "validation_error",
    )
    assert public_ask_case["state"]["auth_calls"] == []


def test_duplicate_idempotency_key_is_rejected_before_service(public_ask_case):
    headers = [*public_ask_case["key_headers"].items(), ("Idempotency-Key", "other-key")]
    assert_problem(
        public_ask_case["client"].post("/ask", json=PAYLOAD, headers=headers),
        422,
        "validation_error",
    )
    assert public_ask_case["state"]["service_calls"] == []


@pytest.mark.parametrize("extra_bytes", [0, 1])
def test_one_mib_raw_body_limit_includes_whitespace(public_ask_case, extra_bytes):
    body = json.dumps(PAYLOAD).encode()
    raw = body + b" " * (MAX_PUBLIC_WRITE_BYTES - len(body) + extra_bytes)
    response = public_ask_case["client"].post(
        "/ask",
        content=raw,
        headers={**public_ask_case["key_headers"], "Content-Type": "application/json"},
    )
    if extra_bytes:
        assert_problem(response, 422, "validation_error")
        assert public_ask_case["state"]["service_calls"] == []
    else:
        assert response.status_code == 200


@pytest.mark.parametrize("content_type", [None, "text/plain", "application/octet-stream"])
def test_non_json_media_type_is_rejected(public_ask_case, content_type):
    headers = dict(public_ask_case["key_headers"])
    if content_type:
        headers["Content-Type"] = content_type
    response = public_ask_case["client"].post("/ask", content=json.dumps(PAYLOAD), headers=headers)
    assert_problem(response, 422, "validation_error")


def test_unsupported_query_parameters_are_explicit(public_ask_case):
    assert_problem(
        public_ask_case["client"].post(
            "/ask?tenant_id=foreign", json=PAYLOAD, headers=public_ask_case["key_headers"]
        ),
        422,
        "validation_error",
    )
    assert public_ask_case["state"]["auth_calls"] == []
