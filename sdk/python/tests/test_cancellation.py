"""Real stdio cancellation and local slow-stream experiments; all inputs synthetic."""

import asyncio
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest
from ai_intel_client.client import DianziClient
from ai_intel_client.models import AskRequest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.exceptions import MCPError
from pydantic import SecretStr
from r18_test_paths import ROOT, RUN

KEY = "synthetic-cancellation-only-no-provider-access-20261016"
CACHE = (
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
ANSWER = {
    "kind": "completed",
    "answer_id": "00000000-0000-4000-8000-000000000081",
    "answer_text": "Explicit fixture with unknown evidence",
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
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_queued_cancel_has_no_backend_dispatch_and_executing_cancel_keeps_io_worker():
    calls = []
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            calls.append(body["question"])
            release.wait(4)
            raw = json.dumps(ANSWER).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ai_intel_client.mcp_stdio"],
        cwd=ROOT,
        env={
            "PYTHONPATH": str(ROOT / "sdk/python"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DIANZI_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "DIANZI_API_KEY": KEY,
            "DIANZI_MCP_ENCODING_CACHE_FILE": CACHE,
        },
    )
    try:
        with (RUN / "cancel_stdio_stderr.log").open("w", encoding="utf-8") as stderr:
            async with (
                stdio_client(params, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream, read_timeout_seconds=5) as session,
            ):
                await session.discover()

                async def call_one(index):
                    return await session.call_tool(
                        "ask",
                        {"question": f"active-{index}", "mode": "library"},
                        read_timeout_seconds=0.3 if index == 0 else 5,
                    )

                tasks = [asyncio.create_task(call_one(index)) for index in range(4)]
                with anyio.fail_after(3):
                    while len(calls) < 4:
                        await anyio.sleep(0.01)
                start = time.monotonic()
                with pytest.raises(MCPError):
                    await session.call_tool(
                        "ask",
                        {"question": "queued-cancelled", "mode": "library"},
                        read_timeout_seconds=0.12,
                    )
                queued_elapsed = time.monotonic() - start
                with pytest.raises(MCPError):
                    await tasks[0]
                await anyio.sleep(0.05)
                assert len(calls) == 4
                start = time.monotonic()
                tools = await session.list_tools()
                discovery_elapsed = time.monotonic() - start
                assert len(tools.tools) == 2
                assert "queued-cancelled" not in calls
                release.set()
                for task in tasks[1:]:
                    result = await task
                    assert result.is_error is False
                await anyio.sleep(0.1)
                assert len(calls) == 4
                (RUN / "cancellation_observation.json").write_text(
                    json.dumps(
                        {
                            "fixture": "synthetic ClientSession stdio and loopback",
                            "network_calls": 4,
                            "cancelled_queued_backend_calls": 0,
                            "queued_cancel_elapsed_seconds": queued_elapsed,
                            "discovery_while_four_sync_io_threads_remain": discovery_elapsed,
                            "executing_cancel_underlying_io_stopped": False,
                            "late_result_observed_by_cancelled_caller": False,
                            "only_io_timeout_no_overall_deadline": True,
                            "product_or_paid_requests": 0,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        worker.join(3)
    assert not worker.is_alive()


def test_actual_slow_stream_exceeds_per_read_timeout_and_documents_inherited_limit():
    chunks = 12
    interval = 0.025

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            raw = json.dumps(ANSWER).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            chunk_size = (len(raw) + chunks - 1) // chunks
            for offset in range(0, len(raw), chunk_size):
                time.sleep(interval)
                self.wfile.write(raw[offset : offset + chunk_size])
                self.wfile.flush()

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        with DianziClient(
            f"http://127.0.0.1:{server.server_port}", SecretStr(KEY), question_timeout_seconds=0.1
        ) as client:
            started = time.monotonic()
            result = client.ask(AskRequest(question="synthetic slow-stream", mode="library"))
            elapsed = time.monotonic() - started
        assert result.freshness == "unknown"
        assert elapsed > 0.1
        (RUN / "inherited_wallclock_observation.json").write_text(
            json.dumps(
                {
                    "fixture": "synthetic real local slow streaming HTTP response",
                    "question_io_timeout_seconds": 0.1,
                    "elapsed_seconds": elapsed,
                    "completed": True,
                    "chunks": chunks,
                    "interval_seconds": interval,
                    "network_calls": 1,
                    "product_or_paid_calls": 0,
                    "scope": (
                        "unchanged SDK documents IO timeout; overall deadline remains a follow-up"
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(3)
    assert not worker.is_alive()
