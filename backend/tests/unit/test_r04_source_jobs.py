"""固定来源输入、URL 与 HTTP 故障分类；显式隔离且不计 live。"""

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_intel.api.app import create_application
from ai_intel.infrastructure.network import FetchResult
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.ingestion.source_documents import SourceDocumentError
from ai_intel.ingestion.source_jobs import (
    SourcePageRequest,
    _http_failure,
    source_page_url,
)
from ai_intel.workers.executor import JobExecutionError


@pytest.mark.parametrize(
    ("kind", "cursor", "expected"),
    [
        (
            "nvd_ollama",
            {},
            {"keywordSearch": ["ollama"], "resultsPerPage": ["20"], "startIndex": ["0"]},
        ),
        (
            "nvd_ollama",
            {"offset": 20},
            {"keywordSearch": ["ollama"], "resultsPerPage": ["20"], "startIndex": ["20"]},
        ),
        ("vllm_vendor", {}, {"per_page": ["10"], "state": ["published"], "page": ["1"]}),
        ("vllm_vendor", {"page": 3}, {"per_page": ["10"], "state": ["published"], "page": ["3"]}),
    ],
)
def test_only_fixed_endpoints_and_query_positions(kind, cursor, expected):
    parts = urlsplit(source_page_url(kind, cursor))
    assert parts.scheme == "https"
    assert parts.hostname == ("services.nvd.nist.gov" if kind == "nvd_ollama" else "api.github.com")
    assert parse_qs(parts.query) == expected
    assert not parts.username and not parts.fragment


@pytest.mark.parametrize(
    "cursor",
    [
        {"offset": -1},
        {"offset": True},
        {"offset": "20"},
        {"offset": 1_000_001},
        {"url": "https://127.0.0.1"},
        {"page": 1},
    ],
)
def test_untrusted_cursor_cannot_change_target(cursor):
    with pytest.raises(SourceDocumentError):
        source_page_url("nvd_ollama", cursor)


@pytest.mark.parametrize(
    ("status", "code", "blocked", "permanent"),
    [
        (401, "source_auth_denied", True, False),
        (403, "source_auth_denied", True, False),
        (429, "source_rate_limited", False, False),
        (404, "source_client_error", False, True),
        (500, "source_server_error", False, False),
        (503, "source_server_error", False, False),
        (302, "source_unexpected_status", False, True),
    ],
)
def test_failure_is_classified_without_reading_or_publishing_body(status, code, blocked, permanent):
    result = FetchResult("https://api.github.com", status, "", b"untrusted upstream diagnostics")
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(result)
    assert str(caught.value) == code
    assert caught.value.blocked is blocked
    assert caught.value.permanent is permanent


@pytest.mark.parametrize(
    ("header", "delay"), [("12", 12), ("9000", 300), ("0", 7), ("tomorrow", 30)]
)
def test_rate_limit_bounded_and_header_case_insensitive(header, delay):
    result = FetchResult("https://api.github.com", 429, "", b"", {"Retry-After": header})
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(result)
    assert caught.value.retry_after_seconds == delay


@pytest.mark.parametrize(
    "extra",
    [
        {"url": "https://127.0.0.1"},
        {"tenant_id": "other"},
        {"remaining_pages": 0},
        {"remaining_pages": 21},
        {"stream_kind": "shell"},
        {"window_end": "2026-10-15T00:00:00"},
    ],
)
def test_task_rejects_extra_identity_and_unbounded_or_unknown_inputs(extra):
    payload = {"source_kind": "nvd_ollama", "window_end": "2026-10-15T00:00:00Z", **extra}
    with pytest.raises(ValidationError):
        SourcePageRequest.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
def test_default_app_registers_source_routes_with_authentication(prefix):
    settings = ApplicationSettings(app_env="test", database_url=None, redis_url=None)
    with TestClient(create_application(settings=settings)) as client:
        payload = {"window_end": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
        response = client.post(prefix + "/sources/nvd_ollama/collect", json=payload)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"
        response = client.get(prefix + "/jobs/00000000-0000-0000-0000-000000000001")
        assert response.status_code == 401
        response = client.post(prefix + "/sources/unknown/collect", json=payload)
        assert response.status_code == 422
