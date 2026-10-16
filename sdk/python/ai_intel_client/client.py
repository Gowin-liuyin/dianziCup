"""Bounded fixed-path HTTP operations against the project's shared backend."""

from __future__ import annotations

import json
import math
import os
import re
import secrets
from collections.abc import Mapping
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
    QAAnswer,
    StackCheckRequest,
    StackCheckResult,
    TaskHandle,
)

MAX_RESPONSE_BYTES = 1048576
MAX_SYNCHRONOUS_REQUEST_BYTES = 1048576
ResultType = TypeVar("ResultType")


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


class DianziClient:
    """No retries, arbitrary URLs, database credentials or duplicated business decisions."""

    def __init__(
        self,
        base_url: str,
        api_key: SecretStr,
        *,
        timeout_seconds: float = 10,
        question_timeout_seconds: float = 100,
        transport: httpx.BaseTransport | None = None,
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
        if (
            type(timeout_seconds) not in {int, float}
            or type(question_timeout_seconds) not in {int, float}
            or not 0 < timeout_seconds <= 60
            or not 0 < question_timeout_seconds <= 120
        ):
            raise ClientConfigurationError("client timeout is outside the allowed bounds")
        self._question_timeout_seconds = question_timeout_seconds
        self._timeout_seconds = timeout_seconds
        self._http = httpx.Client(
            base_url=origin,
            headers={
                "Authorization": "Bearer " + credential,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            event_hooks={"request": [_remove_cookie_authentication]},
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> DianziClient:
        configured = os.environ if environment is None else environment
        base_url = configured.get("DIANZI_API_BASE_URL")
        key = configured.get("DIANZI_API_KEY")
        if not base_url or not key:
            raise ClientConfigurationError("backend base URL and API key must be configured")
        return cls(base_url, SecretStr(key))

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> DianziClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _post(
        self,
        path: str,
        body: str,
        operation_key: str,
        adapter: TypeAdapter[ResultType],
        timeout_seconds: float,
    ) -> tuple[int, ResultType]:
        encoded = body.encode("utf-8")
        if len(encoded) > MAX_SYNCHRONOUS_REQUEST_BYTES:
            raise ClientInputError("synchronous request exceeds the client size boundary")
        try:
            with self._http.stream(
                "POST",
                path,
                content=encoded,
                headers={"Content-Type": "application/json", "Idempotency-Key": operation_key},
                timeout=timeout_seconds,
            ) as response:
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ResponseContractError(
                        "compressed response is outside the client boundary"
                    )
                raw = bytearray()
                for chunk in response.iter_bytes():
                    if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ResponseContractError("response exceeds the allowed size")
                    raw.extend(chunk)
                content = bytes(raw)
                if response.status_code not in {200, 202}:
                    problem = None
                    if (
                        response.headers.get("content-type", "").split(";", 1)[0].lower()
                        == "application/problem+json"
                    ):
                        try:
                            validate_json_bytes(content)
                            problem = ApiProblem.model_validate_json(content)
                        except (ResponseContractError, ValidationError):
                            problem = None
                    if problem is None or problem.status != response.status_code:
                        raise DianziApiError(response.status_code, "http_error", None, False)
                    raise DianziApiError(
                        problem.status,
                        problem.error.code,
                        problem.trace_id,
                        problem.error.retryable,
                    )
                if (
                    response.headers.get("content-type", "").split(";", 1)[0].lower()
                    != "application/json"
                ):
                    raise ResponseContractError("response content type is invalid")
                validate_json_bytes(content)
                try:
                    result = adapter.validate_json(content)
                except ValidationError:
                    raise ResponseContractError(
                        "response does not match the public contract"
                    ) from None
                return response.status_code, result
        except httpx.HTTPError:
            raise DianziTransportError(operation_key, True) from None

    def ask(self, request: AskRequest, *, idempotency_key: str | None = None) -> AskResult:
        if not isinstance(request, AskRequest):
            raise ClientInputError("question request is invalid")
        try:
            validated = AskRequest.model_validate_json(request.wire_json())
        except (ValidationError, UnicodeError, ValueError):
            raise ClientInputError("question request is invalid") from None
        key = _validate_operation_key(
            secrets.token_urlsafe(32) if idempotency_key is None else idempotency_key
        )
        status, result = self._post(
            "/api/v1/ask",
            validated.wire_json(),
            key,
            ASK_RESULT_ADAPTER,
            self._question_timeout_seconds,
        )
        if (isinstance(result, QAAnswer) and status != 200) or (
            isinstance(result, TaskHandle) and status != 202
        ):
            raise ResponseContractError("answer kind does not match HTTP status")
        return result

    def check_stack(
        self, request: StackCheckRequest, *, idempotency_key: str | None = None
    ) -> StackCheckResult:
        if not isinstance(request, StackCheckRequest):
            raise ClientInputError("stack request is invalid")
        try:
            validated = StackCheckRequest.model_validate_json(request.wire_json())
        except (ValidationError, UnicodeError, ValueError):
            raise ClientInputError("stack request is invalid") from None
        key = _validate_operation_key(
            secrets.token_urlsafe(32) if idempotency_key is None else idempotency_key
        )
        status, result = self._post(
            "/api/v1/stack/check",
            validated.wire_json(),
            key,
            TypeAdapter(StackCheckResult),
            self._timeout_seconds,
        )
        if status != 200:
            raise ResponseContractError("synchronous stack result requires HTTP 200")
        return result
