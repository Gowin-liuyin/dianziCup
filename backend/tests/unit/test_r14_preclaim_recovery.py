"""Explicit transport fixtures never connect PG/Redis or invoke models."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError


@pytest.fixture()
def runtime_module(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "fixture")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test_fixture@127.0.0.1/test_dianzi_unit")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/15")
    monkeypatch.setenv("RAW_CONTENT_DIRECTORY", str(tmp_path / "synthetic-raw"))
    from ai_intel.workers import runtime

    return runtime


@pytest.mark.parametrize(
    "job_type", [None, "record_source_fetch_failure", "os.system", "investigation"]
)
def test_only_trusted_fixed_job_type_selects_dedicated_task(runtime_module, monkeypatch, job_type):
    sent = []
    monkeypatch.setattr(
        runtime_module.celery_app, "send_task", lambda *args, **kwargs: sent.append((args, kwargs))
    )
    job_id = str(uuid4())
    runtime_module.publish_job_event(
        {"job_id": job_id, "topic": "os.system", "payload_ref": "untrusted"}, job_type=job_type
    )
    expected = (
        (
            ("ai_intel.investigations.execute",),
            {"args": [job_id], "queue": "ai_intel_investigations", "retry": False},
        )
        if job_type == "investigation"
        else (("ai_intel.jobs.execute",), {"args": [job_id], "retry": False})
    )
    assert sent == [expected]


@pytest.mark.parametrize("dedicated", [False, True])
def test_consumer_preclaim_pg_failure_is_unavailable_not_success_or_retry(
    runtime_module, monkeypatch, dedicated
):
    from ai_intel.workers import investigation

    module = investigation if dedicated else runtime_module
    disposed = []

    class EngineFixture:
        def dispose(self):
            disposed.append(True)

    monkeypatch.setattr(module, "build_engine", lambda settings: EngineFixture())

    def fail(*arguments, **keywords):
        raise OperationalError("synthetic-preclaim", {}, Exception("synthetic-pg-unavailable"))

    if dedicated:
        monkeypatch.setattr(module, "execute_investigation_job", fail)
        consume = module.consume_investigation_job
    else:
        monkeypatch.setattr(module, "build_enrichment_job_service", fail)
        consume = module.consume_job
    job_id = str(uuid4())
    assert consume(job_id) == {"job_id": job_id, "outcome": "delivery_unavailable"}
    assert disposed == [True]


def test_dispatcher_pg_failure_remains_explicit_error(runtime_module, monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise OperationalError("synthetic-dispatch", {}, Exception("synthetic-pg-unavailable"))

        def dispose(self):
            pass

    monkeypatch.setattr(runtime_module, "build_engine", lambda settings: BrokenEngine())
    with pytest.raises(RuntimeError, match="runtime database unavailable"):
        runtime_module.dispatch_pending_jobs()
