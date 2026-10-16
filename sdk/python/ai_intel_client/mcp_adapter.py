"""Official MCP transport handlers for the currently frozen read-tool DTOs."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from functools import partial

import anyio
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import MCPError
from mcp_types import (
    SERVER_INFO_META_KEY,
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)
from mcp_types.jsonrpc import INVALID_PARAMS
from pydantic import ValidationError
from starlette.requests import Request

from ai_intel_client.client import (
    ClientInputError,
    DianziApiError,
    DianziClient,
    DianziDeadlineError,
    DianziTransportError,
    GetTaskResultRequest,
    GetVulnRequest,
    ListSourcesRequest,
    ResponseContractError,
    SearchVulnsRequest,
)
from ai_intel_client.models import (
    ASK_RESULT_ADAPTER,
    AskRequest,
    Citation,
    PublicRecord,
    QAAnswer,
    SourcePage,
    StackCheckEnvelope,
    StackCheckRequest,
    StackCheckResult,
    TaskResultEnvelope,
    Vulnerability,
    VulnerabilityDetailPage,
    VulnerabilityPage,
)
from ai_intel_client.output_budget import McpOutputBudget as McpOutputBudget
from ai_intel_client.output_budget import OutputBudgetTokenizationError

SERVER_NAME = "dianzi-current-read-tools"
SERVER_VERSION = "0.1.0"


def _result_metadata() -> dict[str, object]:
    return {SERVER_INFO_META_KEY: {"name": SERVER_NAME, "version": SERVER_VERSION}}


def _tool_error(code: str) -> CallToolResult:
    return CallToolResult(
        _meta=_result_metadata(),
        is_error=True,
        content=[TextContent(text=json.dumps({"error": {"code": code}}, separators=(",", ":")))],
    )


def _vulnerability_citations(record: Vulnerability) -> list[Citation]:
    return [citation for dimension in record.enrichments for citation in dimension.citations] + [
        citation for relation in record.relations for citation in relation.citations
    ]


def _record_citations(record: PublicRecord) -> list[Citation]:
    if isinstance(record, QAAnswer):
        return list(record.citations)
    if isinstance(record, StackCheckResult):
        return [citation for assessment in record.results for citation in assessment.citations]
    if isinstance(record, StackCheckEnvelope):
        return _record_citations(record.result) + [
            citation for finding in record.risk_summary.findings for citation in finding.citations
        ]
    if isinstance(record, VulnerabilityPage):
        return [citation for item in record.items for citation in _vulnerability_citations(item)]
    if isinstance(record, VulnerabilityDetailPage):
        return _vulnerability_citations(record.vulnerability) + [
            citation for advisory in record.advisories for citation in advisory.citations
        ]
    if isinstance(record, TaskResultEnvelope) and record.result is not None:
        return _record_citations(record.result)
    return []


def _complete_result(record: PublicRecord, budget: McpOutputBudget) -> CallToolResult:
    text = record.wire_json()
    result = CallToolResult(
        _meta=_result_metadata(),
        content=[TextContent(text=text)],
        structured_content=json.loads(text),
    )
    if not budget.fits(result):
        citations = [citation.model_dump(mode="json") for citation in _record_citations(record)]
        details: dict[str, object] = {
            "code": "output_budget_exceeded",
            "budget_profile": budget.profile,
            "complete": False,
            "result_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "pagination": "not_configured",
            "references_status": "complete",
            "citations": citations,
        }
        if isinstance(record, VulnerabilityPage):
            details["result_references"] = [
                f"/api/v1/vulns/{item.event_id}" for item in record.items
            ]
        elif isinstance(record, VulnerabilityDetailPage):
            details["result_references"] = [f"/api/v1/vulns/{record.vulnerability.event_id}"]
        elif isinstance(record, TaskResultEnvelope):
            details["result_references"] = [record.task.poll_uri]
        elif isinstance(record, SourcePage):
            details["result_references"] = ["/api/v1/sources"]
        if (
            isinstance(record, (VulnerabilityPage, VulnerabilityDetailPage, SourcePage))
            and record.next_cursor is not None
        ):
            details["pagination"] = "available"
            details["continuation"] = {"cursor": record.next_cursor}
        error = CallToolResult(
            _meta=_result_metadata(),
            is_error=True,
            content=[TextContent(text=json.dumps({"error": details}, separators=(",", ":")))],
        )
        if budget.fits(error):
            return error
        details["references_status"] = "unavailable_within_budget"
        details.pop("citations")
        error = CallToolResult(
            _meta=_result_metadata(),
            is_error=True,
            content=[TextContent(text=json.dumps({"error": details}, separators=(",", ":")))],
        )
        if budget.fits(error):
            return error
        details.pop("result_references", None)
        details.pop("continuation", None)
        details["pagination"] = "unavailable_within_budget"
        return CallToolResult(
            _meta=_result_metadata(),
            is_error=True,
            content=[TextContent(text=json.dumps({"error": details}, separators=(",", ":")))],
        )
    return result


@asynccontextmanager
async def _server_lifespan(_: Server[None]) -> AsyncIterator[None]:
    yield None


def create_current_read_tool_server(
    client: DianziClient,
    output_budget: McpOutputBudget,
    *,
    include_extended_tools: bool = False,
) -> Server[None]:
    """Keep the old discovery profile and opt into the six frozen read contracts.

    The owning runtime must verify its tokenizer/cache and authenticate transport
    requests before exposing this server. HTTP clients must have a request-bound
    credential; the fixed client supplied here is intended for one stdio identity.
    """
    request_models: dict[str, type[PublicRecord]] = {
        "ask": AskRequest,
        "check_stack": StackCheckRequest,
    }
    output_schemas = {
        "ask": {"type": "object", **ASK_RESULT_ADAPTER.json_schema()},
        "check_stack": StackCheckResult.model_json_schema(),
    }
    descriptions = {
        "ask": "Ask the shared backend with traceable source support.",
        "check_stack": "Check component applicability; absence of a match remains unknown.",
        "search_vulns": "Search visible vulnerability events with bounded cursor pagination.",
        "get_vuln": "Read one visible event and its complete advisories and mapping limits.",
        "get_task_result": "Read the current user's task status without fabricating completion.",
        "list_sources": "Read visible sources and their recorded health, including never_polled.",
    }
    if type(include_extended_tools) is not bool:
        raise ValueError("extended tool profile requires a boolean")
    if include_extended_tools:
        request_models.update(
            {
                "search_vulns": SearchVulnsRequest,
                "get_vuln": GetVulnRequest,
                "get_task_result": GetTaskResultRequest,
                "list_sources": ListSourcesRequest,
            }
        )
        output_schemas.update(
            {
                "search_vulns": VulnerabilityPage.model_json_schema(),
                "get_vuln": VulnerabilityDetailPage.model_json_schema(),
                "get_task_result": TaskResultEnvelope.model_json_schema(),
                "list_sources": SourcePage.model_json_schema(),
            }
        )
    tools = [
        Tool(
            name=name,
            description=descriptions[name],
            input_schema=model.model_json_schema(),
            output_schema=output_schemas[name],
            annotations=ToolAnnotations(
                read_only_hint=True, destructive_hint=False, open_world_hint=True
            ),
        )
        for name, model in request_models.items()
    ]
    worker_slots = anyio.CapacityLimiter(4)

    async def list_tools(
        _: ServerRequestContext[None, Request], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        if params is not None and params.cursor is not None:
            raise MCPError(INVALID_PARAMS, "tool discovery cursor is invalid")
        return ListToolsResult(tools=tools)

    async def call_tool(
        context: ServerRequestContext[None, Request], params: CallToolRequestParams
    ) -> CallToolResult:
        if context.request is not None:
            return _tool_error("not_configured")
        if params.name not in request_models:
            return _tool_error("unknown_tool")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (
            client.question_deadline_seconds
            if params.name == "ask"
            else client.operation_deadline_seconds
        )
        try:
            raw = json.dumps(params.arguments or {}, allow_nan=False).encode("utf-8")
            validated_request = request_models[params.name].model_validate_json(raw)
        except (ValidationError, UnicodeError, ValueError):
            return _tool_error("invalid_arguments")
        record: PublicRecord
        try:
            if client.uses_async_requests:
                async with asyncio.timeout_at(deadline):
                    async with worker_slots:
                        if isinstance(validated_request, AskRequest):
                            record = await client.ask_async(validated_request)
                        elif isinstance(validated_request, StackCheckRequest):
                            record = await client.check_stack_async(validated_request)
                        elif isinstance(validated_request, SearchVulnsRequest):
                            record = await client.search_vulns_async(validated_request)
                        elif isinstance(validated_request, GetVulnRequest):
                            record = await client.get_vuln_async(validated_request)
                        elif isinstance(validated_request, GetTaskResultRequest):
                            record = await client.get_task_result_async(validated_request)
                        elif isinstance(validated_request, ListSourcesRequest):
                            record = await client.list_sources_async(validated_request)
                        else:
                            return _tool_error("invalid_arguments")
                        result = _complete_result(record, output_budget)
                    if loop.time() >= deadline:
                        raise TimeoutError
                    return result
            if isinstance(validated_request, AskRequest):
                record = await anyio.to_thread.run_sync(
                    partial(client.ask, validated_request), limiter=worker_slots
                )
            elif isinstance(validated_request, StackCheckRequest):
                record = await anyio.to_thread.run_sync(
                    partial(client.check_stack, validated_request), limiter=worker_slots
                )
            elif isinstance(validated_request, SearchVulnsRequest):
                record = await anyio.to_thread.run_sync(
                    partial(client.search_vulns, validated_request), limiter=worker_slots
                )
            elif isinstance(validated_request, GetVulnRequest):
                record = await anyio.to_thread.run_sync(
                    partial(client.get_vuln, validated_request), limiter=worker_slots
                )
            elif isinstance(validated_request, GetTaskResultRequest):
                record = await anyio.to_thread.run_sync(
                    partial(client.get_task_result, validated_request), limiter=worker_slots
                )
            elif isinstance(validated_request, ListSourcesRequest):
                record = await anyio.to_thread.run_sync(
                    partial(client.list_sources, validated_request), limiter=worker_slots
                )
            else:
                return _tool_error("invalid_arguments")
            return _complete_result(record, output_budget)
        except ClientInputError:
            return _tool_error("backend_request_error")
        except DianziApiError as error:
            return _tool_error(error.code)
        except (DianziDeadlineError, TimeoutError):
            return _tool_error("backend_deadline_exceeded")
        except DianziTransportError:
            return _tool_error("backend_transport_error")
        except ResponseContractError:
            return _tool_error("backend_contract_error")
        except OutputBudgetTokenizationError:
            return _tool_error("tokenizer_unavailable")
        except Exception:
            return _tool_error("backend_internal_error")

    def input_schema(name: str) -> Mapping[str, object] | None:
        model = request_models.get(name)
        return None if model is None else model.model_json_schema()

    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        lifespan=_server_lifespan,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        get_tool_input_schema=input_schema,
    )
