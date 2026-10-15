"""Response observers execute before source parsers and receive no invented bytes."""

from datetime import UTC, datetime

import pytest
from tests.r06_source_worker_fixtures import avid_responses

from ai_intel.infrastructure.network import FetchResult, NetworkTimeoutError
from ai_intel.ingestion.source_jobs import _fetch_catalog_page
from ai_intel.ingestion.sources.academic import AcademicContractError
from ai_intel.ingestion.sources.repository import RepositoryFetchError
from ai_intel.workers.executor import JobExecutionError

NOW = datetime(2026, 10, 16, tzinfo=UTC)


@pytest.mark.parametrize(
    ("kind", "media", "body"),
    [
        ("arxiv_security", "application/atom+xml", b"<feed>"),
        ("ollama_releases", "application/json", b"[{"),
        ("osv_ollama", "application/json", b'{"vulns":[1]}'),
    ],
)
def test_received_bytes_reach_recorder_before_parse_failure(kind, media, body):
    observed = []
    with pytest.raises((ValueError, AcademicContractError, RepositoryFetchError)):
        _fetch_catalog_page(
            kind,
            {},
            dns_resolver="system",
            fetcher=lambda url: FetchResult(url, 200, media, body),
            poster=lambda url, request_body: FetchResult(url, 200, media, body),
            clock=lambda: NOW,
            response_recorder=lambda request, response, ordinal: observed.append(
                (request, response, ordinal)
            ),
        )
    assert len(observed) == 1
    assert observed[0][1].body == body and observed[0][2] == 1


def test_network_without_response_records_none_and_original_failure():
    observed = []

    def fetch(url):
        raise NetworkTimeoutError("synthetic timeout detail")

    with pytest.raises(NetworkTimeoutError):
        _fetch_catalog_page(
            "arxiv_security",
            {},
            dns_resolver="system",
            fetcher=fetch,
            poster=None,
            clock=lambda: NOW,
            response_recorder=lambda request, response, ordinal: observed.append(
                (response, ordinal)
            ),
        )
    assert observed == [(None, 1)]


def test_failed_receipt_does_not_reach_parser(monkeypatch):
    from ai_intel.ingestion import source_jobs

    def recorder(*args):
        raise JobExecutionError("source_receipt_database_failed", retry_after_seconds=7)

    monkeypatch.setattr(
        source_jobs,
        "normalize_catalog_page",
        lambda *args: pytest.fail("parser ran after receipt failure"),
    )
    with pytest.raises(JobExecutionError, match="source_receipt_database_failed"):
        _fetch_catalog_page(
            "arxiv_security",
            {},
            dns_resolver="system",
            fetcher=lambda url: FetchResult(url, 200, "application/atom+xml", b"<feed>"),
            poster=None,
            clock=lambda: NOW,
            response_recorder=recorder,
        )


def test_avid_tree_normalized_then_bad_blob_is_observed_separately():
    tree, _ = avid_responses()
    observed, normalized = [], []

    def fetch(url):
        return FetchResult(
            url, 200, "application/json", b"bad blob" if "/git/blobs/" in url else tree
        )

    with pytest.raises((ValueError, RepositoryFetchError)):
        _fetch_catalog_page(
            "avid_community",
            {},
            dns_resolver="system",
            fetcher=fetch,
            poster=None,
            clock=lambda: NOW,
            response_recorder=lambda request, response, ordinal: observed.append(
                (response.body, ordinal)
            ),
            normalization_recorder=normalized.append,
        )
    assert observed == [(tree, 1), (b"bad blob", 2)]
    assert normalized == [1]
