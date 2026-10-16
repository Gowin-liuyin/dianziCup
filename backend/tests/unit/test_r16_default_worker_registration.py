"""Exercise default consumer registration with explicit isolated IO substitutes."""

from contextlib import contextmanager
from uuid import uuid4

import pytest
from pydantic import SecretStr

from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.workers.executor import DetachedJobHandler, JobExecutionResult


@pytest.mark.parametrize("configured", [False, True])
def test_default_consumer_registers_only_trusted_configured_revalidation(
    monkeypatch, tmp_path, configured
):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "fixture")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test_fixture@127.0.0.1/test_dianzi_unit")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/15")
    monkeypatch.setenv("RAW_CONTENT_DIRECTORY", str(tmp_path / "synthetic-raw"))
    from ai_intel.workers import runtime

    settings = ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        revalidation_cursor_signing_key=SecretStr("02" * 32) if configured else None,
    )
    disposed = []

    class EngineFixture:
        def dispose(self):
            disposed.append(True)

    engine = EngineFixture()
    store = object()
    registered = []
    observed = []
    handler = DetachedJobHandler(
        lambda context, payload: JobExecutionResult(outcome="partial", error_code="synthetic")
    )

    def revalidation_handlers(actual_engine, actual_store, signing_key):
        registered.append((actual_engine, actual_store, signing_key))
        return {"revalidate_change": handler, "revalidate_assessment": handler}

    @contextmanager
    def projection_handlers(actual_engine, actual_settings):
        assert actual_engine is engine and actual_settings is settings
        yield {}

    def execute(actual_engine, job_id, worker_id, handlers):
        observed.append(dict(handlers))
        assert actual_engine is engine and worker_id.startswith("celery-")
        assert (
            handlers[runtime.SOURCE_JOB_TYPE] is runtime.EXECUTION_HANDLERS[runtime.SOURCE_JOB_TYPE]
        )
        return "not_claimed"

    monkeypatch.setattr(runtime, "load_application_settings", lambda: settings)
    monkeypatch.setattr(runtime, "build_engine", lambda _: engine)
    monkeypatch.setattr(runtime, "build_content_storage", lambda _: store)
    monkeypatch.setattr(runtime, "build_enrichment_job_service", lambda *_: None)
    monkeypatch.setattr(runtime, "build_projection_job_handlers", projection_handlers)
    monkeypatch.setattr(runtime, "make_revalidation_job_handlers", revalidation_handlers)
    monkeypatch.setattr(runtime, "execute_job", execute)
    job_id = str(uuid4())
    assert runtime.consume_job(job_id) == {"job_id": job_id, "outcome": "not_claimed"}
    assert disposed == [True] and len(observed) == 1
    if configured:
        assert registered == [(engine, store, settings.revalidation_cursor_signing_key)]
        assert observed[0]["revalidate_change"] is handler
        assert observed[0]["revalidate_assessment"] is handler
    else:
        assert registered == []
        assert "revalidate_change" not in observed[0]
        assert "revalidate_assessment" not in observed[0]
