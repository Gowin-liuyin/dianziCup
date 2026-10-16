"""Authenticated loopback ASGI entry point using the official MCP transport."""

from __future__ import annotations

import math
import re
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import anyio
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import (
    RequestBodyLimitMiddleware,
    TransportSecurityMiddleware,
    TransportSecuritySettings,
)
from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Message, Receive, Scope, Send

from ai_intel_client.client import (
    ClientConfigurationError,
    DianziApiError,
    DianziClient,
    DianziDeadlineError,
    DianziTransportError,
    ListSourcesRequest,
    ResponseContractError,
    _validate_base_url,
)
from ai_intel_client.mcp_adapter import create_current_read_tool_server
from ai_intel_client.output_budget import McpOutputBudget

MAX_REQUEST_BODY_BYTES = 1048576
CLOSE_DEADLINE_SECONDS = 5
REQUEST_CLIENT_SCOPE_KEY = "dianzi.mcp.request_client"


def _request_client(request: Request) -> DianziClient:
    client = request.scope.get(REQUEST_CLIENT_SCOPE_KEY)
    if not isinstance(client, DianziClient):
        raise ClientConfigurationError("request client is not configured")
    return client


def _security_settings(
    allowed_hosts: Sequence[str], allowed_origins: Sequence[str]
) -> TransportSecuritySettings:
    """Require exact trusted loopback authorities; wildcard ports are unsupported."""
    try:
        if not allowed_hosts or isinstance(allowed_hosts, str) or isinstance(allowed_origins, str):
            raise ValueError
        for host in allowed_hosts:
            parsed = urlsplit("http://" + host)
            if (
                parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.port == 0
                or parsed.netloc != host
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or any(ord(character) <= 32 for character in host)
            ):
                raise ValueError
        for origin in allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.netloc not in allowed_hosts
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError
    except (TypeError, ValueError):
        raise ClientConfigurationError("HTTP transport authorities are invalid") from None
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(allowed_hosts),
        allowed_origins=list(allowed_origins),
    )


def _bearer_credential(request: Request) -> SecretStr:
    values = request.headers.getlist("authorization")
    if len(values) != 1:
        raise ClientConfigurationError("one Bearer credential is required")
    value = values[0]
    if len(value) > 4103 or re.fullmatch(r"(?i:Bearer) [A-Za-z0-9._~+/-]+=*", value) is None:
        raise ClientConfigurationError("Bearer credential is invalid")
    return SecretStr(value[7:])


def _error_response(status: int, code: str, *, retryable: bool = False) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(
        {"error": {"code": code, "retryable": retryable}},
        status_code=status,
        headers=headers,
    )


class _RequestTransport:
    def __init__(
        self,
        manager: StreamableHTTPSessionManager,
        base_url: str,
        security: TransportSecuritySettings,
        request_deadline_seconds: float,
        max_request_body_bytes: int,
    ) -> None:
        self.manager = manager
        self.base_url = base_url
        self.security = TransportSecurityMiddleware(security)
        self.request_deadline_seconds = request_deadline_seconds
        self.request_slots = anyio.CapacityLimiter(4)
        self.bounded_body = RequestBodyLimitMiddleware(
            self._authenticated_request, max_request_body_bytes
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        response_started = False

        async def track_response(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            with anyio.fail_after(self.request_deadline_seconds):
                async with self.request_slots:
                    incoming, outgoing = anyio.create_memory_object_stream[Message](2)
                    async with incoming, outgoing, anyio.create_task_group() as group:

                        async def receive_messages() -> None:
                            while True:
                                message = await receive()
                                await incoming.send(message)
                                if message["type"] == "http.disconnect":
                                    group.cancel_scope.cancel()
                                    return

                        group.start_soon(receive_messages)
                        await self.bounded_body(scope, outgoing.receive, track_response)
                        group.cancel_scope.cancel()
        except TimeoutError:
            if not response_started:
                await _error_response(504, "backend_deadline_exceeded")(scope, receive, send)
            else:
                raise RuntimeError("HTTP transport cleanup exceeded its deadline") from None
        except Exception:
            if not response_started:
                await _error_response(503, "backend_internal_error")(scope, receive, send)
            else:
                raise RuntimeError("HTTP transport could not finish") from None

    async def _authenticated_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope)
        if len(request.headers.getlist("host")) != 1:
            await _error_response(421, "invalid_host")(scope, receive, send)
            return
        if len(request.headers.getlist("origin")) > 1:
            await _error_response(403, "invalid_origin")(scope, receive, send)
            return
        rejection = await self.security.validate_request(request, is_post=scope["method"] == "POST")
        if rejection is not None:
            await rejection(scope, receive, send)
            return
        try:
            credential = _bearer_credential(request)
            client = DianziClient(self.base_url, credential)
        except ClientConfigurationError:
            await _error_response(401, "invalid_credentials")(scope, receive, send)
            return
        authenticated_scope = dict(scope)
        try:
            try:
                await client.list_sources_async(ListSourcesRequest(limit=1))
            except DianziApiError as error:
                await _error_response(error.status, error.code, retryable=error.retryable)(
                    scope, receive, send
                )
                return
            except DianziDeadlineError:
                await _error_response(504, "backend_deadline_exceeded")(scope, receive, send)
                return
            except DianziTransportError:
                await _error_response(503, "backend_transport_error")(scope, receive, send)
                return
            except ResponseContractError:
                await _error_response(502, "backend_contract_error")(scope, receive, send)
                return
            authenticated_scope[REQUEST_CLIENT_SCOPE_KEY] = client
            await self.manager.handle_request(authenticated_scope, receive, send)
        finally:
            authenticated_scope.pop(REQUEST_CLIENT_SCOPE_KEY, None)
            with anyio.CancelScope(shield=True):
                try:
                    with anyio.fail_after(CLOSE_DEADLINE_SECONDS):
                        await client.aclose()
                except Exception:
                    raise RuntimeError("request client cleanup failed") from None


def create_http_app(
    base_url: str,
    output_budget: McpOutputBudget,
    *,
    allowed_hosts: Sequence[str],
    allowed_origins: Sequence[str] = (),
    request_deadline_seconds: float = 120,
    max_request_body_bytes: int = MAX_REQUEST_BODY_BYTES,
) -> Starlette:
    """Create one stateless six-tool app; the ASGI host owns its lifespan.

    Configuration comes from the trusted caller. Every protocol HTTP request
    consumes one additional backend source-read quota to authenticate its Bearer
    credential, including initialize, discovery and notifications. No OAuth
    issuer or client authorization flow is configured by this entry point.
    """
    origin = _validate_base_url(base_url)
    security = _security_settings(allowed_hosts, allowed_origins)
    if (
        type(request_deadline_seconds) not in {int, float}
        or not math.isfinite(request_deadline_seconds)
        or not 0 < request_deadline_seconds <= 120
        or type(max_request_body_bytes) is not int
        or not 0 < max_request_body_bytes <= MAX_REQUEST_BODY_BYTES
    ):
        raise ClientConfigurationError("HTTP transport limits are invalid")
    server = create_current_read_tool_server(
        None, output_budget, include_extended_tools=True, request_client_factory=_request_client
    )
    manager = StreamableHTTPSessionManager(
        server,
        stateless=True,
        json_response=True,
        security_settings=security,
        max_request_body_size=max_request_body_bytes,
    )
    transport = _RequestTransport(
        manager, origin, security, request_deadline_seconds, max_request_body_bytes
    )

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with manager.run():
            yield

    return Starlette(
        routes=[Route("/mcp", transport, methods=["GET", "POST", "DELETE"])],
        lifespan=lifespan,
    )
