"""Verify that only server settings choose source-mode labels in the default registry."""

import importlib

import pytest

from ai_intel.ingestion import source_jobs


@pytest.mark.parametrize("mode", ["fixture", "live"])
def test_default_source_registry_injects_server_data_mode(monkeypatch, tmp_path, mode):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", mode)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test_fixture@127.0.0.1/test_dianzi_unit")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/15")
    monkeypatch.setenv("RAW_CONTENT_DIRECTORY", str(tmp_path / "synthetic-content"))
    observed = []
    original = source_jobs.build_source_page_handler

    def captured_factory(store, *, dns_resolver, data_mode=None):
        observed.append(data_mode)
        return original(store, dns_resolver=dns_resolver, data_mode=data_mode)

    monkeypatch.setattr(source_jobs, "build_source_page_handler", captured_factory)
    from ai_intel.workers import runtime

    importlib.reload(runtime)
    assert observed and all(value == mode for value in observed)
    assert source_jobs.SOURCE_JOB_TYPE in runtime.EXECUTION_HANDLERS
