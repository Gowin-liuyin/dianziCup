"""One-identity stdio entry point with the pinned offline output tokenizer."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp.server.stdio import stdio_server

from ai_intel_client.client import ClientConfigurationError, DianziClient
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.output_budget import McpOutputBudget, OutputBudgetConfigurationError


async def serve_stdio() -> None:
    cache_file = os.environ.get("DIANZI_MCP_ENCODING_CACHE_FILE")
    if not cache_file:
        raise OutputBudgetConfigurationError("not_configured")
    budget = McpOutputBudget(Path(cache_file))
    with DianziClient.from_environment() as backend:
        server = create_current_read_tool_server(backend, budget)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> int:
    try:
        asyncio.run(serve_stdio())
    except (ClientConfigurationError, OutputBudgetConfigurationError):
        sys.stderr.write('{"error":{"code":"not_configured"}}\n')
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
