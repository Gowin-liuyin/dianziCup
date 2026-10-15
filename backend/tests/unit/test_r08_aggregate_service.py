"""Explicit fixture adapters exercise the persistence/service surface with zero wire requests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest

from ai_intel.assets.aggregate_observations import AggregateObservation, total_result
from ai_intel.assets.aggregate_repository import (
    AggregatePersistenceError,
    AggregateServerPolicy,
    StoredAggregate,
    aggregate_call_key,
    canonical_observation,
)
from ai_intel.assets.aggregate_service import AggregateService
from ai_intel.domain.access import AccessScope, Role

NOW = datetime(2026, 10, 15, 20, 0, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("operator", "tenant-a", Role.SYSTEM_ADMIN)
POLICY = AggregateServerPolicy("authorized-test", "fixture", True)


class FixtureRepository:
    def __init__(self) -> None:
        self.records: list[StoredAggregate] = []
        self.fail_save = False

    def save_observation(self, observation, scope, policy, *, recorded_at, observation_id=None):
        if self.fail_save:
            raise AggregatePersistenceError("test database unavailable")
        _, digest = canonical_observation(observation)
        record = StoredAggregate(
            observation_id or uuid4(),
            observation,
            digest,
            aggregate_call_key(observation.provider, observation.query_id, policy),
            "public",
            recorded_at,
        )
        self.records.append(record)
        return record

    def read_latest(self, provider, query_id, scope, policy, *, now, available_only=False):
        key = aggregate_call_key(provider, query_id, policy)
        records = [
            r
            for r in self.records
            if r.call_key == key
            and r.observation.retrieved_at <= now
            and (not available_only or r.observation.outcome == "available")
        ]
        return max(records, key=lambda r: r.observation.retrieved_at, default=None)


class FixtureConnector:
    def __init__(self, observation: AggregateObservation) -> None:
        self.observation = observation
        self.calls = 0
        self.started = Event()
        self.release = Event()
        self.release.set()

    def collect(self, query_id, *, retrieved_at=None):
        self.calls += 1
        self.started.set()
        assert self.release.wait(2)
        return self.observation


class FixtureCache:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, identity):
        self.calls += 1
        raise RuntimeError("provider-secret-must-not-escape")

    def set(self, identity, payload, ttl_seconds):
        self.calls += 1
        raise RuntimeError("provider-secret-must-not-escape")


def make_service(observation=None, policy=POLICY, cache=None):
    repository = FixtureRepository()
    connector = FixtureConnector(
        observation or total_result("hunter", "ollama", 0, NOW, policy.data_mode)
    )
    service = AggregateService(repository, {"hunter": connector}, policy, safe_cache=cache)
    return service, repository, connector


def test_zero_is_available_and_fixture_never_touches_shared_cache():
    cache = FixtureCache()
    service, repository, connector = make_service(cache=cache)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "available"
    assert result.value.service_count == 0
    assert result.freshness == "unknown"
    assert result.cache_status == "bypassed_fixture"
    assert result.observation_id == repository.records[0].observation_id
    assert result.cache_identity == repository.records[0].cache_identity
    assert result.actual_fee_status == "unknown"
    assert connector.calls == 1 and cache.calls == 0


@pytest.mark.parametrize(
    "outcome,error",
    [
        ("unknown", "missing_total"),
        ("unauthorized", "provider_unauthorized"),
        ("rate_limited", "provider_rate_limited"),
        ("failed", "network_timeout"),
        ("not_configured", "credential_missing"),
    ],
)
def test_typed_provider_failure_is_persisted_without_a_value(outcome, error):
    observation = AggregateObservation(
        provider="hunter",
        query_id="ollama",
        retrieved_at=NOW,
        outcome=outcome,
        error_code=error,
        data_mode="fixture",
    )
    service, repository, connector = make_service(observation)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert (result.status, result.error_code, result.value) == (outcome, error, None)
    assert len(repository.records) == 1 and connector.calls == 1


def test_missing_exposure_product_is_unknown_with_no_adapter_requests():
    service, repository, connector = make_service()
    result = service.collect_product_aggregate_observations(None, SCOPE, now=NOW)
    assert result[0].status == "unknown" and result[0].reason == "missing_product_query"
    assert result[0].value is None and connector.calls == 0 and repository.records == []


def test_unauthorized_server_collection_never_calls_adapter():
    service, _, connector = make_service(policy=AggregateServerPolicy("disabled", "fixture"))
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "unauthorized" and result.reason == "collection_not_authorized"
    assert connector.calls == 0


def test_new_failure_does_not_reuse_previous_success_as_current():
    service, repository, connector = make_service()
    repository.save_observation(
        total_result("hunter", "ollama", 12, NOW - timedelta(days=2), "fixture"),
        SCOPE,
        POLICY,
        recorded_at=NOW,
    )
    connector.observation = AggregateObservation(
        provider="hunter",
        query_id="ollama",
        retrieved_at=NOW,
        outcome="failed",
        error_code="network_timeout",
        data_mode="fixture",
    )
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "failed" and result.value is None
    assert result.previous_available.observation.value.service_count == 12
    reread = service.read_current_provider_aggregate("hunter", "ollama", SCOPE, now=NOW)
    assert reread.status == "failed" and reread.value is None
    assert reread.previous_available.observation.value.service_count == 12


def test_exact_ttl_is_stale_and_not_a_current_value():
    service, repository, connector = make_service()
    repository.save_observation(connector.observation, SCOPE, POLICY, recorded_at=NOW)
    result = service.read_current_provider_aggregate(
        "hunter", "ollama", SCOPE, now=NOW + timedelta(days=1)
    )
    assert result.status == "unknown" and result.reason == "stale"
    assert result.freshness == "stale" and result.value is None
    assert result.previous_available.observation.value.service_count == 0


def test_save_failure_never_advances_cache_or_returns_success():
    cache = FixtureCache()
    service, repository, connector = make_service(cache=cache)
    repository.fail_save = True
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "failed" and result.error_code == "persistence_failed"
    assert result.value is None and result.observation_id is None
    assert connector.calls == 1 and cache.calls == 0


def test_future_retrieval_is_persisted_but_never_displayed_as_current():
    service, _, _ = make_service(
        total_result("hunter", "ollama", 3, NOW + timedelta(seconds=1), "fixture")
    )
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "unknown" and result.reason == "future_retrieval"
    assert result.value is None


def test_fixture_live_identity_is_disjoint():
    live = AggregateServerPolicy("authorized-test", "live", True)
    assert aggregate_call_key("hunter", "ollama", live) != aggregate_call_key(
        "hunter", "ollama", POLICY
    )


def test_excess_providers_and_query_injection_are_rejected():
    service, _, connector = make_service()
    with pytest.raises(ValueError):
        service.collect_product_aggregate_observations("ollama; all", SCOPE, now=NOW)
    with pytest.raises(ValueError):
        AggregateService(
            FixtureRepository(),
            {"hunter": connector, "quake": connector, "other": connector},
            POLICY,
        )
    assert connector.calls == 0


def test_concurrent_flight_has_one_adapter_call_and_no_waiting_retry():
    service, repository, connector = make_service()
    connector.release.clear()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            service.collect_provider_aggregate_observation, "hunter", "ollama", SCOPE, now=NOW
        )
        assert connector.started.wait(1)
        second = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
        connector.release.set()
        completed = first.result(timeout=2)
    assert completed.status == "available"
    assert second.status == "rate_limited" and second.reason == "collection_in_progress"
    assert connector.calls == 1 and len(repository.records) == 1


class MemorySafeCache:
    def __init__(self) -> None:
        self.payloads: dict[str, str] = {}
        self.ttls: list[int] = []

    def get(self, identity: str) -> str | None:
        return self.payloads.get(identity)

    def set(self, identity: str, payload: str, ttl_seconds: int) -> None:
        self.payloads[identity] = payload
        self.ttls.append(ttl_seconds)


def test_cache_has_only_persisted_safe_totals_and_pg_always_gates_reads():
    cache = MemorySafeCache()
    policy = AggregateServerPolicy("synthetic-live-label", "live", True)
    service, repository, connector = make_service(policy=policy, cache=cache)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.cache_status == "written" and cache.ttls == [86400]
    reread = service.read_current_provider_aggregate("hunter", "ollama", SCOPE, now=NOW)
    assert reread.cache_status == "verified" and reread.value.service_count == 0
    payload = cache.payloads[result.cache_identity]
    assert (
        "headers" not in payload
        and "limitations" not in payload
        and '"data_mode":"live"' in payload
    )
    cache.payloads[result.cache_identity] = payload.replace(
        '"service_count":0', '"service_count":999'
    )
    invalid = service.read_current_provider_aggregate("hunter", "ollama", SCOPE, now=NOW)
    assert invalid.cache_status == "invalid" and invalid.value.service_count == 0
    repository.records.clear()
    gone = service.read_current_provider_aggregate("hunter", "ollama", SCOPE, now=NOW)
    assert gone.status == "unknown" and gone.value is None
    assert connector.calls == 1


def test_optional_cache_failure_cannot_override_a_committed_pg_result():
    cache = FixtureCache()
    policy = AggregateServerPolicy("synthetic-live-label", "live", True)
    service, repository, connector = make_service(policy=policy, cache=cache)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "available" and result.cache_status == "failed"
    assert result.value.service_count == 0 and len(repository.records) == 1
    assert "provider-secret" not in repr(result) and connector.calls == 1


def test_stale_live_label_never_reads_shared_cache():
    cache = FixtureCache()
    policy = AggregateServerPolicy("synthetic-live-label", "live", True)
    service, repository, connector = make_service(policy=policy, cache=cache)
    repository.save_observation(connector.observation, SCOPE, policy, recorded_at=NOW)
    result = service.read_current_provider_aggregate(
        "hunter", "ollama", SCOPE, now=NOW + timedelta(days=1)
    )
    assert result.reason == "stale" and result.value is None
    assert cache.calls == 0


def test_current_and_observed_ttl_have_independent_boundary():
    service, repository, connector = make_service()
    observation = connector.observation
    observed_value = observation.value.model_copy(update={"observed_at": NOW - timedelta(hours=23)})
    repository.save_observation(
        observation.model_copy(update={"value": observed_value}), SCOPE, POLICY, recorded_at=NOW
    )
    assert (
        service.read_current_provider_aggregate("hunter", "ollama", SCOPE, now=NOW).freshness
        == "current"
    )
    stale = service.read_current_provider_aggregate(
        "hunter", "ollama", SCOPE, now=NOW + timedelta(hours=1)
    )
    assert stale.freshness == "stale" and stale.value is None


def test_unexpected_adapter_error_is_saved_with_a_fixed_safe_error():
    service, repository, connector = make_service()

    def fail(query_id, *, retrieved_at=None):
        raise RuntimeError("provider-secret header and raw host records")

    connector.collect = fail
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "failed" and result.error_code == "network_error"
    assert len(repository.records) == 1 and result.value is None
    assert "provider-secret" not in repr(repository.records) and "provider-secret" not in repr(
        result
    )


def test_product_entry_calls_each_configured_provider_once_sequentially():
    repository = FixtureRepository()
    hunter = FixtureConnector(total_result("hunter", "ollama", 4, NOW, "fixture"))
    quake = FixtureConnector(total_result("quake", "ollama", 6, NOW, "fixture"))
    service = AggregateService(repository, {"hunter": hunter, "quake": quake}, POLICY)
    results = service.collect_product_aggregate_observations("ollama", SCOPE, now=NOW)
    assert [result.value.service_count for result in results] == [4, 6]
    assert hunter.calls == quake.calls == 1
