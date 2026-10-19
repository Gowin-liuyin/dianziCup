"""Real loopback slow responses prove the new deadline independently of IO timeout."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from ai_intel_client.client import DianziClient, DianziTransportError
from ai_intel_client.models import AskRequest
from pydantic import SecretStr

KEY = "synthetic-total-deadline-fixture-no-provider-access"
ANSWER = {
    "kind": "completed",
    "answer_id": "00000000-0000-4000-8000-000000000111",
    "answer_text": "Explicit slow response fixture",
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


@pytest.mark.parametrize("slow_phase", ["headers", "body"])
def test_sync_sdk_total_deadline_rejects_real_slow_drip(
    slow_phase: str, record_property: Callable[[str, object], None]
) -> None:
    dispatched = []
    disconnected = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["content-length"]))
            dispatched.append(self.path)
            raw = json.dumps(ANSWER).encode()
            try:
                if slow_phase == "headers":
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    self.wfile.flush()
                    for _ in range(20):
                        time.sleep(0.02)
                        self.wfile.write(b"a")
                        self.wfile.flush()
                    self.wfile.write(
                        b"\r\nContent-Type: application/json\r\nContent-Length: "
                        + str(len(raw)).encode()
                        + b"\r\n\r\n"
                        + raw
                    )
                else:
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(raw)))
                    self.end_headers()
                    for offset in range(0, len(raw), 20):
                        time.sleep(0.02)
                        self.wfile.write(raw[offset : offset + 20])
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                disconnected.set()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        with DianziClient(
            f"http://127.0.0.1:{server.server_port}",
            SecretStr(KEY),
            question_timeout_seconds=0.1,
            question_deadline_seconds=0.1,
        ) as client:
            started = time.monotonic()
            with pytest.raises(DianziTransportError):
                client.ask(AskRequest(question="explicit slow-stream fixture", mode="library"))
            elapsed = time.monotonic() - started
            assert elapsed < 0.25
            record_property("deadline_seconds", 0.1)
            record_property("operation_elapsed_seconds", elapsed)
        assert disconnected.wait(1)
        assert dispatched == ["/api/v1/ask"]
        record_property("actual_loopback_requests", len(dispatched))
        record_property("server_disconnect_observed", disconnected.is_set())
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
    assert not worker.is_alive()


@pytest.mark.anyio
async def test_async_sdk_cancellation_closes_executing_stream(
    record_property: Callable[[str, object], None],
) -> None:
    dispatched = asyncio.Event()
    disconnected = asyncio.Event()
    handlers: set[asyncio.Task[None]] = set()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            handlers.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            await reader.readexactly(length)
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: 10000\r\n"
                b"Content-Type: application/json\r\n\r\n"
            )
            await writer.drain()
            dispatched.set()
            assert await reader.read() == b""
            disconnected.set()
        finally:
            writer.close()
            await writer.wait_closed()
            if task is not None:
                handlers.discard(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        async with DianziClient(f"http://127.0.0.1:{port}", SecretStr(KEY)) as client:
            operation = asyncio.create_task(
                client.ask_async(
                    AskRequest(question="executing cancellation fixture", mode="library")
                )
            )
            await asyncio.wait_for(dispatched.wait(), timeout=1)
            started = time.monotonic()
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await operation
            await asyncio.wait_for(disconnected.wait(), timeout=1)
            record_property("cancel_to_peer_eof_seconds", time.monotonic() - started)
            record_property("peer_eof_observed", disconnected.is_set())
    finally:
        server.close()
        await server.wait_closed()
        for task in tuple(handlers):
            task.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)
    assert not handlers
    record_property("remaining_owned_handlers", len(handlers))
