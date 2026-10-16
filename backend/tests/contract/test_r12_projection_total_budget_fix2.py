"""Budget and transport boundaries use explicit fixtures, never live model claims."""

import time

import httpx
import pytest

from ai_intel.retrieval.hybrid_contracts import HybridRetrievalError, IndexGeneration
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient


@pytest.mark.parametrize(
    ("failure", "expected"),
    (
        (httpx.ReadTimeout("fixture"), "opensearch_timeout"),
        (httpx.ConnectError("fixture"), "opensearch_unavailable"),
    ),
)
def test_create_failure_preserves_original_transport_code(failure, expected):
    requests = []

    def receive(request):
        requests.append(request.method)
        if request.method == "PUT":
            raise failure
        return httpx.Response(404)

    with (
        httpx.Client(
            base_url="https://fixture.invalid", transport=httpx.MockTransport(receive)
        ) as client,
        pytest.raises(HybridRetrievalError, match=expected),
    ):
        OpenSearchCorpusClient(client).create_index(IndexGeneration("fixture", "dianzi_fixture"))
    assert requests == ["PUT"]


@pytest.mark.parametrize(
    "status,error_type",
    (
        (400, "mapper_parsing_exception"),
        (409, "conflict"),
        (500, "resource_already_exists_exception"),
    ),
)
def test_only_precise_existing_index_response_can_start_mapping_verification(status, error_type):
    requests = []

    def receive(request):
        requests.append(request.method)
        return httpx.Response(status, json={"error": {"type": error_type}})

    with (
        httpx.Client(
            base_url="https://fixture.invalid", transport=httpx.MockTransport(receive)
        ) as client,
        pytest.raises(HybridRetrievalError, match=f"opensearch_http_{status}"),
    ):
        OpenSearchCorpusClient(client).create_index(IndexGeneration("fixture", "dianzi_fixture"))
    assert requests == ["PUT"]


@pytest.mark.parametrize("status", (400, 409))
@pytest.mark.parametrize("use_deadline", (False, True))
def test_precise_already_exists_response_verifies_fixed_space(status, use_deadline):
    generation = IndexGeneration("fixture", "dianzi_fixture")
    requests = []

    def receive(request):
        requests.append(request.method)
        if request.method == "PUT":
            return httpx.Response(
                status, json={"error": {"type": "resource_already_exists_exception"}}
            )
        return httpx.Response(
            200,
            json={
                generation.index_name: {
                    "mappings": {
                        "dynamic": "strict",
                        "_meta": {
                            "generation_id": generation.generation_id,
                            "model_version": generation.model_version,
                            "dimension": 384,
                        },
                    }
                }
            },
        )

    with httpx.Client(
        base_url="https://fixture.invalid", transport=httpx.MockTransport(receive)
    ) as client:
        deadline_options = (
            {
                "deadline": time.monotonic() + 1,
                "async_client_factory": lambda: httpx.AsyncClient(
                    base_url=client.base_url, transport=httpx.MockTransport(receive)
                ),
            }
            if use_deadline
            else {}
        )
        OpenSearchCorpusClient(client, **deadline_options).create_index(generation)
    assert requests == ["PUT", "GET"]


@pytest.mark.parametrize("failure_kind", ("permission", "response_limit"))
def test_create_permission_and_size_failures_never_verify_mapping(failure_kind):
    requests = []

    def receive(request):
        requests.append(request.method)
        return (
            httpx.Response(403)
            if failure_kind == "permission"
            else httpx.Response(200, content=b" " * (2 * 1024**2 + 1))
        )

    expected = (
        "opensearch_permission_denied"
        if failure_kind == "permission"
        else "opensearch_response_limit"
    )
    with (
        httpx.Client(
            base_url="https://fixture.invalid", transport=httpx.MockTransport(receive)
        ) as client,
        pytest.raises(HybridRetrievalError, match=expected),
    ):
        OpenSearchCorpusClient(client).create_index(IndexGeneration("fixture", "dianzi_fixture"))
    assert requests == ["PUT"]


def test_prepare_expired_budget_opens_no_connection():
    from ai_intel.retrieval.indexing import HybridIndexer

    with pytest.raises(HybridRetrievalError, match="corpus_projection_deadline_exceeded"):
        HybridIndexer.prepare_generation(None, deadline=time.monotonic() - 1)


@pytest.mark.parametrize("timeout", (0.0, -1.0, True, float("nan"), float("inf")))
def test_invalid_total_projection_budget_is_rejected(timeout, monkeypatch):
    from ai_intel.retrieval import runtime_policy

    monkeypatch.setattr(runtime_policy, "PROJECTION_TIMEOUT_SECONDS", timeout)
    with pytest.raises(ValueError, match="finite positive"):
        runtime_policy._new_projection_deadline()
