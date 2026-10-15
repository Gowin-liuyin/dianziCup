"""Real isolated PostgreSQL, explicit synthetic observations, zero provider wire calls."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError

from ai_intel.assets import aggregate_repository
from ai_intel.assets.aggregate_observations import AggregateObservation, total_result
from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.assets.aggregate_repository import (
    AggregateIdentityCollision,
    AggregatePersistenceError,
    AggregateServerPolicy,
    PostgresAggregateRepository,
)
from ai_intel.assets.aggregate_service import AggregateService
from ai_intel.assets.hunter_aggregate import HunterAggregateConnector
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.network import FetchResult

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 20, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("operator", "tenant-a", Role.SYSTEM_ADMIN)


@pytest.fixture
def repository(migrated_engine: Engine):
    return PostgresAggregateRepository(migrated_engine)


@pytest.fixture
def policy():
    return AggregateServerPolicy("test-" + uuid4().hex, "fixture", True)


@pytest.mark.parametrize(
    "total,outcome,error",
    [(0, "available", None), (57, "available", None), (None, "unknown", "missing_total")],
)
def test_pg_normal_zero_and_missing(repository, policy, total, outcome, error):
    observation = total_result("hunter", "ollama", total, NOW, "fixture")
    stored = repository.save_observation(observation, ADMIN, policy, recorded_at=NOW)
    result = repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW)
    assert result == stored
    assert (result.observation.outcome, result.observation.error_code) == (outcome, error)
    assert (
        result.observation.value is None
        if total is None
        else result.observation.value.service_count == total
    )
    assert result.fee_status == "unknown"


@pytest.mark.parametrize(
    "outcome,error",
    [
        ("unauthorized", "provider_unauthorized"),
        ("rate_limited", "provider_rate_limited"),
        ("failed", "network_timeout"),
        ("not_configured", "credential_missing"),
    ],
)
def test_pg_failed_outcomes_do_not_hide_behind_old_value(repository, policy, outcome, error):
    old = repository.save_observation(
        total_result("hunter", "ollama", 13, NOW - timedelta(hours=1), "fixture"),
        ADMIN,
        policy,
        recorded_at=NOW,
    )
    failure = AggregateObservation(
        provider="hunter",
        query_id="ollama",
        retrieved_at=NOW,
        outcome=outcome,
        error_code=error,
        data_mode="fixture",
    )
    repository.save_observation(failure, ADMIN, policy, recorded_at=NOW)
    current = repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW)
    assert current.observation.value is None and current.observation.outcome == outcome
    history = repository.read_latest(
        "hunter", "ollama", ADMIN, policy, now=NOW, available_only=True
    )
    assert history == old


def test_pg_replay_is_idempotent_and_collision_preserves_original(repository, policy):
    identifier = uuid4()
    observation = total_result("hunter", "ollama", 7, NOW, "fixture")
    first = repository.save_observation(
        observation, ADMIN, policy, recorded_at=NOW, observation_id=identifier
    )
    assert (
        repository.save_observation(
            observation,
            ADMIN,
            policy,
            recorded_at=NOW + timedelta(seconds=1),
            observation_id=identifier,
        )
        == first
    )
    with pytest.raises(AggregateIdentityCollision):
        repository.save_observation(
            total_result("hunter", "ollama", 8, NOW, "fixture"),
            ADMIN,
            policy,
            recorded_at=NOW,
            observation_id=identifier,
        )
    assert repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW) == first


def test_pg_parallel_same_uuid_is_one_immutable_record(repository, policy):
    identifier = uuid4()
    observation = total_result("quake", "vllm", 9, NOW, "fixture")

    def save():
        return repository.save_observation(
            observation, ADMIN, policy, recorded_at=NOW, observation_id=identifier
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: save(), range(8)))
    assert all(result == results[0] for result in results)
    with repository.engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(aggregate_observations)
                .where(aggregate_observations.c.observation_id == identifier)
            ).scalar()
            == 1
        )


def test_pg_rollback_after_insert_does_not_leave_success(repository, policy, monkeypatch):
    identifier = uuid4()

    def reject(_row):
        raise AggregatePersistenceError("forced typed integrity failure")

    with monkeypatch.context() as patch:
        patch.setattr(aggregate_repository, "stored_aggregate", reject)
        with pytest.raises(AggregatePersistenceError):
            repository.save_observation(
                total_result("hunter", "ollama", 7, NOW, "fixture"),
                ADMIN,
                policy,
                recorded_at=NOW,
                observation_id=identifier,
            )
    with repository.engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(aggregate_observations)
                .where(aggregate_observations.c.observation_id == identifier)
            ).scalar()
            == 0
        )


@pytest.mark.parametrize("mutation", ["update", "delete"])
def test_pg_rejects_history_mutation(repository, policy, mutation):
    stored = repository.save_observation(
        total_result("hunter", "ollama", 7, NOW, "fixture"), ADMIN, policy, recorded_at=NOW
    )
    statement = (
        update(aggregate_observations).values(outcome="failed", error_code="network_error")
        if mutation == "update"
        else delete(aggregate_observations)
    )
    with pytest.raises(DBAPIError) as blocked, repository.engine.begin() as connection:
        connection.execute(
            statement.where(aggregate_observations.c.observation_id == stored.observation_id)
        )
    assert "immutable" in str(blocked.value)
    assert repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW) == stored


def test_pg_older_and_future_observations_never_replace_present(repository, policy):
    present = repository.save_observation(
        total_result("hunter", "ollama", 7, NOW, "fixture"), ADMIN, policy, recorded_at=NOW
    )
    repository.save_observation(
        total_result("hunter", "ollama", 4, NOW - timedelta(hours=1), "fixture"),
        ADMIN,
        policy,
        recorded_at=NOW,
    )
    repository.save_observation(
        total_result("hunter", "ollama", 99, NOW + timedelta(hours=1), "fixture"),
        ADMIN,
        policy,
        recorded_at=NOW,
    )
    assert repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW) == present


def test_pg_public_shared_but_tenant_scope_never_crosses(repository):
    public = AggregateServerPolicy("public-" + uuid4().hex, "fixture", True)
    private = AggregateServerPolicy("tenant-" + uuid4().hex, "fixture", True, "tenant")
    other = AccessScope.for_authenticated_user("other", "tenant-b", Role.TENANT_ADMIN)
    record = total_result("hunter", "ollama", 3, NOW, "fixture")
    shared = repository.save_observation(record, ADMIN, public, recorded_at=NOW)
    assert repository.read_latest("hunter", "ollama", other, public, now=NOW) == shared
    repository.save_observation(record, ADMIN, private, recorded_at=NOW)
    assert repository.read_latest("hunter", "ollama", other, private, now=NOW) is None
    viewer = AccessScope.for_authenticated_user("viewer", "tenant-a", Role.VIEWER)
    with pytest.raises(PermissionDeniedError):
        repository.save_observation(record, viewer, public, recorded_at=NOW)


def test_pg_mode_isolation_and_mismatched_payload_denied(repository, policy):
    fixture = total_result("hunter", "ollama", 3, NOW, "fixture")
    repository.save_observation(fixture, ADMIN, policy, recorded_at=NOW)
    live = AggregateServerPolicy(policy.authorization_profile, "live", True)
    assert repository.read_latest("hunter", "ollama", ADMIN, live, now=NOW) is None
    with pytest.raises(ValueError):
        repository.save_observation(fixture, ADMIN, live, recorded_at=NOW)


def test_pg_detects_json_and_index_corruption_on_read(repository, policy):
    stored = repository.save_observation(
        total_result("hunter", "ollama", 7, NOW, "fixture"), ADMIN, policy, recorded_at=NOW
    )
    with repository.engine.begin() as connection:
        values = dict(
            connection.execute(
                select(aggregate_observations).where(
                    aggregate_observations.c.observation_id == stored.observation_id
                )
            )
            .mappings()
            .one()
        )
        values["observation_id"] = uuid4()
        values["canonical_json"]["value"]["service_count"] = 8
        values["retrieved_at"] = NOW + timedelta(seconds=1)
        connection.execute(insert(aggregate_observations).values(**values))
    with pytest.raises(AggregatePersistenceError):
        repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW + timedelta(seconds=1))


def test_pg_safe_aggregate_does_not_emit_public_outbox_or_raw_records(repository, policy):
    with repository.engine.connect() as connection:
        before = connection.execute(text("SELECT count(*) FROM outbox_events")).scalar()
    observation = total_result("hunter", "ollama", 7, NOW, "fixture")
    stored = repository.save_observation(observation, ADMIN, policy, recorded_at=NOW)
    with repository.engine.connect() as connection:
        raw = connection.execute(
            select(aggregate_observations.c.canonical_json).where(
                aggregate_observations.c.observation_id == stored.observation_id
            )
        ).scalar_one()
        assert connection.execute(text("SELECT count(*) FROM outbox_events")).scalar() == before
    assert raw["value"]["service_count"] == 7
    assert not {"ip", "host", "headers", "response_body", "api_key", "assets"}.intersection(raw)
    assert "provider-secret" not in json.dumps(raw)


class RawProviderFixtureGateway:
    def __init__(self):
        self.adapter_calls = 0

    def fetch(self, url, max_redirect_hops=5):
        self.adapter_calls += 1
        return FetchResult(
            url,
            200,
            "application/json",
            b'{"code":200,"data":{"total":11,"arr":[{"ip":"192.0.2.99","api_key":"provider-secret"}]}}',
        )

    def post_json(self, url, payload):
        raise AssertionError("no POST for the explicit Hunter fixture")


def test_pg_service_reuses_safe_record_without_second_adapter_call(repository, policy):
    gateway = RawProviderFixtureGateway()
    service = AggregateService(
        repository, {"hunter": HunterAggregateConnector(fixture_gateway=gateway)}, policy
    )
    first = service.collect_provider_aggregate_observation("hunter", "ollama", ADMIN, now=NOW)
    second = service.collect_provider_aggregate_observation("hunter", "ollama", ADMIN, now=NOW)
    assert first.status == second.status == "available"
    assert first.value.service_count == second.value.service_count == 11
    assert first.freshness == "unknown" and first.observation_id == second.observation_id
    assert gateway.adapter_calls == 1
    with repository.engine.connect() as connection:
        raw = connection.execute(
            select(aggregate_observations.c.canonical_json).where(
                aggregate_observations.c.observation_id == first.observation_id
            )
        ).scalar_one()
    assert "provider-secret" not in json.dumps(raw) and "192.0.2.99" not in json.dumps(raw)


def test_pg_equal_retrieval_timestamps_choose_failure_conservatively(repository, policy):
    failure = AggregateObservation(
        provider="hunter",
        query_id="ollama",
        retrieved_at=NOW,
        outcome="failed",
        error_code="network_timeout",
        data_mode="fixture",
    )
    repository.save_observation(failure, ADMIN, policy, recorded_at=NOW)
    repository.save_observation(
        total_result("hunter", "ollama", 7, NOW, "fixture"), ADMIN, policy, recorded_at=NOW
    )
    assert (
        repository.read_latest("hunter", "ollama", ADMIN, policy, now=NOW).observation.outcome
        == "failed"
    )


def test_pg_error_check_rejects_null_error_in_an_unavailable_row(repository, policy):
    stored = repository.save_observation(
        total_result("hunter", "ollama", 7, NOW, "fixture"), ADMIN, policy, recorded_at=NOW
    )
    with repository.engine.connect() as connection:
        values = dict(
            connection.execute(
                select(aggregate_observations).where(
                    aggregate_observations.c.observation_id == stored.observation_id
                )
            )
            .mappings()
            .one()
        )
    values.update(observation_id=uuid4(), outcome="unknown", error_code=None)
    with pytest.raises(IntegrityError), repository.engine.begin() as connection:
        connection.execute(insert(aggregate_observations).values(**values))
