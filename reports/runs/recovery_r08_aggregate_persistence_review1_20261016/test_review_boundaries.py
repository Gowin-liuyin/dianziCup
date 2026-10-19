"""Independent isolated PG and synthetic-label boundary probes; zero wire requests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import json
from threading import Barrier, Event, Lock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, insert, select, text

from ai_intel.assets.aggregate_observations import AggregateObservation, total_result
from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.assets.aggregate_repository import (
    AggregateIdentityCollision, AggregatePersistenceError, AggregateServerPolicy,
    PostgresAggregateRepository, aggregate_call_key,
)
from ai_intel.assets.aggregate_service import AggregateService, safe_cache_payload
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from prepare_pg import DATABASE_NAME, test_connection as approved_test_connection

NOW = datetime(2026, 10, 15, 20, 0, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("reviewer", "review-tenant-a", Role.SYSTEM_ADMIN)


@pytest.fixture
def repository():
    engine = create_engine(approved_test_connection().set(database=DATABASE_NAME), hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=20000 -c lock_timeout=5000"})
    with engine.connect() as connection:
        assert connection.execute(text("SELECT current_database()")).scalar() == DATABASE_NAME
    try:
        yield PostgresAggregateRepository(engine)
    finally:
        engine.dispose()


@pytest.fixture
def policy():
    return AggregateServerPolicy("review-" + uuid4().hex, "fixture", True)


class Connector:
    def __init__(self, observation):
        self.observation = observation
        self.calls = 0

    def collect(self, query_id, *, retrieved_at=None):
        self.calls += 1
        return self.observation


class Cache:
    def __init__(self):
        self.payload = None
        self.ttls = []
        self.gets = 0

    def get(self, identity):
        self.gets += 1
        return self.payload

    def set(self, identity, payload, ttl_seconds):
        self.payload = payload
        self.ttls.append(ttl_seconds)


@pytest.mark.parametrize("role,visibility", [
    (Role.TENANT_ADMIN, "public"), (Role.ANALYST, "public"), (Role.VIEWER, "public"),
    (Role.ANALYST, "tenant"), (Role.VIEWER, "tenant"),
])
def test_negative_write_permissions_leave_no_rows(repository, policy, role, visibility):
    selected = AggregateServerPolicy(policy.authorization_profile, "fixture", True, visibility)
    scope = AccessScope.for_authenticated_user("restricted", "review-tenant-a", role)
    observation = total_result("hunter", "ollama", 5, NOW, "fixture")
    with pytest.raises(PermissionDeniedError):
        repository.save_observation(observation, scope, selected, recorded_at=NOW)
    with repository.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(aggregate_observations).where(
            aggregate_observations.c.call_key == aggregate_call_key("hunter", "ollama", selected))).scalar() == 0


def test_tenant_write_and_read_scope_are_server_selected(repository, policy):
    selected = AggregateServerPolicy(policy.authorization_profile, "fixture", True, "tenant")
    scope_a = AccessScope.for_authenticated_user("a", "review-tenant-a", Role.TENANT_ADMIN)
    scope_b = AccessScope.for_authenticated_user("b", "review-tenant-b", Role.TENANT_ADMIN)
    observation = total_result("hunter", "ollama", 5, NOW, "fixture")
    first = repository.save_observation(observation, scope_a, selected, recorded_at=NOW)
    assert first.scope_key == "tenant:review-tenant-a"
    assert repository.read_latest("hunter", "ollama", scope_b, selected, now=NOW) is None
    with pytest.raises(AggregateIdentityCollision):
        repository.save_observation(observation, scope_b, selected, recorded_at=NOW,
            observation_id=first.observation_id)
    assert repository.read_latest("hunter", "ollama", scope_a, selected, now=NOW) == first


@pytest.mark.parametrize("column,replacement", [
    ("provider", "quake"), ("query_id", "vllm"), ("data_mode", "live"),
    ("payload_sha256", "0" * 64), ("observed_at", NOW),
])
def test_negative_duplicate_columns_fail_closed(repository, policy, column, replacement):
    first = repository.save_observation(total_result("hunter", "ollama", 5, NOW, "fixture"),
        ADMIN, policy, recorded_at=NOW)
    with repository.engine.begin() as connection:
        values = dict(connection.execute(select(aggregate_observations).where(
            aggregate_observations.c.observation_id == first.observation_id)).mappings().one())
        values.update(observation_id=uuid4(), recorded_at=NOW + timedelta(seconds=1))
        values[column] = replacement
        connection.execute(insert(aggregate_observations).values(**values))
    service = AggregateService(repository, {"hunter": Connector(first.observation)}, policy)
    result = service.read_current_provider_aggregate("hunter", "ollama", ADMIN, now=NOW)
    assert result.status == "failed" and result.error_code == "persistence_failed"
    assert result.value is None


@pytest.mark.parametrize("field,replacement", [
    ("observation_id", str(uuid4())), ("payload_sha256", "0" * 64),
    ("query_version", "unapproved"), ("data_mode", "fixture"), ("ttl_seconds", 999999),
])
def test_negative_cache_identity_always_returns_pg_value(repository, policy, field, replacement):
    live = AggregateServerPolicy(policy.authorization_profile, "live", True)
    observation = total_result("hunter", "ollama", 5, NOW, "live")
    stored = repository.save_observation(observation, ADMIN, live, recorded_at=NOW)
    cache = Cache()
    payload = json.loads(safe_cache_payload(stored))
    payload[field] = replacement
    cache.payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    service = AggregateService(repository, {"hunter": Connector(observation)}, live, safe_cache=cache)
    result = service.read_current_provider_aggregate("hunter", "ollama", ADMIN, now=NOW)
    assert result.cache_status == "invalid" and result.value.service_count == 5
    assert result.observation_id == stored.observation_id and result.freshness == "unknown"


def test_pg_save_failure_does_not_advance_live_label_cache(repository, policy, monkeypatch):
    live = AggregateServerPolicy(policy.authorization_profile, "live", True)
    connector = Connector(total_result("hunter", "ollama", 5, NOW, "live"))
    cache = Cache()
    service = AggregateService(repository, {"hunter": connector}, live, safe_cache=cache)
    def reject(*args, **kwargs):
        raise AggregatePersistenceError("controlled test failure")
    monkeypatch.setattr(repository, "save_observation", reject)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", ADMIN, now=NOW)
    assert result.status == "failed" and result.error_code == "persistence_failed"
    assert result.value is None and result.observation_id is None and cache.ttls == []
    assert connector.calls == 1


def test_shared_pg_eight_services_have_documented_duplicate_calls(repository, policy):
    gate = Barrier(8)
    guard = Lock()
    calls = []
    class BoundedConnector:
        def collect(self, query_id, *, retrieved_at=None):
            with guard:
                calls.append(query_id)
            gate.wait(timeout=5)
            return total_result("hunter", "ollama", 5, NOW, "fixture")
    services = [AggregateService(repository, {"hunter": BoundedConnector()}, policy) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda service: service.collect_provider_aggregate_observation(
            "hunter", "ollama", ADMIN, now=NOW), services))
    assert all(result.status == "available" for result in results)
    assert len(calls) == 8 and len({result.observation_id for result in results}) == 8
    with repository.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(aggregate_observations).where(
            aggregate_observations.c.call_key == aggregate_call_key("hunter", "ollama", policy),
            aggregate_observations.c.observation_id.in_([result.observation_id for result in results]))).scalar() == 8


def test_same_uuid_different_payload_eight_writers_preserve_one_winner(repository, policy):
    identifier = uuid4()
    gate = Barrier(8)
    def save(number):
        gate.wait(timeout=5)
        try:
            result = repository.save_observation(total_result("hunter", "ollama", number, NOW, "fixture"),
                ADMIN, policy, recorded_at=NOW, observation_id=identifier)
            return ("saved", result.observation.value.service_count)
        except AggregateIdentityCollision:
            return ("collision", number)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(save, range(8)))
    assert sum(status == "saved" for status, number in results) == 1
    assert sum(status == "collision" for status, number in results) == 7
    winner = next(number for status, number in results if status == "saved")
    current = repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW)
    assert current.observation.value.service_count == winner and current.observation_id == identifier


def test_observed_ttl_and_clock_boundaries_use_pg_without_cache(repository, policy):
    live = AggregateServerPolicy(policy.authorization_profile, "live", True)
    observation = total_result("hunter", "ollama", 5, NOW, "live")
    value = observation.value.model_copy(update={"observed_at": NOW - timedelta(hours=23)})
    observation = observation.model_copy(update={"value": value})
    repository.save_observation(observation, ADMIN, live, recorded_at=NOW)
    cache = Cache()
    service = AggregateService(repository, {"hunter": Connector(observation)}, live, safe_cache=cache)
    before = service.read_current_provider_aggregate("hunter", "ollama", ADMIN,
        now=NOW + timedelta(hours=1) - timedelta(microseconds=1))
    exact = service.read_current_provider_aggregate("hunter", "ollama", ADMIN,
        now=NOW + timedelta(hours=1))
    assert before.freshness == "current" and before.value.service_count == 5
    assert exact.freshness == "stale" and exact.value is None and cache.gets == 1
    future = observation.model_copy(update={"retrieved_at": NOW + timedelta(seconds=1),
        "value": observation.value.model_copy(update={"retrieved_at": NOW + timedelta(seconds=1)})})
    repository.save_observation(future, ADMIN, live, recorded_at=NOW + timedelta(seconds=1))
    assert service.read_current_provider_aggregate("hunter", "ollama", ADMIN, now=NOW).observation_id == before.observation_id


def test_cache_ttl_never_exceeds_fractional_pg_remaining_lifetime(repository, policy):
    live = AggregateServerPolicy(policy.authorization_profile, "live", True)
    observation = total_result("hunter", "ollama", 5, NOW, "live")
    cache = Cache()
    service = AggregateService(repository, {"hunter": Connector(observation)}, live, safe_cache=cache)
    reference_time = NOW + timedelta(seconds=86399, microseconds=500000)
    result = service.collect_provider_aggregate_observation("hunter", "ollama", ADMIN, now=reference_time)
    assert result.status == "available" and result.freshness == "unknown"
    remaining = (NOW + timedelta(seconds=86400) - reference_time).total_seconds()
    assert not cache.ttls or cache.ttls[-1] <= remaining


def test_four_in_flight_keys_reject_fifth_without_waiting_or_db_lock(repository, policy):
    private = AggregateServerPolicy(policy.authorization_profile, "fixture", True, "tenant")
    scopes = [AccessScope.for_authenticated_user("operator", "capacity-" + str(number),
        Role.TENANT_ADMIN) for number in range(5)]
    release = Event()
    all_started = Event()
    guard = Lock()
    calls = []
    class BlockingConnector:
        def collect(self, query_id, *, retrieved_at=None):
            with guard:
                calls.append(query_id)
                if len(calls) == 4:
                    all_started.set()
            assert release.wait(5)
            return total_result("hunter", "ollama", 5, NOW, "fixture")
    service = AggregateService(repository, {"hunter": BlockingConnector()}, private)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = [pool.submit(service.collect_provider_aggregate_observation, "hunter",
            "ollama", scope, now=NOW) for scope in scopes[:4]]
        try:
            assert all_started.wait(5)
            assert repository.engine.pool.checkedout() == 0
            rejected = service.collect_provider_aggregate_observation("hunter", "ollama",
                scopes[4], now=NOW)
            assert rejected.status == "rate_limited" and rejected.reason == "collection_in_progress"
            assert len(calls) == 4
        finally:
            release.set()
        assert all(future.result(timeout=5).status == "available" for future in pending)


def test_fixture_pg_service_never_reads_or_writes_shared_cache(repository, policy):
    cache = Cache()
    observation = total_result("hunter", "ollama", 5, NOW, "fixture")
    service = AggregateService(repository, {"hunter": Connector(observation)}, policy, safe_cache=cache)
    created = service.collect_provider_aggregate_observation("hunter", "ollama", ADMIN, now=NOW)
    read = service.read_current_provider_aggregate("hunter", "ollama", ADMIN, now=NOW)
    assert created.cache_status == read.cache_status == "bypassed_fixture"
    assert cache.gets == 0 and cache.ttls == []
