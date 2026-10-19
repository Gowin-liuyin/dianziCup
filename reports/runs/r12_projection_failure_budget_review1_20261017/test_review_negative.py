"""Independent synthetic failure oracles do not establish live OpenSearch service behavior."""

import asyncio
import time
from contextlib import contextmanager

import httpx
import pytest

from ai_intel.retrieval import runtime_policy
from ai_intel.retrieval.hybrid_contracts import HybridRetrievalError, IndexGeneration
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError

GENERATION = IndexGeneration("review-fixture", "dianzi_review_fixture")
CONTEXT = JobExecutionContext("review-fixture", "review-worker", 1, None)


@contextmanager
def search_fixture(receive, bounded):
    with httpx.Client(
        base_url="https://fixture.invalid", transport=httpx.MockTransport(receive)
    ) as client:
        options = (
            {
                "deadline": time.monotonic() + 0.1,
                "async_client_factory": lambda: httpx.AsyncClient(
                    base_url=client.base_url, transport=httpx.MockTransport(receive)
                ),
            }
            if bounded
            else {}
        )
        yield OpenSearchCorpusClient(client, **options)


@pytest.mark.parametrize("bounded", (False, True))
@pytest.mark.parametrize("status", (307, 404))
def test_non_existing_status_never_starts_mapping(status, bounded):
    methods = []

    def receive(request):
        methods.append(request.method)
        return httpx.Response(
            status, json={"error": {"type": "resource_already_exists_exception"}}
        )

    with search_fixture(receive, bounded) as search:
        with pytest.raises(HybridRetrievalError, match=f"^opensearch_http_{status}$"):
            search.create_index(GENERATION)
    assert methods == ["PUT"]


@pytest.mark.parametrize("bounded", (False, True))
def test_mapping_conflict_does_not_recurse_into_creation_exception(bounded):
    methods = []

    def receive(request):
        methods.append(request.method)
        return httpx.Response(
            409, json={"error": {"type": "resource_already_exists_exception"}}
        )

    with search_fixture(receive, bounded) as search:
        with pytest.raises(HybridRetrievalError, match="^opensearch_http_409$"):
            search.create_index(GENERATION)
    assert methods == ["PUT", "GET"]


class DelayedExistingBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        await asyncio.sleep(0.2)
        yield b'{"error":{"type":"resource_already_exists_exception"}}'


class OversizedSplitExistingBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"error":{"type":"resource_already_exists_exception"},"reason":"'
        yield b"x" * (1024**2)
        yield b"y" * (1024**2)
        yield b'"}'


@pytest.mark.parametrize(
    "body,expected",
    (
        (DelayedExistingBody, "opensearch_timeout"),
        (OversizedSplitExistingBody, "opensearch_response_limit"),
    ),
)
def test_error_stream_is_bounded_before_get_and_client_is_closed(body, expected):
    methods = []
    clients = []

    async def receive(request):
        methods.append(request.method)
        return httpx.Response(400, stream=body())

    with httpx.Client(base_url="https://fixture.invalid") as client:

        def new_async_client():
            async_client = httpx.AsyncClient(
                base_url=client.base_url, transport=httpx.MockTransport(receive)
            )
            clients.append(async_client)
            return async_client

        search = OpenSearchCorpusClient(
            client,
            deadline=time.monotonic() + 0.1,
            async_client_factory=new_async_client,
        )
        with pytest.raises(HybridRetrievalError, match=f"^{expected}$"):
            search.create_index(GENERATION)
    assert methods == ["PUT"]
    assert len(clients) == 1
    assert clients[0].is_closed


@pytest.mark.parametrize("deadline", (True, float("nan"), float("inf")))
def test_supplied_invalid_deadline_stops_before_authority_read(deadline, monkeypatch):
    def forbidden_read(*arguments):
        pytest.fail("invalid supplied deadline must not start authority IO")

    monkeypatch.setattr(runtime_policy, "find_projection_change", forbidden_read)
    with pytest.raises(ValueError, match="finite monotonic"):
        runtime_policy.make_knowledge_change_handler(object(), projection_deadline=deadline)(
            None, CONTEXT, b"{}"
        )


def test_client_setup_cannot_start_a_fresh_budget_after_expiry(monkeypatch, tmp_path):
    clock = [100.0]
    original_client = httpx.Client(base_url="https://fixture.invalid")
    settings = runtime_policy.ApplicationSettings(
        opensearch_url="https://fixture.invalid",
        semantic_model_cache_directory=tmp_path,
    )

    def setup_client(**options):
        clock[0] = 121.0
        return original_client

    def forbidden_read(*arguments):
        pytest.fail("client setup exhausted the original absolute deadline")

    monkeypatch.setattr(runtime_policy.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runtime_policy.httpx, "Client", setup_client)
    monkeypatch.setattr(runtime_policy, "find_projection_change", forbidden_read)
    with runtime_policy.build_projection_job_handlers(None, settings) as handlers:
        with pytest.raises(JobExecutionError, match="^corpus_projection_deadline_exceeded$"):
            handlers[runtime_policy.KNOWLEDGE_CHANGE_JOB_TYPE](None, CONTEXT, b"{}")
    assert original_client.is_closed
