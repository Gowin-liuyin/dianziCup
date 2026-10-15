"""Offline scheduling boundaries; no broker, database or source requests."""

import importlib
from datetime import UTC, datetime, timedelta, timezone

import pytest

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.ingestion.source_polling import (
    SOURCE_POLL_INTERVAL_SECONDS,
    enqueue_due_source_collections,
    source_poll_window,
)


def test_all_nine_discovery_sources_have_bounded_polling_policy():
    assert set(SOURCE_POLL_INTERVAL_SECONDS) == set(CATALOG_SOURCES)
    assert SOURCE_POLL_INTERVAL_SECONDS["vllm_vendor"] == 1800
    assert all(300 <= seconds <= 3600 for seconds in SOURCE_POLL_INTERVAL_SECONDS.values())


@pytest.mark.parametrize("kind", tuple(CATALOG_SOURCES))
def test_poll_window_is_same_utc_bucket_across_clock_zones(kind):
    observed = datetime(2026, 10, 15, 10, 17, 22, 999999, tzinfo=UTC)
    slot = source_poll_window(kind, observed)
    assert slot == datetime(2026, 10, 15, 10, tzinfo=UTC)
    assert source_poll_window(kind, observed.astimezone(timezone(timedelta(hours=8)))) == slot
    assert slot <= observed and slot.utcoffset() == timedelta(0)


def test_poll_window_rejects_naive_clock_and_unknown_source():
    with pytest.raises(ValueError):
        source_poll_window("nvd_ollama", datetime(2026, 10, 15))
    with pytest.raises(ValueError):
        source_poll_window("unregistered", datetime.now(UTC))


@pytest.mark.parametrize("role", [Role.VIEWER, Role.TENANT_ADMIN, Role.ANALYST])
def test_untrusted_scope_cannot_even_query_scheduler_database(role):
    scope = AccessScope.for_authenticated_user("fixture", "tenant-a", role)
    with pytest.raises(PermissionDeniedError):
        enqueue_due_source_collections(None, scope, datetime.now(UTC))


def test_polling_requires_explicit_trusted_deployment_opt_in(monkeypatch):
    monkeypatch.delenv("SOURCE_POLLING_ENABLED", raising=False)
    assert ApplicationSettings(app_env="test").source_polling_enabled is False
    monkeypatch.setenv("SOURCE_POLLING_ENABLED", "true")
    assert ApplicationSettings(app_env="test").source_polling_enabled is True


def test_default_worker_has_no_automatic_network_scheduling(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test@127.0.0.1:25432/test_fixture")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/0")
    monkeypatch.setenv("SOURCE_POLLING_ENABLED", "false")
    runtime = importlib.import_module("ai_intel.workers.runtime")
    application = runtime.build_celery_application()
    try:
        assert "poll-public-sources" not in application.conf.beat_schedule
    finally:
        application.close()
    monkeypatch.setenv("SOURCE_POLLING_ENABLED", "true")
    enabled = runtime.build_celery_application()
    try:
        entry = enabled.conf.beat_schedule["poll-public-sources"]
        assert entry["task"] == "ai_intel.sources.poll_due"
        assert entry["schedule"] == 60.0 and entry["options"]["expires"] == 120
    finally:
        enabled.close()


def test_disabled_poll_task_does_not_open_a_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test@127.0.0.1:25432/test_fixture")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/0")
    monkeypatch.setenv("SOURCE_POLLING_ENABLED", "false")
    runtime = importlib.import_module("ai_intel.workers.runtime")

    def unexpected_database(_settings):
        pytest.fail("disabled polling must not open a database")

    monkeypatch.setattr(runtime, "build_engine", unexpected_database)
    assert runtime.poll_due_public_sources() == {"state": "disabled", "queued": 0}
