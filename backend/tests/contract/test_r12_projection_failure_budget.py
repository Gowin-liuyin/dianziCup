"""Synthetic transport and worker boundaries never imply live OpenSearch or semantic quality."""

import asyncio
import ssl
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.retrieval import runtime_policy
from ai_intel.retrieval.hybrid_contracts import (
    HybridRetrievalError,
    IndexChange,
    IndexGeneration,
    IndexReceipt,
)
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError

GENERATION = IndexGeneration("fixture", "dianzi_fixture")
CONTEXT = JobExecutionContext("fixture", "fixture-worker", 1, None)


@contextmanager
def synthetic_search(receive, bounded, *, deadline=None):
    with httpx.Client(
        base_url="https://fixture.invalid", transport=httpx.MockTransport(receive)
    ) as client:
        options = (
            {
                "deadline": time.monotonic() + 1 if deadline is None else deadline,
                "async_client_factory": lambda: httpx.AsyncClient(
                    base_url=client.base_url, transport=httpx.MockTransport(receive)
                ),
            }
            if bounded
            else {}
        )
        yield OpenSearchCorpusClient(client, **options)


@pytest.mark.parametrize(
    "failure,expected",
    (
        (httpx.ReadTimeout("synthetic"), "opensearch_timeout"),
        (httpx.ConnectError("synthetic"), "opensearch_unavailable"),
        (httpx.Response(403), "opensearch_permission_denied"),
        (httpx.Response(409, json={"error": {"type": "conflict"}}), "opensearch_http_409"),
        (
            httpx.Response(500, json={"error": {"type": "resource_already_exists_exception"}}),
            "opensearch_http_500",
        ),
        (httpx.Response(200, content=b" " * (2 * 1024**2 + 1)), "opensearch_response_limit"),
    ),
)
def test_bounded_creation_failure_keeps_first_code_and_stops_io(failure, expected):
    requests = []

    def receive(request):
        requests.append(request.method)
        if isinstance(failure, Exception):
            raise failure
        return failure

    with (
        synthetic_search(receive, True) as search,
        pytest.raises(HybridRetrievalError, match=expected),
    ):
        search.create_index(GENERATION)
    assert requests == ["PUT"]


@pytest.mark.parametrize("bounded", (False, True))
@pytest.mark.parametrize(
    "body",
    (
        b"",
        b"not-json",
        b"[]",
        b'{"error":"resource_already_exists_exception"}',
        b'{"error":{"type":true}}',
        b'{"error":{"root_cause":[{"type":"resource_already_exists_exception"}]}}',
        b'{"error":{"type":"mapper_parsing_exception","reason":"already exists"}}',
    ),
)
def test_malformed_or_indirect_existing_response_never_starts_mapping(body, bounded):
    requests = []

    def receive(request):
        requests.append(request.method)
        return httpx.Response(400, content=body)

    with (
        synthetic_search(receive, bounded) as search,
        pytest.raises(HybridRetrievalError, match="opensearch_http_400"),
    ):
        search.create_index(GENERATION)
    assert requests == ["PUT"]


@pytest.mark.parametrize("bounded", (False, True))
@pytest.mark.parametrize(
    "field,value",
    (("generation_id", "other"), ("model_version", "other"), ("dimension", 768)),
)
def test_existing_index_cannot_bypass_fixed_space_validation(field, value, bounded):
    requests = []

    def receive(request):
        requests.append(request.method)
        if request.method == "PUT":
            return httpx.Response(
                400, json={"error": {"type": "resource_already_exists_exception"}}
            )
        metadata = {
            "generation_id": GENERATION.generation_id,
            "model_version": GENERATION.model_version,
            "dimension": 384,
            field: value,
        }
        return httpx.Response(
            200,
            json={GENERATION.index_name: {"mappings": {"dynamic": "strict", "_meta": metadata}}},
        )

    with (
        synthetic_search(receive, bounded) as search,
        pytest.raises(HybridRetrievalError, match="index_space_rebuild_required"),
    ):
        search.create_index(GENERATION)
    assert requests == ["PUT", "GET"]


@pytest.mark.parametrize("bounded", (False, True))
@pytest.mark.parametrize("mapping_kind", ("malformed", "non_strict", "multiple_indexes"))
def test_existing_index_still_rejects_invalid_mapping_contract(mapping_kind, bounded):
    requests = []

    def receive(request):
        requests.append(request.method)
        if request.method == "PUT":
            return httpx.Response(
                409, json={"error": {"type": "resource_already_exists_exception"}}
            )
        mapping = {
            "mappings": {
                "dynamic": "false" if mapping_kind == "non_strict" else "strict",
                "_meta": {
                    "generation_id": GENERATION.generation_id,
                    "model_version": GENERATION.model_version,
                    "dimension": 384,
                },
            }
        }
        if mapping_kind == "malformed":
            return httpx.Response(200, content=b"not-json")
        mappings = {GENERATION.index_name: mapping}
        if mapping_kind == "multiple_indexes":
            mappings["dianzi_other"] = mapping
        return httpx.Response(200, json=mappings)

    expected = (
        "opensearch_index_space_invalid"
        if mapping_kind == "malformed"
        else "index_space_rebuild_required"
    )
    with (
        synthetic_search(receive, bounded) as search,
        pytest.raises(HybridRetrievalError, match=expected),
    ):
        search.create_index(GENERATION)
    assert requests == ["PUT", "GET"]


@pytest.mark.parametrize("bounded", (False, True))
def test_successful_creation_uses_one_request(bounded):
    requests = []

    def receive(request):
        requests.append(request.method)
        return httpx.Response(200, json={"acknowledged": True})

    with synthetic_search(receive, bounded) as search:
        search.create_index(GENERATION)
    assert requests == ["PUT"]


@pytest.mark.parametrize("bounded", (False, True))
def test_existing_index_response_body_keeps_byte_cap(bounded):
    requests = []

    def receive(request):
        requests.append(request.method)
        return httpx.Response(
            400,
            content=b'{"error":{"type":"resource_already_exists_exception"},"reason":"'
            + b"x" * (2 * 1024**2)
            + b'"}',
        )

    with (
        synthetic_search(receive, bounded) as search,
        pytest.raises(HybridRetrievalError, match="opensearch_response_limit"),
    ):
        search.create_index(GENERATION)
    assert requests == ["PUT"]


@pytest.mark.parametrize("bounded", (False, True))
def test_existing_index_response_at_exact_byte_limit_is_validated(bounded):
    requests = []

    def receive(request):
        requests.append(request.method)
        if request.method == "PUT":
            body = b'{"error":{"type":"resource_already_exists_exception"}}'
            return httpx.Response(400, content=body + b" " * (2 * 1024**2 - len(body)))
        return httpx.Response(401)

    with (
        synthetic_search(receive, bounded) as search,
        pytest.raises(HybridRetrievalError, match="opensearch_permission_denied"),
    ):
        search.create_index(GENERATION)
    assert requests == ["PUT", "GET"]


class ExistingIndexBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"error":{"type":"resource_already_exists_exception"}}'


class SlowMappingBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        await asyncio.sleep(0.15)
        yield b"{}"


def test_mapping_after_existing_response_uses_same_deadline_and_closes_client():
    requests = []
    closed = []

    async def receive(request):
        requests.append(request.method)
        if request.method == "PUT":
            await asyncio.sleep(0.03)
            return httpx.Response(400, stream=ExistingIndexBody())
        return httpx.Response(200, stream=SlowMappingBody())

    class OwnedAsyncClient(httpx.AsyncClient):
        async def __aexit__(self, *arguments):
            await super().__aexit__(*arguments)
            closed.append(self.is_closed)

    tls_context = ssl.create_default_context()
    with httpx.Client(base_url="https://fixture.invalid", verify=tls_context) as client:
        deadline = time.monotonic() + 0.1
        search = OpenSearchCorpusClient(
            client,
            deadline=deadline,
            async_client_factory=lambda: OwnedAsyncClient(
                base_url=client.base_url, verify=tls_context, transport=httpx.MockTransport(receive)
            ),
        )
        with pytest.raises(HybridRetrievalError, match="opensearch_timeout"):
            search.create_index(GENERATION)
        assert search.deadline == deadline
    assert requests == ["PUT", "GET"]
    assert closed == [True, True]


@pytest.mark.parametrize("timeout", ("20", "NaN", "inf", "bad", None))
@pytest.mark.parametrize("entry", ("factory", "handler"))
def test_invalid_budget_formats_are_rejected_before_any_io(timeout, entry, monkeypatch):
    monkeypatch.setattr(runtime_policy, "PROJECTION_TIMEOUT_SECONDS", timeout)

    def forbidden_io(*arguments, **options):
        pytest.fail("invalid configuration must not perform IO")

    monkeypatch.setattr(runtime_policy, "find_projection_change", forbidden_io)
    monkeypatch.setattr(runtime_policy.httpx, "Client", forbidden_io)
    with pytest.raises(ValueError, match="finite positive"):
        if entry == "factory":
            settings = ApplicationSettings(
                opensearch_url="https://fixture.invalid",
                semantic_model_cache_directory=Path("synthetic-model-cache"),
            )
            with runtime_policy.build_projection_job_handlers(None, settings):
                pytest.fail("invalid factory must not yield")
        else:
            runtime_policy.make_knowledge_change_handler(object())(None, CONTEXT, b"{}")


@pytest.mark.parametrize("supplied_deadline", (None, 150.0))
def test_handler_preparation_and_refresh_share_absolute_deadline(supplied_deadline, monkeypatch):
    observed = []

    class SyntheticIndexer:
        def prepare_generation(self, *, deadline):
            observed.append(("prepare", deadline))

        def refresh_scope(self, change, *, deadline):
            observed.append(("refresh", deadline))
            return IndexReceipt("fixture", "fixture-outbox", "public", 1, 0, False)

    monkeypatch.setattr(runtime_policy.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(
        runtime_policy,
        "find_projection_change",
        lambda *arguments: IndexChange("fixture", "public"),
    )
    result = runtime_policy.make_knowledge_change_handler(
        SyntheticIndexer(), projection_deadline=supplied_deadline
    )(None, CONTEXT, b"{}")
    expected = 120.0 if supplied_deadline is None else supplied_deadline
    assert observed == [("prepare", expected), ("refresh", expected)]
    assert result.outcome == "partial"
    assert result.error_code == "knowledge_change_other_consumers_pending"


def test_expired_supplied_deadline_stops_before_authority_read(monkeypatch):
    def forbidden_io(*arguments):
        pytest.fail("expired handler must not start a database read")

    monkeypatch.setattr(runtime_policy, "find_projection_change", forbidden_io)
    with pytest.raises(JobExecutionError, match="corpus_projection_deadline_exceeded"):
        runtime_policy.make_knowledge_change_handler(
            object(), projection_deadline=time.monotonic() - 1
        )(None, CONTEXT, b"{}")


def test_factory_starts_one_deadline_before_client_setup_and_reuses_it(monkeypatch, tmp_path):
    observed = []
    clock = [100.0]
    settings = ApplicationSettings(
        opensearch_url="https://fixture.invalid",
        semantic_model_cache_directory=tmp_path,
    )
    client = httpx.Client(base_url="https://fixture.invalid")

    class SyntheticIndexer:
        def __init__(self, engine, models, search, generation):
            observed.append(("models", models.deadline))
            observed.append(("search", search.deadline))
            assert models._bounded_client().timeout_seconds == 10.0

        def prepare_generation(self, *, deadline):
            observed.append(("prepare", deadline))

        def refresh_scope(self, change, *, deadline):
            observed.append(("refresh", deadline))
            return IndexReceipt("fixture", "fixture-outbox", "public", 1, 0, False)

    def configured_client(**options):
        clock[0] = 103.0
        return client

    monkeypatch.setattr(runtime_policy.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runtime_policy.httpx, "Client", configured_client)
    monkeypatch.setattr(runtime_policy, "HybridIndexer", SyntheticIndexer)
    monkeypatch.setattr(
        runtime_policy,
        "find_projection_change",
        lambda *arguments: IndexChange("fixture", "public"),
    )
    with runtime_policy.build_projection_job_handlers(None, settings) as handlers:
        result = handlers[runtime_policy.KNOWLEDGE_CHANGE_JOB_TYPE](None, CONTEXT, b"{}")
    assert observed == [
        ("models", 120.0),
        ("search", 120.0),
        ("prepare", 120.0),
        ("refresh", 120.0),
    ]
    assert result.outcome == "partial"
    assert client.is_closed
