"""Fractional cache seconds are checked after actual isolated PG commit; no provider wire IO."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from ai_intel.assets.aggregate_observations import AggregateObservation, total_result
from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.assets.aggregate_repository import AggregateServerPolicy, PostgresAggregateRepository
from ai_intel.assets.aggregate_service import AggregateService
from ai_intel.domain.access import AccessScope, Role

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, 1, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("ttl-pg-fixture", "tenant-a", Role.SYSTEM_ADMIN)


class FixtureConnector:
    def __init__(self, observation):
        self.observation = observation
        self.calls = 0

    def collect(self, query_id, *, retrieved_at=None):
        self.calls += 1
        return self.observation


class FixtureCache:
    def __init__(self, repository, fail=False):
        self.repository = repository
        self.writes = []
        self.reads = 0
        self.fail = fail

    def get(self, identity):
        self.reads += 1
        return None

    def set(self, identity, payload, ttl_seconds):
        cached = json.loads(payload)
        with self.repository.engine.connect() as connection:
            persisted = (
                connection.execute(
                    select(aggregate_observations).where(
                        aggregate_observations.c.observation_id == UUID(cached["observation_id"])
                    )
                )
                .mappings()
                .one()
            )
            assert persisted["payload_sha256"] == cached["payload_sha256"]
            assert persisted["canonical_json"]["value"]["service_count"] == cached["service_count"]
        if self.fail:
            raise RuntimeError("synthetic-cache-failure")
        self.writes.append((identity, payload, ttl_seconds))


def build_pg_service(
    engine, age_seconds=0, observed_age_seconds=None, data_mode="live", cache_fail=False
):
    repository = PostgresAggregateRepository(engine)
    observation = total_result(
        "hunter", "ollama", 7, NOW - timedelta(seconds=age_seconds), data_mode
    )
    if observed_age_seconds is not None:
        observation = observation.model_copy(
            update={
                "value": observation.value.model_copy(
                    update={"observed_at": NOW - timedelta(seconds=observed_age_seconds)}
                )
            }
        )
    policy = AggregateServerPolicy("ttl-pg-" + uuid4().hex, data_mode, True)
    connector = FixtureConnector(observation)
    cache = FixtureCache(repository, cache_fail)
    return (
        AggregateService(repository, {"hunter": connector}, policy, safe_cache=cache),
        repository,
        connector,
        cache,
    )


@pytest.mark.parametrize(
    "age_seconds,observed_age_seconds,expected_ttls,status",
    [
        (86399, None, [1], "available"),
        (86399.5, None, [], "available"),
        (86400, None, [], "unknown"),
        (0, 86399, [1], "available"),
        (0, 86399.5, [], "available"),
        (0, 86400, [], "unknown"),
    ],
)
def test_real_pg_remaining_lifetime_does_not_round_cache_ttl_up(
    migrated_engine, age_seconds, observed_age_seconds, expected_ttls, status
):
    service, repository, connector, cache = build_pg_service(
        migrated_engine, age_seconds, observed_age_seconds
    )
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == status and [write[2] for write in cache.writes] == expected_ttls
    assert result.observation_id is not None and connector.calls == 1
    stored = repository.read_latest("hunter", "ollama", SCOPE, service.server_policy, now=NOW)
    assert stored.observation.value.service_count == 7


def test_real_pg_latest_failed_does_not_read_old_total_from_cache(migrated_engine):
    service, repository, connector, cache = build_pg_service(migrated_engine, 86399)
    policy = service.server_policy
    previous = repository.save_observation(connector.observation, SCOPE, policy, recorded_at=NOW)
    failure = AggregateObservation(
        provider="hunter",
        query_id="ollama",
        retrieved_at=NOW,
        outcome="failed",
        error_code="network_timeout",
        data_mode="live",
    )
    repository.save_observation(failure, SCOPE, policy, recorded_at=NOW)
    result = service.read_current_provider_aggregate("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "failed" and result.value is None
    assert result.previous_available == previous
    assert cache.reads == 0 and cache.writes == [] and connector.calls == 0


def test_real_pg_cache_failure_cannot_turn_committed_zero_into_failure_or_stale(migrated_engine):
    service, repository, connector, cache = build_pg_service(
        migrated_engine, 86399, cache_fail=True
    )
    connector.observation = total_result(
        "hunter", "ollama", 0, NOW - timedelta(seconds=86399), "live"
    )
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "available" and result.cache_status == "failed"
    assert result.value.service_count == 0
    assert (
        repository.read_latest(
            "hunter", "ollama", SCOPE, service.server_policy, now=NOW
        ).observation.value.service_count
        == 0
    )
    assert cache.writes == []


def test_real_pg_fixture_never_uses_live_cache_or_live_call_identity(migrated_engine):
    service, repository, _, cache = build_pg_service(migrated_engine, 86399, data_mode="fixture")
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.cache_status == "bypassed_fixture" and cache.writes == [] and cache.reads == 0
    live_policy = AggregateServerPolicy(service.server_policy.authorization_profile, "live", True)
    assert repository.read_latest("hunter", "ollama", SCOPE, live_policy, now=NOW) is None


def test_real_pg_future_retrieval_remains_history_and_never_advances_cache(migrated_engine):
    service, repository, _, cache = build_pg_service(migrated_engine, -0.5)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.value is None and result.reason == "future_retrieval"
    assert repository.read_latest("hunter", "ollama", SCOPE, service.server_policy, now=NOW) is None
    assert cache.writes == [] and cache.reads == 0
