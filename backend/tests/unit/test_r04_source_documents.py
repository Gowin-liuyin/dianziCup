"""Source-page boundaries and exact member extraction without database fixtures."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.ingestion.source_documents import (
    SourceDocumentError,
    SourceResponse,
    _prepare_documents,
    ensure_source_registration,
    persist_source_response,
)

NOW = datetime(2026, 10, 15, 5, 15, tzinfo=UTC)
NVD_URL = (
    "https://services.nvd.nist.gov/rest/json/cves/2.0"
    "?keywordSearch=ollama&resultsPerPage=1&startIndex=0"
)
VENDOR_URL = (
    "https://api.github.com/repos/vllm-project/vllm/security-advisories"
    "?per_page=1&state=published&page=1"
)
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures/recorded"


@pytest.fixture
def administrator() -> AccessScope:
    return AccessScope.for_authenticated_user("test-source-admin", None, Role.SYSTEM_ADMIN)


@pytest.mark.parametrize(
    "kind,filename,url",
    [
        ("nvd_ollama", "nvd_api_20261015_public.json", NVD_URL),
        ("vllm_vendor", "vllm_vendor_20261015_public.json", VENDOR_URL),
    ],
)
def test_recorded_page_prepares_one_exact_member(kind, filename, url):
    response = SourceResponse(kind, (FIXTURES / filename).read_bytes(), url, NOW)
    members = _prepare_documents(response)
    assert len(members) == 1
    member = members[0]
    assert member.payload in response.body
    assert member.parsed.status == "parsed"
    if kind == "nvd_ollama":
        assert member.record_id == "CVE-2024-28224"
        assert member.source_json_pointer == "/vulnerabilities/0"
        assert member.source_published_at is None
        assert member.source_modified_at is None
        assert member.canonical_uri == "https://nvd.nist.gov/vuln/detail/CVE-2024-28224"
        assert any(fact.predicate == "cvss_score" for fact in member.facts)
    else:
        assert member.record_id == "GHSA-6cxc-2vcg-w5qc"
        assert member.source_json_pointer == "/0"
        assert member.source_published_at == datetime(2026, 10, 6, 20, 45, 8, tzinfo=UTC)
        assert member.external_ids == (("ghsa", "GHSA-6cxc-2vcg-w5qc"),)
        assert any(
            fact.predicate == "affected_product" and fact.value == "vllm" for fact in member.facts
        )


def test_unicode_and_escaped_member_bytes_are_not_reserialized():
    body = (FIXTURES / "vllm_vendor_20261015_public.json").read_bytes()
    record = json.loads(body)[0]
    record["description"] = '中文🙂\n引用 "mask" 和 \\ 路径'
    raw_member = json.dumps(record, ensure_ascii=False, indent=3).encode("utf-8")
    response = SourceResponse("vllm_vendor", b"[ \n " + raw_member + b"\n ]", VENDOR_URL, NOW)
    member = _prepare_documents(response)[0]
    assert member.payload == raw_member
    assert member.parsed.normalized_text.count('中文🙂\n引用 "mask" 和 \\ 路径') == 1
    excerpt = next(fact for fact in member.facts if fact.predicate == "source_excerpt")
    assert excerpt.value == record["description"]


@pytest.mark.parametrize(
    "url",
    [
        VENDOR_URL + "&api_key=synthetic-not-a-secret",
        VENDOR_URL + "&unrecognized=1",
        VENDOR_URL + "#fragment",
        VENDOR_URL.replace("https:", "http:"),
        VENDOR_URL.replace("api.github.com", "api.github.com.evil.example"),
        VENDOR_URL.replace("api.github.com", "user:pass@api.github.com"),
        VENDOR_URL.replace("vllm-project/vllm", "other/repository"),
        VENDOR_URL.replace("per_page=1", "per_page=101"),
        VENDOR_URL.replace("per_page=1", "per_page=0"),
        VENDOR_URL.replace("page=1", "page=0"),
        VENDOR_URL.replace("page=1", "page=1&page=2"),
        VENDOR_URL.replace("state=published", "state=draft"),
        VENDOR_URL.replace("api.github.com", "api.github.com\n"),
        " " + VENDOR_URL,
    ],
)
def test_bad_vendor_request_url_fails_before_io(tmp_path, administrator, url):
    with Session() as session, pytest.raises(SourceDocumentError, match="request URL"):
        persist_source_response(
            session,
            ContentStore(tmp_path),
            administrator,
            SourceResponse("vllm_vendor", b"[]", url, NOW),
            ingested_at=NOW,
        )


@pytest.mark.parametrize(
    "url",
    [
        NVD_URL.replace("keywordSearch=ollama", "keywordSearch=anything"),
        NVD_URL.replace("resultsPerPage=1", "resultsPerPage=0"),
        NVD_URL.replace("startIndex=0", "startIndex=-1"),
        NVD_URL + "&cveId=CVE-2024-28224",
        NVD_URL.replace("startIndex=0", "startIndex=0&startIndex=1"),
    ],
)
def test_bad_nvd_request_url_fails_before_io(tmp_path, administrator, url):
    with Session() as session, pytest.raises(SourceDocumentError, match="request URL"):
        persist_source_response(
            session,
            ContentStore(tmp_path),
            administrator,
            SourceResponse("nvd_ollama", b"{}", url, NOW),
            ingested_at=NOW,
        )


@pytest.mark.parametrize(
    "role,tenant",
    [
        (Role.ANALYST, "tenant-a"),
        (Role.TENANT_ADMIN, "tenant-a"),
        (Role.SYSTEM_ADMIN, "tenant-a"),
        (Role.VIEWER, None),
    ],
)
def test_nonpublic_administrator_is_denied_before_io(tmp_path, role, tenant):
    scope = AccessScope.for_authenticated_user("test-not-public-admin", tenant, role)
    with Session() as session, pytest.raises(PermissionDeniedError):
        persist_source_response(
            session,
            ContentStore(tmp_path),
            scope,
            SourceResponse("vllm_vendor", b"[]", VENDOR_URL, NOW),
            ingested_at=NOW,
        )


@pytest.mark.parametrize(
    "body",
    [
        b'[{"summary":"a","summary":"b"}]',
        b"[NaN]",
        b"[Infinity]",
        b"[1e400]",
        b'[{"x":"\\u0000"}]',
        b'[{"x":"\\ud800"}]',
        b"[\xff]",
        b"[[[",
        (b"[" * 34) + b"0" + (b"]" * 34),
        pytest.param(b" " * (5 * 1024 * 1024 + 1), id="oversized_response"),
    ],
)
def test_invalid_json_is_rejected_before_io(tmp_path, administrator, body):
    with Session() as session, pytest.raises(SourceDocumentError):
        persist_source_response(
            session,
            ContentStore(tmp_path),
            administrator,
            SourceResponse("vllm_vendor", body, VENDOR_URL, NOW),
            ingested_at=NOW,
        )


@pytest.mark.parametrize("body", [b"{}", b"null", b"[null]", b"[] []", b"[{}]"])
def test_bad_vendor_shape_or_member_does_not_succeed(body):
    with pytest.raises(SourceDocumentError):
        _prepare_documents(SourceResponse("vllm_vendor", body, VENDOR_URL, NOW))


def test_duplicate_vendor_record_ids_are_not_silently_deduplicated():
    record = json.loads((FIXTURES / "vllm_vendor_20261015_public.json").read_bytes())[0]
    response = SourceResponse(
        "vllm_vendor",
        json.dumps([record, record]).encode(),
        VENDOR_URL.replace("per_page=1", "per_page=2"),
        NOW,
    )
    with pytest.raises(SourceDocumentError, match="duplicate record"):
        _prepare_documents(response)


def test_member_count_limit_is_exact():
    response = SourceResponse(
        "vllm_vendor", b"[" + b",".join([b"{}"] * 101) + b"]", VENDOR_URL, NOW
    )
    with pytest.raises(SourceDocumentError, match="page limit"):
        _prepare_documents(response)


@pytest.mark.parametrize("field", ["observed_at", "ingested_at"])
def test_naive_observation_or_ingestion_time_is_rejected(tmp_path, administrator, field):
    observed, ingested = NOW, NOW
    if field == "observed_at":
        observed = NOW.replace(tzinfo=None)
    else:
        ingested = NOW.replace(tzinfo=None)
    with Session() as session, pytest.raises(SourceDocumentError, match="time"):
        persist_source_response(
            session,
            ContentStore(tmp_path),
            administrator,
            SourceResponse("vllm_vendor", b"[]", VENDOR_URL, observed),
            ingested_at=ingested,
        )


def test_query_order_can_change_without_broadening_scope():
    response = SourceResponse(
        "vllm_vendor",
        b"[]",
        "https://api.github.com/repos/vllm-project/vllm/security-advisories"
        "?state=published&page=1&per_page=100",
        NOW,
    )
    assert _prepare_documents(response) == ()


def test_source_excerpt_is_bounded_and_exact_prefix():
    record = json.loads((FIXTURES / "vllm_vendor_20261015_public.json").read_bytes())[0]
    description = "中文🙂原始条件" * 300
    record["description"] = description
    member = _prepare_documents(
        SourceResponse("vllm_vendor", json.dumps([record]).encode(), VENDOR_URL, NOW)
    )[0]
    fact = next(fact for fact in member.facts if fact.predicate == "source_excerpt")
    assert fact.value == description[:2000]
    assert fact.json_pointer == "/description"


def test_empty_nvd_window_is_distinct_from_incomplete_window():
    payload = {
        "format": "NVD_CVE",
        "version": "2.0",
        "vulnerabilities": [],
        "startIndex": 0,
        "totalResults": 0,
        "resultsPerPage": 0,
    }
    assert (
        _prepare_documents(SourceResponse("nvd_ollama", json.dumps(payload).encode(), NVD_URL, NOW))
        == ()
    )
    payload["totalResults"] = 1
    with pytest.raises(SourceDocumentError):
        _prepare_documents(SourceResponse("nvd_ollama", json.dumps(payload).encode(), NVD_URL, NOW))


def test_source_registration_denies_scope_before_any_io():
    with Session() as session, pytest.raises(PermissionDeniedError):
        ensure_source_registration(
            session,
            AccessScope.for_authenticated_user("tenant-admin", "tenant-a", Role.TENANT_ADMIN),
            "vllm_vendor",
            NOW,
        )


def test_source_registration_rejects_naive_time_before_io(administrator):
    with Session() as session, pytest.raises(SourceDocumentError, match="time"):
        ensure_source_registration(session, administrator, "vllm_vendor", NOW.replace(tzinfo=None))
