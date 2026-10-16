"""Independent explicit synthetic fixture using the actual native asynchronous SDK."""

import asyncio
import os
from pathlib import Path

import httpx
from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.output_budget import McpOutputBudget
from mcp.server.stdio import stdio_server
from pydantic import SecretStr

MARKER = "synthetic-independent-native-error-marker-no-provider-access"


async def fault(request: httpx.Request) -> httpx.Response:
    raise RuntimeError(MARKER)


async def main() -> None:
    options = (
        {"async_transport": httpx.MockTransport(fault)}
        if os.getenv("REVIEW_MODE") == "fault"
        else {}
    )
    async with DianziClient(
        os.environ["REVIEW_ORIGIN"],
        SecretStr(MARKER),
        operation_deadline_seconds=0.08,
        question_deadline_seconds=5,
        **options,
    ) as backend:
        budget = McpOutputBudget(Path(os.environ["REVIEW_CACHE"]))
        server = create_current_read_tool_server(backend, budget)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
