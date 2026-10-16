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
    ResponseContractError,
)
from ai_intel_client.models import (
    ASK_RESULT_ADAPTER,
    AskRequest,
    PublicRecord,
    QAAnswer,
    StackCheckRequest,
    StackCheckResult,
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


def _complete_result(record: PublicRecord, budget: McpOutputBudget) -> CallToolResult:
    text = record.wire_json()
    result = CallToolResult(
        _meta=_result_metadata(),
        content=[TextContent(text=text)],
        structured_content=json.loads(text),
    )
    if not budget.fits(result):
        citations = []
        if isinstance(record, QAAnswer):
            citations = [citation.model_dump(mode="json") for citation in record.citations]
        elif isinstance(record, StackCheckResult):
            citations = [
                citation.model_dump(mode="json")
                for assessment in record.results
                for citation in assessment.citations
            ]
        details = {
            "code": "output_budget_exceeded",
            "budget_profile": budget.profile,
            "complete": False,
            "result_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "pagination": "not_configured",
            "references_status": "complete",
            "citations": citations,
        }
        error = CallToolResult(
            _meta=_result_metadata(),
            is_error=True,
            content=[TextContent(text=json.dumps({"error": details}, separators=(",", ":")))],
        )
        if budget.fits(error):
            return error
        details["references_status"] = "unavailable_within_budget"
        details.pop("citations")
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
) -> Server[None]:
    """Expose only implemented shared-backend calls; no HTTP auth or invented endpoints.

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
    tools = [
        Tool(
            name=name,
            description=(
                "Ask the shared backend with traceable source support."
                if name == "ask"
                else "Check component applicability; absence of a match remains unknown."
            ),
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
                        else:
                            return _tool_error("invalid_arguments")
                        result = _complete_result(record, output_budget)
                    if loop.time() >= deadline:
                        raise TimeoutError
                    return result
            if params.name == "ask":
                if not isinstance(validated_request, AskRequest):
                    return _tool_error("invalid_arguments")
                record = await anyio.to_thread.run_sync(
                    partial(client.ask, validated_request), limiter=worker_slots
                )
            else:
                if not isinstance(validated_request, StackCheckRequest):
                    return _tool_error("invalid_arguments")
                record = await anyio.to_thread.run_sync(
                    partial(client.check_stack, validated_request), limiter=worker_slots
                )
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
