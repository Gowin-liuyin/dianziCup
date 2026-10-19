"""Explicit callback fault injection; no actual OS signals or product resources."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.output_budget import McpOutputBudget
from mcp_types import CallToolRequestParams
from pydantic import SecretStr


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit, asyncio.CancelledError])
async def test_base_exceptions_escape_safe_exception_boundary(
    exception: type[BaseException],
) -> None:
    budget = McpOutputBudget(
        Path(
            "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/"
            "fb374d419588a4632f3f557e76b4b70aebbca790"
        )
    )
    with DianziClient(
        "http://127.0.0.1:43217", SecretStr("synthetic-process-control-no-provider-access-20261016")
    ) as backend:
        server = create_current_read_tool_server(backend, budget)
        callback = server._request_handlers["tools/call"].handler

        async def raise_control(*args: object, **kwargs: object) -> None:
            raise exception()

        with (
            patch("ai_intel_client.mcp_adapter.anyio.to_thread.run_sync", new=raise_control),
            pytest.raises(exception),
        ):
            await callback(
                SimpleNamespace(request=None),
                CallToolRequestParams(
                    name="ask",
                    arguments={"question": "explicit control exception", "mode": "library"},
                ),
            )
