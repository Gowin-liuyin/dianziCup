"""Independent native socket cleanup, ownership, and bounded failure probes."""

import asyncio
from unittest.mock import patch

import pytest
from ai_intel_client.client import ClientConfigurationError, DianziClient
from ai_intel_client.models import AskRequest
from pydantic import SecretStr
from test_independent_native import KEY, TcpEvidence, record


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def start_four(tcp, client):
    tasks = [
        asyncio.create_task(client.ask_async(AskRequest(question=name, mode="library")))
        for name in ("idle", "held-a", "held-b", "held-c")
    ]
    await tcp.wait(lambda: len(tcp.requests) == 4)
    assert (await tasks[0]).data_mode == "fixture"
    return tasks


@pytest.mark.anyio
async def test_cancelled_waiter_without_retry_owned_cleanup_finishes_real_four_eof():
    async with TcpEvidence() as tcp:
        client = DianziClient(tcp.origin, SecretStr(KEY), question_deadline_seconds=3)
        tasks = await start_four(tcp, client)
        try:
            closing = asyncio.create_task(client.aclose())
            await asyncio.sleep(0)
            closing.cancel()
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
            await tcp.wait(lambda: len(tcp.eof) == 4)
            await tcp.wait(lambda: client._close_task.done())
            assert client._async_http.is_closed
            assert not client._close_task.cancelled()
            for task in tasks[1:]:
                with pytest.raises(asyncio.CancelledError):
                    await task
            assert not client._active_operations
            with pytest.raises(ClientConfigurationError):
                await client.ask_async(AskRequest(question="after-close", mode="library"))
            assert len(tcp.requests) == 4
            record(
                "independent_owned_no_retry",
                {
                    "same_waiter_cancel_requests": 2,
                    "retry_needed_for_eof": False,
                    "eof": tcp.eof,
                    "peak": tcp.peak,
                    "pool_closed": client._async_http.is_closed,
                    "owned_cleanup_done": client._close_task.done(),
                    "active_operations": len(client._active_operations),
                    "new_dispatches": 0,
                    "no_cleanup_yield_hook": True,
                },
            )
        finally:
            await client.aclose()


@pytest.mark.anyio
async def test_three_close_waiters_cancel_two_keep_one_owned_cleanup():
    async with TcpEvidence() as tcp:
        client = DianziClient(tcp.origin, SecretStr(KEY), question_deadline_seconds=3)
        tasks = await start_four(tcp, client)
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = 0
        native_close = client._async_http.aclose

        async def explicit_scheduling_gate():
            nonlocal calls
            calls += 1
            entered.set()
            async with asyncio.timeout(2):
                await release.wait()
            await native_close()

        try:
            with patch.object(client._async_http, "aclose", new=explicit_scheduling_gate):
                waiters = [asyncio.create_task(client.aclose()) for _ in range(3)]
                await asyncio.wait_for(entered.wait(), 1)
                owned = client._close_task
                assert all(not task.done() for task in waiters)
                waiters[0].cancel()
                waiters[0].cancel()
                waiters[1].cancel()
                for task in waiters[:2]:
                    with pytest.raises(asyncio.CancelledError):
                        await task
                assert not owned.cancelled() and not owned.done()
                assert not waiters[2].done()
                with pytest.raises(ClientConfigurationError):
                    await client.ask_async(AskRequest(question="during-close", mode="library"))
                assert "during-close" not in tcp.requests
                release.set()
                await asyncio.wait_for(waiters[2], 1)
                await client.aclose()
                await tcp.wait(lambda: len(tcp.eof) == 4)
                assert client._close_task is owned
                assert calls == 1 and client._async_http.is_closed
                for task in tasks[1:]:
                    with pytest.raises(asyncio.CancelledError):
                        await task
                record(
                    "independent_three_waiters",
                    {
                        "same_waiter_double_cancel": True,
                        "second_waiter_cancelled": True,
                        "third_waiter_waited": True,
                        "one_owned_cleanup": calls,
                        "eof": tcp.eof,
                        "pool_closed": True,
                        "new_dispatches": 0,
                        "scheduling_gate": "explicit fixture, not a performance proof",
                    },
                )
        finally:
            release.set()
            await client.aclose()


@pytest.mark.anyio
async def test_close_failure_is_finite_and_repeated_close_preserves_error():
    async with TcpEvidence() as tcp:
        client = DianziClient(tcp.origin, SecretStr(KEY), question_deadline_seconds=3)
        tasks = await start_four(tcp, client)
        native_close = client._async_http.aclose
        failure = RuntimeError("synthetic-resource-close-failure-no-secret")
        calls = 0

        async def fail_cleanup():
            nonlocal calls
            calls += 1
            raise failure

        try:
            with patch.object(client._async_http, "aclose", new=fail_cleanup):
                for _ in range(3):
                    with pytest.raises(RuntimeError) as raised:
                        await asyncio.wait_for(client.aclose(), 1)
                    assert raised.value is failure
                assert client._close_task.done() and not client._close_task.cancelled()
                assert calls == 1
                for task in tasks[1:]:
                    with pytest.raises(asyncio.CancelledError):
                        await task
                await tcp.wait(lambda: len(tcp.eof) == 3)
                assert not client._async_http.is_closed
                record(
                    "independent_close_failure",
                    {
                        "explicit_failure_injection": True,
                        "three_close_waiters_bounded_errors": True,
                        "one_failed_cleanup": calls,
                        "owned_task_done": True,
                        "eof_before_forced_cleanup": tcp.eof[:],
                        "pool_closed_before_forced_cleanup": client._async_http.is_closed,
                        "automatic_retry_after_cleanup_exception": False,
                    },
                )
        finally:
            await native_close()
            await tcp.wait(lambda: len(tcp.eof) == 4)
