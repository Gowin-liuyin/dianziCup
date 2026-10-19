"""Synthetic transport tests assert calls, failure boundaries and public semantics."""

from __future__ import annotations

import json

import httpx
import pytest
from ai_intel_client.client import (
    MAX_RESPONSE_BYTES,
    MAX_SYNCHRONOUS_REQUEST_BYTES,
    ClientConfigurationError,
    ClientInputError,
    DianziApiError,
    DianziClient,
    DianziTransportError,
    ResponseContractError,
    validate_json_bytes,
)
from ai_intel_client.models import AskRequest, QAAnswer, StackCheckRequest, TaskHandle
from pydantic import SecretStr

SYNTHETIC_KEY = "synthetic-test-key-with-no-provider-access"
ID = "00000000-0000-4000-8000-000000000001"
ANSWER = {
    "kind": "completed",
    "answer_id": ID,
    "answer_text": "synthetic unknown",
    "claims": [],
    "citations": [],
    "limitations": ["fixture has no evidence"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}
TASK = {
    "kind": "task",
    "task_id": ID,
    "status": "queued",
    "poll_uri": "/api/v1/tasks/" + ID,
    "created_at": "2026-10-16T00:00:00Z",
}
QUESTION = AskRequest(question="synthetic question", mode="library")


def problem(status: int) -> dict[str, object]:
    return {
        "type": "urn:ai-intel:problem:not_found",
        "title": "not_found",
        "status": status,
        "detail": "SYNTHETIC_PRIVATE_DETAIL_MUST_NOT_BE_LOGGED",
        "instance": "/api/v1/ask",
        "trace_id": ID,
        "error": {
            "code": "not_found",
            "message": "SYNTHETIC_PRIVATE_MESSAGE",
            "retryable": False,
            "details": {},
        },
    }


def test_ask_uses_fixed_path_bearer_and_operation_key_without_cookie() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=ANSWER)

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(SYNTHETIC_KEY), transport=httpx.MockTransport(handler)
    ) as client:
        result = client.ask(QUESTION, idempotency_key="synthetic-operation-key")
        assert isinstance(result, QAAnswer)
        assert result.data_mode == "fixture"
        assert SYNTHETIC_KEY not in repr(client)
    assert len(calls) == 1
    request = calls[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/ask"
    assert request.headers["authorization"] == "Bearer " + SYNTHETIC_KEY
    assert request.headers["idempotency-key"] == "synthetic-operation-key"
    assert "cookie" not in request.headers
    assert request.headers["accept-encoding"] == "identity"
    assert json.loads(request.content) == {"question": "synthetic question", "mode": "library"}


def test_async_handle_remains_async_and_has_no_fabricated_answer() -> None:
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(202, json=TASK)),
    ) as client:
        result = client.ask(QUESTION)
    assert isinstance(result, TaskHandle)
    assert not hasattr(result, "answer_text")
    assert result.task_id.hex


@pytest.mark.parametrize("status, value", [(200, TASK), (202, ANSWER)])
def test_http_status_must_match_completed_or_async_kind(
    status: int, value: dict[str, object]
) -> None:
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(status, json=value)),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.ask(QUESTION)


@pytest.mark.parametrize("status", [401, 403, 404, 409, 422, 429, 503])
def test_problem_status_and_error_metadata_preserved_without_server_text(status: int) -> None:
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    status,
                    json=problem(status),
                    headers={"Content-Type": "application/problem+json"},
                )
            ),
        ) as client,
        pytest.raises(DianziApiError) as caught,
    ):
        client.ask(QUESTION)
    assert caught.value.status == status
    assert caught.value.code == "not_found"
    assert caught.value.trace_id == ID
    assert not caught.value.retryable
    assert "SYNTHETIC_PRIVATE" not in str(caught.value)
    assert SYNTHETIC_KEY not in repr(caught.value)


def test_network_failure_is_not_retried_and_may_have_executed() -> None:
    calls = 0

    def failing(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(failing),
        ) as client,
        pytest.raises(DianziTransportError) as caught,
    ):
        client.ask(QUESTION, idempotency_key="recover-this-operation")
    assert calls == 1
    assert caught.value.may_have_executed
    assert caught.value.idempotency_key == "recover-this-operation"
    assert SYNTHETIC_KEY not in str(caught.value)


def test_redirect_is_not_followed_or_given_credentials_at_second_origin() -> None:
    calls: list[str] = []

    def redirected(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://example.org/collect-key"})

    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(redirected),
        ) as client,
        pytest.raises(DianziApiError) as caught,
    ):
        client.ask(QUESTION)
    assert caught.value.status == 307
    assert calls == ["http://127.0.0.1:12345/api/v1/ask"]


@pytest.mark.parametrize(
    "base",
    [
        "http://example.org",
        "https://user:pass@example.org",
        "https://example.org?key=synthetic",
        "https://example.org/#fragment",
        "https://example.org/path",
        "http://127.0.0.1:0",
    ],
)
def test_configuration_rejects_insecure_or_ambiguous_origins(base: str) -> None:
    with pytest.raises(ClientConfigurationError):
        DianziClient(base, SecretStr(SYNTHETIC_KEY))


@pytest.mark.parametrize("key", ["", "short", SYNTHETIC_KEY + "\r\nX-Injected: value", "=" * 5000])
def test_credential_header_boundary(key: str) -> None:
    with pytest.raises(ClientConfigurationError):
        DianziClient("http://127.0.0.1:12345", SecretStr(key))


@pytest.mark.parametrize("key", ["", "\n", "x" * 201])
def test_invalid_operation_key_is_rejected_before_transport(key: str) -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be used")

    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(forbidden),
        ) as client,
        pytest.raises(ClientInputError),
    ):
        client.ask(QUESTION, idempotency_key=key)


@pytest.mark.parametrize(
    "content",
    [
        b'{"kind":"completed","kind":"task"}',
        b'{"number":NaN}',
        b"not JSON",
        b'{"kind":"completed","secret":"SYNTHETIC_PRIVATE"}',
    ],
)
def test_invalid_duplicate_nonfinite_or_uncontracted_json_is_rejected(content: bytes) -> None:
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, content=content, headers={"Content-Type": "application/json"}
                )
            ),
        ) as client,
        pytest.raises(ResponseContractError) as caught,
    ):
        client.ask(QUESTION)
    assert "SYNTHETIC_PRIVATE" not in str(caught.value)


def test_response_size_limit_is_enforced_without_truncating_a_success() -> None:
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    content=b" " * (MAX_RESPONSE_BYTES + 1),
                    headers={"Content-Type": "application/json"},
                )
            ),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.ask(QUESTION)


def test_compressed_content_is_rejected_before_decoder_reads_it() -> None:
    class Unreadable(httpx.SyncByteStream):
        def __iter__(self):
            raise AssertionError("compressed response must not be decoded")

    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    stream=Unreadable(),
                    headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
                )
            ),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.ask(QUESTION)


def test_model_construct_cannot_bypass_stack_component_limit() -> None:
    request = StackCheckRequest.model_construct(
        components=tuple(
            {"ecosystem": "PyPI", "package_name": "synthetic", "version": None} for _ in range(201)
        )
    )

    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be used")

    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(forbidden),
        ) as client,
        pytest.raises(ClientInputError),
    ):
        client.check_stack(request)


def test_response_cookie_cannot_change_authentication_of_later_requests() -> None:
    calls: list[httpx.Request] = []

    def setting_cookie(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json=ANSWER,
            headers={"Set-Cookie": "ai_intel_session=synthetic-session; Path=/"},
        )

    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(setting_cookie),
    ) as client:
        client.ask(QUESTION, idempotency_key="synthetic-first-key")
        client.ask(QUESTION, idempotency_key="synthetic-second-key")
    assert len(calls) == 2
    assert all("cookie" not in request.headers for request in calls)
    assert all(request.headers["authorization"] == "Bearer " + SYNTHETIC_KEY for request in calls)


def test_float_overflow_does_not_bypass_nonfinite_json_boundary() -> None:
    with pytest.raises(ResponseContractError):
        validate_json_bytes(b'{"number":1e999}')


def test_large_component_value_is_rejected_before_network_even_below_200_components() -> None:
    request = StackCheckRequest.model_validate_json(
        json.dumps(
            {
                "components": [
                    {
                        "ecosystem": "PyPI",
                        "package_name": "x" * MAX_SYNCHRONOUS_REQUEST_BYTES,
                        "version": None,
                    }
                ]
            }
        )
    )

    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("oversized request must not be sent")

    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(SYNTHETIC_KEY),
            transport=httpx.MockTransport(forbidden),
        ) as client,
        pytest.raises(ClientInputError),
    ):
        client.check_stack(request)
