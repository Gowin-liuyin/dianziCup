"""Independent synthetic protocol checks; no product credentials or external service."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import tiktoken.load
import tiktoken_ext.openai_public
from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.models import QAAnswer
from ai_intel_client.output_budget import (
    MAX_TOOL_OUTPUT_BYTES,
    McpOutputBudget,
    OutputBudgetConfigurationError,
    load_offline_encoding,
)
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    PROTOCOL_VERSION_META_KEY,
    SERVER_INFO_META_KEY,
    CallToolResult,
    TextContent,
)
from pydantic import SecretStr

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CACHE = Path(
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
KEY = "synthetic-independent-only-no-provider-access-20261016"
ID = "00000000-0000-4000-8000-000000000071"
CITATION = {
    "evidence_id": ID,
    "revision_id": ID,
    "quote": "已明确范围中的原文；🙂",
    "locator": "page 2, paragraph 3",
    "source_uri": "https://example.invalid/synthetic-revision/71",
}
ANSWER = {
    "kind": "completed",
    "answer_id": ID,
    "answer_text": "版本缺失，保持未知；🙂",
    "claims": [{"text": "原文存在明确范围", "kind": "source_fact", "support_ids": [ID]}],
    "citations": [CITATION],
    "limitations": ["独立合成夹具，没有实际资产版本"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}
OBSERVATIONS = {}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def budget():
    return McpOutputBudget(CACHE)


@pytest.fixture(scope="module", autouse=True)
def save_observations():
    yield
    (RUN / "independent_observations.json").write_text(
        json.dumps(OBSERVATIONS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def count(budget, result):
    raw = result.model_dump_json(by_alias=True, exclude_none=True)
    return len(budget.encoding.encode_ordinary(raw)), len(raw.encode("utf-8"))


def protocol_result(record):
    text = QAAnswer.model_validate_json(json.dumps(record)).wire_json()
    return CallToolResult(
        _meta={SERVER_INFO_META_KEY: {"name": "dianzi-current-read-tools", "version": "0.1.0"}},
        content=[TextContent(text=text)],
        structured_content=json.loads(text),
    )


@pytest.mark.parametrize("tokens,expected", [(7999, True), (8000, True), (8001, False)])
def test_full_final_token_difference_one(budget, tokens, expected):
    result = CallToolResult(
        _meta={SERVER_INFO_META_KEY: {"name": "dianzi-current-read-tools", "version": "0.1.0"}},
        content=[TextContent(text=" z")],
        structured_content={
            "status": "unknown",
            "continuation": {"cursor": "synthetic", "complete": False},
        },
    )
    baseline, _ = count(budget, result)
    result.content[0].text = " z" * (tokens - baseline + 1)
    actual, size = count(budget, result)
    assert actual == tokens
    assert budget.fits(result) is expected
    OBSERVATIONS[f"final_token_{tokens}"] = {
        "tokens": actual,
        "utf8_bytes": size,
        "fits": expected,
        "includes_text_structured_continuation_serverInfo": True,
    }


@pytest.mark.parametrize("delta,expected", [(-1, True), (0, True), (1, False)])
def test_final_byte_difference_one_orthogonal_guard(budget, delta, expected):
    result = CallToolResult(
        _meta={SERVER_INFO_META_KEY: {"name": "dianzi-current-read-tools", "version": "0.1.0"}},
        content=[TextContent(text="")],
    )
    overhead = len(result.model_dump_json(by_alias=True, exclude_none=True).encode())
    result.content[0].text = " " * (MAX_TOOL_OUTPUT_BYTES + delta - overhead)
    assert (
        len(result.model_dump_json(by_alias=True, exclude_none=True).encode())
        == MAX_TOOL_OUTPUT_BYTES + delta
    )
    with patch.object(budget.encoding, "encode_ordinary", return_value=[0]) as token_counter:
        assert budget.fits(result) is expected
        assert token_counter.call_count == (1 if expected else 0)
    OBSERVATIONS[f"byte_guard_{delta}"] = {
        "bytes": MAX_TOOL_OUTPUT_BYTES + delta,
        "fits": expected,
        "token_counter_injection": "explicit synthetic one-token signal; only byte boundary proven",
    }


def test_pinned_reader_isolated_from_globals_environment_and_concurrent_invalid_load(
    tmp_path, budget
):
    before_environment = os.environ.copy()
    reader = tiktoken.load.read_file_cached
    loader = tiktoken_ext.openai_public.load_tiktoken_bpe
    missing = tmp_path / "missing"
    corrupt = tmp_path / "corrupt"
    corrupt.write_bytes(CACHE.read_bytes()[:-1] + b"!")

    def load_one(path):
        try:
            return load_offline_encoding(path).encode_ordinary("中文🙂 <|endoftext|>")
        except OutputBudgetConfigurationError as error:
            return str(error)

    with (
        patch(
            "tiktoken.load.read_file", side_effect=AssertionError("forbidden network")
        ) as cached_io,
        patch("requests.get", side_effect=AssertionError("forbidden network")) as request_io,
    ):
        with ThreadPoolExecutor(max_workers=3) as workers:
            results = list(workers.map(load_one, [CACHE, missing, corrupt]))
        assert cached_io.call_count == request_io.call_count == 0
    assert results == [
        budget.encoding.encode_ordinary("中文🙂 <|endoftext|>"),
        "not_configured",
        "not_configured",
    ]
    assert os.environ == before_environment
    assert tiktoken.load.read_file_cached is reader
    assert tiktoken_ext.openai_public.load_tiktoken_bpe is loader
    OBSERVATIONS["concurrent_loader"] = {
        "valid": 1,
        "invalid": 2,
        "network_calls": 0,
        "environment_or_global_mutations": 0,
    }


@pytest.mark.anyio
async def test_official_clientsession_real_stdio_current_unicode_atomic_limit_and_metadata(budget):
    lower = 0
    upper = 5000
    while lower + 1 < upper:
        candidate = (lower + upper) // 2
        if count(budget, protocol_result(dict(ANSWER, answer_text=" z" * candidate)))[0] <= 8000:
            lower = candidate
        else:
            upper = candidate
    boundary = dict(ANSWER, answer_text=" z" * lower)
    over = dict(ANSWER, answer_text=" z" * (lower + 1))
    assert count(budget, protocol_result(boundary))[0] <= 8000
    assert count(budget, protocol_result(over))[0] > 8000
    response_map = {"small": ANSWER, "boundary": boundary, "over": over}
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            calls.append(
                {
                    "path": self.path,
                    "authenticated_with_synthetic_key": self.headers.get("authorization")
                    == "Bearer " + KEY,
                }
            )
            raw = json.dumps(response_map[body["question"]], ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ai_intel_client.mcp_stdio"],
            cwd=ROOT,
            env={
                "PYTHONPATH": str(ROOT / "sdk/python"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONIOENCODING": "ascii",
                "DIANZI_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "DIANZI_API_KEY": KEY,
                "DIANZI_MCP_ENCODING_CACHE_FILE": str(CACHE),
            },
        )
        with (RUN / "clientsession_stdio_stderr.log").open("w", encoding="utf-8") as stderr:
            async with (
                stdio_client(params, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream, read_timeout_seconds=10) as session,
            ):
                discovered = await session.discover()
                listed = await session.list_tools()
                assert [tool.name for tool in listed.tools] == ["ask", "check_stack"]
                for question, expected in response_map.items():
                    result = await session.call_tool(
                        "ask", {"question": question, "mode": "library"}
                    )
                    final_count, final_size = count(budget, result)
                    assert final_count <= 8000 and final_size <= MAX_TOOL_OUTPUT_BYTES
                    assert result.meta[SERVER_INFO_META_KEY] == {
                        "name": "dianzi-current-read-tools",
                        "version": "0.1.0",
                    }
                    if question == "over":
                        assert result.is_error is True and result.structured_content is None
                        error = json.loads(result.content[0].text)["error"]
                        assert (
                            error["complete"] is False and error["pagination"] == "not_configured"
                        )
                        assert error["citations"] == [CITATION]
                        assert (
                            error["result_sha256"]
                            == hashlib.sha256(
                                QAAnswer.model_validate_json(json.dumps(expected))
                                .wire_json()
                                .encode()
                            ).hexdigest()
                        )
                    else:
                        assert result.is_error is False
                        assert result.structured_content == expected
                        assert json.loads(result.content[0].text) == expected
                    OBSERVATIONS[f"clientsession_stdio_{question}"] = {
                        "final_tokens": final_count,
                        "final_bytes": final_size,
                        "isError": result.is_error,
                        "metadata_retained": True,
                    }
                OBSERVATIONS["clientsession_discover"] = discovered.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(3)
    assert not worker.is_alive()
    assert len(calls) == 3 and all(call["authenticated_with_synthetic_key"] for call in calls)
    assert all(call["path"] == "/api/v1/ask" for call in calls)
    OBSERVATIONS["stdio_synthetic_loopback"] = {
        "calls": calls,
        "product_requests": 0,
        "paid_requests": 0,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "authorization,host,origin,status",
    [
        (None, "127.0.0.1:43217", "http://127.0.0.1:43217", 200),
        (
            "Bearer synthetic-other-principal-9999999999",
            "127.0.0.1:43217",
            "http://127.0.0.1:43217",
            200,
        ),
        (None, "evil.example:43217", "http://127.0.0.1:43217", 421),
        (None, "127.0.0.1:43217", "https://evil.example", 403),
    ],
)
async def test_modern_http_tools_call_has_no_shared_identity_and_enforces_host_origin(
    budget, authorization, host, origin, status
):
    calls = []
    with DianziClient(
        "http://127.0.0.1:43217",
        SecretStr(KEY),
        transport=httpx.MockTransport(
            lambda request: (calls.append(request), httpx.Response(200, json=ANSWER))[1]
        ),
    ) as backend:
        app = create_current_read_tool_server(backend, budget).streamable_http_app(
            stateless_http=True,
            json_response=True,
            max_request_body_size=1048576,
            transport_security=TransportSecuritySettings(
                allowed_hosts=["127.0.0.1:43217"], allowed_origins=["http://127.0.0.1:43217"]
            ),
        )
        headers = {
            "Accept": "application/json, text/event-stream",
            "host": host,
            "origin": origin,
            "MCP-Protocol-Version": "2026-07-28",
            "MCP-Method": "tools/call",
            "MCP-Name": "ask",
        }
        if authorization:
            headers["authorization"] = authorization
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:43217"
            ) as http,
        ):
            response = await http.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 71,
                    "method": "tools/call",
                    "params": {
                        "name": "ask",
                        "arguments": {"question": "synthetic", "mode": "library"},
                        "_meta": {
                            PROTOCOL_VERSION_META_KEY: "2026-07-28",
                            CLIENT_CAPABILITIES_META_KEY: {},
                        },
                    },
                },
            )
            assert response.status_code == status
            if status == 200:
                wire = response.json()["result"]
                result = CallToolResult.model_validate(wire)
                assert result.is_error is True
                assert json.loads(result.content[0].text) == {"error": {"code": "not_configured"}}
                assert budget.fits(result)
            assert KEY not in response.text
    assert calls == []
    OBSERVATIONS[f"modern_http_{authorization is not None}_{status}"] = {
        "http_status": status,
        "backend_calls": 0,
        "fixture": True,
    }
