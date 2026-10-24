"""Default worker graph consumer registration, with explicit isolated driver substitutes."""

from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import SecretStr

from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.default_graph_runtime import (
    GRAPH_APPLY_JOB_TYPE,
    GRAPH_CAPTURE_JOB_TYPE,
    GRAPH_RECONCILE_JOB_TYPE,
    build_default_graph_job_handlers,
)
from ai_intel.knowledge.graph_projection import GRAPH_APPLY_JOB_TYPE as PROJECTION_APPLY

GRAPH_JOB_TYPES = (GRAPH_RECONCILE_JOB_TYPE, GRAPH_CAPTURE_JOB_TYPE, GRAPH_APPLY_JOB_TYPE)


def graph_settings(configured: bool) -> ApplicationSettings:
    return ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        database_url="postgresql://test_fixture:fixture-password@127.0.0.1:5432/test_dianzi_unit",
        redis_url="redis://127.0.0.1:26379/15",
        neo4j_uri="bolt://127.0.0.1:47687" if configured else None,
        neo4j_username="fixture-operator" if configured else None,
        neo4j_password=SecretStr("02" * 16) if configured else None,
    )


@pytest.mark.parametrize("configured", [False, True])
def test_default_graph_handlers_register_graph_types_without_real_neo4j(monkeypatch, configured):
    from ai_intel.knowledge import default_graph_runtime

    settings = graph_settings(configured)

    @contextmanager
    def projection_handlers(actual_engine, actual_settings):
        assert actual_settings is settings
        yield {"knowledge_change": object(), PROJECTION_APPLY + "-sentinel": object()}

    drivers = []

    def fake_driver(uri, auth=None, **kwargs):
        driver = MagicMock()
        drivers.append((uri, auth, driver))
        return driver

    monkeypatch.setattr(default_graph_runtime, "build_projection_job_handlers", projection_handlers)
    monkeypatch.setattr(default_graph_runtime.AsyncGraphDatabase, "driver", fake_driver)

    class EngineFixture:
        def dispose(self):
            return None

    with build_default_graph_job_handlers(EngineFixture(), settings) as handlers:
        for job_type in GRAPH_JOB_TYPES:
            assert handlers[job_type] is not None
        if configured:
            assert drivers and drivers[0][0] == "bolt://127.0.0.1:47687"
        else:
            assert drivers == []
    if configured:
        drivers[0][2].close.assert_called_once()


def test_default_worker_consume_job_registers_graph_types(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "fixture")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test_fixture:fixture-password@127.0.0.1:5432/test_dianzi_unit",
    )
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/15")
    monkeypatch.setenv("RAW_CONTENT_DIRECTORY", str(tmp_path / "synthetic-raw"))
    from ai_intel.knowledge import default_graph_runtime
    from ai_intel.workers import runtime

    settings = graph_settings(False)
    observed = []

    @contextmanager
    def projection_handlers(actual_engine, actual_settings):
        yield {}

    def execute(actual_engine, job_id, worker_id, handlers):
        observed.append(dict(handlers))
        return "not_claimed"

    class EngineFixture:
        def dispose(self):
            return None

    monkeypatch.setattr(runtime, "load_application_settings", lambda: settings)
    monkeypatch.setattr(runtime, "build_engine", lambda _: EngineFixture())
    monkeypatch.setattr(runtime, "build_content_storage", lambda _: object())
    monkeypatch.setattr(runtime, "build_enrichment_job_service", lambda *_: None)
    monkeypatch.setattr(default_graph_runtime, "build_projection_job_handlers", projection_handlers)
    monkeypatch.setattr(runtime, "execute_job", execute)
    job_id = str(uuid4())
    assert runtime.consume_job(job_id) == {"job_id": job_id, "outcome": "not_claimed"}
    for job_type in GRAPH_JOB_TYPES:
        assert job_type in observed[0]
