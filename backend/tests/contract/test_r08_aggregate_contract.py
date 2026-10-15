"""Fixed query and wire contracts come from official documentation, not asset fixtures."""

import base64
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from ai_intel.assets.hunter_aggregate import HunterAggregateConnector
from ai_intel.assets.quake_aggregate import QuakeAggregateConnector
from ai_intel.infrastructure.network import FetchResult


class ContractFixtureGateway:
    def __init__(self, provider: str, body: bytes | None = None) -> None:
        self.provider = provider
        self.body = body
        self.calls: list[tuple[str, bytes | None, int | None]] = []

    def fetch(self, url: str, max_redirect_hops: int = 5) -> FetchResult:
        self.calls.append((url, None, max_redirect_hops))
        return FetchResult(
            url,
            200,
            "application/json",
            self.body if self.body is not None else b'{"code":200,"data":{"total":5}}',
        )

    def post_json(self, url: str, payload: bytes) -> FetchResult:
        self.calls.append((url, payload, None))
        return FetchResult(
            url,
            200,
            "application/json",
            self.body if self.body is not None else b'{"code":0,"meta":{"pagination":{"total":5}}}',
        )


@pytest.mark.parametrize(
    "query_id,expected_query", [("ollama", 'app.name="Ollama"'), ("vllm", 'app.name="vLLM"')]
)
def test_hunter_fixed_get_contract(query_id: str, expected_query: str) -> None:
    gateway = ContractFixtureGateway("hunter")
    result = HunterAggregateConnector(fixture_gateway=gateway).collect(query_id)
    url, payload, max_redirect_hops = gateway.calls[0]
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path) == (
        "https",
        "hunter.qianxin.com",
        "/openApi/search",
    )
    parameters = parse_qs(parts.query)
    assert base64.urlsafe_b64decode(parameters["search"][0]).decode() == expected_query
    assert {key: value for key, value in parameters.items() if key != "search"} == {
        "page": ["1"],
        "page_size": ["1"],
        "is_web": ["3"],
        "fields": ["updated_at"],
    }
    assert payload is None
    assert max_redirect_hops == 0
    assert result.value is not None and result.value.service_count == 5


@pytest.mark.parametrize(
    "query_id,expected_query", [("ollama", 'app:"Ollama"'), ("vllm", 'app:"vLLM"')]
)
def test_quake_fixed_post_search_contract(query_id: str, expected_query: str) -> None:
    gateway = ContractFixtureGateway("quake")
    result = QuakeAggregateConnector(fixture_gateway=gateway).collect(query_id)
    url, payload, _ = gateway.calls[0]
    assert url == "https://quake.360.net/api/v3/search/quake_service"
    assert payload is not None
    assert json.loads(payload) == {"query": expected_query, "start": 0, "size": 1}
    assert result.value is not None and result.value.service_count == 5


@pytest.mark.parametrize(
    "connector_type,provider,body,outcome,error_code",
    [
        (HunterAggregateConnector, "hunter", b'{"code":200,"data":{}}', "unknown", "missing_total"),
        (
            QuakeAggregateConnector,
            "quake",
            b'{"code":0,"meta":{"pagination":{}}}',
            "unknown",
            "missing_total",
        ),
        (
            HunterAggregateConnector,
            "hunter",
            b'{"code":400,"message":"private-diagnostic"}',
            "failed",
            "provider_error",
        ),
        (
            QuakeAggregateConnector,
            "quake",
            b'{"code":1,"message":"private-diagnostic"}',
            "failed",
            "provider_error",
        ),
        (
            HunterAggregateConnector,
            "hunter",
            b'{"code":200,"data":null}',
            "failed",
            "invalid_response",
        ),
        (QuakeAggregateConnector, "quake", b'{"code":0,"meta":null}', "failed", "invalid_response"),
        (
            QuakeAggregateConnector,
            "quake",
            b'{"code":0,"meta":{"pagination":[]}}',
            "failed",
            "invalid_response",
        ),
        (
            HunterAggregateConnector,
            "hunter",
            b'{"code":"200","data":{"total":0}}',
            "failed",
            "invalid_response",
        ),
        (
            QuakeAggregateConnector,
            "quake",
            b'{"code":false,"meta":{"pagination":{"total":0}}}',
            "failed",
            "invalid_response",
        ),
    ],
)
def test_only_documented_success_envelope_produces_value(
    connector_type, provider: str, body: bytes, outcome: str, error_code: str
) -> None:
    result = connector_type(fixture_gateway=ContractFixtureGateway(provider, body)).collect(
        "ollama"
    )
    assert result.outcome == outcome
    assert result.error_code == error_code
    assert result.value is None
    assert "private-diagnostic" not in result.model_dump_json()
