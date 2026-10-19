"""Reviewer-owned negative cases for queue cancellation and late backend work."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from ai_intel_client import http_transport
from ai_intel_client.output_budget import McpOutputBudget
from starlette.types import Message, Scope
from test_http_transport import (
    BASE,
    HOST,
    FixtureBackend,
    anyio_backend,
    backend,
    budget,
    headers,
    open_app,
    rpc,
)


@pytest.mark.anyio
async def test_expired_queue_never_authenticates_after_capacity_returns(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    backend.wait_path = "/api/v1/sources"
    app = http_transport.create_http_app(
        BASE, budget, allowed_hosts=[HOST], request_deadline_seconds=1
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://" + HOST) as client,
    ):
        occupants = [
            asyncio.create_task(client.post("/mcp", headers=headers(), json=rpc("tools/list")))
            for _ in range(4)
        ]
        async with asyncio.timeout(1):
            while backend.active < 4:
                await asyncio.sleep(0.001)
        app.routes[0].app.request_deadline_seconds = 0.03
        queued = await client.post("/mcp", headers=headers(), json=rpc("tools/list"))
        assert queued.status_code == 504 and len(backend.calls) == 4
        backend.release.set()
        responses = await asyncio.gather(*occupants)
        await asyncio.sleep(0.04)
        assert all(response.status_code == 200 for response in responses)
    assert len(backend.calls) == len(backend.closed) == 4 and backend.active == 0


@pytest.mark.anyio
async def test_disconnect_during_incomplete_body_makes_no_authentication_request(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    app = http_transport.create_http_app(BASE, budget, allowed_hosts=[HOST])
    request_headers = headers()
    request_headers.update({"host": HOST, "content-type": "application/json"})
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/mcp",
        "raw_path": b"/mcp",
        "query_string": b"",
        "root_path": "",
        "headers": [(key.lower().encode(), value.encode()) for key, value in request_headers.items()],
        "client": ("127.0.0.1", 1111),
        "server": ("127.0.0.1", 8765),
    }
    messages = iter([
        {"type": "http.request", "body": b'{"jsonrpc":', "more_body": True},
        {"type": "http.disconnect"},
    ])
    sent: list[Message] = []

    async def receive() -> Message:
        return next(messages)

    async def send(message: Message) -> None:
        sent.append(message)

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(app(scope, receive, send), 1)
    assert sent == [] and backend.calls == [] and backend.transports == []


@pytest.mark.anyio
@pytest.mark.parametrize("modern", [False, True])
async def test_timed_out_tool_cannot_resume_io_when_fixture_backend_is_released(
    backend: FixtureBackend, budget: McpOutputBudget, modern: bool
) -> None:
    backend.wait_path = "/api/v1/ask"
    before = asyncio.all_tasks()
    async with open_app(budget, request_deadline_seconds=0.04) as client:
        response = await client.post(
            "/mcp",
            headers=headers(modern=modern, method="tools/call", name="ask"),
            json=rpc("tools/call", {"name": "ask", "arguments": {"question": "late", "mode": "library"}}, modern=modern),
        )
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "backend_deadline_exceeded"
        assert len(backend.calls) == 2 and backend.active == 0 and len(backend.closed) == 1
        backend.release.set()
        await asyncio.sleep(0.04)
    await asyncio.sleep(0)
    assert len(backend.calls) == 2 and backend.active == 0 and len(backend.closed) == 1
    assert not [task for task in asyncio.all_tasks() - before if not task.done()]
    assert "Bearer" not in json.dumps(response.json())
