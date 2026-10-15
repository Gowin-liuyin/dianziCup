"""Production head rejects forged aggregate fields and immutable history mutations."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from ai_intel.assets.aggregate_observations import total_result
from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.assets.aggregate_repository import AggregateServerPolicy, PostgresAggregateRepository
from ai_intel.domain.access import AccessScope, Role

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("migration-fixture-operator", None, Role.SYSTEM_ADMIN)


@pytest.fixture
def aggregate_record(migrated_engine):
    with migrated_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0019_aggregate_observations"
        )
    repository = PostgresAggregateRepository(migrated_engine)
    stored = repository.save_observation(
        total_result("hunter", "ollama", 0, NOW, "fixture"),
        SCOPE,
        AggregateServerPolicy("migration-" + uuid4().hex, "fixture", True),
        recorded_at=NOW,
    )
    with migrated_engine.connect() as connection:
        return dict(
            connection.execute(
                select(aggregate_observations).where(
                    aggregate_observations.c.observation_id == stored.observation_id
                )
            )
            .mappings()
            .one()
        )


@pytest.mark.parametrize(
    "changes,constraint",
    [
        ({"schema_version": "other"}, "ck_r08_schema"),
        ({"provider": "other"}, "ck_r08_provider"),
        ({"query_id": "arbitrary_query"}, "ck_r08_query"),
        ({"query_version": "other"}, "ck_r08_query_version"),
        ({"data_mode": "unmarked"}, "ck_r08_mode"),
        ({"fee_status": "0"}, "ck_r08_fee"),
        ({"payload_sha256": "invalid"}, "ck_r08_hashes"),
        ({"call_key": "invalid"}, "ck_r08_hashes"),
        ({"scope_key": "tenant:forged"}, "ck_r08_scope"),
        ({"visibility": "tenant", "tenant_id": None}, "ck_r08_scope"),
        ({"outcome": "failed", "error_code": "uncontrolled_raw_error"}, "ck_r08_outcome"),
        ({"outcome": "available", "error_code": "network_timeout"}, "ck_r08_outcome"),
        ({"outcome": "unknown", "error_code": None}, "ck_r08_required_error"),
    ],
)
def test_production_checks_reject_invalid_safe_observation(
    migrated_engine, aggregate_record, changes, constraint
):
    forged_id = uuid4()
    forged = {**aggregate_record, "observation_id": forged_id, **changes}
    with pytest.raises(IntegrityError) as rejected, migrated_engine.begin() as connection:
        connection.execute(insert(aggregate_observations).values(**forged))
    assert rejected.value.orig.sqlstate == "23514"
    assert rejected.value.orig.diag.constraint_name == constraint
    with migrated_engine.connect() as connection:
        assert (
            connection.scalar(
                select(aggregate_observations.c.observation_id).where(
                    aggregate_observations.c.observation_id == forged_id
                )
            )
            is None
        )


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_production_database_rejects_aggregate_mutation(
    migrated_engine, aggregate_record, operation
):
    statement = (
        update(aggregate_observations).values(canonical_json={"forged": True})
        if operation == "update"
        else delete(aggregate_observations)
    ).where(aggregate_observations.c.observation_id == aggregate_record["observation_id"])
    with pytest.raises(DBAPIError) as rejected, migrated_engine.begin() as connection:
        connection.execute(statement)
    assert rejected.value.orig.sqlstate == "55000"
    with migrated_engine.connect() as connection:
        assert (
            dict(
                connection.execute(
                    select(aggregate_observations).where(
                        aggregate_observations.c.observation_id
                        == aggregate_record["observation_id"]
                    )
                )
                .mappings()
                .one()
            )
            == aggregate_record
        )
