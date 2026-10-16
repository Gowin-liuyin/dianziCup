"""Explicit ASGI fixtures verify official HTTP protocol and per-request ownership."""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from ai_intel_client import http_transport
from ai_intel_client.client import ClientConfigurationError, DianziClient
from ai_intel_client.output_budget import McpOutputBudget
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    PROTOCOL_VERSION_META_KEY,
    CallToolResult,
)
from pydantic import SecretStr
from starlette.types import Message, Scope
from test_six_read_tools import (
    ANSWER,
    CACHE,
    DETAIL,
    EVENT_ID,
    SOURCE_PAGE,
    TASK,
    TASK_ID,
    TOOL_NAMES,
    VULN_PAGE,
)

KEY_A = "synthetic-http-user-a-no-provider-access"
KEY_B = "synthetic-http-user-b-no-provider-access"
HOST = "127.0.0.1:8765"
BASE = "http://127.0.0.1:12345"
STACK = {
    "kind": "completed",
    "results": [],
    "limitations": ["explicit fixture; no asset claims"],
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def budget() -> McpOutputBudget:
    return McpOutputBudget(CACHE)


def rpc(
    method: str, params: dict[str, object] | None = None, *, modern: bool = False
) -> dict[str, object]:
    body: dict[str, object] = {"jsonrpc": "2.0", "id": 1, "method": method}
    parameters = dict(params or {})
    if modern:
        parameters["_meta"] = {
            PROTOCOL_VERSION_META_KEY: "2026-07-28",
            CLIENT_CAPABILITIES_META_KEY: {},
        }
    if method == "initialize":
        parameters = {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "explicit-fixture", "version": "1"},
        }
    body["params"] = parameters
    return body


def headers(
    key: str = KEY_A, *, modern: bool = False, method: str = "tools/list", name: str = ""
) -> dict[str, str]:
    result = {
        "Authorization": "Bearer " + key,
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28" if modern else "2025-11-25",
    }
    if modern:
        result["MCP-Method"] = method
        if name:
            result["MCP-Name"] = name
    return result


def problem(status: int, code: str) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"Content-Type": "application/problem+json"},
        json={
            "type": "https://example.invalid/explicit-fixture",
            "title": "explicit fixture",
            "status": status,
            "detail": "PRIVATE_FIXTURE_DETAIL",
            "instance": "/api/v1/sources",
            "trace_id": EVENT_ID,
            "error": {
                "code": code,
                "message": "PRIVATE_FIXTURE_DETAIL",
                "retryable": status == 429,
                "details": {"credential": KEY_A},
            },
        },
    )


class FixtureBackend:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.transports: list[httpx.AsyncBaseTransport] = []
        self.closed: list[httpx.AsyncBaseTransport] = []
        self.probe_error: tuple[int, str] | str | None = None
        self.tool_error: tuple[int, str] | str | None = None
        self.answer = copy.deepcopy(ANSWER)
        self.wait_path: str | None = None
        self.wait_key: str | None = None
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.active = self.peak = 0

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        owner = self

        class FixtureTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                owner.calls.append(request)
                owner.active += 1
                owner.peak = max(owner.peak, owner.active)
                try:
                    if request.url.path == owner.wait_path and (
                        owner.wait_key is None
                        or request.headers["authorization"] == "Bearer " + owner.wait_key
                    ):
                        owner.started.set()
                        await owner.release.wait()
                    probe = (
                        request.url.path == "/api/v1/sources"
                        and request.url.params.get("limit") == "1"
                    )
                    error = owner.probe_error if probe else owner.tool_error
                    if isinstance(error, tuple):
                        return problem(*error)
                    if error == "network":
                        raise httpx.ReadError("PRIVATE_FIXTURE_NETWORK")
                    if error == "contract":
                        return httpx.Response(200, json={"private": KEY_A})
                    if error == "internal":
                        raise RuntimeError("PRIVATE_FIXTURE_INTERNAL " + KEY_A)
                    payload = {
                        "/api/v1/sources": SOURCE_PAGE,
                        "/api/v1/vulns": VULN_PAGE,
                        "/api/v1/vulns/" + EVENT_ID: DETAIL,
                        "/api/v1/tasks/" + TASK_ID: TASK,
                        "/api/v1/ask": owner.answer,
                        "/api/v1/stack/check": STACK,
                    }[request.url.path]
                    return httpx.Response(
                        200, json=payload, headers={"set-cookie": "fixture=value"}
                    )
                finally:
                    owner.active -= 1

            async def aclose(self) -> None:
                owner.closed.append(self)

        class FixtureClient(DianziClient):
            def __init__(self, base_url: str, api_key: SecretStr) -> None:
                transport = FixtureTransport()
                super().__init__(base_url, api_key, async_transport=transport)
                owner.transports.append(transport)

        monkeypatch.setattr(http_transport, "DianziClient", FixtureClient)


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> FixtureBackend:
    fixture = FixtureBackend()
    fixture.install(monkeypatch)
    return fixture


@asynccontextmanager
async def open_app(budget: McpOutputBudget, **limits: object) -> AsyncIterator[httpx.AsyncClient]:
    app = http_transport.create_http_app(
        BASE, budget, allowed_hosts=[HOST], allowed_origins=["http://" + HOST], **limits
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://" + HOST) as client,
    ):
        yield client


@pytest.mark.anyio
@pytest.mark.parametrize("modern", [False, True])
async def test_discovery_requires_probe_and_exposes_exact_six_tools(
    backend: FixtureBackend, budget: McpOutputBudget, modern: bool
) -> None:
    async with open_app(budget) as client:
        response = await client.post(
            "/mcp", headers=headers(modern=modern), json=rpc("tools/list", modern=modern)
        )
    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    assert [tool["name"] for tool in tools] == TOOL_NAMES
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)
    assert all("outputSchema" in tool and tool["annotations"]["readOnlyHint"] for tool in tools)
    assert [(call.url.path, dict(call.url.params)) for call in backend.calls] == [
        ("/api/v1/sources", {"limit": "1"})
    ]
    assert len(backend.transports) == len(backend.closed) == 1
    assert KEY_A not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method", ["initialize", "tools/list", "notifications/initialized", "get", "delete"]
)
async def test_all_protocol_requests_require_authentication(
    backend: FixtureBackend, budget: McpOutputBudget, method: str
) -> None:
    async with open_app(budget) as client:
        request_headers = headers()
        request_headers.pop("Authorization")
        if method in {"get", "delete"}:
            response = await client.request(method.upper(), "/mcp", headers=request_headers)
        else:
            response = await client.post("/mcp", headers=request_headers, json=rpc(method))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert backend.calls == [] and backend.transports == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "authorization",
    [
        "Basic synthetic",
        "Bearer short",
        "Bearer " + KEY_A + " ",
        "Bearer " + KEY_A + ",Bearer " + KEY_B,
    ],
)
async def test_malformed_credentials_do_not_create_a_client(
    backend: FixtureBackend, budget: McpOutputBudget, authorization: str
) -> None:
    async with open_app(budget) as client:
        request_headers = headers()
        request_headers["Authorization"] = authorization
        response = await client.post("/mcp", headers=request_headers, json=rpc("tools/list"))
    assert response.status_code == 401
    assert backend.transports == []
    assert KEY_A not in response.text and KEY_B not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    "duplicate,status", [("authorization", 401), ("host", 421), ("origin", 403)]
)
async def test_duplicate_sensitive_headers_are_rejected(
    backend: FixtureBackend, budget: McpOutputBudget, duplicate: str, status: int
) -> None:
    request_headers = [*headers().items(), ("origin", "http://" + HOST)]
    value = {"authorization": "Bearer " + KEY_B, "host": HOST, "origin": "http://" + HOST}[
        duplicate
    ]
    request_headers.extend([(duplicate, value)])
    if duplicate == "host":
        request_headers.append(("host", HOST))
    async with open_app(budget) as client:
        response = await client.post("/mcp", headers=request_headers, json=rpc("tools/list"))
    assert response.status_code == status
    assert backend.calls == [] and backend.transports == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "header,value,status",
    [
        ("host", "attacker.invalid:8765", 421),
        ("host", "127.0.0.1:8765.attacker.invalid", 421),
        ("origin", "https://attacker.invalid", 403),
    ],
)
async def test_origin_host_and_dns_rebinding_rejected_before_auth(
    backend: FixtureBackend, budget: McpOutputBudget, header: str, value: str, status: int
) -> None:
    async with open_app(budget) as client:
        request_headers = headers()
        request_headers[header] = value
        response = await client.post("/mcp", headers=request_headers, json=rpc("tools/list"))
    assert response.status_code == status
    assert backend.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "credential_revoked"),
        (403, "forbidden"),
        (429, "rate_limited"),
        (503, "currentness_unavailable"),
    ],
)
@pytest.mark.parametrize("method", ["initialize", "tools/list"])
async def test_probe_failure_keeps_backend_status_and_safe_code(
    backend: FixtureBackend, budget: McpOutputBudget, status: int, code: str, method: str
) -> None:
    backend.probe_error = (status, code)
    async with open_app(budget) as client:
        response = await client.post("/mcp", headers=headers(), json=rpc(method))
    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "retryable": status == 429}}
    assert "PRIVATE_FIXTURE" not in response.text and KEY_A not in response.text
    assert len(backend.calls) == len(backend.transports) == len(backend.closed) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error,status,code",
    [("network", 503, "backend_transport_error"), ("contract", 502, "backend_contract_error")],
)
async def test_probe_network_and_contract_failures_do_not_initialize(
    backend: FixtureBackend, budget: McpOutputBudget, error: str, status: int, code: str
) -> None:
    backend.probe_error = error
    async with open_app(budget) as client:
        response = await client.post("/mcp", headers=headers(), json=rpc("initialize"))
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert len(backend.calls) == len(backend.closed) == 1


@pytest.mark.anyio
async def test_initialize_and_notification_use_separate_authenticated_clients(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    async with open_app(budget) as client:
        initialized = await client.post("/mcp", headers=headers(), json=rpc("initialize"))
        notification = await client.post(
            "/mcp",
            headers=headers(),
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
    assert initialized.status_code == 200
    assert initialized.json()["result"]["protocolVersion"] == "2025-11-25"
    assert notification.status_code == 202
    assert len(backend.calls) == len(backend.transports) == len(backend.closed) == 2


@pytest.mark.anyio
async def test_revocation_on_later_request_is_not_cached(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    async with open_app(budget) as client:
        first = await client.post("/mcp", headers=headers(), json=rpc("tools/list"))
        backend.probe_error = (401, "credential_revoked")
        second = await client.post("/mcp", headers=headers(), json=rpc("tools/list"))
    assert first.status_code == 200 and second.status_code == 401
    assert second.json()["error"]["code"] == "credential_revoked"
    assert len(backend.transports) == len(backend.closed) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error,code",
    [
        ((401, "credential_revoked"), "credential_revoked"),
        ((403, "forbidden"), "forbidden"),
        ((429, "rate_limited"), "rate_limited"),
        ((503, "not_configured"), "not_configured"),
        ("network", "backend_transport_error"),
        ("contract", "backend_contract_error"),
        ("internal", "backend_internal_error"),
    ],
)
async def test_ask_preserves_real_backend_error_and_closes_client(
    backend: FixtureBackend, budget: McpOutputBudget, error: tuple[int, str] | str, code: str
) -> None:
    backend.tool_error = error
    async with open_app(budget) as client:
        response = await client.post(
            "/mcp",
            headers=headers(),
            json=rpc(
                "tools/call",
                {"name": "ask", "arguments": {"question": "explicit fixture", "mode": "library"}},
            ),
        )
    assert response.status_code == 200
    result = CallToolResult.model_validate(response.json()["result"])
    assert result.is_error is True and json.loads(result.content[0].text)["error"]["code"] == code
    assert "PRIVATE_FIXTURE" not in response.text and KEY_A not in response.text
    assert len(backend.calls) == 2 and len(backend.closed) == 1


@pytest.mark.anyio
async def test_unexpected_probe_failure_does_not_expose_exception(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    backend.probe_error = "internal"
    async with open_app(budget) as client:
        response = await client.post("/mcp", headers=headers(), json=rpc("tools/list"))
    assert (
        response.status_code == 503 and response.json()["error"]["code"] == "backend_internal_error"
    )
    assert "PRIVATE_FIXTURE" not in response.text and KEY_A not in response.text
    assert len(backend.closed) == 1


@pytest.mark.anyio
async def test_slow_authentication_hits_outer_deadline_and_releases_client(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    backend.wait_path = "/api/v1/sources"
    async with open_app(budget, request_deadline_seconds=0.05) as client:
        response = await client.post("/mcp", headers=headers(), json=rpc("initialize"))
    assert response.status_code == 504
    assert len(backend.calls) == len(backend.closed) == 1 and backend.active == 0


@pytest.mark.anyio
@pytest.mark.parametrize("close_fault", ["exception", "timeout"])
async def test_close_failure_after_response_is_a_safe_finite_application_error(
    backend: FixtureBackend,
    budget: McpOutputBudget,
    monkeypatch: pytest.MonkeyPatch,
    close_fault: str,
) -> None:
    client_type = http_transport.DianziClient
    original_close = client_type.aclose

    async def failing_close(client: DianziClient) -> None:
        await original_close(client)
        if close_fault == "timeout":
            await asyncio.sleep(1)
        raise RuntimeError("PRIVATE_FIXTURE_CLOSE " + KEY_A)

    monkeypatch.setattr(client_type, "aclose", failing_close)
    monkeypatch.setattr(http_transport, "CLOSE_DEADLINE_SECONDS", 0.01)
    async with open_app(budget) as client:
        with pytest.raises(RuntimeError, match="HTTP transport could not finish") as raised:
            await client.post("/mcp", headers=headers(), json=rpc("tools/list"))
    assert KEY_A not in str(raised.value) and "PRIVATE_FIXTURE" not in str(raised.value)
    assert len(backend.closed) == 1


@pytest.mark.anyio
async def test_chunked_body_limit_applies_without_content_length(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"x" * 128
        yield b"y" * 129

    async with open_app(budget, max_request_body_bytes=256) as client:
        response = await client.post("/mcp", headers=headers(), content=chunks())
    assert response.status_code == 413
    assert backend.calls == [] and backend.transports == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name,arguments,payload",
    [
        ("ask", {"question": "explicit fixture", "mode": "library"}, ANSWER),
        ("check_stack", {"components": []}, STACK),
        ("search_vulns", {"q": "fixture"}, VULN_PAGE),
        ("get_vuln", {"event_id": EVENT_ID}, DETAIL),
        ("get_task_result", {"task_id": TASK_ID}, TASK),
        ("list_sources", {}, SOURCE_PAGE),
    ],
)
async def test_http_tool_results_keep_complete_wire_schema(
    backend: FixtureBackend,
    budget: McpOutputBudget,
    name: str,
    arguments: dict[str, object],
    payload: dict[str, object],
) -> None:
    async with open_app(budget) as client:
        response = await client.post(
            "/mcp",
            headers=headers(modern=True, method="tools/call", name=name),
            json=rpc("tools/call", {"name": name, "arguments": arguments}, modern=True),
        )
    assert response.status_code == 200
    result = CallToolResult.model_validate(response.json()["result"])
    assert result.is_error is False and result.structured_content == payload
    assert json.loads(result.content[0].text) == payload
    assert budget.fits(result)
    assert len(backend.calls) == 2 and len(backend.closed) == 1
    assert all(
        call.headers["authorization"] == "Bearer " + KEY_A and "cookie" not in call.headers
        for call in backend.calls
    )


@pytest.mark.anyio
async def test_two_users_interleave_without_client_or_credential_reuse(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    backend.wait_path = "/api/v1/ask"
    backend.wait_key = KEY_A
    async with open_app(budget) as client:
        first = asyncio.create_task(
            client.post(
                "/mcp",
                headers=headers(KEY_A),
                json=rpc(
                    "tools/call", {"name": "ask", "arguments": {"question": "a", "mode": "library"}}
                ),
            )
        )
        await asyncio.wait_for(backend.started.wait(), 1)
        second = await client.post(
            "/mcp",
            headers=headers(KEY_B),
            json=rpc("tools/call", {"name": "list_sources", "arguments": {}}),
        )
        backend.release.set()
        first_result = await first
        repeated = await client.post("/mcp", headers=headers(KEY_A), json=rpc("tools/list"))
    assert first_result.status_code == second.status_code == repeated.status_code == 200
    assert [call.headers["authorization"] for call in backend.calls] == [
        "Bearer " + KEY_A,
        "Bearer " + KEY_A,
        "Bearer " + KEY_B,
        "Bearer " + KEY_B,
        "Bearer " + KEY_A,
    ]
    assert len(backend.transports) == len(set(backend.transports)) == len(backend.closed) == 3


@pytest.mark.anyio
@pytest.mark.parametrize(
    "injection",
    [
        {"tenant_id": EVENT_ID},
        {"authorization": "Bearer " + KEY_B},
        {"url": "https://attacker.invalid"},
        {"base_url": "https://attacker.invalid"},
    ],
)
async def test_request_arguments_cannot_inject_identity_or_backend_origin(
    backend: FixtureBackend, budget: McpOutputBudget, injection: dict[str, object]
) -> None:
    async with open_app(budget) as client:
        request_headers = headers()
        request_headers.update(
            {
                "x-forwarded-host": "attacker.invalid",
                "x-forwarded-proto": "https",
                "x-dianzi-api-base-url": "https://attacker.invalid",
            }
        )
        response = await client.post(
            "/mcp",
            headers=request_headers,
            json=rpc("tools/call", {"name": "list_sources", "arguments": injection}),
        )
    result = response.json()["result"]
    assert result["isError"] is True and "invalid_arguments" in json.dumps(result)
    assert len(backend.calls) == 1 and str(backend.calls[0].url).startswith(
        BASE + "/api/v1/sources"
    )
    assert backend.calls[0].headers["authorization"] == "Bearer " + KEY_A


@pytest.mark.anyio
async def test_request_timeout_and_cancellation_close_only_owned_clients(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    backend.wait_path = "/api/v1/ask"
    backend.wait_key = KEY_A
    async with open_app(budget, request_deadline_seconds=0.1) as client:
        timed_out = await client.post(
            "/mcp",
            headers=headers(),
            json=rpc(
                "tools/call", {"name": "ask", "arguments": {"question": "slow", "mode": "library"}}
            ),
        )
        assert timed_out.status_code == 504
        first = asyncio.create_task(
            client.post(
                "/mcp",
                headers=headers(),
                json=rpc(
                    "tools/call",
                    {"name": "ask", "arguments": {"question": "cancel", "mode": "library"}},
                ),
            )
        )
        for _ in range(100):
            if len(backend.calls) >= 4:
                break
            await asyncio.sleep(0.001)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        other = await client.post("/mcp", headers=headers(KEY_B), json=rpc("tools/list"))
    assert other.status_code == 200
    assert len(backend.transports) == len(backend.closed) == 3 and backend.active == 0


@pytest.mark.anyio
async def test_capacity_includes_authentication_and_returns_all_slots(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    backend.wait_path = "/api/v1/sources"
    async with open_app(budget) as client:
        requests = [
            asyncio.create_task(client.post("/mcp", headers=headers(), json=rpc("tools/list")))
            for _ in range(8)
        ]
        for _ in range(100):
            if backend.active == 4:
                break
            await asyncio.sleep(0.001)
        assert backend.active == len(backend.transports) == 4
        backend.release.set()
        responses = await asyncio.gather(*requests)
    assert all(response.status_code == 200 for response in responses)
    assert backend.peak == 4 and backend.active == 0
    assert len(backend.transports) == len(backend.closed) == 8


@pytest.mark.anyio
async def test_body_limit_and_output_budget_do_not_truncate_facts(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    async with open_app(budget, max_request_body_bytes=256) as client:
        oversized = await client.post("/mcp", headers=headers(), content=b"x" * 257)
    assert oversized.status_code == 413 and backend.calls == []
    backend.answer["answer_text"] = "explicit fixture " * 10000
    async with open_app(budget) as client:
        response = await client.post(
            "/mcp",
            headers=headers(),
            json=rpc(
                "tools/call", {"name": "ask", "arguments": {"question": "large", "mode": "library"}}
            ),
        )
    result = CallToolResult.model_validate(response.json()["result"])
    assert result.is_error is True and result.structured_content is None
    assert json.loads(result.content[0].text)["error"]["code"] == "output_budget_exceeded"
    assert budget.fits(result)


@pytest.mark.anyio
async def test_explicit_disconnect_cancels_and_closes_modern_request(
    backend: FixtureBackend, budget: McpOutputBudget
) -> None:
    backend.wait_path = "/api/v1/ask"
    app = http_transport.create_http_app(BASE, budget, allowed_hosts=[HOST])
    body = json.dumps(
        rpc(
            "tools/call",
            {"name": "ask", "arguments": {"question": "disconnect", "mode": "library"}},
            modern=True,
        )
    ).encode()
    request_headers = headers(modern=True, method="tools/call", name="ask")
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
        "headers": [
            (key.lower().encode(), value.encode()) for key, value in request_headers.items()
        ],
        "client": ("127.0.0.1", 1111),
        "server": ("127.0.0.1", 8765),
    }
    initial = True
    sent: list[Message] = []

    async def receive() -> Message:
        nonlocal initial
        if initial:
            initial = False
            return {"type": "http.request", "body": body, "more_body": False}
        await backend.started.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(app(scope, receive, send), 1)
    assert sent == [] and backend.active == 0
    assert len(backend.transports) == len(backend.closed) == 1


@pytest.mark.parametrize(
    "limits",
    [
        {"request_deadline_seconds": 0},
        {"request_deadline_seconds": float("nan")},
        {"request_deadline_seconds": 121},
        {"max_request_body_bytes": True},
        {"max_request_body_bytes": 1048577},
    ],
)
def test_limits_are_finite_and_bounded(budget: McpOutputBudget, limits: dict[str, object]) -> None:
    with pytest.raises(ClientConfigurationError):
        http_transport.create_http_app(BASE, budget, allowed_hosts=[HOST], **limits)


@pytest.mark.parametrize(
    "hosts,origins",
    [
        ([], []),
        (["attacker.invalid:8765"], []),
        (["127.0.0.1:*"], []),
        ([HOST], ["https://attacker.invalid"]),
        ([HOST], ["http://" + HOST + "/path"]),
    ],
)
def test_configuration_requires_exact_loopback_authorities(
    budget: McpOutputBudget, hosts: list[str], origins: list[str]
) -> None:
    with pytest.raises(ClientConfigurationError):
        http_transport.create_http_app(BASE, budget, allowed_hosts=hosts, allowed_origins=origins)
