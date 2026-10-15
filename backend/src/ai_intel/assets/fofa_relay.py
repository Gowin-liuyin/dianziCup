"""第三方FOFA relay的固定来源配置和只读账户探测。

只读接口依据用户给定页面当前实现；不提供资产搜索入口。
账户有效和额度可用不能证明FOFA官方账户、资产授权或观察能力。
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import SecretStr

from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkRequestError,
    NetworkTimeoutError,
    OriginCredentials,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
    create_network_gateway,
)

RELAY_ORIGIN = "https://fafaapi.info"
ACCOUNT_PATH = "/fofaapi/v1/validate-key"
PROVIDER_ID: Literal["fofa_relay"] = "fofa_relay"
ErrorCode = Literal[
    "not_configured",
    "invalid_configuration",
    "authentication_failed",
    "payment_required",
    "rate_limited",
    "provider_unavailable",
    "provider_error",
    "http_error",
    "timeout",
    "network_error",
    "network_policy_violation",
    "invalid_response",
]


class FofaRelayError(RuntimeError):
    """仅暴露固定错误代码，不传出供应商响应、URL或原始异常。"""

    def __init__(self, code: ErrorCode, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


@dataclass(frozen=True)
class FofaRelayConfig:
    api_key: SecretStr = field(repr=False)
    base_url: str = RELAY_ORIGIN
    provider_id: Literal["fofa_relay"] = PROVIDER_ID

    def __post_init__(self) -> None:
        if (
            self.base_url != RELAY_ORIGIN
            or self.provider_id != PROVIDER_ID
            or not isinstance(self.api_key, SecretStr)
            or re.fullmatch(r"[a-fA-F0-9]{32}", self.api_key.get_secret_value()) is None
        ):
            raise FofaRelayError("invalid_configuration")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> FofaRelayConfig:
        """由服务端注入秘密；明确provider身份，防止把relay凭据发给官方。"""
        environment = os.environ if environment is None else environment
        provider_id = environment.get("DIANZI_FOFA_PROVIDER")
        if provider_id is None:
            raise FofaRelayError("not_configured")
        if provider_id != PROVIDER_ID:
            raise FofaRelayError("invalid_configuration")
        api_key = environment.get("DIANZI_FOFA_RELAY_API_KEY")
        if not api_key:
            raise FofaRelayError("not_configured")
        return cls(
            api_key=SecretStr(api_key),
            base_url=environment.get("DIANZI_FOFA_RELAY_BASE_URL", RELAY_ORIGIN),
        )


@dataclass(frozen=True)
class RelayAccountStatus:
    status: Literal["available", "budget_exhausted", "unknown"]
    today_remaining: int | None
    total_remaining: int | None
    provider_id: Literal["fofa_relay"] = PROVIDER_ID
    provider_kind: Literal["third_party_relay"] = "third_party_relay"
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_synthetic: bool = False


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _reject_nonfinite_json(value: str) -> object:
    raise ValueError("nonfinite JSON value")


def _quota_value(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None or (key == "totalRemaining" and type(value) is int and value == -1):
        return None
    if key == "totalRemaining" and isinstance(value, str):
        if len(value) > 64 or any(ord(character) < 32 for character in value):
            raise FofaRelayError("invalid_response")
        return None
    if type(value) is not int or value < 0:
        raise FofaRelayError("invalid_response")
    return value


def parse_relay_account_response(body: bytes, *, is_synthetic: bool = False) -> RelayAccountStatus:
    """只保留账户额度白名单；缺失/字符串总额度为unknown，零额度单独标记。"""
    if not isinstance(body, bytes) or not 1 <= len(body) <= 65536:
        raise FofaRelayError("invalid_response")
    try:
        payload: object = json.loads(
            body,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonfinite_json,
        )
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise FofaRelayError("invalid_response") from None
    if not isinstance(payload, dict):
        raise FofaRelayError("invalid_response")
    if "error" in payload and type(payload["error"]) is not bool:
        raise FofaRelayError("invalid_response")
    if payload.get("error") is True:
        raise FofaRelayError("provider_error")
    if type(payload.get("valid")) is not bool:
        raise FofaRelayError("invalid_response")
    if payload["valid"] is False:
        raise FofaRelayError("authentication_failed")
    today_remaining = _quota_value(payload, "todayRemaining")
    total_remaining = _quota_value(payload, "totalRemaining")
    status: Literal["available", "budget_exhausted", "unknown"] = "unknown"
    if today_remaining == 0 or total_remaining == 0:
        status = "budget_exhausted"
    elif today_remaining is not None and total_remaining is not None:
        status = "available"
    return RelayAccountStatus(status, today_remaining, total_remaining, is_synthetic=is_synthetic)


class RelayGateway(Protocol):
    def fetch(self, url: str, max_redirect_hops: int = 5) -> FetchResult: ...


class FofaRelayClient:
    """单次账户只读探测；凭据限于固定HTTPS origin，不重定向、不重试。"""

    def __init__(
        self,
        config: FofaRelayConfig,
        *,
        fixture_gateway: RelayGateway | None = None,
        fixture_mode: bool = False,
    ) -> None:
        if fixture_mode != (fixture_gateway is not None):
            raise FofaRelayError("invalid_configuration")
        self._fixture_mode = fixture_mode
        if fixture_gateway is not None:
            self._gateway: RelayGateway = fixture_gateway
        else:
            self._gateway = create_network_gateway(
                NetworkPolicy(
                    allowed_domains=("fafaapi.info",),
                    max_response_bytes=65536,
                    allowed_content_types=("application/json",),
                    total_timeout_seconds=10,
                    dns_resolver="cloudflare_doh",
                ),
                OriginCredentials(config.base_url, query_parameters={"key": config.api_key}),
                max_concurrent_requests=1,
            )

    def probe_account(self) -> RelayAccountStatus:
        try:
            response = self._gateway.fetch(RELAY_ORIGIN + ACCOUNT_PATH, max_redirect_hops=0)
        except NetworkTimeoutError:
            raise FofaRelayError("timeout", retryable=True) from None
        except (UnsupportedContentTypeError, ResponseTooLargeError):
            raise FofaRelayError("invalid_response") from None
        except NetworkPolicyViolation:
            raise FofaRelayError("network_policy_violation") from None
        except NetworkRequestError:
            raise FofaRelayError("network_error", retryable=True) from None
        if response.status_code in (401, 403):
            raise FofaRelayError("authentication_failed")
        if response.status_code == 402:
            raise FofaRelayError("payment_required")
        if response.status_code == 429:
            raise FofaRelayError("rate_limited", retryable=True)
        if response.status_code >= 500:
            raise FofaRelayError("provider_unavailable", retryable=True)
        if not 200 <= response.status_code < 300:
            raise FofaRelayError("http_error")
        return parse_relay_account_response(response.body, is_synthetic=self._fixture_mode)
