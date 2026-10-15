"""Internal aggregate-only boundary; raw provider records never become a business value."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict, SecretStr, model_validator

from ai_intel.domain.enrichment_values import ExposureAggregateValue
from ai_intel.domain.values import UtcTimestamp
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkGateway,
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkRequestError,
    OriginCredentials,
    create_network_gateway,
)

AggregateProvider = Literal["hunter", "quake"]
AggregateQueryId = Literal["ollama", "vllm"]
AggregateOutcome = Literal[
    "available", "unknown", "unauthorized", "rate_limited", "failed", "not_configured"
]
AggregateErrorCode = Literal[
    "missing_total",
    "invalid_total",
    "invalid_response",
    "provider_unauthorized",
    "provider_rate_limited",
    "provider_http_error",
    "provider_error",
    "credential_missing",
    "network_error",
    "network_dns_error",
    "network_tls_error",
    "network_timeout",
    "network_policy_violation",
    "response_too_large",
    "unsupported_content_type",
]
QUERY_VERSION: Literal["r08-product-name-1"] = "r08-product-name-1"
TTL_SECONDS = 86400
MAX_RESPONSE_BYTES = 262144
LIMITATIONS = (
    "Service count is not a count of vulnerable or owned assets.",
    "Product-name matching can omit unrecognized services and include false matches.",
    "Ollama/vLLM provider fingerprint names and match accuracy have not been verified live.",
    "The provider supplies no aggregate observation timestamp; "
    "retrieval time is not observation time.",
    "Only the search total is retained; provider asset records are discarded in memory.",
)


class AggregateGateway(Protocol):
    """Explicit fixture gateways implement the same bounded request surface without network IO."""

    def fetch(self, url: str, max_redirect_hops: int = 5) -> FetchResult: ...

    def post_json(self, url: str, payload: bytes) -> FetchResult: ...


class AggregateIdentity(TypedDict):
    provider: AggregateProvider
    query_id: AggregateQueryId
    retrieved_at: datetime
    data_mode: Literal["live", "fixture"]


class AggregateObservation(BaseModel):
    """Failures retain a fixed reason and query identity rather than a fabricated count."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    schema_version: Literal["r08-aggregate-observation-1"] = "r08-aggregate-observation-1"
    provider: AggregateProvider
    query_id: AggregateQueryId
    query_version: Literal["r08-product-name-1"] = QUERY_VERSION
    retrieved_at: UtcTimestamp
    outcome: AggregateOutcome
    error_code: AggregateErrorCode | None = None
    value: ExposureAggregateValue | None = None
    data_mode: Literal["live", "fixture"]

    @model_validator(mode="after")
    def consistent_result(self) -> AggregateObservation:
        if self.outcome == "available":
            if self.value is None or self.error_code is not None:
                raise ValueError("available aggregate requires a value without an error")
            if (
                self.value.provider != self.provider
                or self.value.query_id != self.query_id
                or self.value.query_version != self.query_version
                or self.value.retrieved_at != self.retrieved_at
            ):
                raise ValueError("aggregate identity and retrieval time must agree")
        elif self.value is not None or self.error_code is None:
            raise ValueError("unavailable aggregate requires an error without a value")
        elif (
            (self.outcome == "unknown") != (self.error_code == "missing_total")
            or (self.outcome == "unauthorized") != (self.error_code == "provider_unauthorized")
            or (self.outcome == "rate_limited") != (self.error_code == "provider_rate_limited")
            or (self.outcome == "not_configured") != (self.error_code == "credential_missing")
        ):
            raise ValueError("aggregate outcome must agree with its fixed error code")
        return self


def require_query_id(query_id: AggregateQueryId) -> None:
    if type(query_id) is not str or query_id not in ("ollama", "vllm"):
        raise ValueError("query_id must be ollama or vllm")


def retrieval_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at must be a timezone-aware datetime")
    return value.astimezone(UTC)


def aggregate_freshness(
    value: ExposureAggregateValue, now: datetime
) -> Literal["current", "stale", "unknown"]:
    evaluated_at = retrieval_time(now)
    age_seconds = (evaluated_at - value.retrieved_at).total_seconds()
    if age_seconds < 0:
        raise ValueError("freshness cannot be evaluated before retrieval")
    if age_seconds >= value.ttl_seconds:
        return "stale"
    if value.observed_at is None:
        return "unknown"
    observed_age = (evaluated_at - value.observed_at).total_seconds()
    if observed_age < 0:
        raise ValueError("observation cannot be in the future")
    return "stale" if observed_age >= value.ttl_seconds else "current"


def build_aggregate_gateway(
    provider: AggregateProvider,
    api_key: SecretStr,
    dns_resolver: Literal["system", "cloudflare_doh"],
) -> NetworkGateway:
    if not isinstance(api_key, SecretStr):
        raise ValueError("api_key requires a bounded SecretStr")
    secret = api_key.get_secret_value()
    if (
        not 1 <= len(secret) <= 4096
        or not secret.isascii()
        or any(ord(character) <= 32 or ord(character) == 127 for character in secret)
    ):
        raise ValueError("api_key requires a bounded SecretStr")
    if provider == "hunter":
        origin = "https://hunter.qianxin.com"
        credentials = OriginCredentials(origin, query_parameters={"api-key": api_key})
        domain = "hunter.qianxin.com"
    elif provider == "quake":
        origin = "https://quake.360.net"
        credentials = OriginCredentials(origin, headers={"X-QuakeToken": api_key})
        domain = "quake.360.net"
    else:
        raise ValueError("unsupported aggregate provider")
    return create_network_gateway(
        NetworkPolicy(
            (domain,),
            max_response_bytes=MAX_RESPONSE_BYTES,
            allowed_content_types=("application/json",),
            total_timeout_seconds=20.0,
            dns_resolver=dns_resolver,
        ),
        credentials,
        max_concurrent_requests=1,
    )


def response_error(response: FetchResult) -> tuple[AggregateOutcome, AggregateErrorCode] | None:
    if response.status_code in (401, 403):
        return "unauthorized", "provider_unauthorized"
    if response.status_code == 429:
        return "rate_limited", "provider_rate_limited"
    if not 200 <= response.status_code < 300:
        return "failed", "provider_http_error"
    return None


def decode_aggregate_response(response: FetchResult) -> dict[str, object]:
    if response.content_type != "application/json":
        raise ValueError("aggregate response requires JSON")
    return strict_json_object(response.body, MAX_RESPONSE_BYTES)


def network_error_code(error: NetworkRequestError | NetworkPolicyViolation) -> AggregateErrorCode:
    if isinstance(error, NetworkPolicyViolation):
        return "network_policy_violation"
    if error.code == "network_dns_error":
        return "network_dns_error"
    if error.code == "network_tls_error":
        return "network_tls_error"
    if error.code == "network_timeout":
        return "network_timeout"
    if error.code == "response_too_large":
        return "response_too_large"
    if error.code == "unsupported_content_type":
        return "unsupported_content_type"
    return "network_error"


def total_result(
    provider: AggregateProvider,
    query_id: AggregateQueryId,
    total: object,
    retrieved_at: datetime,
    data_mode: Literal["live", "fixture"],
) -> AggregateObservation:
    if total is None:
        return AggregateObservation(
            provider=provider,
            query_id=query_id,
            retrieved_at=retrieved_at,
            outcome="unknown",
            error_code="missing_total",
            data_mode=data_mode,
        )
    if not isinstance(total, int) or type(total) is not int or not 0 <= total <= 2**63 - 1:
        return AggregateObservation(
            provider=provider,
            query_id=query_id,
            retrieved_at=retrieved_at,
            outcome="failed",
            error_code="invalid_total",
            data_mode=data_mode,
        )
    return AggregateObservation(
        provider=provider,
        query_id=query_id,
        retrieved_at=retrieved_at,
        outcome="available",
        value=ExposureAggregateValue(
            provider=provider,
            query_id=query_id,
            query_version=QUERY_VERSION,
            service_count=total,
            retrieved_at=retrieved_at,
            ttl_seconds=TTL_SECONDS,
            limitations=LIMITATIONS,
        ),
        data_mode=data_mode,
    )
