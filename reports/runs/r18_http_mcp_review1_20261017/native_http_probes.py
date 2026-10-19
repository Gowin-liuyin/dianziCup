"""Official MCP clients reach the real HTTP entry over fixture-only loopback TCP."""

from __future__ import annotations

import asyncio
import json
import socket
from collections import Counter

import httpx
import httpx2
import pytest
import uvicorn
from ai_intel_client import http_transport
from ai_intel_client.output_budget import McpOutputBudget
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from starlette.types import Message, Scope
from test_http_transport import KEY_A, KEY_B, anyio_backend, budget, headers, rpc
from test_six_read_tools import SOURCE_PAGE, TOOL_NAMES


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_real_official_client_and_native_bearer_backend_probe(
    budget: McpOutputBudget, mode: str, record_property
) -> None:
    calls: list[tuple[str, str]] = []
    handlers: set[asyncio.Task] = set()
    backend_writers = set()
    protocol_requests = []
    slow_started = asyncio.Event()
    slow_peer_eof = asyncio.Event()
    body = json.dumps(SOURCE_PAGE).encode()
    started = asyncio.get_running_loop().time()

    async def backend_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        current = asyncio.current_task()
        handlers.add(current)
        backend_writers.add(writer)
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
            lines = raw.decode("latin-1").split("\r\n")
            method, path, _ = lines[0].split(" ")
            request_headers = dict(line.split(": ", 1) for line in lines[1:] if line)
            key = request_headers.get("Authorization")
            assert method == "GET" and path.startswith("/api/v1/sources?limit=")
            assert key in {"Bearer " + KEY_A, "Bearer " + KEY_B}
            assert not any(name.lower() == "cookie" for name in request_headers)
            assert len(calls) < 20 and asyncio.get_running_loop().time() - started < 8
            calls.append((path, "a" if key == "Bearer " + KEY_A else "b"))
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         b"Connection: close\r\nContent-Length: " + str(len(body)).encode()
                         + b"\r\n\r\n")
            await writer.drain()
            if path == "/api/v1/sources?limit=2":
                slow_started.set()
                assert await asyncio.wait_for(reader.read(), 1) == b""
                slow_peer_eof.set()
            else:
                writer.write(body)
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(current)
            backend_writers.discard(writer)

    backend_server = await asyncio.start_server(backend_handler, "127.0.0.1", 0)
    backend_port = backend_server.sockets[0].getsockname()[1]
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.setblocking(False)
    http_port = listener.getsockname()[1]
    app = http_transport.create_http_app(
        f"http://127.0.0.1:{backend_port}", budget,
        allowed_hosts=[f"127.0.0.1:{http_port}"], request_deadline_seconds=2,
    )

    async def observed_app(scope: Scope, receive, send) -> None:
        if scope["type"] == "http":
            protocol_requests.append(scope["method"])
        await app(scope, receive, send)

    server = uvicorn.Server(uvicorn.Config(observed_app, host="127.0.0.1", log_level="error",
                                           access_log=False, lifespan="on", loop="asyncio"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    url = f"http://127.0.0.1:{http_port}/mcp"
    try:
        async with asyncio.timeout(2):
            while not server.started:
                await asyncio.sleep(0.005)
        async with httpx.AsyncClient(trust_env=False) as unauthenticated:
            rejected = await unauthenticated.post(
                url, headers={"Accept": "application/json, text/event-stream"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
        assert rejected.status_code == 401 and calls == []
        for key in [KEY_A, KEY_B]:
            async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + key},
                                         trust_env=False) as native_http:
                transport = streamable_http_client(url, http_client=native_http)
                async with Client(transport, mode=mode, cache=None, read_timeout_seconds=2) as client:
                    tools = await client.list_tools()
                    assert [tool.name for tool in tools.tools] == TOOL_NAMES
                    result = await client.call_tool("list_sources", {})
                    assert not result.is_error and result.structured_content == SOURCE_PAGE
                    assert json.loads(result.content[0].text) == SOURCE_PAGE and budget.fits(result)
        for owner in ["a", "b"]:
            owner_calls = [path for path, key in calls if key == owner]
            assert owner_calls.count("/api/v1/sources?limit=20") == 1
            assert owner_calls.count("/api/v1/sources?limit=1") >= 2
        async with httpx.AsyncClient(trust_env=False) as disconnecting:
            modern = mode == "2026-07-28"
            cancelled = asyncio.create_task(disconnecting.post(
                url, headers=headers(KEY_A, modern=modern, method="tools/call", name="list_sources"),
                json=rpc("tools/call", {"name": "list_sources", "arguments": {"limit": 2}}, modern=modern),
            ))
            await asyncio.wait_for(slow_started.wait(), 1)
            cancelled.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled
            await asyncio.wait_for(slow_peer_eof.wait(), 1)
        await asyncio.sleep(0.02)
        assert sum(path == "/api/v1/sources?limit=2" for path, _ in calls) == 1
        assert not handlers and not backend_writers
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, 3)
        listener.close()
        backend_server.close()
        await backend_server.wait_closed()
        for handler in tuple(handlers):
            handler.cancel()
        await asyncio.gather(*tuple(handlers), return_exceptions=True)
    assert not handlers and not backend_writers and serving.done()
    for port in [backend_port, http_port]:
        with socket.socket() as closed_probe:
            closed_probe.settimeout(0.2)
            assert closed_probe.connect_ex(("127.0.0.1", port)) != 0
    record_property("fixture_only", True)
    record_property("official_client_mode", mode)
    record_property("protocol_request_count", len(protocol_requests))
    record_property("backend_read_counts", dict(Counter(path for path, _ in calls)))
    record_property("remaining_owned_handlers", 0)
    record_property("remaining_owned_listeners", 0)
    record_property("request_disconnect_closed_backend_peer", slow_peer_eof.is_set())
