"""Explicit native TCP test fixture; no product credentials or external services."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.output_budget import McpOutputBudget
from mcp.server.stdio import stdio_server
from pydantic import SecretStr


async def serve_fixture() -> None:
    async with DianziClient(
        os.environ["DIANZI_FIXTURE_LOOPBACK_ORIGIN"],
        SecretStr("synthetic-native-stdio-fixture-no-provider-access"),
        question_deadline_seconds=5,
        operation_deadline_seconds=0.08,
    ) as backend:
        budget = McpOutputBudget(Path(os.environ["DIANZI_FIXTURE_ENCODING_CACHE"]))
        server = create_current_read_tool_server(backend, budget)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(serve_fixture())
