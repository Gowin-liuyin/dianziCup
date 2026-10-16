"""Independent real TCP lifecycle probes. All payloads and credentials are synthetic."""

import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ai_intel_client import client as client_module
from ai_intel_client import mcp_adapter
from ai_intel_client.client import DianziClient, DianziDeadlineError
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.models import AskRequest, StackCheckRequest
from ai_intel_client.output_budget import McpOutputBudget
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.exceptions import MCPError
from mcp_types import CallToolRequestParams
from pydantic import SecretStr
from r18_test_paths import FIXTURES, ROOT, RUN

CACHE = (
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
KEY = "synthetic-independent-native-error-marker-no-provider-access"
ANSWER = {
    "kind": "completed",
    "answer_id": "00000000-0000-4000-8000-000000000231",
    "answer_text": "独立原生TCP，未知版本；🙂",
    "claims": [],
    "citations": [],
    "limitations": ["explicit synthetic fixture"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def record(name, value):
    (RUN / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class TcpEvidence:
    def __init__(self):
        self.requests = []
        self.eof = []
        self.tasks = set()
        self.writers = set()
        self.peak = 0
        self.trace = []

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.origin = f"http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *args):
        self.server.close()
        await self.server.wait_closed()
        for writer in tuple(self.writers):
            writer.close()
        if self.tasks:
            await asyncio.wait_for(asyncio.gather(*tuple(self.tasks), return_exceptions=True), 2)
        assert not self.tasks and not self.writers
        record("tcp_trace_" + str(self.port), self.trace)

    async def wait(self, predicate):
        async with asyncio.timeout(2):
            while not predicate():
                await asyncio.sleep(0.005)

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.writers.add(writer)
        eof = None
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            size = next(
                int(row.split(b":", 1)[1])
                for row in head.split(b"\r\n")
                if row.lower().startswith(b"content-length:")
            )
            body = json.loads(await reader.readexactly(size))
            name = body.get("question", "stack")
            self.trace.append({"name": name, "received_at": time.monotonic()})
            self.requests.append(name)
            self.peak = max(self.peak, len(self.writers))
            eof = asyncio.create_task(reader.read())
            raw = json.dumps(ANSWER, ensure_ascii=False).encode()
            headers = (
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b"Connection: keep-alive\r\nContent-Length: " + str(len(raw)).encode() + b"\r\n\r\n"
            )
            if name == "drip-headers":
                writer.write(b"HTTP/1.1 200 OK\r\nX-Drip: ")
                await writer.drain()
                for _ in range(40):
                    if eof.done():
                        break
                    await asyncio.sleep(0.03)
                    writer.write(b"x")
                    await writer.drain()
                    self.trace.append({"name": name, "header_drip_at": time.monotonic()})
            else:
                writer.write(headers)
                await writer.drain()
                if name == "drip-body":
                    for offset in range(0, len(raw), 8):
                        if eof.done():
                            break
                        await asyncio.sleep(0.03)
                        writer.write(raw[offset : offset + 8])
                        await writer.drain()
                        self.trace.append(
                            {"name": name, "body_offset": offset, "drip_at": time.monotonic()}
                        )
                elif name == "idle":
                    writer.write(raw)
                    await writer.drain()
            if await eof == b"":
                self.eof.append(name)
        except (ConnectionError, asyncio.IncompleteReadError):
            if eof is not None and eof.done() and not eof.cancelled() and eof.result() == b"":
                self.eof.append(name)
        finally:
            if eof is not None and not eof.done():
                eof.cancel()
                await asyncio.gather(eof, return_exceptions=True)
            writer.close()
            await writer.wait_closed()
            self.writers.discard(writer)
            self.tasks.discard(task)


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["headers", "body"])
async def test_real_drip_total_deadline_and_peer_eof(phase):
    async with (
        TcpEvidence() as tcp,
        DianziClient(
            tcp.origin,
            SecretStr(KEY),
            question_timeout_seconds=0.5,
            question_deadline_seconds=0.12,
        ) as client,
    ):
        started = time.monotonic()
        with pytest.raises(DianziDeadlineError) as expired:
            await client.ask_async(
                AskRequest(question="drip-" + phase, mode="library"),
                idempotency_key="synthetic-drip-key",
            )
        elapsed = time.monotonic() - started
        await tcp.wait(lambda: len(tcp.eof) == 1)
        assert expired.value.idempotency_key == "synthetic-drip-key"
        assert expired.value.may_have_executed is True
        assert elapsed < 0.35
        record(
            "independent_drip_" + phase,
            {
                "total_seconds": elapsed,
                "deadline": 0.12,
                "io_timeout": 0.5,
                "actual_peer_eof": tcp.eof,
                "requests": tcp.requests,
            },
        )


@pytest.mark.anyio
async def test_four_running_queue_cancel_replacement_and_close_all_eof():
    async with (
        TcpEvidence() as tcp,
        DianziClient(
            tcp.origin,
            SecretStr(KEY),
            operation_deadline_seconds=0.08,
            question_deadline_seconds=3,
        ) as client,
    ):
        tasks = [
            asyncio.create_task(client.ask_async(AskRequest(question=f"held-{i}", mode="library")))
            for i in range(4)
        ]
        await tcp.wait(lambda: len(tcp.requests) == 4)
        with pytest.raises(DianziDeadlineError) as queued:
            await client.check_stack_async(StackCheckRequest(components=()))
        assert queued.value.may_have_executed is False
        fifth = asyncio.create_task(
            client.ask_async(AskRequest(question="queued-cancelled", mode="library"))
        )
        await asyncio.sleep(0.02)
        fifth.cancel()
        with pytest.raises(asyncio.CancelledError):
            await fifth
        tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[0]
        await tcp.wait(lambda: "held-0" in tcp.eof)
        replacement = asyncio.create_task(
            client.ask_async(AskRequest(question="held-4", mode="library"))
        )
        await tcp.wait(lambda: len(tcp.requests) == 5)
        await client.aclose()
        for task in [*tasks[1:], replacement]:
            with pytest.raises(asyncio.CancelledError):
                await task
        await tcp.wait(lambda: len(tcp.eof) == 5)
        assert tcp.peak == 4
        assert "stack" not in tcp.requests and "queued-cancelled" not in tcp.requests
        record(
            "independent_sdk_close",
            {"requests": tcp.requests, "peer_eof": tcp.eof, "peak": tcp.peak},
        )


@pytest.mark.anyio
async def test_cancelled_aclose_can_retry_and_close_idle_connection():
    async with TcpEvidence() as tcp:
        client = DianziClient(tcp.origin, SecretStr(KEY), question_deadline_seconds=3)
        await client.__aenter__()
        tasks = [
            asyncio.create_task(client.ask_async(AskRequest(question=name, mode="library")))
            for name in ["idle", "held-a", "held-b", "held-c"]
        ]
        try:
            await tcp.wait(lambda: len(tcp.requests) == 4)
            assert (await tasks[0]).data_mode == "fixture"
            closing = asyncio.create_task(client.aclose())
            await asyncio.sleep(0)
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
            for task in tasks[1:]:
                with pytest.raises(asyncio.CancelledError):
                    await task
            await client.aclose()
            await asyncio.sleep(0.1)
            record(
                "cancelled_aclose_observation",
                {
                    "requests": tcp.requests,
                    "peer_eof_before_forced_cleanup": tcp.eof[:],
                    "sdk_closed": client._closed,
                    "native_pool_closed": client._async_http.is_closed,
                    "explicit_synthetic_real_tcp": True,
                    "expected_eof_count": 4,
                },
            )
            assert len(tcp.eof) == 4
        finally:
            await client._async_http.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("protocol", ["handshake", "modern"])
async def test_native_unexpected_error_real_stdio_has_no_marker(protocol):
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(FIXTURES / "native_stdio_fixture.py")],
        cwd=ROOT,
        env={
            "PYTHONPATH": str(ROOT / "sdk/python"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "REVIEW_MODE": "fault",
            "REVIEW_ORIGIN": "http://127.0.0.1:32197",
            "REVIEW_CACHE": CACHE,
        },
    )
    stderr_path = RUN / f"native_fault_{protocol}_stderr.log"
    with stderr_path.open("w", encoding="utf-8") as stderr:
        async with (
            stdio_client(params, errlog=stderr) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            if protocol == "modern":
                await session.discover()
            else:
                await session.initialize()
            result = await session.call_tool(
                "ask", {"question": "synthetic native fault", "mode": "library"}
            )
            assert result.is_error is True and "backend_internal_error" in result.model_dump_json()
            assert KEY not in result.model_dump_json()
            assert McpOutputBudget(Path(CACHE)).fits(result)
            record(
                "native_fault_" + protocol,
                result.model_dump(mode="json", by_alias=True, exclude_none=True),
            )
    assert stderr_path.read_bytes() == b""


@pytest.mark.anyio
async def test_stdio_queued_running_cancel_list_and_shutdown_peer_eof():
    async with TcpEvidence() as tcp:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURES / "native_stdio_fixture.py")],
            cwd=ROOT,
            env={
                "PYTHONPATH": str(ROOT / "sdk/python"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "REVIEW_ORIGIN": tcp.origin,
                "REVIEW_CACHE": CACHE,
            },
        )
        stderr_path = RUN / "native_stdio_resources_stderr.log"
        tasks = []
        with stderr_path.open("w", encoding="utf-8") as stderr:
            async with (
                stdio_client(params, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.discover()
                tasks = [
                    asyncio.create_task(
                        session.call_tool(
                            "ask",
                            {"question": f"held-{i}", "mode": "library"},
                            read_timeout_seconds=0.4 if i == 0 else 5,
                        )
                    )
                    for i in range(4)
                ]
                await tcp.wait(lambda: len(tcp.requests) == 4)
                queued = await session.call_tool("check_stack", {"components": []})
                assert queued.is_error and "backend_deadline_exceeded" in queued.model_dump_json()
                with pytest.raises(MCPError):
                    await session.call_tool(
                        "ask",
                        {"question": "queued-cancelled", "mode": "library"},
                        read_timeout_seconds=0.07,
                    )
                with pytest.raises(MCPError):
                    await tasks[0]
                await tcp.wait(lambda: "held-0" in tcp.eof)
                tasks.append(
                    asyncio.create_task(
                        session.call_tool(
                            "ask", {"question": "held-4", "mode": "library"}, read_timeout_seconds=5
                        )
                    )
                )
                await tcp.wait(lambda: len(tcp.requests) == 5)
                start = time.monotonic()
                assert len((await session.list_tools()).tools) == 2
                list_elapsed = time.monotonic() - start
                assert list_elapsed < 0.2
                assert "stack" not in tcp.requests and "queued-cancelled" not in tcp.requests
            results = await asyncio.gather(*tasks[1:], return_exceptions=True)
            assert all(isinstance(result, BaseException) for result in results)
        await tcp.wait(lambda: len(tcp.eof) == 5)
        assert tcp.peak == 4
        assert stderr_path.read_bytes() == b""
        record(
            "independent_stdio_resources",
            {
                "requests": tcp.requests,
                "peak": tcp.peak,
                "peer_eof": tcp.eof,
                "list_elapsed_seconds": list_elapsed,
                "queued_dispatches": 0,
                "shutdown_all_eof": True,
            },
        )


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["decode", "output"])
async def test_real_tcp_slow_cpu_cannot_return_late_success(stage):
    async with (
        TcpEvidence() as tcp,
        DianziClient(
            tcp.origin,
            SecretStr(KEY),
            question_deadline_seconds=0.1,
        ) as backend,
    ):
        started = time.monotonic()
        hook_calls = 0
        if stage == "decode":
            original = client_module._decode_response

            def slow(*args, **kwargs):
                nonlocal hook_calls
                hook_calls += 1
                time.sleep(0.18)
                return original(*args, **kwargs)

            with (
                patch.object(client_module, "_decode_response", new=slow),
                pytest.raises(DianziDeadlineError),
            ):
                await backend.ask_async(AskRequest(question="idle", mode="library"))
        else:
            original = mcp_adapter._complete_result

            def slow(*args, **kwargs):
                nonlocal hook_calls
                hook_calls += 1
                time.sleep(0.18)
                return original(*args, **kwargs)

            callback = (
                create_current_read_tool_server(backend, McpOutputBudget(Path(CACHE)))
                ._request_handlers["tools/call"]
                .handler
            )
            started = time.monotonic()
            with patch.object(mcp_adapter, "_complete_result", new=slow):
                result = await callback(
                    SimpleNamespace(request=None),
                    CallToolRequestParams(
                        name="ask", arguments={"question": "idle", "mode": "library"}
                    ),
                )
            assert result.is_error and "backend_deadline_exceeded" in result.model_dump_json()
            assert result.structured_content is None
        assert hook_calls == 1
        record(
            "independent_slow_cpu_" + stage,
            {
                "elapsed_seconds": time.monotonic() - started,
                "deadline_seconds": 0.1,
                "cpu_sleep_injected_seconds": 0.18,
                "hook_calls": hook_calls,
                "late_success": False,
                "cpu_interruption_proven": False,
            },
        )
