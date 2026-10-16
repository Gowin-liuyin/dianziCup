"""Bounded fixed-path HTTP operations against the project's shared backend."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import secrets
from collections.abc import Coroutine, Mapping
from typing import TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    TypeAdapter,
    ValidationError,
)

from ai_intel_client.models import (
    ASK_RESULT_ADAPTER,
    AskRequest,
    AskResult,
    PublicRecord,
    PublicUuid,
    QAAnswer,
    SourcePage,
    StackCheckRequest,
    StackCheckResult,
    TaskHandle,
    TaskResultEnvelope,
    VulnerabilityDetailPage,
    VulnerabilityPage,
)

MAX_RESPONSE_BYTES = 1048576
MAX_SYNCHRONOUS_REQUEST_BYTES = 1048576
ResultType = TypeVar("ResultType")


class SearchVulnsRequest(PublicRecord):
    q: str | None = Field(default=None, min_length=1, max_length=4096)
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


class GetVulnRequest(PublicRecord):
    event_id: PublicUuid
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


class GetTaskResultRequest(PublicRecord):
    task_id: PublicUuid


class ListSourcesRequest(PublicRecord):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


class ClientConfigurationError(ValueError):
    """Missing or unsafe client configuration; no configuration value is echoed."""


class ClientInputError(ValueError):
    """Invalid local input before a backend request was sent."""


class ResponseContractError(ValueError):
    """The backend result did not satisfy the frozen response boundary."""


class ApiErrorDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    message: str
    retryable: bool
    details: dict[str, JsonValue]


class ApiProblem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    type: str
    title: str
    status: int = Field(ge=400, le=599)
    detail: str
    instance: str
    error: ApiErrorDetails
    trace_id: str = Field(pattern=r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")


class DianziApiError(RuntimeError):
    """Public fixed error metadata, without server text or response bodies in logs."""

    def __init__(self, status: int, code: str, trace_id: str | None, retryable: bool) -> None:
        super().__init__(f"backend request failed: HTTP {status}")
        self.status = status
        self.code = code
        self.trace_id = trace_id
        self.retryable = retryable


class DianziTransportError(RuntimeError):
    """A POST may have executed; callers can query or reuse its operation key."""

    def __init__(self, idempotency_key: str, may_have_executed: bool) -> None:
        super().__init__("backend request could not be completed")
        self.idempotency_key = idempotency_key
        self.may_have_executed = may_have_executed


class DianziDeadlineError(DianziTransportError):
    """The complete operation exceeded its wallclock budget; no automatic retry."""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_nonfinite_json(_: str) -> object:
    raise ValueError("nonfinite JSON number")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("nonfinite JSON number")
    return parsed


def validate_json_bytes(raw: bytes) -> None:
    """Reject duplicate fields and invalid JSON before typed validation chooses values."""
    try:
        json.loads(
            raw,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonfinite_json,
            parse_float=_parse_finite_float,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise ResponseContractError("response JSON is invalid") from None


def _validate_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
        http_allowed = parsed.scheme == "http" and parsed.hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
        if (
            not value
            or value != value.strip()
            or any(ord(character) <= 32 for character in value)
            or parsed.scheme not in {"http", "https"}
            or (parsed.scheme == "http" and not http_allowed)
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or (port is not None and port == 0)
        ):
            raise ValueError("invalid base URL")
        httpx.URL(value)
    except (ValueError, httpx.InvalidURL):
        raise ClientConfigurationError("backend base URL is invalid") from None
    return value.rstrip("/")


def _validate_operation_key(value: str) -> str:
    if re.fullmatch(r"[\x21-\x7e]{1,200}", value) is None:
        raise ClientInputError("operation key is invalid")
    return value


def _remove_cookie_authentication(request: httpx.Request) -> None:
    """A server's Set-Cookie must not turn subsequent Bearer calls into cookie calls."""
    request.headers.pop("cookie", None)


async def _remove_async_cookie_authentication(request: httpx.Request) -> None:
    _remove_cookie_authentication(request)


def _validate_timeout(value: float, upper_bound: float) -> None:
    if type(value) not in {int, float} or not 0 < value <= upper_bound:
        raise ClientConfigurationError("client timeout is outside the allowed bounds")


def _request_body(request: PublicRecord, model: type[PublicRecord]) -> str:
    if not isinstance(request, model):
        raise ClientInputError("request is invalid")
    try:
        validated = model.model_validate(
            request.model_dump(mode="python", exclude_unset=True, warnings="error")
        )
        body = model.model_validate_json(validated.wire_json()).wire_json()
    except (ValidationError, UnicodeError, ValueError):
        raise ClientInputError("request is invalid") from None
    if len(body.encode("utf-8")) > MAX_SYNCHRONOUS_REQUEST_BYTES:
        raise ClientInputError("synchronous request exceeds the client size boundary")
    return body


def _query_parameters(request: PublicRecord, model: type[PublicRecord]) -> dict[str, str]:
    body = _request_body(request, model)
    validated = model.model_validate_json(body)
    parameters: dict[str, str] = {}
    for name in ("q", "limit", "cursor"):
        if name not in model.model_fields:
            continue
        value: object = getattr(validated, name)
        if value is None:
            if name in validated.model_fields_set:
                raise ClientInputError("query input cannot be explicitly null")
            continue
        if isinstance(value, str):
            if not value.strip() or "\0" in value:
                raise ClientInputError("query input is invalid")
            parameters[name] = value
        elif type(value) is int:
            parameters[name] = str(value)
        else:
            raise ClientInputError("query input is invalid")
    return parameters


def _decode_response[ResultType](
    response: httpx.Response, content: bytes, adapter: TypeAdapter[ResultType]
) -> tuple[int, ResultType]:
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if response.status_code not in {200, 202}:
        problem = None
        if content_type == "application/problem+json":
            try:
                validate_json_bytes(content)
                problem = ApiProblem.model_validate_json(content)
            except (ResponseContractError, ValidationError):
                problem = None
        if problem is None or problem.status != response.status_code:
            raise DianziApiError(response.status_code, "http_error", None, False)
        raise DianziApiError(
            problem.status, problem.error.code, problem.trace_id, problem.error.retryable
        )
    if content_type != "application/json":
        raise ResponseContractError("response content type is invalid")
    validate_json_bytes(content)
    try:
        result = adapter.validate_json(content)
    except ValidationError:
        raise ResponseContractError("response does not match the public contract") from None
    return response.status_code, result


def _check_compression(response: httpx.Response) -> None:
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        raise ResponseContractError("compressed response is outside the client boundary")


def _append_chunk(raw: bytearray, chunk: bytes) -> None:
    if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
        raise ResponseContractError("response exceeds the allowed size")
    raw.extend(chunk)


def _ask_result(status: int, result: AskResult) -> AskResult:
    if (isinstance(result, QAAnswer) and status != 200) or (
        isinstance(result, TaskHandle) and status != 202
    ):
        raise ResponseContractError("answer kind does not match HTTP status")
    return result


def _stack_result(status: int, result: StackCheckResult) -> StackCheckResult:
    if status != 200:
        raise ResponseContractError("synchronous stack result requires HTTP 200")
    return result


def _read_result[ResultType](
    status: int, result: ResultType, parameters: dict[str, str]
) -> ResultType:
    if status != 200:
        raise ResponseContractError("synchronous read result requires HTTP 200")
    if isinstance(result, (VulnerabilityPage, SourcePage)):
        count = len(result.items)
    elif isinstance(result, VulnerabilityDetailPage):
        count = len(result.advisories)
    else:
        return result
    if count > int(parameters["limit"]):
        raise ResponseContractError("read page exceeds its requested limit")
    return result


class DianziClient:
    """No retries, arbitrary URLs, database credentials or duplicated business decisions."""

    def __init__(
        self,
        base_url: str,
        api_key: SecretStr,
        *,
        timeout_seconds: float = 10,
        question_timeout_seconds: float = 100,
        operation_deadline_seconds: float = 10,
        question_deadline_seconds: float = 100,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        origin = _validate_base_url(base_url)
        if not isinstance(api_key, SecretStr):
            raise ClientConfigurationError("API key must use SecretStr")
        credential = api_key.get_secret_value()
        if (
            not 32 <= len(credential) <= 4096
            or re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", credential) is None
        ):
            raise ClientConfigurationError("API key is invalid")
        for value, upper_bound in (
            (timeout_seconds, 60),
            (question_timeout_seconds, 120),
            (operation_deadline_seconds, 60),
            (question_deadline_seconds, 120),
        ):
            _validate_timeout(value, upper_bound)
        if transport is not None and async_transport is not None:
            raise ClientConfigurationError("choose one isolated transport injection")
        self._question_timeout_seconds = question_timeout_seconds
        self._timeout_seconds = timeout_seconds
        self._operation_deadline_seconds = operation_deadline_seconds
        self._question_deadline_seconds = question_deadline_seconds
        self._runner: asyncio.Runner | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._active_operations: set[asyncio.Task[object]] = set()
        self._operation_slots = asyncio.Semaphore(4)
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        headers = {
            "Authorization": "Bearer " + credential,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }
        self._http = (
            None
            if transport is None
            else httpx.Client(
                base_url=origin,
                headers=headers,
                timeout=timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=transport,
                event_hooks={"request": [_remove_cookie_authentication]},
            )
        )
        self._async_http = (
            None
            if transport is not None
            else httpx.AsyncClient(
                base_url=origin,
                headers=headers,
                timeout=timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=async_transport,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
                event_hooks={"request": [_remove_async_cookie_authentication]},
            )
        )

    @property
    def uses_async_requests(self) -> bool:
        """False only for explicitly injected legacy synchronous contract fixtures.

        A synchronous fixture handler cannot be forcefully interrupted. Its old
        compatibility path does not demonstrate product cancellation or deadline.
        """
        return self._async_http is not None

    @property
    def operation_deadline_seconds(self) -> float:
        return self._operation_deadline_seconds

    @property
    def question_deadline_seconds(self) -> float:
        return self._question_deadline_seconds

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> DianziClient:
        configured = os.environ if environment is None else environment
        base_url = configured.get("DIANZI_API_BASE_URL")
        key = configured.get("DIANZI_API_KEY")
        if not base_url or not key:
            raise ClientConfigurationError("backend base URL and API key must be configured")
        return cls(base_url, SecretStr(key))

    def close(self) -> None:
        if self._closed and self._http is not None:
            return
        if self._close_task is not None and self._close_task.done():
            self._close_task.result()
            return
        if self._http is not None:
            self._closed = True
            self._http.close()
            return
        self._check_sync_context()
        runner = self._get_runner()
        try:
            runner.run(self.aclose())
        finally:
            runner.close()
            self._runner = None

    async def aclose(self) -> None:
        """Reject new work immediately; caller cancellation does not cancel owned cleanup.

        A later close awaits the same finite task, including idle pool connections.
        Cleanup still belongs to this client's event loop and must be awaited before
        the owning loop is shut down; it is not an out-of-process cleanup service.
        """
        if self._close_task is not None and self._close_task.done():
            self._close_task.result()
            return
        if self._http is not None:
            if self._closed:
                return
            raise ClientConfigurationError("legacy fixture requires synchronous close")
        self._bind_loop()
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(
                self._close_async_resources(asyncio.current_task()), name="dianzi-client-close"
            )
        await asyncio.shield(self._close_task)

    async def _close_async_resources(self, initiator: asyncio.Task[object] | None) -> None:
        operations = [task for task in self._active_operations if task is not initiator]
        for task in operations:
            task.cancel()
        if operations:
            await asyncio.gather(*operations, return_exceptions=True)
        if self._async_http is not None:
            await self._async_http.aclose()

    def _bind_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not loop:
            raise ClientConfigurationError("client cannot be reused across event loops")
        self._loop = loop
        return loop

    def _check_sync_context(self) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise ClientConfigurationError("running event loop requires async client methods")

    def _get_runner(self) -> asyncio.Runner:
        if self._closed:
            raise ClientConfigurationError("client is closed")
        if self._runner is None:
            if self._loop is not None:
                raise ClientConfigurationError("async client requires aclose on its owning loop")
            self._runner = asyncio.Runner()
        return self._runner

    def _run_sync(self, operation: Coroutine[object, object, ResultType]) -> ResultType:
        try:
            self._check_sync_context()
            runner = self._get_runner()
        except Exception:
            operation.close()
            raise
        return runner.run(operation)

    def __enter__(self) -> DianziClient:
        if self._closed:
            raise ClientConfigurationError("client is closed")
        if self.uses_async_requests:
            self._check_sync_context()
            self._get_runner()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    async def __aenter__(self) -> DianziClient:
        if self._closed or not self.uses_async_requests:
            raise ClientConfigurationError("native async client is required")
        self._bind_loop()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def _request(
        self,
        path: str,
        body: str,
        operation_key: str,
        adapter: TypeAdapter[ResultType],
        timeout_seconds: float,
        *,
        method: str = "POST",
        parameters: dict[str, str] | None = None,
    ) -> tuple[int, ResultType]:
        if self._http is None or self._closed:
            raise ClientConfigurationError("legacy synchronous fixture is unavailable")
        encoded = body.encode("utf-8") if method == "POST" else None
        headers = (
            {"Content-Type": "application/json", "Idempotency-Key": operation_key}
            if method == "POST"
            else None
        )
        try:
            with self._http.stream(
                method,
                path,
                content=encoded,
                headers=headers,
                params=parameters,
                timeout=timeout_seconds,
            ) as response:
                _check_compression(response)
                raw = bytearray()
                for chunk in response.iter_bytes():
                    _append_chunk(raw, chunk)
                return _decode_response(response, bytes(raw), adapter)
        except httpx.HTTPError:
            raise DianziTransportError(operation_key, method == "POST") from None

    async def _request_async(
        self,
        path: str,
        body: str,
        operation_key: str,
        adapter: TypeAdapter[ResultType],
        timeout_seconds: float,
        deadline: float,
        *,
        method: str = "POST",
        parameters: dict[str, str] | None = None,
    ) -> tuple[int, ResultType]:
        loop = self._bind_loop()
        if self._closed or self._async_http is None:
            raise ClientConfigurationError("native async client is unavailable")
        operation = asyncio.current_task()
        if operation is None:
            raise ClientConfigurationError("async operation requires a task")
        self._active_operations.add(operation)
        dispatched = False
        headers = (
            {"Content-Type": "application/json", "Idempotency-Key": operation_key}
            if method == "POST"
            else None
        )
        try:
            async with asyncio.timeout_at(deadline):
                async with self._operation_slots:
                    if loop.time() >= deadline:
                        raise TimeoutError
                    dispatched = True
                    async with self._async_http.stream(
                        method,
                        path,
                        content=body.encode("utf-8") if method == "POST" else None,
                        headers=headers,
                        params=parameters,
                        timeout=timeout_seconds,
                    ) as response:
                        _check_compression(response)
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            _append_chunk(raw, chunk)
                        result = _decode_response(response, bytes(raw), adapter)
                    if loop.time() >= deadline:
                        raise TimeoutError
                    return result
        except TimeoutError:
            raise DianziDeadlineError(operation_key, dispatched and method == "POST") from None
        except httpx.HTTPError:
            raise DianziTransportError(operation_key, dispatched and method == "POST") from None
        finally:
            self._active_operations.discard(operation)

    def _get[ResultType](
        self, path: str, parameters: dict[str, str], model: type[ResultType]
    ) -> ResultType:
        status, result = self._request(
            path,
            "",
            "",
            TypeAdapter(model),
            self._timeout_seconds,
            method="GET",
            parameters=parameters,
        )
        return _read_result(status, result, parameters)

    async def _get_async[ResultType](
        self, path: str, parameters: dict[str, str], model: type[ResultType], deadline: float
    ) -> ResultType:
        status, result = await self._request_async(
            path,
            "",
            "",
            TypeAdapter(model),
            self._timeout_seconds,
            deadline,
            method="GET",
            parameters=parameters,
        )
        result = _read_result(status, result, parameters)
        if self._bind_loop().time() >= deadline:
            raise DianziDeadlineError("", False)
        return result

    def search_vulns(self, request: SearchVulnsRequest) -> VulnerabilityPage:
        if self.uses_async_requests:
            return self._run_sync(self.search_vulns_async(request))
        return self._get(
            "/api/v1/vulns", _query_parameters(request, SearchVulnsRequest), VulnerabilityPage
        )

    async def search_vulns_async(self, request: SearchVulnsRequest) -> VulnerabilityPage:
        deadline = self._bind_loop().time() + self.operation_deadline_seconds
        return await self._get_async(
            "/api/v1/vulns",
            _query_parameters(request, SearchVulnsRequest),
            VulnerabilityPage,
            deadline,
        )

    def get_vuln(self, request: GetVulnRequest) -> VulnerabilityDetailPage:
        if self.uses_async_requests:
            return self._run_sync(self.get_vuln_async(request))
        validated = GetVulnRequest.model_validate_json(_request_body(request, GetVulnRequest))
        result = self._get(
            f"/api/v1/vulns/{validated.event_id}",
            _query_parameters(validated, GetVulnRequest),
            VulnerabilityDetailPage,
        )
        if result.vulnerability.event_id != validated.event_id:
            raise ResponseContractError("vulnerability result does not match the requested event")
        return result

    async def get_vuln_async(self, request: GetVulnRequest) -> VulnerabilityDetailPage:
        deadline = self._bind_loop().time() + self.operation_deadline_seconds
        validated = GetVulnRequest.model_validate_json(_request_body(request, GetVulnRequest))
        result = await self._get_async(
            f"/api/v1/vulns/{validated.event_id}",
            _query_parameters(validated, GetVulnRequest),
            VulnerabilityDetailPage,
            deadline,
        )
        if result.vulnerability.event_id != validated.event_id:
            raise ResponseContractError("vulnerability result does not match the requested event")
        if self._bind_loop().time() >= deadline:
            raise DianziDeadlineError("", False)
        return result

    def get_task_result(self, request: GetTaskResultRequest) -> TaskResultEnvelope:
        if self.uses_async_requests:
            return self._run_sync(self.get_task_result_async(request))
        validated = GetTaskResultRequest.model_validate_json(
            _request_body(request, GetTaskResultRequest)
        )
        result = self._get(f"/api/v1/tasks/{validated.task_id}", {}, TaskResultEnvelope)
        if result.task.task_id != validated.task_id:
            raise ResponseContractError("task result does not match the requested task")
        return result

    async def get_task_result_async(self, request: GetTaskResultRequest) -> TaskResultEnvelope:
        deadline = self._bind_loop().time() + self.operation_deadline_seconds
        validated = GetTaskResultRequest.model_validate_json(
            _request_body(request, GetTaskResultRequest)
        )
        result = await self._get_async(
            f"/api/v1/tasks/{validated.task_id}", {}, TaskResultEnvelope, deadline
        )
        if result.task.task_id != validated.task_id:
            raise ResponseContractError("task result does not match the requested task")
        if self._bind_loop().time() >= deadline:
            raise DianziDeadlineError("", False)
        return result

    def list_sources(self, request: ListSourcesRequest) -> SourcePage:
        if self.uses_async_requests:
            return self._run_sync(self.list_sources_async(request))
        return self._get(
            "/api/v1/sources", _query_parameters(request, ListSourcesRequest), SourcePage
        )

    async def list_sources_async(self, request: ListSourcesRequest) -> SourcePage:
        deadline = self._bind_loop().time() + self.operation_deadline_seconds
        return await self._get_async(
            "/api/v1/sources",
            _query_parameters(request, ListSourcesRequest),
            SourcePage,
            deadline,
        )

    def ask(self, request: AskRequest, *, idempotency_key: str | None = None) -> AskResult:
        if self.uses_async_requests:
            return self._run_sync(self.ask_async(request, idempotency_key=idempotency_key))
        body = _request_body(request, AskRequest)
        key = _validate_operation_key(
            secrets.token_urlsafe(32) if idempotency_key is None else idempotency_key
        )
        status, result = self._request(
            "/api/v1/ask",
            body,
            key,
            ASK_RESULT_ADAPTER,
            self._question_timeout_seconds,
        )
        return _ask_result(status, result)

    async def ask_async(
        self, request: AskRequest, *, idempotency_key: str | None = None
    ) -> AskResult:
        loop = self._bind_loop()
        deadline = loop.time() + self.question_deadline_seconds
        body = _request_body(request, AskRequest)
        key = _validate_operation_key(
            secrets.token_urlsafe(32) if idempotency_key is None else idempotency_key
        )
        status, result = await self._request_async(
            "/api/v1/ask",
            body,
            key,
            ASK_RESULT_ADAPTER,
            self._question_timeout_seconds,
            deadline,
        )
        result = _ask_result(status, result)
        if loop.time() >= deadline:
            raise DianziDeadlineError(key, True)
        return result

    def check_stack(
        self, request: StackCheckRequest, *, idempotency_key: str | None = None
    ) -> StackCheckResult:
        if self.uses_async_requests:
            return self._run_sync(self.check_stack_async(request, idempotency_key=idempotency_key))
        body = _request_body(request, StackCheckRequest)
        key = _validate_operation_key(
            secrets.token_urlsafe(32) if idempotency_key is None else idempotency_key
        )
        status, result = self._request(
            "/api/v1/stack/check",
            body,
            key,
            TypeAdapter(StackCheckResult),
            self._timeout_seconds,
        )
        return _stack_result(status, result)

    async def check_stack_async(
        self, request: StackCheckRequest, *, idempotency_key: str | None = None
    ) -> StackCheckResult:
        loop = self._bind_loop()
        deadline = loop.time() + self.operation_deadline_seconds
        body = _request_body(request, StackCheckRequest)
        key = _validate_operation_key(
            secrets.token_urlsafe(32) if idempotency_key is None else idempotency_key
        )
        status, result = await self._request_async(
            "/api/v1/stack/check",
            body,
            key,
            TypeAdapter(StackCheckResult),
            self._timeout_seconds,
            deadline,
        )
        result = _stack_result(status, result)
        if loop.time() >= deadline:
            raise DianziDeadlineError(key, True)
        return result
