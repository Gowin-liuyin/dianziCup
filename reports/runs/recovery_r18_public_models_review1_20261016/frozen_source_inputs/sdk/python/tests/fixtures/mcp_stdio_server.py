"""Explicit stdio fixture process, isolated from product API keys and live services."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx
import tiktoken
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import McpOutputBudget, create_current_read_tool_server
from mcp.server.stdio import stdio_server

ID = "00000000-0000-4000-8000-000000000001"


async def main() -> None:
    if os.environ.get("DIANZI_MCP_TEST_MODE") != "fixture":
        raise SystemExit("stdio harness requires explicit fixture mode")
    encoding = tiktoken.Encoding(
        "synthetic-byte-vocabulary-fixture",
        pat_str=r"(?s).",
        mergeable_ranks={bytes([value]): value for value in range(256)},
        special_tokens={},
    )
    answer = {
        "kind": "completed",
        "answer_id": ID,
        "answer_text": "explicit stdio fixture",
        "claims": [],
        "citations": [],
        "limitations": ["fixture has no evidence"],
        "freshness": "unknown",
        "data_mode": "fixture",
        "started_at": "2026-10-16T00:00:00Z",
        "completed_at": "2026-10-16T00:00:01Z",
        "latency_milliseconds": 1000,
    }
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr("synthetic-test-key-with-no-provider-access"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=answer)),
    ) as backend:
        server = create_current_read_tool_server(backend, McpOutputBudget.for_fixture(encoding))
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
