"""Synthetic live labels exercise cache seconds without any provider wire requests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ai_intel.assets.aggregate_observations import total_result
from ai_intel.assets.aggregate_repository import (
    AggregateServerPolicy,
    StoredAggregate,
    aggregate_call_key,
    canonical_observation,
)
from ai_intel.assets.aggregate_service import AggregateService
from ai_intel.domain.access import AccessScope, Role

NOW = datetime(2026, 10, 16, 1, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("ttl-fixture", "tenant-a", Role.SYSTEM_ADMIN)


class FixtureRepository:
    def __init__(self):
        self.records = []

    def read_latest(self, provider, query_id, scope, policy, *, now, available_only=False):
        key = aggregate_call_key(provider, query_id, policy)
        records = [
            record
            for record in self.records
            if record.call_key == key
            and record.observation.retrieved_at <= now
            and (not available_only or record.observation.outcome == "available")
        ]
        return max(records, key=lambda record: record.observation.retrieved_at, default=None)

    def save_observation(self, observation, scope, policy, *, recorded_at, observation_id=None):
        _, digest = canonical_observation(observation)
        stored = StoredAggregate(
            observation_id or uuid4(),
            observation,
            digest,
            aggregate_call_key(observation.provider, observation.query_id, policy),
            "public",
            recorded_at,
        )
        self.records.append(stored)
        return stored


class FixtureConnector:
    def __init__(self, observation):
        self.observation = observation
        self.calls = 0

    def collect(self, query_id, *, retrieved_at=None):
        self.calls += 1
        return self.observation


class FixtureCache:
    def __init__(self, fail=False):
        self.writes = []
        self.reads = 0
        self.fail = fail

    def get(self, identity):
        self.reads += 1
        return None

    def set(self, identity, payload, ttl_seconds):
        if self.fail:
            raise RuntimeError("synthetic-cache-failure")
        self.writes.append((identity, payload, ttl_seconds))


def build_fixture_service(
    age_seconds=0, *, observed_age_seconds=None, data_mode="live", cache_fail=False
):
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
    policy = AggregateServerPolicy("ttl-synthetic-boundary", data_mode, True)
    repository = FixtureRepository()
    connector = FixtureConnector(observation)
    cache = FixtureCache(cache_fail)
    return (
        AggregateService(repository, {"hunter": connector}, policy, safe_cache=cache),
        repository,
        connector,
        cache,
    )


@pytest.mark.parametrize(
    "age_seconds,expected_ttls,status",
    [
        (86399, [1], "available"),
        (86399.5, [], "available"),
        (86400, [], "unknown"),
    ],
)
def test_cache_ttl_never_exceeds_fractional_pg_retrieval_remaining(
    age_seconds, expected_ttls, status
):
    service, repository, connector, cache = build_fixture_service(age_seconds)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert [write[2] for write in cache.writes] == expected_ttls
    assert result.status == status
    assert len(repository.records) == 1 and connector.calls == 1
    for ttl in expected_ttls:
        assert ttl <= 86400 - age_seconds


@pytest.mark.parametrize(
    "observed_age_seconds,expected_ttls", [(86399, [1]), (86399.5, []), (86400, [])]
)
def test_observed_time_remaining_also_limits_cache_ttl(observed_age_seconds, expected_ttls):
    service, _, _, cache = build_fixture_service(observed_age_seconds=observed_age_seconds)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert [write[2] for write in cache.writes] == expected_ttls
    assert result.freshness == ("stale" if observed_age_seconds == 86400 else "current")


def test_future_retrieval_is_never_written_to_cache_or_exposed_current():
    service, _, connector, cache = build_fixture_service(-0.5)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.reason == "future_retrieval" and result.value is None
    assert cache.writes == [] and cache.reads == 0 and connector.calls == 1


def test_future_observation_is_rejected_before_safe_cache_write():
    service, repository, _, cache = build_fixture_service(observed_age_seconds=-0.5)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "failed" and result.error_code == "invalid_response"
    assert repository.records[0].observation.value is None
    assert cache.writes == [] and cache.reads == 0


def test_cache_failure_still_returns_only_committed_available_pg_value():
    service, repository, _, cache = build_fixture_service(86399, cache_fail=True)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.status == "available" and result.cache_status == "failed"
    assert result.value.service_count == repository.records[0].observation.value.service_count == 7
    assert cache.writes == []


def test_fixture_never_writes_even_at_one_second_remaining():
    service, _, _, cache = build_fixture_service(86399, data_mode="fixture")
    result = service.collect_provider_aggregate_observation("hunter", "ollama", SCOPE, now=NOW)
    assert result.cache_status == "bypassed_fixture"
    assert cache.writes == [] and cache.reads == 0
