"""本地fixture网关合同；不调用FOFA、不搜索资产、不计live。"""

from unittest.mock import Mock

import pytest
from pydantic import SecretStr

import ai_intel.assets.fofa_relay as relay
from ai_intel.assets.fofa_relay import FofaRelayClient, FofaRelayConfig, FofaRelayError
from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkPolicyViolation,
    NetworkRequestError,
    NetworkTimeoutError,
    UnsupportedContentTypeError,
)


class FixtureGateway:
    def __init__(self, response: FetchResult | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, int]] = []

    def fetch(self, url: str, max_redirect_hops: int = 5) -> FetchResult:
        self.calls.append((url, max_redirect_hops))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def fixture_config() -> FofaRelayConfig:
    return FofaRelayConfig(api_key=SecretStr("1" * 32))


def fixture_response(status: int = 200, body: bytes = b'{"valid":true}') -> FetchResult:
    return FetchResult(
        "https://fafaapi.info/fofaapi/v1/validate-key", status, "application/json", body
    )


def test_account_probe_uses_fixed_path_without_query_or_email_and_is_synthetic() -> None:
    gateway = FixtureGateway(fixture_response())
    client = FofaRelayClient(fixture_config(), fixture_gateway=gateway, fixture_mode=True)
    account = client.probe_account()
    assert gateway.calls == [("https://fafaapi.info/fofaapi/v1/validate-key", 0)]
    assert account.provider_id == "fofa_relay"
    assert account.provider_kind == "third_party_relay"
    assert account.is_synthetic
    assert account.retrieved_at.utcoffset() is not None
    assert not hasattr(client, "search")


def test_falsey_fixture_gateway_never_constructs_real_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FalseyFixtureGateway(FixtureGateway):
        def __bool__(self) -> bool:
            return False

    gateway = FalseyFixtureGateway(
        fixture_response(body=b'{"valid":true,"todayRemaining":2,"totalRemaining":10}')
    )
    real_factory = Mock(side_effect=AssertionError("fixture mode attempted real gateway creation"))
    monkeypatch.setattr(relay, "create_network_gateway", real_factory)
    client = FofaRelayClient(fixture_config(), fixture_gateway=gateway, fixture_mode=True)
    account = client.probe_account()
    real_factory.assert_not_called()
    assert gateway.calls == [("https://fafaapi.info/fofaapi/v1/validate-key", 0)]
    assert (account.status, account.today_remaining, account.total_remaining) == (
        "available",
        2,
        10,
    )
    assert account.is_synthetic


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "authentication_failed", False),
        (403, "authentication_failed", False),
        (402, "payment_required", False),
        (429, "rate_limited", True),
        (501, "provider_unavailable", True),
        (502, "provider_unavailable", True),
        (504, "provider_unavailable", True),
        (400, "http_error", False),
    ],
)
def test_http_errors_are_not_reported_as_success_or_zero_quota(
    status: int, code: str, retryable: bool
) -> None:
    gateway = FixtureGateway(fixture_response(status))
    client = FofaRelayClient(fixture_config(), fixture_gateway=gateway, fixture_mode=True)
    with pytest.raises(FofaRelayError) as caught:
        client.probe_account()
    assert (caught.value.code, caught.value.retryable) == (code, retryable)
    assert len(gateway.calls) == 1


@pytest.mark.parametrize(
    "failure,code,retryable",
    [
        (NetworkTimeoutError("fixture secret URL"), "timeout", True),
        (NetworkRequestError("fixture secret URL"), "network_error", True),
        (NetworkPolicyViolation("fixture secret URL"), "network_policy_violation", False),
        (UnsupportedContentTypeError("fixture secret URL"), "invalid_response", False),
    ],
)
def test_transport_errors_remain_safe_and_make_one_attempt(
    failure: Exception, code: str, retryable: bool
) -> None:
    gateway = FixtureGateway(failure)
    client = FofaRelayClient(fixture_config(), fixture_gateway=gateway, fixture_mode=True)
    with pytest.raises(FofaRelayError) as caught:
        client.probe_account()
    assert (caught.value.code, caught.value.retryable) == (code, retryable)
    assert "fixture secret URL" not in str(caught.value)
    assert caught.value.__suppress_context__
    assert len(gateway.calls) == 1
