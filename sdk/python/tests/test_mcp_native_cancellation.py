"""Real loopback TCP and official MCP stdio cancellation, with synthetic backend responses."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from ai_intel_client.client import DianziClient, DianziDeadlineError
from ai_intel_client.models import AskRequest, StackCheckRequest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.exceptions import MCPError
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[3]
CACHE = (
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
KEY = "synthetic-native-cancellation-only-no-provider-access"
ANSWER = {
    "kind": "completed",
    "answer_id": "00000000-0000-4000-8000-000000000111",
    "answer_text": "Explicit native fixture 中文 🧪",
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


class HeldLoopbackBackend:
    """Hold incomplete local HTTP responses until release or actual client EOF."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.calls: list[str] = []
        self.disconnected: list[str] = []
        self.handlers: set[asyncio.Task[None]] = set()
        self.active = 0
        self.peak = 0
        self.origin = ""

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        current = asyncio.current_task()
        if current is not None:
            self.handlers.add(current)
        waiters: list[asyncio.Task[object]] = []
        counted = False
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in header.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            body = json.loads(await reader.readexactly(length))
            name = body.get("question", "stack")
            self.calls.append(name)
            self.active += 1
            counted = True
            self.peak = max(self.peak, self.active)
            raw = json.dumps(ANSWER).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b"Connection: close\r\nContent-Length: " + str(len(raw)).encode() + b"\r\n\r\n"
            )
            await writer.drain()
            release = asyncio.create_task(self.release.wait())
            eof = asyncio.create_task(reader.read())
            waiters.extend([release, eof])
            done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
            if eof in done:
                assert eof.result() == b""
                self.disconnected.append(name)
            else:
                writer.write(raw)
                await writer.drain()
        finally:
            for task in waiters:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
            writer.close()
            await writer.wait_closed()
            if counted:
                self.active -= 1
            if current is not None:
                self.handlers.discard(current)

    async def wait_for_calls(self, count: int) -> None:
        async with asyncio.timeout(3):
            while len(self.calls) < count:
                await asyncio.sleep(0.01)

    async def wait_for_disconnect(self, name: str) -> None:
        async with asyncio.timeout(2):
            while name not in self.disconnected:
                await asyncio.sleep(0.01)


@asynccontextmanager
async def local_backend() -> AsyncIterator[HeldLoopbackBackend]:
    backend = HeldLoopbackBackend()
    server = await asyncio.start_server(backend.handle, "127.0.0.1", 0)
    backend.origin = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    try:
        yield backend
    finally:
        server.close()
        await server.wait_closed()
        for handler in tuple(backend.handlers):
            handler.cancel()
        await asyncio.gather(*tuple(backend.handlers), return_exceptions=True)
    assert not backend.handlers
    assert backend.active == 0


@pytest.mark.anyio
async def test_sdk_queue_deadline_has_no_dispatch_and_close_cancels_all_active_tcp(
    record_property: Callable[[str, object], None],
) -> None:
    async with (
        local_backend() as server,
        DianziClient(
            server.origin,
            SecretStr(KEY),
            operation_deadline_seconds=0.08,
            question_deadline_seconds=5,
        ) as client,
    ):
        tasks = [
            asyncio.create_task(
                client.ask_async(AskRequest(question=f"active-{index}", mode="library"))
            )
            for index in range(4)
        ]
        await server.wait_for_calls(4)
        started = time.monotonic()
        with pytest.raises(DianziDeadlineError) as expired:
            await client.check_stack_async(StackCheckRequest(components=()))
        queue_elapsed = time.monotonic() - started
        assert queue_elapsed < 0.25
        assert expired.value.may_have_executed is False
        assert server.calls == [f"active-{index}" for index in range(4)]
        fifth = asyncio.create_task(
            client.ask_async(AskRequest(question="queued-close", mode="library"))
        )
        await asyncio.sleep(0.02)
        await client.aclose()
        for operation in [*tasks, fifth]:
            with pytest.raises(asyncio.CancelledError):
                await operation
        for index in range(4):
            await server.wait_for_disconnect(f"active-{index}")
        assert server.peak == 4
        assert len(server.calls) == 4
        assert len(server.disconnected) == 4
        record_property("queued_deadline_seconds", 0.08)
        record_property("queued_elapsed_seconds", queue_elapsed)
        record_property("queued_backend_requests", 0)
        record_property("actual_loopback_requests", len(server.calls))
        record_property("peak_active_io", server.peak)
        record_property("executing_peer_eof_count", len(server.disconnected))
    record_property("remaining_owned_handlers", len(server.handlers))


@pytest.mark.anyio
async def test_native_stdio_queue_and_executing_cancel_release_socket_and_slot(
    tmp_path: Path,
    record_property: Callable[[str, object], None],
) -> None:
    async with local_backend() as server:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "sdk/python/tests/fixtures/mcp_native_deadline_stdio.py")],
            cwd=ROOT,
            env={
                "PYTHONPATH": str(ROOT / "sdk/python"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "DIANZI_FIXTURE_LOOPBACK_ORIGIN": server.origin,
                "DIANZI_FIXTURE_ENCODING_CACHE": CACHE,
            },
        )
        stderr_file = tmp_path / "native_stdio_stderr.raw"
        with stderr_file.open("w", encoding="utf-8") as stderr:
            async with (
                stdio_client(params, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream, read_timeout_seconds=5) as session,
            ):
                await session.discover()
                listed = await session.list_tools()
                assert [tool.name for tool in listed.tools] == ["ask", "check_stack"]

                async def call(index: int):
                    return await session.call_tool(
                        "ask",
                        {"question": f"active-{index}", "mode": "library"},
                        read_timeout_seconds=0.5 if index == 0 else 5,
                    )

                tasks = [asyncio.create_task(call(index)) for index in range(4)]
                await server.wait_for_calls(4)
                queued_started = time.monotonic()
                stack = await session.call_tool("check_stack", {"components": []})
                assert stack.is_error is True
                assert "backend_deadline_exceeded" in stack.model_dump_json()
                queue_elapsed = time.monotonic() - queued_started
                assert queue_elapsed < 0.25
                assert "stack" not in server.calls
                with pytest.raises(MCPError):
                    await session.call_tool(
                        "ask",
                        {"question": "queued-cancelled", "mode": "library"},
                        read_timeout_seconds=0.06,
                    )
                with pytest.raises(MCPError):
                    await tasks[0]
                await server.wait_for_disconnect("active-0")
                assert "queued-cancelled" not in server.calls
                replacement = asyncio.create_task(call(4))
                await server.wait_for_calls(5)
                assert len((await session.list_tools()).tools) == 2
                server.release.set()
                for operation in [*tasks[1:], replacement]:
                    answer = await operation
                    assert answer.is_error is False
                    assert answer.structured_content == ANSWER
                assert server.peak == 4
                assert len(server.calls) == 5
                assert server.disconnected == ["active-0"]
                record_property("queued_deadline_seconds", 0.08)
                record_property("queued_elapsed_seconds", queue_elapsed)
                record_property("queued_backend_requests", 0)
                record_property("actual_loopback_requests", len(server.calls))
                record_property("peak_active_io", server.peak)
                record_property("executing_peer_eof_count", len(server.disconnected))
        assert stderr_file.read_bytes() == b""
        record_property("stdio_stderr_bytes", stderr_file.stat().st_size)
    record_property("remaining_owned_handlers", len(server.handlers))
