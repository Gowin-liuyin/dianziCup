"""Fixed catalog worker boundaries; synthetic/recorded responses never count as live."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from tests.r06_source_worker_fixtures import avid_responses, source_response

from ai_intel.api.app import create_application
from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkTimeoutError,
    UnsupportedContentTypeError,
)
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES, SourceCatalogError
from ai_intel.ingestion.source_jobs import SourcePageRequest, _fetch_catalog_page
from ai_intel.workers.executor import JobExecutionError

NOW = datetime(2026, 10, 15, 8, tzinfo=UTC)


@pytest.mark.parametrize("kind", tuple(CATALOG_SOURCES))
def test_all_registered_source_keys_are_valid_worker_inputs(kind):
    request = SourcePageRequest.model_validate_json(
        json.dumps({"source_kind": kind, "window_end": NOW.isoformat()})
    )
    assert request.source_kind == kind and request.remaining_pages == 20


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
@pytest.mark.parametrize("kind", tuple(CATALOG_SOURCES))
def test_all_fixed_source_routes_reach_authentication_before_scheduling(prefix, kind):
    settings = ApplicationSettings(app_env="test", database_url=None, redis_url=None)
    with TestClient(create_application(settings=settings)) as client:
        response = client.post(
            prefix + "/sources/" + kind + "/collect", json={"window_end": NOW.isoformat()}
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize("kind", ["unknown", "https://127.0.0.1", "avid", "osv", ""])
def test_unregistered_or_url_source_keys_are_rejected(kind):
    with pytest.raises(ValidationError):
        SourcePageRequest.model_validate_json(
            json.dumps({"source_kind": kind, "window_end": NOW.isoformat()})
        )


class FixtureGateway:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def fetch(self, url, max_redirect_hops=0, *, deadline=None):
        self.calls.append(("GET", url, None, max_redirect_hops, deadline))
        body, content_type = next(self.results)
        return FetchResult(url, 200, content_type, body)

    def post_json(self, url, payload, *, deadline=None):
        self.calls.append(("POST", url, payload, 0, deadline))
        body, content_type = next(self.results)
        return FetchResult(url, 200, content_type, body)


@pytest.mark.parametrize(
    ("kind", "count", "document_kind"),
    [
        ("osv_ollama", 1, "advisory"),
        ("avid_community", 1, "article"),
        ("ollama_releases", 1, "repository_record"),
        ("trailofbits_blog", 20, "article"),
        ("arxiv_security", 2, "paper"),
        ("nist_ai_rmf", 1, "standard"),
        ("cac_generative_ai", 1, "policy"),
    ],
)
def test_catalog_transport_uses_fixed_method_domain_type_and_normalizer(
    monkeypatch, kind, count, document_kind
):
    results = (
        [(body, "application/json") for body in avid_responses()]
        if kind == "avid_community"
        else [source_response(kind)]
    )
    gateway = FixtureGateway(results)
    policies = []

    def create(policy, max_concurrent_requests):
        assert max_concurrent_requests == 1
        policies.append(policy)
        return gateway

    monkeypatch.setattr(source_jobs, "create_network_gateway", create)
    page, responses = _fetch_catalog_page(
        kind, {}, dns_resolver="system", fetcher=None, poster=None, clock=lambda: NOW
    )
    assert len(page.documents) == count
    assert all(item.kind.value == document_kind for item in page.documents)
    assert len(gateway.calls) == len(responses) == (2 if kind == "avid_community" else 1)
    assert policies[0].allowed_domains == (CATALOG_SOURCES[kind].base_origin.split("//")[1],)
    assert policies[0].allowed_content_types == source_jobs.CATALOG_CONTENT_TYPES[kind]
    assert policies[0].total_timeout_seconds == 12
    assert all(call[3] == 0 for call in gateway.calls)
    assert all(call[4] is gateway.calls[0][4] for call in gateway.calls)
    if kind == "osv_ollama":
        assert gateway.calls[0][0:2] == ("POST", "https://api.osv.dev/v1/query")
        assert json.loads(gateway.calls[0][2]) == {
            "package": {"ecosystem": "Go", "name": "github.com/ollama/ollama"}
        }
    else:
        assert all(call[0] == "GET" for call in gateway.calls)
    if kind == "avid_community":
        assert (
            gateway.calls[0][1]
            == "https://api.github.com/repos/avidml/avid-db/git/trees/main?recursive=1"
        )
        assert "/git/blobs/" in gateway.calls[1][1]
        assert responses[0][1].body == results[0][0]
        assert responses[1][1].body == results[1][0]


@pytest.mark.parametrize("kind", tuple(source_jobs.CATALOG_CONTENT_TYPES))
def test_bad_catalog_cursor_has_no_network_call(monkeypatch, kind):
    monkeypatch.setattr(
        source_jobs,
        "create_network_gateway",
        lambda *args, **kwargs: pytest.fail("invalid cursor opened gateway"),
    )
    with pytest.raises(SourceCatalogError):
        _fetch_catalog_page(
            kind,
            {"url": "https://127.0.0.1"},
            dns_resolver="system",
            fetcher=None,
            poster=None,
            clock=lambda: NOW,
        )


def test_avid_page_cannot_start_from_blob_cursor(monkeypatch):
    monkeypatch.setattr(
        source_jobs,
        "create_network_gateway",
        lambda *args, **kwargs: pytest.fail("blob cursor opened gateway"),
    )
    with pytest.raises(SourceCatalogError):
        _fetch_catalog_page(
            "avid_community",
            {"blob_sha": "a" * 40},
            dns_resolver="system",
            fetcher=None,
            poster=None,
            clock=lambda: NOW,
        )


def test_avid_second_request_uses_remaining_total_deadline(monkeypatch):
    current = [100.0]
    monkeypatch.setattr(source_jobs.time, "monotonic", lambda: current[0])
    tree, blob = avid_responses()
    seen = []

    def fetch(url):
        seen.append(url)
        current[0] += 7
        return FetchResult(url, 200, "application/json", tree if len(seen) == 1 else blob)

    with pytest.raises(NetworkTimeoutError):
        _fetch_catalog_page(
            "avid_community",
            {},
            dns_resolver="system",
            fetcher=fetch,
            poster=None,
            clock=lambda: NOW,
        )
    assert len(seen) == 2


@pytest.mark.parametrize("stage", [1, 2])
def test_avid_http_limit_failure_keeps_existing_retry_contract(stage):
    tree, blob = avid_responses()
    seen = []

    def fetch(url):
        seen.append(url)
        if len(seen) == stage:
            return FetchResult(
                url, 429, "text/plain", b"upstream diagnostics", {"Retry-After": "13"}
            )
        return FetchResult(url, 200, "application/json", tree if len(seen) == 1 else blob)

    with pytest.raises(JobExecutionError) as error:
        _fetch_catalog_page(
            "avid_community",
            {},
            dns_resolver="system",
            fetcher=fetch,
            poster=None,
            clock=lambda: NOW,
        )
    assert error.value.error_code == "source_rate_limited"
    assert error.value.retry_after_seconds == 13
    assert len(seen) == stage


@pytest.mark.parametrize("kind", tuple(source_jobs.CATALOG_CONTENT_TYPES))
def test_wrong_response_type_fails_before_normalization(kind):
    with pytest.raises(UnsupportedContentTypeError):
        _fetch_catalog_page(
            kind,
            {},
            dns_resolver="system",
            fetcher=lambda url: FetchResult(url, 200, "image/png", b"not source content"),
            poster=lambda url, body: FetchResult(url, 200, "image/png", b"not source content"),
            clock=lambda: NOW,
        )
