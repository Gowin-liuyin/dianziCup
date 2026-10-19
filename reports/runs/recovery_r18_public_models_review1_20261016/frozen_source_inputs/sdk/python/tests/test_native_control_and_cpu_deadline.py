"""Approved async-seam control probes and late parsing checks; explicit synthetic fixtures."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from ai_intel_client import client as client_module
from ai_intel_client import mcp_adapter
from ai_intel_client.client import DianziClient, DianziDeadlineError
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.models import AskRequest
from ai_intel_client.output_budget import McpOutputBudget
from mcp_types import CallToolRequestParams
from pydantic import SecretStr

CACHE = Path(
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
KEY = "synthetic-process-control-no-provider-access-20261016"
ANSWER = {
    "kind": "completed",
    "answer_id": "00000000-0000-4000-8000-000000000111",
    "answer_text": "Explicit bounded parsing fixture",
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


@pytest.mark.anyio
@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit, asyncio.CancelledError])
async def test_base_exceptions_escape_native_safe_boundary(exception: type[BaseException]) -> None:
    budget = McpOutputBudget(CACHE)
    async with DianziClient("http://127.0.0.1:43217", SecretStr(KEY)) as backend:
        server = create_current_read_tool_server(backend, budget)
        callback = server._request_handlers["tools/call"].handler

        async def raise_control(*args: object, **kwargs: object) -> None:
            raise exception()

        with patch.object(backend, "ask_async", new=raise_control), pytest.raises(exception):
            await callback(
                SimpleNamespace(request=None),
                CallToolRequestParams(
                    name="ask",
                    arguments={"question": "explicit control exception", "mode": "library"},
                ),
            )


@pytest.mark.anyio
async def test_slow_bounded_json_parser_cannot_return_late_success() -> None:
    original_decode = client_module._decode_response

    def slow_decode(*args, **kwargs):
        time.sleep(0.05)
        return original_decode(*args, **kwargs)

    async with DianziClient(
        "http://127.0.0.1:43217",
        SecretStr(KEY),
        question_deadline_seconds=0.02,
        async_transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
    ) as backend:
        with (
            patch.object(client_module, "_decode_response", new=slow_decode),
            pytest.raises(DianziDeadlineError),
        ):
            await backend.ask_async(AskRequest(question="bounded parser fixture", mode="library"))


@pytest.mark.anyio
async def test_slow_complete_mcp_output_validation_cannot_return_late_success() -> None:
    original_complete = mcp_adapter._complete_result

    def slow_complete(*args, **kwargs):
        time.sleep(0.05)
        return original_complete(*args, **kwargs)

    async with DianziClient(
        "http://127.0.0.1:43217",
        SecretStr(KEY),
        question_deadline_seconds=0.02,
        async_transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
    ) as backend:
        server = create_current_read_tool_server(backend, McpOutputBudget(CACHE))
        callback = server._request_handlers["tools/call"].handler
        with patch.object(mcp_adapter, "_complete_result", new=slow_complete):
            result = await callback(
                SimpleNamespace(request=None),
                CallToolRequestParams(
                    name="ask", arguments={"question": "bounded output fixture", "mode": "library"}
                ),
            )
        assert result.is_error is True
        assert "backend_deadline_exceeded" in result.model_dump_json()
        assert result.structured_content is None


@pytest.mark.anyio
async def test_native_unexpected_transport_exception_preserves_fixed_private_error(capsys) -> None:
    marker = "synthetic-native-credential-marker"

    async def failing(_: httpx.Request) -> httpx.Response:
        raise RuntimeError(marker)

    async with DianziClient(
        "http://127.0.0.1:43217", SecretStr(KEY), async_transport=httpx.MockTransport(failing)
    ) as backend:
        server = create_current_read_tool_server(backend, McpOutputBudget(CACHE))
        callback = server._request_handlers["tools/call"].handler
        result = await callback(
            SimpleNamespace(request=None),
            CallToolRequestParams(
                name="ask",
                arguments={"question": "explicit native error fixture", "mode": "library"},
            ),
        )
        assert result.is_error is True
        assert "backend_internal_error" in result.model_dump_json()
        assert marker not in result.model_dump_json()
        assert KEY not in result.model_dump_json()
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
