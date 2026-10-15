"""Provider wire bodies remain confined to explicit fixture gateways before typed persistence."""

from datetime import UTC, datetime

from ai_intel.assets.aggregate_repository import canonical_observation
from ai_intel.assets.hunter_aggregate import HunterAggregateConnector
from ai_intel.infrastructure.network import FetchResult


class RawSecretFixtureGateway:
    def fetch(self, url: str, max_redirect_hops: int = 5) -> FetchResult:
        return FetchResult(
            url,
            200,
            "application/json",
            b'{"code":200,"data":{"total":7,"arr":[{"ip":"192.0.2.99","api_key":"provider-secret","headers":{"Authorization":"provider-secret"}}]}}',
        )

    def post_json(self, url: str, payload: bytes) -> FetchResult:
        raise AssertionError("fixture Hunter gateway never POSTs")


def test_wire_record_secrets_are_not_in_the_persistence_value_or_error(capsys):
    observation = HunterAggregateConnector(fixture_gateway=RawSecretFixtureGateway()).collect(
        "ollama", retrieved_at=datetime(2026, 10, 15, 20, tzinfo=UTC)
    )
    canonical, _ = canonical_observation(observation)
    assert observation.value.service_count == 7
    assert "provider-secret" not in canonical and "192.0.2.99" not in canonical
    assert "Authorization" not in canonical and "headers" not in canonical
    assert capsys.readouterr().out == "" and capsys.readouterr().err == ""
