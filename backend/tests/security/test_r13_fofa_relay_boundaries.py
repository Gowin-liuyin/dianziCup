"""凭据目标、provider身份与脱敏边界，全部使用合成key。"""

from collections.abc import Iterable
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr

from ai_intel.assets.fofa_relay import FofaRelayClient, FofaRelayConfig, FofaRelayError
from ai_intel.infrastructure.network import (
    NetworkGateway,
    NetworkPolicy,
    OriginCredentials,
    RequestDeadline,
)

FIXTURE_KEY = "1" * 32


@pytest.mark.parametrize(
    "base_url",
    [
        "http://fafaapi.info",
        "https://fofa.info",
        "https://hamal.cc.cd",
        "https://fafaapi.info.evil.example",
        "https://sub.fafaapi.info",
        "https://fafaapi.info:443",
        "https://fafaapi.info/",
        "https://fafaapi.info?key=fixture",
        "https://user@fafaapi.info",
    ],
)
def test_only_documented_exact_relay_origin_is_accepted(base_url: str) -> None:
    with pytest.raises(FofaRelayError) as caught:
        FofaRelayConfig(api_key=SecretStr(FIXTURE_KEY), base_url=base_url)
    assert caught.value.code == "invalid_configuration"
    assert base_url not in str(caught.value)


def test_fixture_gateway_requires_explicit_fixture_flag() -> None:
    with pytest.raises(FofaRelayError) as caught:
        FofaRelayClient(FofaRelayConfig(api_key=SecretStr(FIXTURE_KEY)), fixture_mode=True)
    assert caught.value.code == "invalid_configuration"


def test_fixture_gateway_cannot_implicitly_select_fixture_mode() -> None:
    gateway = NetworkGateway(NetworkPolicy(allowed_domains=("fafaapi.info",)))
    with pytest.raises(FofaRelayError) as caught:
        FofaRelayClient(FofaRelayConfig(api_key=SecretStr(FIXTURE_KEY)), fixture_gateway=gateway)
    assert caught.value.code == "invalid_configuration"


class FixtureResponse:
    status_code = 200

    def __init__(self) -> None:
        self.headers = {"content-type": "application/json", "x-echo": FIXTURE_KEY}

    def iter_bytes(self) -> Iterable[bytes]:
        yield b'{"valid":true,"todayRemaining":2,"totalRemaining":10}'

    def close(self) -> None:
        pass


class FixtureTransport:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def resolve_addresses(self, hostname: str, deadline: RequestDeadline) -> list[str]:
        assert hostname == "fafaapi.info"
        return ["1.1.1.1"]

    def request(
        self,
        url: str,
        addresses: tuple[str, ...],
        deadline: RequestDeadline,
        headers: dict[str, str],
    ) -> FixtureResponse:
        self.requests.append(url)
        assert addresses == ("1.1.1.1",)
        assert not headers
        return FixtureResponse()


def test_shared_gateway_injects_key_only_at_origin_and_redacts_its_audit_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = OriginCredentials(
        "https://fafaapi.info", query_parameters={"key": SecretStr(FIXTURE_KEY)}
    )
    transport = FixtureTransport()
    gateway = NetworkGateway(
        NetworkPolicy(allowed_domains=("fafaapi.info",)),
        credentials,
    )
    monkeypatch.setattr(gateway, "_transport", transport)
    fetch = gateway.fetch("https://fafaapi.info/fofaapi/v1/validate-key", max_redirect_hops=0)
    assert parse_qs(urlsplit(transport.requests[0]).query) == {"key": [FIXTURE_KEY]}
    assert FIXTURE_KEY not in repr(fetch)
    assert fetch.redacted_headers["x-echo"] == "REDACTED"
    assert "key=REDACTED" in fetch.final_url
    other_url = "https://fofa.info/api/v1/search/all"
    assert credentials.inject(other_url) == (other_url, {})
