"""Explicit fixtures verify fixed REST and model-space contracts, not semantic quality."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from ai_intel.domain.access import AccessScope, Role
from ai_intel.retrieval.hybrid_contracts import HybridQuery, HybridRetrievalError, IndexGeneration
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient, bm25_body

GENERATION = IndexGeneration("fixture-generation", "dianzi_test_r12_contract")


@pytest.mark.parametrize("dimension,version", [(383, None), (384, "other-space"), (True, None)])
def test_t30_c05_space_changes_require_rebuild(dimension: int, version: str | None) -> None:
    from ai_intel.infrastructure.models.semantic import E5_MODEL

    with pytest.raises(HybridRetrievalError, match="index_space_rebuild_required"):
        IndexGeneration(
            "new", "dianzi_test_r12_new", version or E5_MODEL.model_version, dimension
        ).require_fixed_space()


def test_bm25_request_prefilters_all_acl_and_time_bounds() -> None:
    scope = AccessScope.for_authenticated_user("server-reader", "tenant-a", Role.ANALYST)
    query = HybridQuery(
        "risk", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC), False
    )
    serialized = json.dumps(bm25_body(GENERATION, scope, query))
    assert '"tenant_id": "tenant-a"' in serialized
    assert '"tenant:tenant-a"' in serialized
    assert '"tenant-b"' not in serialized
    assert '"minimum_should_match": 1' in serialized
    assert '"gte": "2026-01-01T00:00:00+00:00"' in serialized
    assert '"lte": "2026-02-01T00:00:00+00:00"' in serialized
    assert '"_source": false' in serialized


@pytest.mark.parametrize(
    "response",
    [
        {"timed_out": True, "_shards": {"failed": 0}, "hits": {"hits": []}},
        {"timed_out": False, "_shards": {"failed": 1}, "hits": {"hits": []}},
        {
            "timed_out": False,
            "_shards": {"failed": 0},
            "hits": {"hits": [{"_id": "a", "_score": "x"}]},
        },
    ],
)
def test_incomplete_search_is_not_successful_empty_result(response: dict[str, object]) -> None:
    client = httpx.Client(
        base_url="http://127.0.0.1:29200",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    with client, pytest.raises(HybridRetrievalError):
        OpenSearchCorpusClient(client).search(
            GENERATION,
            AccessScope.for_authenticated_user("reader", "tenant-a", Role.VIEWER),
            HybridQuery("risk"),
        )


def test_http_failure_does_not_echo_credentials_or_body() -> None:
    def failure(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="fixture secret token")

    with httpx.Client(
        base_url="https://search.invalid", transport=httpx.MockTransport(failure)
    ) as client:
        with pytest.raises(HybridRetrievalError) as caught:
            OpenSearchCorpusClient(client).search(
                GENERATION,
                AccessScope.for_authenticated_user("reader", "tenant-a", Role.VIEWER),
                HybridQuery("risk"),
            )
        assert str(caught.value) == "opensearch_permission_denied"


def test_http_timeout_is_classified_without_request_secrets() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture secret token", request=request)

    with httpx.Client(
        base_url="https://search.invalid", transport=httpx.MockTransport(timeout)
    ) as client:
        with pytest.raises(HybridRetrievalError) as caught:
            OpenSearchCorpusClient(client).search(
                GENERATION,
                AccessScope.for_authenticated_user("reader", "tenant-a", Role.VIEWER),
                HybridQuery("risk"),
            )
        assert str(caught.value) == "opensearch_timeout"
