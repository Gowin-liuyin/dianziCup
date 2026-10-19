"""Explicit loopback/ASGI fixtures for the official MCP and credential boundary."""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anyio
import httpx
import pytest
from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.output_budget import McpOutputBudget
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY
from pydantic import SecretStr

CACHE_FILE = Path(
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
KEY = "synthetic-test-key-with-no-provider-access"
ID = "00000000-0000-4000-8000-000000000001"
ANSWER = {
    "kind": "completed",
    "answer_id": ID,
    "answer_text": "中文证据不足；🙂",
    "claims": [],
    "citations": [],
    "limitations": ["explicit synthetic loopback fixture"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def official_budget() -> McpOutputBudget:
    return McpOutputBudget(CACHE_FILE)


@pytest.mark.anyio
@pytest.mark.parametrize("authorization", [None, "Bearer synthetic-other-identity-token-12345"])
async def test_http_cannot_execute_using_shared_stdio_identity(
    official_budget: McpOutputBudget, authorization: str | None
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=ANSWER)

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(handler)
    ) as backend:
        app = create_current_read_tool_server(backend, official_budget).streamable_http_app(
            stateless_http=True,
            json_response=True,
            max_request_body_size=1048576,
            transport_security=TransportSecuritySettings(
                allowed_hosts=["127.0.0.1:12345"],
                allowed_origins=["http://127.0.0.1:12345"],
            ),
        )
        headers = {
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "MCP-Method": "tools/call",
            "MCP-Name": "ask",
        }
        if authorization is not None:
            headers["authorization"] = authorization
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:12345"
            ) as client,
        ):
            for request_id in (1, 2):
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "tools/call",
                        "params": {
                            "name": "ask",
                            "arguments": {"question": "synthetic", "mode": "library"},
                            "_meta": {
                                PROTOCOL_VERSION_META_KEY: "2026-07-28",
                                CLIENT_CAPABILITIES_META_KEY: {},
                            },
                        },
                    },
                )
                assert response.status_code == 200, response.text
                result = response.json()["result"]
                assert result["isError"] is True
                assert "not_configured" in json.dumps(result)
                assert KEY not in json.dumps(result)
    assert calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,code", [(401, "credential_revoked"), (403, "forbidden"), (429, "rate_limited")]
)
async def test_backend_permission_and_rate_errors_keep_fixed_safe_metadata(
    official_budget: McpOutputBudget, status: int, code: str
) -> None:
    problem = {
        "type": "https://example.invalid/explicit-fixture-error",
        "title": "synthetic",
        "status": status,
        "detail": "SYNTHETIC_PRIVATE_BODY",
        "instance": "/api/v1/ask",
        "trace_id": ID,
        "error": {
            "code": code,
            "message": "SYNTHETIC_PRIVATE_BODY",
            "retryable": status == 429,
            "details": {"private": KEY},
        },
    }
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status,
            json=problem,
            headers={
                "set-cookie": "synthetic=private",
                "content-type": "application/problem+json",
            },
        )

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(handler)
    ) as backend:
        async with Client(create_current_read_tool_server(backend, official_budget)) as client:
            for _ in range(2):
                result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
                serialized = result.model_dump_json()
                assert result.is_error is True
                assert code in serialized
                assert "PRIVATE_BODY" not in serialized
                assert KEY not in serialized
                assert official_budget.fits(result)
    assert len(calls) == 2
    assert all("cookie" not in request.headers for request in calls)


@pytest.mark.anyio
async def test_network_failure_has_no_success_or_automatic_retry(
    official_budget: McpOutputBudget,
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("SYNTHETIC_PRIVATE_NETWORK_ERROR")

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(handler)
    ) as backend:
        async with Client(create_current_read_tool_server(backend, official_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is True
            assert "backend_transport_error" in result.model_dump_json()
            assert "PRIVATE_NETWORK" not in result.model_dump_json()
    assert len(calls) == 1


@pytest.mark.anyio
async def test_parallel_backend_calls_keep_four_worker_bound(
    official_budget: McpOutputBudget,
) -> None:
    lock = threading.Lock()
    active = peak = completed = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal active, peak, completed
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1
            completed += 1
        return httpx.Response(200, json=ANSWER)

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(handler)
    ) as backend:
        async with Client(create_current_read_tool_server(backend, official_budget)) as client:

            async def call_once() -> None:
                result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
                assert result.is_error is False
                assert official_budget.fits(result)

            with anyio.fail_after(10):
                async with anyio.create_task_group() as group:
                    for _ in range(8):
                        group.start_soon(call_once)
    assert completed == 8
    assert peak == 4
    assert active == 0


@pytest.mark.anyio
async def test_real_stdio_entry_discovers_and_calls_loopback_with_ascii_environment(
    official_budget: McpOutputBudget,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []
    deadline = time.monotonic() + 60

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if len(calls) >= 10 or time.monotonic() > deadline:
                self.send_error(503)
                return
            size = int(self.headers.get("content-length", "0"))
            if not 0 < size <= 1048576:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(size))
            calls.append((self.path, self.headers.get("authorization", ""), body))
            raw = json.dumps(ANSWER, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ai_intel_client.mcp_stdio"],
            env={
                "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                "PYTHONIOENCODING": "ascii",
                "DIANZI_API_BASE_URL": "http://127.0.0.1:" + str(server.server_port),
                "DIANZI_API_KEY": KEY,
                "DIANZI_MCP_ENCODING_CACHE_FILE": str(CACHE_FILE),
            },
        )
        async with Client(parameters, read_timeout_seconds=10) as client:
            listed = await client.list_tools()
            assert [tool.name for tool in listed.tools] == ["ask", "check_stack"]
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is False
            assert result.structured_content == ANSWER
            assert official_budget.fits(result)
            assert "io.modelcontextprotocol/serverInfo" in (result.meta or {})
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
    assert not worker.is_alive()
    assert calls == [("/api/v1/ask", "Bearer " + KEY, {"question": "synthetic", "mode": "library"})]
