"""Real async stream cancellation verifies elapsed-body deadlines without external IO."""

import asyncio
import time

import httpx
import pytest

from ai_intel.retrieval.hybrid_contracts import HybridRetrievalError
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient


class SlowBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        for _ in range(30):
            await asyncio.sleep(0.02)
            yield b" "


def test_whole_stream_deadline_cancels_a_trickling_body() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowBody()))
    with httpx.Client(base_url="https://search.invalid") as client:
        search = OpenSearchCorpusClient(
            client,
            deadline=time.monotonic() + 0.1,
            async_client_factory=lambda: httpx.AsyncClient(
                base_url="https://search.invalid", transport=transport
            ),
        )
        started = time.monotonic()
        with pytest.raises(HybridRetrievalError, match="opensearch_timeout"):
            search._request("GET", "/dianzi_test_deadline")
        assert time.monotonic() - started < 0.5


def test_sync_caller_timeout_is_not_overridden_with_ten_seconds() -> None:
    observed = []

    def receive(request: httpx.Request) -> httpx.Response:
        observed.append(request.extensions["timeout"])
        return httpx.Response(200, json={"synthetic": True})

    with httpx.Client(
        base_url="https://search.invalid", timeout=0.25, transport=httpx.MockTransport(receive)
    ) as client:
        assert OpenSearchCorpusClient(client)._request("GET", "/fixture").json() == {
            "synthetic": True
        }
    assert observed == [{"connect": 0.25, "read": 0.25, "write": 0.25, "pool": 0.25}]


def test_deadline_client_origin_cannot_change() -> None:
    with httpx.Client(base_url="https://search.invalid") as client:
        search = OpenSearchCorpusClient(
            client,
            deadline=time.monotonic() + 1,
            async_client_factory=lambda: httpx.AsyncClient(base_url="https://other.invalid"),
        )
        with pytest.raises(HybridRetrievalError, match="opensearch_origin_mismatch"):
            search._request("GET", "/fixture")
