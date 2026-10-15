"""Explicit fixtures test count semantics without contacting a provider."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ai_intel.assets.aggregate_observations import AggregateObservation, aggregate_freshness
from ai_intel.assets.hunter_aggregate import HunterAggregateConnector
from ai_intel.assets.quake_aggregate import QuakeAggregateConnector
from ai_intel.infrastructure.network import FetchResult, NetworkTimeoutError

RETRIEVED_AT = datetime(2026, 10, 16, tzinfo=UTC)
CONNECTORS = (HunterAggregateConnector, QuakeAggregateConnector)


class FixtureGateway:
    """Only this explicitly injected object supplies fixture responses."""

    def __init__(self, response: FetchResult | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, bytes | None, int | None]] = []

    def __bool__(self) -> bool:
        return False

    def fetch(self, url: str, max_redirect_hops: int = 5) -> FetchResult:
        self.calls.append((url, None, max_redirect_hops))
        return self._response()

    def post_json(self, url: str, payload: bytes) -> FetchResult:
        self.calls.append((url, payload, None))
        return self._response()

    def _response(self) -> FetchResult:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def response_for(provider: str, total: object = 42, *, status: int = 200) -> FetchResult:
    document = (
        {"code": 200, "data": {"total": total, "arr": [{"ip": "192.0.2.123"}]}}
        if provider == "hunter"
        else {"code": 0, "meta": {"pagination": {"total": total}}, "data": [{"ip": "192.0.2.123"}]}
    )
    return FetchResult(
        "https://example.invalid", status, "application/json", json.dumps(document).encode()
    )


@pytest.mark.parametrize("connector_type", CONNECTORS)
@pytest.mark.parametrize("total", [0, 42, 2**63 - 1])
def test_success_count_never_uses_asset_details(connector_type, total: int) -> None:
    provider = "hunter" if connector_type is HunterAggregateConnector else "quake"
    gateway = FixtureGateway(response_for(provider, total))
    result = connector_type(fixture_gateway=gateway).collect("ollama", retrieved_at=RETRIEVED_AT)
    assert result.outcome == "available"
    assert result.data_mode == "fixture"
    assert result.value is not None
    assert result.value.service_count == total
    assert result.value.observed_at is None
    assert result.value.retrieved_at == RETRIEVED_AT
    assert result.value.query_version == "r08-product-name-1"
    assert result.value.ttl_seconds == 86400
    assert "192.0.2.123" not in result.model_dump_json()
    assert "vulnerable" not in result.model_dump()
    assert "Service count is not a count of vulnerable or owned assets." in result.value.limitations
    assert len(gateway.calls) == 1


@pytest.mark.parametrize("connector_type", CONNECTORS)
@pytest.mark.parametrize("total", [None, True, -1, 1.5, "42", 2**63])
def test_invalid_total_is_unknown_or_failed_never_zero(connector_type, total: object) -> None:
    provider = "hunter" if connector_type is HunterAggregateConnector else "quake"
    result = connector_type(fixture_gateway=FixtureGateway(response_for(provider, total))).collect(
        "vllm"
    )
    assert result.outcome == ("unknown" if total is None else "failed")
    assert result.error_code == ("missing_total" if total is None else "invalid_total")
    assert result.value is None


@pytest.mark.parametrize("connector_type", CONNECTORS)
@pytest.mark.parametrize(
    "status,outcome,error_code",
    [
        (401, "unauthorized", "provider_unauthorized"),
        (403, "unauthorized", "provider_unauthorized"),
        (429, "rate_limited", "provider_rate_limited"),
        (500, "failed", "provider_http_error"),
    ],
)
def test_http_failures_remain_distinct(
    connector_type, status: int, outcome: str, error_code: str
) -> None:
    gateway = FixtureGateway(FetchResult("https://example.invalid", status, "text/html", b"secret"))
    result = connector_type(fixture_gateway=gateway).collect("ollama")
    assert result.outcome == outcome
    assert result.error_code == error_code
    assert result.value is None
    assert "secret" not in repr(result)


@pytest.mark.parametrize("connector_type", CONNECTORS)
@pytest.mark.parametrize("body", [b"{", b"[]", b'{"code":0,"code":200}', b'{"code":NaN}', b"\xff"])
def test_bad_json_is_safe_failure(connector_type, body: bytes) -> None:
    gateway = FixtureGateway(FetchResult("https://example.invalid", 200, "application/json", body))
    result = connector_type(fixture_gateway=gateway).collect("ollama")
    assert (result.outcome, result.error_code, result.value) == ("failed", "invalid_response", None)


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_network_failure_does_not_fallback_to_zero_or_retry(connector_type) -> None:
    gateway = FixtureGateway(NetworkTimeoutError("credential-and-private-diagnostic"))
    result = connector_type(fixture_gateway=gateway).collect("ollama")
    assert (result.outcome, result.error_code, result.value) == ("failed", "network_timeout", None)
    assert "credential" not in result.model_dump_json()
    assert len(gateway.calls) == 1


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_unconfigured_connector_has_no_success_default(connector_type) -> None:
    result = connector_type().collect("ollama")
    assert (result.outcome, result.error_code, result.value) == (
        "not_configured",
        "credential_missing",
        None,
    )
    assert result.data_mode == "live"


def test_ttl_expiry_preserves_historical_count_and_unknown_observed_time() -> None:
    result = HunterAggregateConnector(
        fixture_gateway=FixtureGateway(response_for("hunter"))
    ).collect("ollama", retrieved_at=RETRIEVED_AT)
    assert result.value is not None
    assert aggregate_freshness(result.value, RETRIEVED_AT + timedelta(hours=23)) == "unknown"
    assert aggregate_freshness(result.value, RETRIEVED_AT + timedelta(days=1)) == "stale"
    assert result.value.service_count == 42
    with pytest.raises(ValueError, match="before retrieval"):
        aggregate_freshness(result.value, RETRIEVED_AT - timedelta(seconds=1))


def test_output_rejects_details_and_inconsistent_available_state() -> None:
    result = HunterAggregateConnector(
        fixture_gateway=FixtureGateway(response_for("hunter"))
    ).collect("ollama")
    with pytest.raises(ValidationError):
        AggregateObservation.model_validate({**result.model_dump(), "ip": "192.0.2.123"})
    with pytest.raises(ValidationError):
        AggregateObservation.model_validate({**result.model_dump(), "outcome": "failed"})


@pytest.mark.parametrize(
    "outcome,error_code",
    [
        ("unknown", "provider_unauthorized"),
        ("failed", "missing_total"),
        ("unauthorized", "provider_error"),
        ("failed", "provider_rate_limited"),
        ("rate_limited", "invalid_response"),
        ("not_configured", "network_timeout"),
    ],
)
def test_unavailable_status_cannot_mislabel_the_error(outcome: str, error_code: str) -> None:
    with pytest.raises(ValidationError, match="must agree"):
        AggregateObservation.model_validate(
            {
                "provider": "hunter",
                "query_id": "ollama",
                "retrieved_at": RETRIEVED_AT,
                "outcome": outcome,
                "error_code": error_code,
                "data_mode": "fixture",
            }
        )


def test_observed_at_freshness_requires_real_observation_time() -> None:
    result = HunterAggregateConnector(
        fixture_gateway=FixtureGateway(response_for("hunter"))
    ).collect("ollama", retrieved_at=RETRIEVED_AT)
    assert result.value is not None
    value = result.value.model_copy(update={"observed_at": RETRIEVED_AT - timedelta(days=2)})
    assert aggregate_freshness(value, RETRIEVED_AT) == "stale"
    value = result.value.model_copy(update={"observed_at": RETRIEVED_AT})
    assert aggregate_freshness(value, RETRIEVED_AT + timedelta(seconds=1)) == "current"


@pytest.mark.parametrize("connector_type", CONNECTORS)
def test_fixture_retrieval_timestamp_rejects_naive_input(connector_type) -> None:
    gateway = FixtureGateway(response_for("hunter"))
    with pytest.raises(ValueError, match="timezone-aware"):
        connector_type(fixture_gateway=gateway).collect(
            "ollama", retrieved_at=datetime(2026, 10, 16)
        )
    assert gateway.calls == []
