"""独立安全边界反例，只使用合成凭据和本地传输。"""

import json
import traceback
from collections.abc import Iterable
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from pydantic import SecretStr

import ai_intel.assets.fofa_relay as relay
from ai_intel.infrastructure.network import FetchResult, NetworkGateway, NetworkTimeoutError

FIXTURE_KEY = "3" * 32


class FixtureGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def fetch(self, url: str, max_redirect_hops: int = 5) -> FetchResult:
        self.calls.append((url, max_redirect_hops))
        return FetchResult(url, 200, "application/json", b'{"valid":true}')


class EmptyFixtureGateway(FixtureGateway):
    def __len__(self) -> int:
        return 0


class NoTruthEvaluationFixtureGateway(FixtureGateway):
    def __bool__(self) -> bool:
        raise AssertionError("fixture truth value must not be evaluated")


@pytest.mark.parametrize("gateway_class", [FixtureGateway, EmptyFixtureGateway, NoTruthEvaluationFixtureGateway])
def test_fixture_identity_not_truthiness_selects_injected_gateway(monkeypatch, gateway_class):
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("explicit fixture called production factory")

    monkeypatch.setattr(relay, "create_network_gateway", forbidden_factory)
    fixture = gateway_class()
    client = relay.FofaRelayClient(relay.FofaRelayConfig(SecretStr(FIXTURE_KEY)), fixture_gateway=fixture, fixture_mode=True)
    assert client._gateway is fixture
    account = client.probe_account()
    assert fixture.calls == [("https://fafaapi.info/fofaapi/v1/validate-key", 0)]
    assert account.is_synthetic is True


def test_missing_provider_or_key_never_reaches_production_factory(monkeypatch):
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("unconfigured input called production factory")

    monkeypatch.setattr(relay, "create_network_gateway", forbidden_factory)
    for environment in ({}, {"DIANZI_FOFA_PROVIDER": "fofa_relay"}):
        with pytest.raises(relay.FofaRelayError) as caught:
            relay.FofaRelayClient(relay.FofaRelayConfig.from_environment(environment))
        assert caught.value.code == "not_configured"


class LocalResponse:
    status_code = 200

    def __init__(self, *, timeout: bool = False) -> None:
        self.headers = {"content-type": "application/json", "location": "https://fafaapi.info/?key=" + quote(FIXTURE_KEY), "x-echo": FIXTURE_KEY}
        self.timeout = timeout
        self.closed = False

    def iter_bytes(self) -> Iterable[bytes]:
        if self.timeout:
            raise NetworkTimeoutError("fixture URL ?key=" + FIXTURE_KEY)
        yield b'{"valid":true,"todayRemaining":200,"totalRemaining":"fixture unknown","firstUsedAt":"fixture private","expireTime":"fixture private"}'

    def close(self) -> None:
        self.closed = True


class LocalTransport:
    def __init__(self, response: LocalResponse) -> None:
        self.calls: list[str] = []
        self.response = response

    def request(self, url, addresses, deadline, headers):
        self.calls.append(url)
        assert 0 < deadline.remaining_seconds() <= 10
        assert not headers
        return self.response


def local_production_client(monkeypatch, addresses, response):
    transport = LocalTransport(response)
    captures = []

    def factory(policy, credentials, max_concurrent_requests):
        gateway = NetworkGateway(policy, credentials, max_concurrent_requests)
        gateway._resolve_addresses = lambda host, deadline: addresses
        gateway._transport = transport
        captures.append(gateway)
        return gateway

    monkeypatch.setattr(relay, "create_network_gateway", factory)
    client = relay.FofaRelayClient(relay.FofaRelayConfig(SecretStr(FIXTURE_KEY)))
    return client, transport, captures[0]


@pytest.mark.parametrize("addresses", [["127.0.0.1"], ["10.1.2.3"], ["169.254.169.254"], ["::1"], ["fc00::1"], ["1.1.1.1", "192.168.1.2"]])
def test_private_or_mixed_dns_never_sends_relay_key(monkeypatch, addresses):
    client, transport, _ = local_production_client(monkeypatch, addresses, LocalResponse())
    with pytest.raises(relay.FofaRelayError) as caught:
        client.probe_account()
    assert caught.value.code == "network_policy_violation"
    assert transport.calls == []
    assert FIXTURE_KEY not in "".join(traceback.format_exception(caught.value))


def test_production_factory_result_is_not_synthetic_and_url_is_redacted(monkeypatch):
    response = LocalResponse()
    client, transport, gateway = local_production_client(monkeypatch, ["1.1.1.1"], response)
    account = client.probe_account()
    assert account.is_synthetic is False
    assert account.status == "unknown"
    assert account.today_remaining == 200 and account.total_remaining is None
    assert "private" not in repr(account)
    assert len(transport.calls) == 1
    assert parse_qs(urlsplit(transport.calls[0]).query) == {"key": [FIXTURE_KEY]}
    result = gateway.fetch(relay.RELAY_ORIGIN + relay.ACCOUNT_PATH, max_redirect_hops=0)
    assert parse_qs(urlsplit(result.final_url).query) == {"key": ["REDACTED"]}
    assert result.redacted_headers["x-echo"] == "REDACTED"
    assert FIXTURE_KEY not in repr(result)
    assert response.closed


def test_stream_timeout_closes_response_and_does_not_retry(monkeypatch):
    response = LocalResponse(timeout=True)
    client, transport, _ = local_production_client(monkeypatch, ["1.1.1.1"], response)
    with pytest.raises(relay.FofaRelayError) as caught:
        client.probe_account()
    assert (caught.value.code, caught.value.retryable) == ("timeout", True)
    assert len(transport.calls) == 1 and response.closed
    assert FIXTURE_KEY not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("total", ["0", "200", "无限", "", "x" * 64])
def test_real_observed_string_type_remains_unknown_without_invented_quota(total):
    body = json.dumps({"valid": True, "todayRemaining": 200, "totalRemaining": total}).encode()
    status = relay.parse_relay_account_response(body, is_synthetic=True)
    assert status.status == "unknown" and status.total_remaining is None
    assert status.today_remaining == 200 and status.is_synthetic is True


def test_json_byte_limit_accepts_valid_64_kib_and_rejects_next_byte():
    body = b'{"valid":true}'
    exact = body + b" " * (65536 - len(body))
    assert relay.parse_relay_account_response(exact).status == "unknown"
    with pytest.raises(relay.FofaRelayError) as caught:
        relay.parse_relay_account_response(exact + b" ")
    assert caught.value.code == "invalid_response"
