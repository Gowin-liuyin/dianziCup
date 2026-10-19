"""独立固定时钟与真实传输代码负例；所有DNS/socket/模型结果均为fixture。"""

import io
import json
from itertools import count
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr
from test_r03_network_transport import FixtureSocket, _install_socket_fixtures

from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.clients import EgressPolicyViolation
from ai_intel.infrastructure.models.generation import (
    GenerationClient,
    GenerationFailure,
    GenerationLimits,
    GenerationRequest,
)
from ai_intel.infrastructure.network import FetchResult

PROVIDERS = ("openai", "anthropic", "deepseek_openai", "deepseek_anthropic")


class ReviewAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str


def client_for(provider, timeout=1.0):
    return GenerationClient(
        provider,
        "deepseek-flash",
        SecretStr("review-synthetic-secret"),
        limits=GenerationLimits(total_timeout_seconds=timeout, max_concurrent_requests=1),
    )


def valid_request():
    return GenerationRequest(
        system_text="Return evidence bounded JSON.",
        question="Known?",
        evidence_texts=("Public fixture sentence.",),
        prompt_version="review1",
        schema_version="review1",
        model_version="deepseek-flash",
        max_output_tokens=80,
        allow_format_repair=True,
    )


def response_wire(provider, raw='{"outcome":"unknown"}'):
    common = {"id": "review-response", "model": "deepseek-flash"}
    if provider.endswith("anthropic"):
        return {
            **common,
            "type": "message",
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": raw}],
            "usage": {"input_tokens": 5, "output_tokens": 4},
        }
    return {
        **common,
        "object": "chat.completion",
        "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": raw}}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 4},
    }


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("later", [101.0, 103.0])
def test_no_slot_or_transport_on_exact_or_overdue_deadline(monkeypatch, provider, later):
    client = client_for(provider)
    readings = count()
    monkeypatch.setattr(
        generation.time, "monotonic", lambda: 100.0 if next(readings) == 0 else later
    )
    acquire = Mock(wraps=client._slots.acquire)
    release = Mock(wraps=client._slots.release)
    dns = Mock(side_effect=AssertionError("fixture DNS must not be reached"))
    post = Mock(side_effect=AssertionError("fixture POST must not be reached"))
    monkeypatch.setattr(client._slots, "acquire", acquire)
    monkeypatch.setattr(client._slots, "release", release)
    monkeypatch.setattr(client._gateway._transport, "resolve_addresses", dns)
    monkeypatch.setattr(client._gateway._transport, "request", post)
    with pytest.raises(GenerationFailure) as observed:
        client.generate(valid_request(), ReviewAnswer)
    assert observed.value.code == "model_network_timeout"
    assert observed.value.attempts == ()
    assert observed.value.finish_reason is None
    assert observed.value.__cause__ is None and observed.value.__suppress_context__
    assert str(observed.value) == "model_network_timeout"
    acquire.assert_not_called()
    release.assert_not_called()
    dns.assert_not_called()
    post.assert_not_called()
    assert client._slots.acquire(blocking=False)
    assert not client._slots.acquire(blocking=False)
    client._slots.release()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_expired_request_cannot_release_another_request_slot(monkeypatch, provider):
    client = client_for(provider)
    assert client._slots.acquire(blocking=False)
    readings = count()
    monkeypatch.setattr(
        generation.time, "monotonic", lambda: 100.0 if next(readings) == 0 else 103.0
    )
    with pytest.raises(GenerationFailure, match=r"^model_network_timeout$"):
        client.generate(valid_request(), ReviewAnswer)
    assert not client._slots.acquire(blocking=False)
    client._slots.release()
    assert client._slots.acquire(blocking=False)
    client._slots.release()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_real_occupied_slot_remains_concurrency_timeout(monkeypatch, provider):
    client = client_for(provider, timeout=0.01)
    assert client._slots.acquire(blocking=False)
    monkeypatch.setattr(generation.time, "monotonic", lambda: 100.0)
    with pytest.raises(GenerationFailure) as observed:
        client.generate(valid_request(), ReviewAnswer)
    assert observed.value.code == "model_concurrency_timeout"
    assert observed.value.attempts == ()
    assert not client._slots.acquire(blocking=False)
    client._slots.release()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_unknown_acquire_error_is_not_swallowed(monkeypatch, provider):
    client = client_for(provider)
    unexpected = RuntimeError("independent unknown acquire error")
    monkeypatch.setattr(client._slots, "acquire", Mock(side_effect=unexpected))
    release = Mock(wraps=client._slots.release)
    monkeypatch.setattr(client._slots, "release", release)
    with pytest.raises(RuntimeError) as observed:
        client.generate(valid_request(), ReviewAnswer)
    assert observed.value is unexpected
    release.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_private_denial_precedes_timeout_without_acquiring(monkeypatch, provider):
    client = client_for(provider)
    readings = count()
    monkeypatch.setattr(
        generation.time, "monotonic", lambda: 100.0 if next(readings) == 0 else 103.0
    )
    acquire = Mock(wraps=client._slots.acquire)
    monkeypatch.setattr(client._slots, "acquire", acquire)
    with pytest.raises(EgressPolicyViolation):
        client.generate(
            valid_request(), ReviewAnswer, content_is_private=True, egress_granted=False
        )
    acquire.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_deadline_expiry_during_repair_keeps_two_attempts_without_third(monkeypatch, provider):
    client = client_for(provider)
    clock = [100.0]
    calls = []
    monkeypatch.setattr(generation.time, "monotonic", lambda: clock[0])

    def post(url, body, *, protocol_headers, deadline):
        calls.append((body, deadline))
        if len(calls) == 2:
            clock[0] = 103.0
            deadline.remaining_seconds()
        return FetchResult(
            url, 200, "application/json", json.dumps(response_wire(provider, "{}")).encode()
        )

    monkeypatch.setattr(client._gateway, "post_json", post)
    with pytest.raises(GenerationFailure) as observed:
        client.generate(valid_request(), ReviewAnswer)
    assert observed.value.code == "model_network_timeout"
    assert [item.outcome for item in observed.value.attempts] == [
        "model_format_invalid",
        "model_network_timeout",
    ]
    assert len(calls) == 2 and calls[0][1] is calls[1][1]
    assert observed.value.attempts[1].usage.output_tokens is None
    assert all(item.fee == "unknown" for item in observed.value.attempts)
    assert client._slots.acquire(blocking=False)
    client._slots.release()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("operation", ["connect", "do_handshake", "read", "dns"])
def test_generation_uses_real_transport_timeout_classification_and_slot_reuse(
    monkeypatch, provider, operation
):
    body = json.dumps(response_wire(provider)).encode()
    response = (
        b"HTTP/1.1 200 Fixture\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )
    client = client_for(provider, timeout=10.0)
    with monkeypatch.context() as isolated:
        sockets, queries = _install_socket_fixtures(isolated, [response])

        def fail(*args, **kwargs):
            raise TimeoutError("synthetic diagnostic must not leak")

        if operation in {"connect", "do_handshake"}:
            isolated.setattr(FixtureSocket, operation, fail)
        elif operation == "read":

            class TimeoutBody(io.BytesIO):
                def read(self, size=-1):
                    raise TimeoutError("synthetic body diagnostic")

            isolated.setattr(
                FixtureSocket, "makefile", lambda self, mode: TimeoutBody(self.response_bytes)
            )
        else:
            isolated.setattr("ai_intel.infrastructure.http_transport.socket.getaddrinfo", fail)
        with pytest.raises(GenerationFailure) as observed:
            client.generate(valid_request(), ReviewAnswer)
        assert observed.value.code == "model_network_timeout"
        assert len(observed.value.attempts) == 1
        assert observed.value.attempts[0].fee == "unknown"
        assert observed.value.attempts[0].usage.input_tokens is None
        assert "synthetic" not in str(observed.value)
        assert all(item.closed for item in sockets)
        assert len(sockets) <= 1 and len(queries) <= 1
    with monkeypatch.context() as isolated:
        sockets, queries = _install_socket_fixtures(isolated, [response])
        result = client.generate(valid_request(), ReviewAnswer)
        assert result.value.outcome == "unknown"
        assert len(result.attempts) == len(sockets) == len(queries) == 1
        assert b"POST " in b"".join(sockets[0].sent) and sockets[0].closed
