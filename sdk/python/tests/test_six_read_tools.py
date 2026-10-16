"""Explicit six-tool fixtures cover strict contracts and real local IO boundaries."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
import pytest
from ai_intel_client.client import (
    ClientInputError,
    DianziApiError,
    DianziClient,
    DianziDeadlineError,
    GetTaskResultRequest,
    GetVulnRequest,
    ListSourcesRequest,
    ResponseContractError,
    SearchVulnsRequest,
)
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.models import PublicRecord
from ai_intel_client.output_budget import McpOutputBudget
from mcp import Client
from mcp.client import stdio as stdio_module
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.stdio import stdio_server
from pydantic import SecretStr
from r18_test_paths import RUN
from test_independent_stdio_boundary import ObservedProcess

EVENT_ID = "00000000-0000-4000-8000-000000000111"
INTEL_ID = "00000000-0000-4000-8000-000000000222"
TASK_ID = "00000000-0000-4000-8000-000000000333"
OTHER_ID = "00000000-0000-4000-8000-000000000444"
KEY = "synthetic-six-read-tools-only-no-provider-access"
CACHE = Path(
    "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790"
)
ROOT = Path(__file__).resolve().parents[3]
VULNERABILITY = {
    "intel_id": INTEL_ID,
    "event_id": EVENT_ID,
    "title": "Explicit fixture; unknown enrichment remains unknown",
    "external_ids": ["CVE-2026-00001"],
    "enrichments": [],
    "relations": [],
    "freshness": "unknown",
}
VULN_PAGE = {"items": [VULNERABILITY], "next_cursor": None, "data_mode": "fixture"}
DETAIL = {
    "vulnerability": VULNERABILITY,
    "advisories": [],
    "next_cursor": None,
    "mapping_limits": ["No archived advisories in this explicit fixture"],
    "data_mode": "fixture",
}
SOURCE = {
    "source_id": "synthetic-unpolled-source",
    "name": "Explicit unpolled fixture source",
    "category": "structured_vulnerability",
    "enabled": True,
    "health": "never_polled",
    "last_attempt_at": None,
    "last_success_at": None,
    "reason_code": "not_polled",
    "data_mode": "fixture",
}
SOURCE_PAGE = {"items": [SOURCE], "next_cursor": None, "data_mode": "fixture"}
ANSWER = {
    "kind": "completed",
    "answer_id": OTHER_ID,
    "answer_text": "Explicit fixture answer; no live result is claimed",
    "claims": [],
    "citations": [],
    "limitations": ["No live evidence"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}
TASK = {
    "task": {
        "task_id": TASK_ID,
        "task_type": "ask",
        "status": "queued",
        "poll_uri": "/api/v1/tasks/" + TASK_ID,
        "created_at": "2026-10-16T00:00:00Z",
        "updated_at": "2026-10-16T00:00:01Z",
    },
    "result": None,
    "error": None,
    "completed_steps": [],
    "pending_steps": ["execute"],
    "failed_steps": [],
}
TOOL_NAMES = ["ask", "check_stack", "search_vulns", "get_vuln", "get_task_result", "list_sources"]
CASES = [
    ("search_vulns", SearchVulnsRequest(q="fixture +/=?& 中文"), VULN_PAGE, "/api/v1/vulns"),
    (
        "get_vuln",
        GetVulnRequest.model_validate_json(json.dumps({"event_id": EVENT_ID})),
        DETAIL,
        "/api/v1/vulns/" + EVENT_ID,
    ),
    (
        "get_task_result",
        GetTaskResultRequest.model_validate_json(json.dumps({"task_id": TASK_ID})),
        TASK,
        "/api/v1/tasks/" + TASK_ID,
    ),
    ("list_sources", ListSourcesRequest(), SOURCE_PAGE, "/api/v1/sources"),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def budget() -> McpOutputBudget:
    return McpOutputBudget(CACHE)


def invoke(client: DianziClient, name: str, read_request: PublicRecord) -> PublicRecord:
    if name == "search_vulns" and isinstance(read_request, SearchVulnsRequest):
        return client.search_vulns(read_request)
    if name == "get_vuln" and isinstance(read_request, GetVulnRequest):
        return client.get_vuln(read_request)
    if name == "get_task_result" and isinstance(read_request, GetTaskResultRequest):
        return client.get_task_result(read_request)
    if name == "list_sources" and isinstance(read_request, ListSourcesRequest):
        return client.list_sources(read_request)
    raise AssertionError("unknown explicit fixture case")


async def invoke_async(client: DianziClient, name: str, read_request: PublicRecord) -> PublicRecord:
    if name == "search_vulns" and isinstance(read_request, SearchVulnsRequest):
        return await client.search_vulns_async(read_request)
    if name == "get_vuln" and isinstance(read_request, GetVulnRequest):
        return await client.get_vuln_async(read_request)
    if name == "get_task_result" and isinstance(read_request, GetTaskResultRequest):
        return await client.get_task_result_async(read_request)
    if name == "list_sources" and isinstance(read_request, ListSourcesRequest):
        return await client.list_sources_async(read_request)
    raise AssertionError("unknown explicit fixture case")


@pytest.mark.parametrize("name,read_request,payload,path", CASES)
def test_sync_read_fixed_path_strict_projection_and_bearer_only(
    name: str, read_request: PublicRecord, payload: dict[str, object], path: str
) -> None:
    calls: list[httpx.Request] = []

    def handler(wire: httpx.Request) -> httpx.Response:
        calls.append(wire)
        return httpx.Response(200, json=payload, headers={"Set-Cookie": "fixture=value; Path=/"})

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(handler)
    ) as client:
        result = invoke(client, name, read_request)
        assert json.loads(result.wire_json()) == payload
        invoke(client, name, read_request)
    assert len(calls) == 2
    for call in calls:
        assert call.method == "GET" and call.url.path == path
        assert call.headers["authorization"] == "Bearer " + KEY
        assert "cookie" not in call.headers and "idempotency-key" not in call.headers
        assert call.content == b"" and call.headers["accept-encoding"] == "identity"
    if name == "search_vulns":
        assert calls[0].url.params["q"] == "fixture +/=?& 中文"
        assert calls[0].url.host == "127.0.0.1" and calls[0].url.params["limit"] == "20"


@pytest.mark.anyio
@pytest.mark.parametrize("name,read_request,payload,path", CASES)
async def test_async_read_uses_the_same_public_contract(
    name: str, read_request: PublicRecord, payload: dict[str, object], path: str
) -> None:
    calls: list[httpx.Request] = []

    async def handler(wire: httpx.Request) -> httpx.Response:
        calls.append(wire)
        return httpx.Response(200, json=payload)

    async with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), async_transport=httpx.MockTransport(handler)
    ) as client:
        result = await invoke_async(client, name, read_request)
    assert json.loads(result.wire_json()) == payload
    assert len(calls) == 1 and calls[0].url.path == path


@pytest.mark.parametrize("name,read_request,payload,path", CASES)
@pytest.mark.parametrize("status", [202, 401, 403, 404, 429, 503])
def test_read_status_never_becomes_default_success(
    name: str, read_request: PublicRecord, payload: dict[str, object], path: str, status: int
) -> None:
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(status, json=payload)),
        ) as client,
        pytest.raises(ResponseContractError if status == 202 else DianziApiError),
    ):
        invoke(client, name, read_request)


@pytest.mark.parametrize("name,read_request,payload,path", CASES)
@pytest.mark.parametrize(
    "malformed",
    [b"not-json", b'{"items":[],"items":[]}', b'{"value":NaN}', b'{"tenant_id":"forged"}'],
)
def test_malformed_extra_and_duplicate_json_fail_closed(
    name: str, read_request: PublicRecord, payload: dict[str, object], path: str, malformed: bytes
) -> None:
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(KEY),
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, content=malformed, headers={"Content-Type": "application/json"}
                )
            ),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        invoke(client, name, read_request)


@pytest.mark.parametrize(
    "read_request",
    [
        SearchVulnsRequest.model_construct(limit=True),
        SearchVulnsRequest.model_construct(limit=0),
        SearchVulnsRequest.model_construct(limit=101),
        SearchVulnsRequest.model_construct(q="x" * 4097),
        SearchVulnsRequest.model_construct(q=" \t"),
        SearchVulnsRequest.model_construct(q="\0"),
        SearchVulnsRequest.model_construct(q="\ud800"),
        SearchVulnsRequest.model_construct(cursor="x" * 2049),
        SearchVulnsRequest.model_construct(cursor=""),
        SearchVulnsRequest.model_construct(cursor=None),
        GetVulnRequest.model_construct(event_id="https://example.invalid/private"),
        GetVulnRequest.model_construct(event_id="../assets/" + EVENT_ID),
        GetTaskResultRequest.model_construct(task_id="/api/v1/tasks/" + TASK_ID),
    ],
)
def test_invalid_input_is_rejected_before_transport(read_request: PublicRecord) -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid local input must not dispatch")

    if isinstance(read_request, SearchVulnsRequest):
        name = "search_vulns"
    elif isinstance(read_request, GetVulnRequest):
        name = "get_vuln"
    else:
        name = "get_task_result"
    with (
        DianziClient(
            "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(forbidden)
        ) as client,
        pytest.raises(ClientInputError),
    ):
        invoke(client, name, read_request)


@pytest.mark.parametrize("name,read_request,payload,path", CASES)
def test_response_identity_and_duplicate_objects_are_rejected(
    name: str, read_request: PublicRecord, payload: dict[str, object], path: str
) -> None:
    wrong = copy.deepcopy(payload)
    if name in {"search_vulns", "list_sources"}:
        wrong["items"] = [*payload["items"], *payload["items"]]
    elif name == "get_vuln":
        wrong["vulnerability"]["event_id"] = OTHER_ID
    else:
        wrong["task"]["task_id"] = OTHER_ID
        wrong["task"]["poll_uri"] = "/api/v1/tasks/" + OTHER_ID
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=wrong)),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        invoke(client, name, read_request)


@pytest.mark.parametrize("name", ["search_vulns", "list_sources"])
def test_empty_page_stays_an_explicit_empty_query_scope(name: str) -> None:
    page = {"items": [], "next_cursor": None, "data_mode": "fixture"}
    read_request = SearchVulnsRequest() if name == "search_vulns" else ListSourcesRequest()
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=page)),
    ) as client:
        result = invoke(client, name, read_request)
    assert json.loads(result.wire_json()) == page
    assert "safe" not in result.wire_json() and "clean" not in result.wire_json()


@pytest.mark.parametrize("name", ["search_vulns", "get_vuln", "list_sources"])
def test_server_cannot_exceed_the_requested_page_limit(name: str) -> None:
    if name == "search_vulns":
        payload = copy.deepcopy(VULN_PAGE)
        second = dict(VULNERABILITY, event_id=OTHER_ID)
        payload["items"].append(second)
        read_request = SearchVulnsRequest(limit=1)
    elif name == "list_sources":
        payload = copy.deepcopy(SOURCE_PAGE)
        payload["items"].append(dict(SOURCE, source_id="synthetic-second-source"))
        read_request = ListSourcesRequest(limit=1)
    else:
        payload = copy.deepcopy(DETAIL)
        payload["advisories"] = [
            {
                "intel_id": identity,
                "revision_id": identity,
                "title": "Explicit advisory fixture",
                "source_uri": "https://example.invalid/explicit-fixture",
                "published_at": None,
                "citations": [],
            }
            for identity in (INTEL_ID, OTHER_ID)
        ]
        read_request = GetVulnRequest.model_validate_json(
            json.dumps({"event_id": EVENT_ID, "limit": 1})
        )
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        invoke(client, name, read_request)


@pytest.mark.parametrize("page_mode,item_mode", [("live", "fixture"), ("fixture", "live")])
def test_source_page_cannot_mislabel_fixture_or_live_records(
    page_mode: str, item_mode: str
) -> None:
    payload = dict(SOURCE_PAGE, data_mode=page_mode, items=[dict(SOURCE, data_mode=item_mode)])
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.list_sources(ListSourcesRequest())


@pytest.mark.parametrize(
    "status",
    [
        "queued",
        "running",
        "retry_wait",
        "waiting_approval",
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "blocked",
    ],
)
def test_current_task_state_never_becomes_a_fabricated_answer(status: str) -> None:
    payload = copy.deepcopy(TASK)
    payload["task"]["status"] = status
    if status == "succeeded":
        payload["result"] = ANSWER
        payload["completed_steps"] = ["execute"]
        payload["pending_steps"] = []
    elif status == "partial":
        payload["result"] = ANSWER
        payload["completed_steps"] = ["retrieve"]
    elif status in {"failed", "cancelled", "blocked"}:
        payload["error"] = {
            "type": "urn:dianzi:problem:explicit_fixture",
            "title": "Explicit fixture task failure",
            "status": 503,
            "error": "not_configured",
            "trace_id": OTHER_ID,
        }
        payload["failed_steps"] = ["execute"]
        payload["pending_steps"] = []
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    ) as client:
        result = client.get_task_result(
            GetTaskResultRequest.model_validate_json(json.dumps({"task_id": TASK_ID}))
        )
    assert json.loads(result.wire_json()) == payload
    assert result.task.status == status
    if status not in {"succeeded", "partial"}:
        assert result.result is None


@pytest.mark.parametrize(
    "fault",
    [
        "success_without_result",
        "wrong_kind",
        "unbound_poll_uri",
        "pending_with_result",
        "failed_without_error",
        "duplicate_steps",
    ],
)
def test_task_malformed_kind_state_or_steps_fails_closed(fault: str) -> None:
    payload = copy.deepcopy(TASK)
    if fault == "success_without_result":
        payload["task"]["status"] = "succeeded"
    elif fault == "wrong_kind":
        payload["task"]["status"] = "succeeded"
        payload["task"]["task_type"] = "stack_check"
        payload["result"] = ANSWER
        payload["pending_steps"] = []
    elif fault == "unbound_poll_uri":
        payload["task"]["poll_uri"] = "https://example.invalid/private"
    elif fault == "pending_with_result":
        payload["result"] = ANSWER
    elif fault == "failed_without_error":
        payload["task"]["status"] = "failed"
    else:
        payload["pending_steps"] = ["execute", "execute"]
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(KEY),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.get_task_result(
            GetTaskResultRequest.model_validate_json(json.dumps({"task_id": TASK_ID}))
        )


@pytest.mark.anyio
async def test_mcp_six_tool_discovery_exact_opt_in_and_typed_calls(budget: McpOutputBudget) -> None:
    def handler(wire: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture_payload(wire.url.path))

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(handler)
    ) as backend:
        async with Client(create_current_read_tool_server(backend, budget)) as client:
            assert [tool.name for tool in (await client.list_tools()).tools] == [
                "ask",
                "check_stack",
            ]
        async with Client(
            create_current_read_tool_server(backend, budget, include_extended_tools=True)
        ) as client:
            tools = (await client.list_tools()).tools
            assert [tool.name for tool in tools] == TOOL_NAMES
            assert all(
                tool.annotations.read_only_hint and not tool.annotations.destructive_hint
                for tool in tools
            )
            for name, read_request, payload, _ in CASES:
                result = await client.call_tool(name, json.loads(read_request.wire_json()))
                assert result.is_error is False and result.structured_content == payload
                assert json.loads(result.content[0].text) == payload
                assert budget.fits(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments", [{"tenant_id": "forged"}, {"limit": True}, {"limit": 101}, {"q": "x" * 4097}]
)
async def test_mcp_rejects_identity_and_invalid_parameters_without_backend(
    budget: McpOutputBudget, arguments: dict[str, object]
) -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid MCP arguments must not dispatch")

    with DianziClient(
        "http://127.0.0.1:12345", SecretStr(KEY), transport=httpx.MockTransport(forbidden)
    ) as backend:
        async with Client(
            create_current_read_tool_server(backend, budget, include_extended_tools=True)
        ) as client:
            result = await client.call_tool("search_vulns", arguments)
            assert result.is_error and "invalid_arguments" in result.model_dump_json()


@pytest.mark.anyio
async def test_mcp_large_atomic_page_never_truncates_into_success(budget: McpOutputBudget) -> None:
    page = copy.deepcopy(VULN_PAGE)
    page["items"][0]["title"] = " 中文证据未知🙂" * 4000
    page["next_cursor"] = "explicit-fixture-continuation"
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=page)),
    ) as backend:
        async with Client(
            create_current_read_tool_server(backend, budget, include_extended_tools=True)
        ) as client:
            result = await client.call_tool("search_vulns", {})
            assert result.is_error and result.structured_content is None and budget.fits(result)
            error = json.loads(result.content[0].text)["error"]
            assert error["complete"] is False and error["code"] == "output_budget_exceeded"
            assert error["pagination"] == "available"
            assert error["continuation"]["cursor"] == "explicit-fixture-continuation"
            assert "中文证据未知" not in result.model_dump_json()


@pytest.mark.anyio
async def test_oversized_task_preserves_applicability_and_cvss_support(
    budget: McpOutputBudget,
) -> None:
    applicability = {
        "evidence_id": EVENT_ID,
        "revision_id": INTEL_ID,
        "quote": "Explicit fixture applicable component",
        "locator": "fixture block 1",
        "source_uri": "https://example.invalid/fixture-applicability",
    }
    grading = dict(
        applicability,
        evidence_id=TASK_ID,
        quote="Explicit fixture CVSS source",
        source_uri="https://example.invalid/fixture-cvss",
    )
    payload = copy.deepcopy(TASK)
    payload["task"]["task_type"] = "stack_check"
    payload["task"]["status"] = "succeeded"
    payload["pending_steps"] = []
    payload["completed_steps"] = ["execute"]
    payload["result"] = {
        "result": {
            "kind": "completed",
            "results": [
                {
                    "component": {
                        "ecosystem": "PyPI",
                        "package_name": "synthetic-only",
                        "version": "1",
                    },
                    "status": "supported_applicability",
                    "reason_code": "explicit_fixture",
                    "assessment_id": OTHER_ID,
                    "citations": [applicability],
                    "freshness": "current",
                }
            ],
            "limitations": [" x" * 7000],
        },
        "risk_summary": {
            "policy_version": "r18-risk-policy-1",
            "minimum_severity": "high",
            "confirmation": "confirmed",
            "coverage": "complete",
            "freshness": "current",
            "evaluated_components": 1,
            "unknown_component_indices": [],
            "findings": [
                {
                    "component_index": 0,
                    "event_id": EVENT_ID,
                    "assessment_id": OTHER_ID,
                    "rule_id": INTEL_ID,
                    "rule_version": 1,
                    "grading_claim_id": TASK_ID,
                    "severity": "critical",
                    "cvss_score": 9.8,
                    "cvss_version": "3.1",
                    "citations": [grading],
                    "freshness": "current",
                }
            ],
        },
    }
    with DianziClient(
        "http://127.0.0.1:12345",
        SecretStr(KEY),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    ) as backend:
        async with Client(
            create_current_read_tool_server(backend, budget, include_extended_tools=True)
        ) as client:
            result = await client.call_tool("get_task_result", {"task_id": TASK_ID})
    assert result.is_error and budget.fits(result)
    error = json.loads(result.content[0].text)["error"]
    assert error["complete"] is False and error["references_status"] == "complete"
    assert error["citations"] == [applicability, grading]
    assert error["result_references"] == ["/api/v1/tasks/" + TASK_ID]


def fixture_payload(path: str) -> dict[str, object]:
    if path == "/api/v1/vulns":
        return VULN_PAGE
    if path == "/api/v1/vulns/" + EVENT_ID:
        return DETAIL
    if path == "/api/v1/tasks/" + TASK_ID:
        return TASK
    if path == "/api/v1/sources":
        return SOURCE_PAGE
    if path == "/api/v1/ask":
        return ANSWER
    if path == "/api/v1/stack/check":
        return {"kind": "completed", "results": [], "limitations": ["Explicit empty fixture"]}
    raise AssertionError("fixture received an unexpected fixed path")


class LocalReadBackend:
    """Track one owned local server and close all writers even on Windows peer resets."""

    def __init__(self, phase: str) -> None:
        self.phase = phase
        self.origin = ""
        self.calls: list[str] = []
        self.handlers: set[asyncio.Task[None]] = set()
        self.eof = asyncio.Event()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.active = 0
        self.peak = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        current = asyncio.current_task()
        if current is not None:
            self.handlers.add(current)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            method, path, _ = headers.split(b"\r\n", 1)[0].split(b" ")
            assert method == b"GET"
            self.calls.append(path.decode("ascii"))
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.started.set()
            raw = json.dumps(fixture_payload(urlsplit(path.decode()).path)).encode()
            if self.phase == "headers":
                writer.write(b"HTTP/1.1 200 OK\r\nX-Fixture: ")
                await writer.drain()
                for _ in range(30):
                    writer.write(b"a")
                    await writer.drain()
                    await asyncio.sleep(0.025)
                writer.write(b"\r\n")
            else:
                writer.write(b"HTTP/1.1 200 OK\r\n")
            writer.write(
                b"Content-Type: application/json\r\nConnection: close\r\nContent-Length: "
                + str(len(raw)).encode()
                + b"\r\n\r\n"
            )
            await writer.drain()
            if self.phase == "cancel":
                assert await reader.read() == b""
                self.eof.set()
            elif self.phase == "body":
                for offset in range(0, len(raw), 10):
                    writer.write(raw[offset : offset + 10])
                    await writer.drain()
                    await asyncio.sleep(0.025)
            else:
                writer.write(raw)
                await writer.drain()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.eof.set()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.eof.set()
            self.active -= 1
            if current is not None:
                self.handlers.discard(current)


@asynccontextmanager
async def local_backend(phase: str) -> AsyncIterator[LocalReadBackend]:
    backend = LocalReadBackend(phase)
    server = await asyncio.start_server(backend.handle, "127.0.0.1", 0)
    backend.origin = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    try:
        yield backend
    finally:
        server.close()
        await server.wait_closed()
        tasks = tuple(backend.handlers)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert not backend.handlers and backend.active == 0


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["headers", "body"])
async def test_real_get_total_deadline_includes_slow_complete_response(
    phase: str, record_property: Callable[[str, object], None]
) -> None:
    async with (
        local_backend(phase) as tcp,
        DianziClient(
            tcp.origin, SecretStr(KEY), timeout_seconds=1, operation_deadline_seconds=0.08
        ) as client,
    ):
        start = time.monotonic()
        with pytest.raises(DianziDeadlineError) as expired:
            await client.list_sources_async(ListSourcesRequest())
        elapsed = time.monotonic() - start
        assert elapsed < 0.3 and not expired.value.may_have_executed
        await asyncio.wait_for(tcp.eof.wait(), timeout=1)
        assert len(tcp.calls) == 1
        record_property("complete_deadline_seconds", 0.08)
        record_property("actual_operation_elapsed_seconds", elapsed)
        record_property("actual_loopback_requests", len(tcp.calls))
    record_property("remaining_owned_handlers", len(tcp.handlers))


@pytest.mark.anyio
async def test_real_executing_get_cancellation_closes_peer_socket(
    record_property: Callable[[str, object], None],
) -> None:
    async with local_backend("cancel") as tcp, DianziClient(tcp.origin, SecretStr(KEY)) as client:
        operation = asyncio.create_task(client.search_vulns_async(SearchVulnsRequest()))
        await asyncio.wait_for(tcp.started.wait(), timeout=1)
        start = time.monotonic()
        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await operation
        await asyncio.wait_for(tcp.eof.wait(), timeout=1)
        record_property("cancel_to_peer_eof_seconds", time.monotonic() - start)
        record_property("actual_loopback_requests", len(tcp.calls))
        assert len(tcp.calls) == 1
    record_property("remaining_owned_handlers", len(tcp.handlers))


async def fixture_stdio() -> None:
    if os.environ.get("DIANZI_MCP_TEST_MODE") != "fixture":
        raise RuntimeError("explicit fixture mode is required")
    origin = os.environ.get("DIANZI_FIXTURE_LOOPBACK_ORIGIN")
    if origin:
        async with DianziClient(origin, SecretStr(KEY), operation_deadline_seconds=2) as backend:
            server = create_current_read_tool_server(
                backend, McpOutputBudget(CACHE), include_extended_tools=True
            )
            async with stdio_server() as (reader, writer):
                await server.run(reader, writer, server.create_initialization_options())
    else:
        with DianziClient(
            "http://127.0.0.1:12345",
            SecretStr(KEY),
            transport=httpx.MockTransport(
                lambda read_request: httpx.Response(
                    200, json=fixture_payload(read_request.url.path)
                )
            ),
        ) as backend:
            server = create_current_read_tool_server(
                backend, McpOutputBudget(CACHE), include_extended_tools=True
            )
            async with stdio_server() as (reader, writer):
                await server.run(reader, writer, server.create_initialization_options())


@pytest.mark.anyio
async def test_real_stdio_six_discovery_and_calls_have_protocol_only_stdout() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__)), "--fixture-stdio"],
        cwd=ROOT,
        env={
            "PYTHONPATH": str(ROOT / "sdk/python"),
            "DIANZI_MCP_TEST_MODE": "fixture",
            "SDK_TEST_EVIDENCE_DIR": str(RUN / "stdio_child"),
        },
    )
    processes = []
    stdout_chunks = []
    original_spawn = stdio_module._create_platform_compatible_process

    async def observe_spawn(*args, **kwargs):
        process = await original_spawn(*args, **kwargs)
        processes.append(process)
        return ObservedProcess(process, stdout_chunks)

    stderr_path = RUN / "six_stdio_stderr.log"
    with (
        patch.object(stdio_module, "_create_platform_compatible_process", observe_spawn),
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        async with (
            stdio_client(parameters, errlog=stderr) as (reader, writer),
            ClientSession(reader, writer, read_timeout_seconds=5) as session,
        ):
            await session.discover()
            assert [tool.name for tool in (await session.list_tools()).tools] == TOOL_NAMES
            for name, read_request, payload, _ in CASES:
                result = await session.call_tool(name, json.loads(read_request.wire_json()))
                assert not result.is_error and result.structured_content == payload
            answer = await session.call_tool(
                "ask", {"question": "Explicit six-tool fixture", "mode": "library"}
            )
            stack = await session.call_tool("check_stack", {"components": []})
            assert not answer.is_error and answer.structured_content == ANSWER
            assert not stack.is_error and stack.structured_content["limitations"] == [
                "Explicit empty fixture"
            ]
    raw = b"".join(stdout_chunks)
    (RUN / "six_stdio_stdout.log").write_bytes(raw)
    messages = [json.loads(line) for line in raw.splitlines() if line]
    assert len(messages) >= 7 and all(message["jsonrpc"] == "2.0" for message in messages)
    assert stderr_path.read_bytes() == b"" and KEY.encode() not in raw
    assert len(processes) == 1 and processes[0].returncode == 0


@pytest.mark.anyio
async def test_real_stdio_get_cancellation_closes_owned_process_and_socket(
    record_property: Callable[[str, object], None],
) -> None:
    processes = []
    original_spawn = stdio_module._create_platform_compatible_process

    async def observe_spawn(*args, **kwargs):
        process = await original_spawn(*args, **kwargs)
        processes.append(process)
        return process

    async with local_backend("cancel") as tcp:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__)), "--fixture-stdio"],
            cwd=ROOT,
            env={
                "PYTHONPATH": str(ROOT / "sdk/python"),
                "DIANZI_MCP_TEST_MODE": "fixture",
                "DIANZI_FIXTURE_LOOPBACK_ORIGIN": tcp.origin,
                "SDK_TEST_EVIDENCE_DIR": str(RUN / "cancel_child"),
            },
        )
        stderr_path = RUN / "six_stdio_cancel_stderr.log"
        with (
            patch.object(stdio_module, "_create_platform_compatible_process", observe_spawn),
            stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            async with (
                stdio_client(params, errlog=stderr) as (reader, writer),
                ClientSession(reader, writer, read_timeout_seconds=5) as session,
            ):
                await session.discover()
                start = time.monotonic()
                from mcp.shared.exceptions import MCPError

                with pytest.raises(MCPError):
                    await session.call_tool("list_sources", {}, read_timeout_seconds=0.08)
                await asyncio.wait_for(tcp.eof.wait(), timeout=2)
                assert [tool.name for tool in (await session.list_tools()).tools] == TOOL_NAMES
                assert len(tcp.calls) == 1
                record_property("stdio_call_start_to_peer_eof_seconds", time.monotonic() - start)
                record_property("actual_loopback_requests", len(tcp.calls))
        assert stderr_path.read_bytes() == b""
        assert len(processes) == 1 and processes[0].returncode == 0
        record_property("actual_subprocess_returncode", processes[0].returncode)
    record_property("remaining_owned_handlers", len(tcp.handlers))


if __name__ == "__main__" and sys.argv[1:] == ["--fixture-stdio"]:
    asyncio.run(fixture_stdio())
