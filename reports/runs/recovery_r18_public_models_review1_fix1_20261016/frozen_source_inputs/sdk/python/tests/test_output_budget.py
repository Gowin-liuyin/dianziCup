"""Pinned tokenizer tests use local official bytes and explicit protocol fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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
    ENCODING_SHA256,
    MAX_TOOL_OUTPUT_BYTES,
    OUTPUT_BUDGET_PROFILE,
    McpOutputBudget,
    OutputBudgetConfigurationError,
    OutputBudgetTokenizationError,
    load_offline_encoding,
)
from mcp import Client
from mcp_types import CallToolResult, TextContent
from pydantic import SecretStr

CACHE_FILE = Path(
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
SYNTHETIC_KEY = "synthetic-test-key-with-no-provider-access"
ID = "00000000-0000-4000-8000-000000000001"
ANSWER = {
    "kind": "completed",
    "answer_id": ID,
    "answer_text": "中文证据不足；🙂 <|endoftext|>",
    "claims": [],
    "citations": [],
    "limitations": ["explicit fixture with unknown evidence"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def official_budget() -> McpOutputBudget:
    return McpOutputBudget(CACHE_FILE)


def test_official_loader_never_touches_network_environment_or_module_globals() -> None:
    environment = os.environ.copy()
    reader = tiktoken.load.read_file_cached
    constructor_loader = tiktoken_ext.openai_public.load_tiktoken_bpe
    with (
        patch("tiktoken.load.read_file", side_effect=AssertionError("network forbidden")) as io,
        patch("requests.get", side_effect=AssertionError("network forbidden")) as network,
    ):
        with ThreadPoolExecutor(max_workers=2) as workers:
            encodings = list(workers.map(load_offline_encoding, [CACHE_FILE, CACHE_FILE]))
        for encoding in encodings:
            for text in ("中文🙂", "ordinary ASCII", "<|endoftext|>"):
                assert encoding.decode(encoding.encode_ordinary(text)) == text
        assert io.call_count == network.call_count == 0
    assert os.environ == environment
    assert tiktoken.load.read_file_cached is reader
    assert tiktoken_ext.openai_public.load_tiktoken_bpe is constructor_loader
    assert encodings[0].name == encodings[1].name == "o200k_base"


@pytest.mark.parametrize("state", ["missing", "empty", "corrupt", "oversized"])
def test_missing_corrupt_cache_is_not_configured_without_download(
    tmp_path: Path, state: str
) -> None:
    cache = tmp_path / "encoding"
    if state == "empty":
        cache.write_bytes(b"")
    elif state == "corrupt":
        cache.write_bytes(b"x" * 3613922)
    elif state == "oversized":
        cache.write_bytes(b"x" * 3613923)
    with patch("requests.get", side_effect=AssertionError("network forbidden")) as network:
        with pytest.raises(OutputBudgetConfigurationError, match="not_configured"):
            load_offline_encoding(cache)
        assert network.call_count == 0
    if cache.exists():
        assert cache.read_bytes() == (b"" if state == "empty" else b"x" * cache.stat().st_size)


def test_verified_encoding_survives_cache_replacement(
    tmp_path: Path, official_budget: McpOutputBudget
) -> None:
    path = tmp_path / "encoding"
    path.write_bytes(CACHE_FILE.read_bytes())
    encoding = load_offline_encoding(path)
    path.write_bytes(b"corrupt after deployment preload")
    text = "并发中文🙂"
    assert encoding.encode_ordinary(text) == official_budget.encoding.encode_ordinary(text)


def test_cache_official_digest_and_profile(official_budget: McpOutputBudget) -> None:
    assert hashlib.sha256(CACHE_FILE.read_bytes()).hexdigest() == ENCODING_SHA256
    assert official_budget.profile == OUTPUT_BUDGET_PROFILE


def test_complete_result_counts_text_structured_and_continuation(
    official_budget: McpOutputBudget,
) -> None:
    text = "证据🙂" * 900
    text_only = CallToolResult(content=[TextContent(text=text)])
    complete = CallToolResult(
        content=[TextContent(text=text)],
        structured_content={"unknown": text, "continuation": text},
    )
    assert official_budget.fits(text_only)
    assert not official_budget.fits(complete)


@pytest.mark.parametrize("token_count,expected", [(7999, True), (8000, True), (8001, False)])
def test_official_exact_token_boundary(
    official_budget: McpOutputBudget, token_count: int, expected: bool
) -> None:
    overhead = (
        len(
            official_budget.encoding.encode_ordinary(
                CallToolResult(content=[TextContent(text=" x")]).model_dump_json(
                    by_alias=True, exclude_none=True
                )
            )
        )
        - 1
    )
    result = CallToolResult(content=[TextContent(text=" x" * (token_count - overhead))])
    actual = len(
        official_budget.encoding.encode_ordinary(
            result.model_dump_json(by_alias=True, exclude_none=True)
        )
    )
    assert actual == token_count
    assert official_budget.fits(result) is expected


def test_byte_ceiling_is_independent_of_token_ceiling(
    official_budget: McpOutputBudget,
) -> None:
    result = CallToolResult(content=[TextContent(text=" " * MAX_TOOL_OUTPUT_BYTES)])
    compact = result.model_dump_json(by_alias=True, exclude_none=True)
    assert len(compact.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES
    with patch.object(
        official_budget.encoding, "encode_ordinary", side_effect=AssertionError("byte guard first")
    ) as encoder:
        assert not official_budget.fits(result)
        assert encoder.call_count == 0


def test_native_regex_stack_failure_is_explicit_not_a_fake_count(
    official_budget: McpOutputBudget,
) -> None:
    result = CallToolResult(content=[TextContent(text=" " * 500000)])
    assert len(result.model_dump_json().encode()) < MAX_TOOL_OUTPUT_BYTES
    assert official_budget.fits(result)

    class PanicException(BaseException):
        """Explicit native-failure-shape injection; no actual panic is claimed."""

        __module__ = "pyo3_runtime"

    with (
        patch.object(
            official_budget.encoding, "encode_ordinary", side_effect=PanicException("synthetic")
        ),
        pytest.raises(OutputBudgetTokenizationError, match="tokenizer_unavailable"),
    ):
        official_budget.fits(result)


@pytest.mark.anyio
async def test_native_tokenizer_failure_stays_a_bounded_tool_error(
    official_budget: McpOutputBudget,
) -> None:
    class PanicException(BaseException):
        """Explicit isolated native-failure injection."""

        __module__ = "pyo3_runtime"

    answer = dict(ANSWER)
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=answer)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, official_budget)) as client:
            with patch.object(
                official_budget.encoding, "encode_ordinary", side_effect=PanicException("synthetic")
            ):
                result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is True
            assert "tokenizer_unavailable" in result.model_dump_json()
            assert official_budget.fits(result)


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
def test_process_control_exceptions_are_not_swallowed(
    official_budget: McpOutputBudget, exception: type[BaseException]
) -> None:
    with (
        patch.object(official_budget.encoding, "encode_ordinary", side_effect=exception()),
        pytest.raises(exception),
    ):
        official_budget.fits(CallToolResult(content=[TextContent(text="synthetic")]))


@pytest.mark.anyio
async def test_formal_result_retains_unicode_unknown_and_complete_citation(
    official_budget: McpOutputBudget,
) -> None:
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=ANSWER)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, official_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is False
            assert result.structured_content == ANSWER
            assert official_budget.fits(result)


@pytest.mark.anyio
@pytest.mark.parametrize("oversized_reference", [False, True])
async def test_oversized_atomic_result_has_hash_and_honest_reference_status(
    official_budget: McpOutputBudget, oversized_reference: bool
) -> None:
    citation = {
        "evidence_id": ID,
        "revision_id": ID,
        "quote": "中文证据" * (6000 if oversized_reference else 1),
        "locator": "page 1",
        "source_uri": "https://example.invalid/explicit-fixture",
    }
    answer = dict(ANSWER, answer_text=" x" * 6000, citations=[citation])
    expected_hash = hashlib.sha256(
        QAAnswer.model_validate_json(json.dumps(answer)).wire_json().encode()
    ).hexdigest()
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=answer)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, official_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is True
            assert official_budget.fits(result)
            error = json.loads(result.content[0].text)["error"]
            assert error["result_sha256"] == expected_hash
            assert error["complete"] is False
            assert error["pagination"] == "not_configured"
            if oversized_reference:
                assert error["references_status"] == "unavailable_within_budget"
                assert "citations" not in error
            else:
                assert error["references_status"] == "complete"
                assert error["citations"] == [citation]


@pytest.mark.parametrize(
    "field,value",
    [
        ("answer_id", ID.replace("-", "")),
        ("answer_id", "{" + ID + "}"),
        ("answer_id", "urn:uuid:" + ID),
        ("started_at", "2026-10-16 00:00:00Z"),
        ("started_at", "2026-10-16T00:00:00+0800"),
        ("started_at", "2026-10-16T00:00:00,123Z"),
        ("started_at", "1760572800"),
    ],
)
@pytest.mark.anyio
async def test_fixed_sdk_wire_format_root_cause_is_rejected_through_mcp(
    official_budget: McpOutputBudget, field: str, value: str
) -> None:
    answer = dict(ANSWER)
    answer[field] = value
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(SYNTHETIC_KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=answer)),
    ) as backend:
        async with Client(create_current_read_tool_server(backend, official_budget)) as client:
            result = await client.call_tool("ask", {"question": "synthetic", "mode": "library"})
            assert result.is_error is True
            assert "backend_contract_error" in result.model_dump_json()


def test_missing_stdio_tokenizer_reports_not_configured_without_stdout(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("DIANZI_MCP_ENCODING_CACHE_FILE", None)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-m", "ai_intel_client.mcp_stdio"],
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
        cwd=tmp_path,
    )
    assert result.returncode == 3
    assert result.stdout == b""
    assert json.loads(result.stderr)["error"]["code"] == "not_configured"
