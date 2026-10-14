"""真实PG运行观测边界；固定比较时刻不冒充墙钟持续运行。"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.infrastructure.runtime_observations import (
    read_runtime_readiness,
    record_runtime_observation,
)
from ai_intel.knowledge.models import runtime_observations

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def observation_engine(migrated_engine: Engine) -> Iterator[Engine]:
    """专用test库中每例独立schema，不覆盖正在运行组件的观测。"""
    schema_name = "test_r01_observations_" + uuid4().hex
    with migrated_engine.begin() as connection:
        connection.execute(CreateSchema(schema_name))
    isolated_engine = migrated_engine.execution_options(schema_translate_map={None: schema_name})
    try:
        runtime_observations.create(isolated_engine)
        yield isolated_engine
    finally:
        with migrated_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True))


@pytest.mark.parametrize(
    ("age", "expected_state"),
    [
        (None, "not_observed_or_stale"),
        (timedelta(0), "ready"),
        (timedelta(seconds=44), "ready"),
        (timedelta(seconds=45), "ready"),
        (timedelta(seconds=45, microseconds=1), "not_observed_or_stale"),
        (timedelta(microseconds=-1), "not_observed_or_stale"),
        (timedelta(days=1), "not_observed_or_stale"),
    ],
)
def test_pg_readiness_includes_45_seconds_but_rejects_future_and_missing(
    observation_engine: Engine, age: timedelta | None, expected_state: str
) -> None:
    comparison_time = datetime(2026, 10, 15, 0, 0, 0, tzinfo=UTC)
    if age is not None:
        record_runtime_observation(observation_engine, "worker", comparison_time - age)
    assert read_runtime_readiness(observation_engine, comparison_time) == {
        "worker": {"state": expected_state},
        "scheduler": {"state": "not_observed_or_stale"},
    }


def test_pg_component_upsert_persists_one_row_across_new_engine(observation_engine: Engine) -> None:
    first_observation = datetime(2026, 10, 15, 0, 0, 0, tzinfo=UTC)
    last_observation = first_observation + timedelta(seconds=10)
    record_runtime_observation(observation_engine, "scheduler", first_observation)
    record_runtime_observation(observation_engine, "scheduler", last_observation)
    fresh_engine = create_engine(
        observation_engine.url,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
        execution_options=observation_engine.get_execution_options(),
    )
    try:
        with fresh_engine.connect() as connection:
            rows = connection.execute(select(runtime_observations)).mappings().all()
        assert len(rows) == 1
        assert rows[0]["observed_at"] == last_observation
        assert read_runtime_readiness(fresh_engine, last_observation) == {
            "worker": {"state": "not_observed_or_stale"},
            "scheduler": {"state": "ready"},
        }
    finally:
        fresh_engine.dispose()
