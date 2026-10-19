"""Real four-socket close cancellation with an explicit bounded cleanup scheduling hook."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from ai_intel_client.client import ClientConfigurationError, DianziClient
from ai_intel_client.models import AskRequest
from pydantic import SecretStr
from test_independent_native import KEY, TcpEvidence, record


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("cancel_count", [1, 2])
async def test_repeated_cancelled_close_waits_one_cleanup_and_rejects_new_work(
    cancel_count: int,
) -> None:
    async with (
        TcpEvidence() as tcp,
        DianziClient(tcp.origin, SecretStr(KEY), question_deadline_seconds=3) as client,
    ):
        operations = [
            asyncio.create_task(client.ask_async(AskRequest(question=name, mode="library")))
            for name in ("idle", "held-a", "held-b", "held-c")
        ]
        await tcp.wait(lambda: len(tcp.requests) == 4)
        assert (await operations[0]).data_mode == "fixture"
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_calls = 0
        original_close = client._async_http.aclose

        async def held_pool_cleanup() -> None:
            nonlocal cleanup_calls
            cleanup_calls += 1
            cleanup_started.set()
            async with asyncio.timeout(2):
                await cleanup_release.wait()
            await original_close()

        with patch.object(client._async_http, "aclose", new=held_pool_cleanup):
            try:
                for _ in range(cancel_count):
                    closing = asyncio.create_task(client.aclose())
                    await asyncio.wait_for(cleanup_started.wait(), 1)
                    await asyncio.sleep(0)
                    closing.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await closing
                with pytest.raises(ClientConfigurationError):
                    await client.ask_async(AskRequest(question="must-not-dispatch", mode="library"))
                assert "must-not-dispatch" not in tcp.requests
                assert cleanup_calls == 1
                waiting = asyncio.create_task(client.aclose())
                await asyncio.sleep(0)
                assert not waiting.done()
                cleanup_release.set()
                await waiting
                await client.aclose()
                for operation in operations[1:]:
                    with pytest.raises(asyncio.CancelledError):
                        await operation
                await tcp.wait(lambda: len(tcp.eof) == 4)
                assert client._async_http.is_closed
                assert client._close_task.done()
                assert cleanup_calls == 1
                assert len(tcp.requests) == 4
                record(
                    "close_reentry_" + str(cancel_count),
                    {
                        "cancelled_public_close_callers": cancel_count,
                        "actual_tcp_requests": 4,
                        "peer_eof_count": len(tcp.eof),
                        "pool_closed": True,
                        "owned_cleanup_done": True,
                        "cleanup_calls": cleanup_calls,
                        "new_work_dispatches": 0,
                        "cleanup_scheduling_hook": "explicit fixture; actual native TCP IO",
                        "product_or_paid_calls": 0,
                    },
                )
            finally:
                cleanup_release.set()
                await client.aclose()
    assert not tcp.tasks and not tcp.writers
