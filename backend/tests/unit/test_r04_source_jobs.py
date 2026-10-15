"""固定来源输入、URL 与 HTTP 故障分类；显式隔离且不计 live。"""

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_intel.api.app import create_application
from ai_intel.infrastructure.network import FetchResult
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.ingestion.source_documents import (
    SourceDocumentError,
    SourceResponse,
    _request_parameters,
)
from ai_intel.ingestion.source_jobs import (
    SourcePageRequest,
    _http_failure,
    _next_position,
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
        ("vllm_vendor", {}, {"per_page": ["10"], "state": ["published"]}),
        ("vllm_vendor", {"page": 1}, {"per_page": ["10"], "state": ["published"]}),
        (
            "vllm_vendor",
            {"cursor_version": 2, "after": "Y3Vyc29yOnYyOpHOAAg-eQ=="},
            {"per_page": ["10"], "state": ["published"], "after": ["Y3Vyc29yOnYyOpHOAAg-eQ=="]},
        ),
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


VENDOR_URL = "https://api.github.com/repos/vllm-project/vllm/security-advisories"
NEXT_AFTER = "Y3Vyc29yOnYyOpHOAAg-eQ=="
RECORDED_LINK = (
    "<https://api.github.com/repositories/599547518/security-advisories?"
    'per_page=10&state=published&after=Y3Vyc29yOnYyOpHOAAg-eQ%3D%3D>; rel="next"'
)


def test_recorded_github_link_drives_cursor_without_following_numeric_alias():
    following = _next_position("vllm_vendor", b"[{}]", {}, {"Link": RECORDED_LINK})
    assert following == {"cursor_version": 2, "after": NEXT_AFTER}
    url = source_page_url("vllm_vendor", following)
    assert url.startswith(VENDOR_URL + "?")
    assert parse_qs(urlsplit(url).query)["after"] == [NEXT_AFTER]
    assert "page=" not in url.replace("per_page=", "")


@pytest.mark.parametrize("headers", [{}, {"LINK": '<https://api.github.com/unused>; rel="prev"'}])
def test_vendor_full_page_without_next_is_terminal(headers):
    assert _next_position("vllm_vendor", json.dumps([{}] * 10).encode(), {}, headers) == {}
    assert _next_position("vllm_vendor", b"[]", {}, headers) == {}


@pytest.mark.parametrize("page", [2, 3, 1_000_001])
def test_legacy_vendor_cursor_requires_explicit_restart(page):
    with pytest.raises(JobExecutionError, match="legacy_vendor_cursor_requires_restart") as caught:
        source_page_url("vllm_vendor", {"page": page})
    assert caught.value.blocked is True


@pytest.mark.parametrize(
    "cursor",
    [
        {"page": True},
        {"page": 0},
        {"page": "1"},
        {"cursor_version": 1, "after": "valid"},
        {"cursor_version": True, "after": "valid"},
        {"cursor_version": 2},
        {"cursor_version": 2, "after": "valid", "url": "https://evil.example"},
        {"cursor_version": 2, "after": ""},
        {"cursor_version": 2, "after": "a b"},
        {"cursor_version": 2, "after": "a\nb"},
        {"cursor_version": 2, "after": "你好"},
        {"cursor_version": 2, "after": "%2f"},
        {"cursor_version": 2, "after": "a" * 2049},
        {"cursor_version": 2, "after": 1},
        {"after": "valid"},
    ],
    ids=lambda cursor: "invalid-cursor-" + str(len(str(cursor))),
)
def test_vendor_cursor_rejects_untrusted_or_unbounded_values(cursor):
    with pytest.raises(SourceDocumentError):
        source_page_url("vllm_vendor", cursor)


@pytest.mark.parametrize(
    "uri",
    [
        "https://evil.example/repositories/599547518/security-advisories",
        "http://api.github.com/repositories/599547518/security-advisories",
        "https://127.0.0.1/repositories/599547518/security-advisories",
        "https://api.github.com:444/repositories/599547518/security-advisories",
        "https://api.github.com:/repositories/599547518/security-advisories",
        "https://user@api.github.com/repositories/599547518/security-advisories",
        "https://api.github.com/repositories/599547519/security-advisories",
        VENDOR_URL + "/other",
    ],
)
def test_next_link_cannot_change_approved_target(uri):
    link = f'<{uri}?per_page=10&state=published&after=next>; rel="next"'
    with pytest.raises(SourceDocumentError):
        _next_position("vllm_vendor", b"[]", {}, {"Link": link})


@pytest.mark.parametrize(
    "query",
    [
        "per_page=10&state=published&after=x&after=y",
        "per_page=10&state=published&after=x&page=2",
        "per_page=10&state=published&after=x&token=x",
        "per_page=20&state=published&after=x",
        "per_page=10&state=draft&after=x",
        "per_page=10&state=published",
        "per_page=10&state=published&after=",
        "per_page=10&state=published&after=x#fragment",
        "per_page=10&state=published&after=x%0A",
        "per_page=10&state=published&after=%ZZ",
    ],
)
def test_next_link_requires_exact_fixed_query(query):
    with pytest.raises(SourceDocumentError):
        _next_position("vllm_vendor", b"[]", {}, {"Link": f'<{VENDOR_URL}?{query}>; rel="next"'})


@pytest.mark.parametrize(
    "headers",
    [
        {"Link": ""},
        {"Link": "not a Link header"},
        {"Link": RECORDED_LINK + ", " + RECORDED_LINK},
        {"Link": RECORDED_LINK.replace('rel="next"', 'rel="next next"')},
        {"Link": RECORDED_LINK, "link": RECORDED_LINK},
        {"Link": RECORDED_LINK + "\n"},
        {"Link": " " * 8193},
        {"Link": ", ".join(['<https://api.github.com/unused>; rel="prev"'] * 17)},
    ],
    ids=[
        "empty",
        "malformed",
        "duplicate-next",
        "duplicate-rel",
        "duplicate-header",
        "control",
        "too-long",
        "too-many",
    ],
)
def test_ambiguous_or_malformed_link_fails_explicitly(headers):
    with pytest.raises(SourceDocumentError):
        _next_position("vllm_vendor", b"[]", {}, headers)


def test_repeating_same_after_fails_instead_of_looping():
    with pytest.raises(SourceDocumentError):
        _next_position(
            "vllm_vendor",
            b"[]",
            {"cursor_version": 2, "after": NEXT_AFTER},
            {"Link": RECORDED_LINK},
        )


@pytest.mark.parametrize(
    "link",
    [
        RECORDED_LINK.replace("api.github.com/", "api.github.com:443/"),
        RECORDED_LINK.replace("/repositories/599547518/", "/repos/vllm-project/vllm/"),
        '<https://api.github.com/unused?before=old>; rel="prev", ' + RECORDED_LINK,
    ],
)
def test_approved_alias_default_port_and_multiple_relations(link):
    assert _next_position("vllm_vendor", b"[]", {}, {"link": link}) == {
        "cursor_version": 2,
        "after": NEXT_AFTER,
    }


def test_vendor_cursor_maximum_survives_url_encoding_and_source_boundary():
    after = "/+=" * 682 + "ab"
    url = source_page_url("vllm_vendor", {"cursor_version": 2, "after": after})
    assert len(after) == 2048 and len(url) > 2000
    parameters = _request_parameters(SourceResponse("vllm_vendor", b"[]", url, datetime.now(UTC)))
    assert parameters == {"per_page": "10", "state": "published", "after": after}


@pytest.mark.parametrize("extra", [{}, {"after": NEXT_AFTER}, {"page": "12"}])
def test_source_boundary_accepts_new_and_historical_vendor_requests(extra):
    parameters = {"per_page": "10", "state": "published", **extra}
    response = SourceResponse(
        "vllm_vendor", b"[]", VENDOR_URL + "?" + urlencode(parameters), datetime.now(UTC)
    )
    assert _request_parameters(response) == parameters


@pytest.mark.parametrize(
    "query",
    [
        "per_page=10&state=published&after=x&page=2",
        "per_page=10&state=published&after=x&after=y",
        "per_page=10&state=published&after=x&before=y",
        "per_page=10&state=published&after=a+b",
        "per_page=10&state=published&page=0",
    ],
)
def test_source_boundary_rejects_mixed_or_unsafe_cursor_query(query):
    response = SourceResponse("vllm_vendor", b"[]", VENDOR_URL + "?" + query, datetime.now(UTC))
    with pytest.raises(SourceDocumentError):
        _request_parameters(response)
