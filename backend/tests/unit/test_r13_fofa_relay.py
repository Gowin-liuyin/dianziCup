"""第三方relay账户配置及额度解析的显式合成夹具。"""

import json

import pytest
from pydantic import SecretStr

from ai_intel.assets.fofa_relay import (
    FofaRelayConfig,
    FofaRelayError,
    parse_relay_account_response,
)

FIXTURE_KEY = SecretStr("1" * 32)


def test_explicit_relay_environment_configuration() -> None:
    config = FofaRelayConfig.from_environment(
        {
            "DIANZI_FOFA_PROVIDER": "fofa_relay",
            "DIANZI_FOFA_RELAY_BASE_URL": "https://fafaapi.info",
            "DIANZI_FOFA_RELAY_API_KEY": FIXTURE_KEY.get_secret_value(),
        }
    )
    assert config.provider_id == "fofa_relay"
    assert config.base_url == "https://fafaapi.info"
    assert config.api_key == FIXTURE_KEY
    assert FIXTURE_KEY.get_secret_value() not in repr(config)


@pytest.mark.parametrize(
    "environment, code",
    [
        ({}, "not_configured"),
        ({"DIANZI_FOFA_PROVIDER": "fofa_official"}, "invalid_configuration"),
        (
            {"DIANZI_FOFA_PROVIDER": "fofa_relay", "DIANZI_FOFA_RELAY_API_KEY": ""},
            "not_configured",
        ),
        (
            {"DIANZI_FOFA_PROVIDER": "fofa_relay", "DIANZI_FOFA_RELAY_API_KEY": "bad"},
            "invalid_configuration",
        ),
    ],
)
def test_environment_configuration_errors_are_distinct(
    environment: dict[str, str], code: str
) -> None:
    with pytest.raises(FofaRelayError) as caught:
        FofaRelayConfig.from_environment(environment)
    assert caught.value.code == code
    assert not caught.value.retryable


@pytest.mark.parametrize("today, total", [(0, 10), (10, 0), (0, 0)])
def test_account_success_with_zero_quota_is_budget_exhausted(today: int, total: int) -> None:
    payload = json.dumps({"valid": True, "todayRemaining": today, "totalRemaining": total})
    account = parse_relay_account_response(payload.encode())
    assert account.status == "budget_exhausted"
    assert account.today_remaining == today
    assert account.total_remaining == total


def test_account_success_with_positive_known_counters_is_available() -> None:
    account = parse_relay_account_response(
        b'{"valid":true,"todayRemaining":4,"totalRemaining":100}'
    )
    assert account.status == "available"
    assert (account.today_remaining, account.total_remaining) == (4, 100)


@pytest.mark.parametrize(
    "payload",
    [
        {"valid": True},
        {"valid": True, "todayRemaining": None, "totalRemaining": None},
        {"valid": True, "todayRemaining": 4, "totalRemaining": -1},
        {"valid": True, "todayRemaining": 4},
        {"valid": True, "todayRemaining": 200, "totalRemaining": "fixture unspecified"},
        {"valid": True, "todayRemaining": 200, "totalRemaining": "100"},
        {"valid": True, "todayRemaining": 200, "totalRemaining": ""},
    ],
)
def test_missing_or_unbounded_counters_remain_unknown(payload: dict[str, object]) -> None:
    account = parse_relay_account_response(json.dumps(payload).encode())
    assert account.status == "unknown"
    assert account.total_remaining is None


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b"{}",
        b'{"valid":"true"}',
        b'{"valid":1}',
        b'{"valid":true,"todayRemaining":true}',
        b'{"valid":true,"todayRemaining":1.5}',
        b'{"valid":true,"todayRemaining":-1}',
        b'{"valid":true,"totalRemaining":-2}',
        b'{"valid":true,"totalRemaining":[]}',
        b'{"valid":true,"totalRemaining":"control\\nvalue"}',
        b'{"valid":true,"totalRemaining":"' + b"a" * 65 + b'"}',
        b'{"valid":true,"error":"false"}',
        b'{"valid":true,"error":null}',
        b'{"valid":true,"todayRemaining":NaN}',
        b'{"valid":true,"valid":false}',
        b"<html>gateway failure</html>",
        b"\xff",
    ],
)
def test_malformed_account_response_never_becomes_empty_success(payload: bytes) -> None:
    with pytest.raises(FofaRelayError) as caught:
        parse_relay_account_response(payload)
    assert caught.value.code == "invalid_response"
    assert not caught.value.retryable


def test_valid_false_is_authentication_failure_without_provider_message() -> None:
    with pytest.raises(FofaRelayError) as caught:
        parse_relay_account_response(b'{"valid":false,"errmsg":"private diagnostic"}')
    assert caught.value.code == "authentication_failed"
    assert "private diagnostic" not in str(caught.value)


def test_error_envelope_overrides_a_success_flag_and_empty_counters() -> None:
    with pytest.raises(FofaRelayError) as caught:
        parse_relay_account_response(b'{"valid":true,"error":true,"errmsg":"quota?"}')
    assert caught.value.code == "provider_error"
    assert "quota?" not in str(caught.value)


def test_unrequested_asset_fields_are_discarded() -> None:
    account = parse_relay_account_response(
        b'{"valid":true,"todayRemaining":4,"totalRemaining":10,"results":["fixture private"]}'
    )
    assert "fixture private" not in repr(account)
    assert not hasattr(account, "results")


@pytest.mark.parametrize("body", [b"", b"a" * 65537], ids=["empty", "over_64_kib"])
def test_account_json_body_is_bounded(body: bytes) -> None:
    with pytest.raises(FofaRelayError) as caught:
        parse_relay_account_response(body)
    assert caught.value.code == "invalid_response"
