"""Isolated async transport contracts; these fixtures never demonstrate live service IO."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from ai_intel_client.client import (
    ClientConfigurationError,
    DianziApiError,
    DianziClient,
    DianziDeadlineError,
    ResponseContractError,
)
from ai_intel_client.models import AskRequest
from pydantic import SecretStr

KEY = "synthetic-async-contract-only-no-provider-access"
ANSWER = {
    "kind": "completed",
    "answer_id": "00000000-0000-4000-8000-000000000111",
    "answer_text": "Explicit async fixture 中文 🧪",
    "claims": [],
    "citations": [],
    "limitations": ["No live evidence"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize("parameter", ["operation_deadline_seconds", "question_deadline_seconds"])
@pytest.mark.parametrize("value", [True, False, 0, -1, float("nan"), float("inf"), 121])
def test_deadline_parameters_reject_nonfinite_boolean_and_out_of_bounds(
    parameter: str,
    value: float,
) -> None:
    with pytest.raises(ClientConfigurationError):
        DianziClient("http://127.0.0.1:32197", SecretStr(KEY), **{parameter: value})


def test_two_transport_injections_are_rejected() -> None:
    with pytest.raises(ClientConfigurationError):
        DianziClient(
            "http://127.0.0.1:32197",
            SecretStr(KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
            async_transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
        )


@pytest.mark.anyio
async def test_sync_method_in_running_loop_rejects_without_dispatch_or_deadlock() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=ANSWER)

    async with DianziClient(
        "http://127.0.0.1:32197", SecretStr(KEY), async_transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(ClientConfigurationError, match="requires async"):
            client.ask(AskRequest(question="explicit loop boundary", mode="library"))
        with pytest.raises(ClientConfigurationError, match="requires async"):
            client.close()
        assert calls == []
        assert (
            await client.ask_async(AskRequest(question="explicit fixture", mode="library"))
        ).data_mode == "fixture"
    await client.aclose()
    assert calls == ["/api/v1/ask"]


@pytest.mark.anyio
async def test_shared_async_decoder_and_cookies_are_strict_under_parallel_requests() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json=ANSWER, headers={"set-cookie": "session=synthetic-fixture"})

    async with DianziClient(
        "http://127.0.0.1:32197", SecretStr(KEY), async_transport=httpx.MockTransport(handler)
    ) as client:
        first, second = await asyncio.gather(
            *[
                client.ask_async(AskRequest(question="parallel fixture", mode="library"))
                for _ in range(2)
            ]
        )
        third = await client.ask_async(AskRequest(question="cookie fixture", mode="library"))
        assert first.answer_text == second.answer_text == third.answer_text
        assert all("cookie" not in request.headers for request in requests)
        assert all(request.headers["authorization"] == "Bearer " + KEY for request in requests)
    assert len(requests) == 3


@pytest.mark.anyio
@pytest.mark.parametrize("raw", [b'{"kind":"completed","kind":"task"}', b'{"kind":NaN}'])
async def test_async_decoder_rejects_duplicate_and_nonfinite_wire(raw: bytes) -> None:
    async with DianziClient(
        "http://127.0.0.1:32197",
        SecretStr(KEY),
        async_transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=raw, headers={"content-type": "application/json"})
        ),
    ) as client:
        with pytest.raises(ResponseContractError):
            await client.ask_async(AskRequest(question="invalid wire fixture", mode="library"))


@pytest.mark.anyio
async def test_async_deadline_has_operation_key_and_no_server_text() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json=ANSWER)

    async with DianziClient(
        "http://127.0.0.1:32197",
        SecretStr(KEY),
        question_deadline_seconds=0.05,
        async_transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(DianziDeadlineError) as error:
            await client.ask_async(
                AskRequest(question="fixture deadline", mode="library"),
                idempotency_key="fixed-operation-fixture",
            )
        assert error.value.idempotency_key == "fixed-operation-fixture"
        assert error.value.may_have_executed is True
        assert KEY not in str(error.value)


@pytest.mark.anyio
async def test_async_http_failure_does_not_echo_response_text() -> None:
    marker = "synthetic-http-error-credential-marker"
    async with DianziClient(
        "http://127.0.0.1:32197",
        SecretStr(KEY),
        async_transport=httpx.MockTransport(lambda _: httpx.Response(403, text=marker)),
    ) as client:
        with pytest.raises(DianziApiError) as error:
            await client.ask_async(AskRequest(question="fixture denial", mode="library"))
        assert error.value.status == 403
        assert marker not in str(error.value)
        assert KEY not in str(error.value)


def test_same_native_implementation_supports_sync_bridge_and_closed_boundary() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=json.dumps(ANSWER), headers={"content-type": "application/json"}
        )

    client = DianziClient(
        "http://127.0.0.1:32197", SecretStr(KEY), async_transport=httpx.MockTransport(handler)
    )
    with client:
        assert (
            client.ask(AskRequest(question="fixture sync bridge", mode="library")).data_mode
            == "fixture"
        )
        assert (
            client.ask(AskRequest(question="fixture reused loop", mode="library")).freshness
            == "unknown"
        )
    client.close()
    with pytest.raises(ClientConfigurationError):
        client.ask(AskRequest(question="closed fixture", mode="library"))
