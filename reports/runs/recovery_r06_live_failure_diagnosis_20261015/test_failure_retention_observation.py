"""Document current pre-persistence failure ordering; this synthetic observation is not PG proof."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.source_jobs import SourcePageRequest, build_source_page_handler
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError


def test_received_malformed_page_loses_raw_response_before_registration(monkeypatch):
    observed = {"http_responses": 0, "raw_registrations": 0, "source_documents": 0}
    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    monkeypatch.setattr(source_jobs, "ensure_source_registration", lambda *args: "fixed-source")
    repository = SimpleNamespace(claim=lambda **kwargs: SimpleNamespace(cursor_json={}))
    monkeypatch.setattr(source_jobs, "SourceCursorRepository", lambda *args, **kwargs: repository)
    monkeypatch.setattr(source_jobs, "create_network_gateway", lambda *args, **kwargs: object())

    def fetched(url):
        observed["http_responses"] += 1
        return FetchResult(url, 200, "application/json", b"{synthetic-invalid-json}")

    def registered(*args):
        observed["raw_registrations"] += 1
        raise AssertionError("unreachable raw registration")

    monkeypatch.setattr(source_jobs, "register_response_content", registered)
    request = SourcePageRequest(source_kind="ollama_releases", window_end=now)
    handler = build_source_page_handler(object(), fetcher=fetched, clock=lambda: now)
    with pytest.raises(JobExecutionError) as captured:
        handler(SimpleNamespace(scalar=lambda statement: None),
                JobExecutionContext("synthetic-job", "synthetic-worker", 1, None),
                request.model_dump_json().encode())
    assert captured.value.error_code == "source_response_invalid"
    assert captured.value.blocked is True
    assert observed == {"http_responses": 1, "raw_registrations": 0, "source_documents": 0}
