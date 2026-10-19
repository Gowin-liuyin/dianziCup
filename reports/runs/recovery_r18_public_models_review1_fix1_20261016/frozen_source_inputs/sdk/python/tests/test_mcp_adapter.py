"""Explicit fixture-only SDK transport tests; no live backend or product credentials."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
import tiktoken
from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import (
    McpOutputBudget,
    create_current_read_tool_server,
)
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp_types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY
from pydantic import SecretStr

SYNTHETIC_KEY = "synthetic-test-key-with-no-provider-access"
ID = "00000000-0000-4000-8000-000000000001"
ANSWER = {
    "kind": "completed",
    "answer_id": ID,
    "answer_text": "synthetic unknown",
    "claims": [],
    "citations": [],
    "limitations": ["fixture has no evidence"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fixture_token_budget() -> McpOutputBudget:
    """Synthetic tokenizer exercises counting code; it is never named o200k_base."""
    encoding = tiktoken.Encoding(
        "synthetic-byte-vocabulary-fixture",
        pat_str=r"(?s).",
        mergeable_ranks={bytes([value]): value for value in range(256)},
        special_tokens={},
    )
    return McpOutputBudget.for_fixture(encoding)


@pytest.mark.anyio
async def test_official_client_discovers_exact_implemented_tools_and_calls_shared_rest(
    fixture_token_budget: McpOutputBudget,
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=ANSWER)

    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(handler),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            listed = await client.list_tools()
            assert [tool.name for tool in listed.tools] == ["ask", "check_stack"]
            assert all(tool.input_schema["additionalProperties"] is False for tool in listed.tools)
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is False
            assert result.structured_content == ANSWER
            assert "fixture" in result.model_dump_json()
    assert len(calls) == 1
    assert calls[0].url.path == "/api/v1/ask"
    assert calls[0].headers["authorization"] == "Bearer " + SYNTHETIC_KEY


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments",
    [
        {"question": "synthetic", "mode": "library", "tenant_id": ID},
        {"question": "synthetic", "mode": "library", "skip_validation": True},
        {"question": "synthetic", "mode": "unsupported"},
        {"question": "synthetic", "mode": "library", "event_ids": "[]"},
    ],
)
async def test_extra_identity_bypass_and_stringified_json_rejected_before_backend(
    fixture_token_budget: McpOutputBudget, arguments: dict[str, object]
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=ANSWER)

    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(handler),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            result = await client.call_tool("ask", arguments)
            assert result.is_error is True
            assert "invalid_arguments" in result.model_dump_json()
    assert calls == []


@pytest.mark.anyio
async def test_queued_handle_preserved_without_answer(
    fixture_token_budget: McpOutputBudget,
) -> None:
    queued = {
        "kind": "task",
        "task_id": ID,
        "status": "queued",
        "poll_uri": "/api/v1/tasks/" + ID,
        "created_at": "2026-10-16T00:00:00Z",
    }
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(202, json=queued)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is False
            assert result.structured_content == queued
            assert "answer_text" not in result.model_dump_json()


@pytest.mark.anyio
async def test_backend_contract_failure_remains_distinct_from_input_failure(
    fixture_token_budget: McpOutputBudget,
) -> None:
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"unexpected": True})),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is True
            assert "backend_contract_error" in result.model_dump_json()


@pytest.mark.anyio
async def test_atomic_output_budget_fails_instead_of_truncating_evidence(
    fixture_token_budget: McpOutputBudget,
) -> None:
    large_answer = dict(ANSWER, answer_text="synthetic " * 900)
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=large_answer)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is True
            assert result.structured_content is None
            assert "output_budget_exceeded" in result.model_dump_json()
            assert "synthetic " not in result.model_dump_json()


@pytest.mark.anyio
async def test_backend_permission_failure_has_no_server_body_or_key(
    fixture_token_budget: McpOutputBudget,
) -> None:
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(403, text="SYNTHETIC_PRIVATE_BACKEND_BODY")
        ),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is True
            assert "http_error" in result.model_dump_json()
            assert "SYNTHETIC_PRIVATE" not in result.model_dump_json()
            assert SYNTHETIC_KEY not in result.model_dump_json()


@pytest.mark.anyio
async def test_stack_unknown_semantics_preserved(
    fixture_token_budget: McpOutputBudget,
) -> None:
    stack = {
        "kind": "completed",
        "results": [],
        "limitations": ["fixture has no inventory"],
    }
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=stack)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            result = await client.call_tool("check_stack", {"components": []})
            assert result.is_error is False
            assert result.structured_content == stack
            assert "clean" not in json.dumps(result.structured_content)


@pytest.mark.anyio
async def test_official_stdio_subprocess_discovery_and_tool_call() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).parent / "fixtures" / "mcp_stdio_server.py")],
        env={"DIANZI_MCP_TEST_MODE": "fixture"},
    )
    async with Client(parameters, read_timeout_seconds=10) as client:
        listed = await client.list_tools()
        assert [tool.name for tool in listed.tools] == ["ask", "check_stack"]
        result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
        assert result.is_error is False
        assert isinstance(result.structured_content, dict)
        assert result.structured_content["data_mode"] == "fixture"
        assert result.structured_content["answer_text"] == "explicit stdio fixture"


@pytest.mark.anyio
async def test_tool_discovery_rejects_unbound_cursor_as_protocol_input_error(
    fixture_token_budget: McpOutputBudget,
) -> None:
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, fixture_token_budget)) as client:
            with pytest.raises(MCPError) as raised:
                await client.list_tools(cursor="unbound-cursor")
            assert raised.value.code == -32602


@pytest.mark.anyio
@pytest.mark.parametrize(
    "host,origin,expected_status",
    [
        ("127.0.0.1:12345", "http://127.0.0.1:12345", 200),
        ("untrusted.example:12345", "http://127.0.0.1:12345", 421),
        ("127.0.0.1:12345", "https://untrusted.example", 403),
    ],
)
async def test_official_http_asgi_discovery_host_and_origin_boundary(
    fixture_token_budget: McpOutputBudget,
    host: str,
    origin: str,
    expected_status: int,
) -> None:
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
    ) as backend:
        server = create_current_read_tool_server(backend, fixture_token_budget)
        app = server.streamable_http_app(
            stateless_http=True,
            json_response=True,
            max_request_body_size=1048576,
            transport_security=TransportSecuritySettings(
                allowed_hosts=["127.0.0.1:12345"],
                allowed_origins=["http://127.0.0.1:12345"],
            ),
        )
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1:12345",
            ) as client,
        ):
            response = await client.post(
                "/mcp",
                headers={
                    "host": host,
                    "origin": origin,
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2026-07-28",
                    "MCP-Method": "tools/list",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {
                        "_meta": {
                            PROTOCOL_VERSION_META_KEY: "2026-07-28",
                            CLIENT_CAPABILITIES_META_KEY: {},
                        }
                    },
                },
            )
            assert response.status_code == expected_status, response.text
            if expected_status == 200:
                body = response.json()
                assert [tool["name"] for tool in body["result"]["tools"]] == [
                    "ask",
                    "check_stack",
                ]
