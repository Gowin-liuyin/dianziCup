"""Explicit unexpected transport-failure injection with synthetic credential marker."""

import asyncio
from pathlib import Path

import httpx
from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.output_budget import McpOutputBudget
from mcp.server.stdio import stdio_server
from pydantic import SecretStr

SYNTHETIC_MARKER = "synthetic-review-secret-marker-no-provider-access-20261016"


def unexpected_failure(request: httpx.Request) -> httpx.Response:
    raise RuntimeError("unexpected transport failure: " + SYNTHETIC_MARKER)


async def main() -> None:
    budget = McpOutputBudget(
        Path(
            "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/"
            "fb374d419588a4632f3f557e76b4b70aebbca790"
        )
    )
    with DianziClient(
        "http://127.0.0.1:43217",
        SecretStr(SYNTHETIC_MARKER),
        transport=httpx.MockTransport(unexpected_failure),
    ) as client:
        server = create_current_read_tool_server(client, budget)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
