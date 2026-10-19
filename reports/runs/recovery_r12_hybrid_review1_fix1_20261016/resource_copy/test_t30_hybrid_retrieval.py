"""Real isolated PG and OpenSearch; fixture semantics and real E5 checks stay distinguished."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.r12_hybrid_fixtures import NOW, FixtureSemanticModels, record_change, seed_fact

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.models.clients import EmbeddingResult, ModelContractError
from ai_intel.infrastructure.models.semantic import LocalSemanticModels
from ai_intel.knowledge.models import document_revisions, documents, scope_epochs
from ai_intel.knowledge.persistence_models import claim_evidence, claims, events
from ai_intel.retrieval.hybrid import HybridRetriever
from ai_intel.retrieval.hybrid_contracts import (
    HybridQuery,
    HybridRetrievalError,
    IndexChange,
    IndexGeneration,
)
from ai_intel.retrieval.hybrid_schema import (
    hybrid_chunks,
    hybrid_index_receipts,
    hybrid_index_watermarks,
    hybrid_metadata,
)
from ai_intel.retrieval.indexing import HybridIndexer
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient

pytestmark = pytest.mark.real_pg
PUBLIC = AccessScope.for_authenticated_user("synthetic-reader", "tenant-a", Role.VIEWER)


@pytest.fixture
def corpus(
    isolated_test_database_url: str,
) -> Iterator[tuple[Engine, HybridIndexer, HybridRetriever]]:
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r12_review1fix1_20261016"
    schema = "test_r12_review1fix1_" + uuid4().hex
    base = create_engine(url, connect_args={"connect_timeout": 5})
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    migration_url = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000"}
    )
    run_migrations(migration_url.render_as_string(hide_password=False))
    runtime_url = url.update_query_dict(
        {"options": f"-c search_path={schema},public -c statement_timeout=15000"}
    )
    engine = create_engine(runtime_url, connect_args={"connect_timeout": 5})
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        for table in hybrid_metadata.sorted_tables:
            table.create(connection)
    configured_url = os.environ.get("R12_OPENSEARCH_URL")
    if not configured_url:
        pytest.fail("blocked_integration: R12_OPENSEARCH_URL is required")
    client = httpx.Client(base_url=configured_url, timeout=10.0)
    search = OpenSearchCorpusClient(client)
    generation = IndexGeneration("r12-" + uuid4().hex, "dianzi_test_r12_review1fix1_" + uuid4().hex)
    models = FixtureSemanticModels()
    indexer = HybridIndexer(engine, models, search, generation)
    retriever = HybridRetriever(engine, models, search, generation)
    try:
        indexer.prepare_generation()
        yield engine, indexer, retriever
    finally:
        assert generation.index_name.startswith("dianzi_test_r12_review1fix1_")
        response = client.delete("/" + generation.index_name)
        assert response.status_code in {200, 404}
        client.close()
        engine.dispose()
        assert schema.startswith("test_r12_review1fix1_") and schema.isidentifier()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()
        print(
            json.dumps({"cleanup": "owned_only", "index": generation.index_name, "schema": schema})
        )


def index_fact_set(engine: Engine, indexer: HybridIndexer, scope: str = "public") -> IndexChange:
    change = record_change(engine, scope)
    indexer.refresh_scope(change)
    return change


def test_t30_c01_exact_cve_has_priority_even_after_reranker(corpus) -> None:
    engine, indexer, retriever = corpus
    target = seed_fact(
        engine, "CVE-2026-10001 synthetic prompt injection risk.", cve="CVE-2026-10001"
    )
    seed_fact(engine, "A different prompt injection risk has very similar wording.")
    index_fact_set(engine, indexer)
    result = retriever.retrieve(
        PUBLIC, HybridQuery("CVE-2026-10001 prompt injection", include_graph=False)
    )
    assert result.hits[0].candidate.event_id == target["event_id"]
    assert result.hits[0].exact_identifier
    assert result.trace.bm25_count > 0 and result.trace.vector_count == 2
    assert result.hits[0].candidate.chunk_id != result.hits[0].candidate.evidence_id
    assert result.partial is False


def test_t30_c03_each_real_branch_prefilters_tenant_and_time(corpus) -> None:
    engine, indexer, retriever = corpus
    public = seed_fact(engine, "shared prompt injection risk")
    own = seed_fact(engine, "shared prompt injection risk own", tenant="tenant-a")
    other = seed_fact(engine, "shared prompt injection risk other", tenant="tenant-b")
    future = seed_fact(
        engine,
        "shared prompt injection future",
        tenant="tenant-a",
        available_at=NOW + timedelta(days=10),
    )
    for key in ("public", "tenant:tenant-a", "tenant:tenant-b"):
        index_fact_set(engine, indexer, key)
    scope = AccessScope.for_authenticated_user("synthetic-analyst", "tenant-a", Role.ANALYST)
    result = retriever.retrieve(
        scope,
        HybridQuery(
            "shared prompt injection", available_before=NOW + timedelta(days=1), include_graph=False
        ),
    )
    assert {hit.candidate.evidence_id for hit in result.hits} == {
        public["evidence_id"],
        own["evidence_id"],
    }
    assert result.trace.bm25_count == result.trace.vector_count == 2
    assert other["evidence_id"] not in repr(result)
    assert future["evidence_id"] not in repr(result)
    viewer = retriever.retrieve(PUBLIC, HybridQuery("shared prompt injection", include_graph=False))
    assert {hit.candidate.evidence_id for hit in viewer.hits} == {public["evidence_id"]}
    assert viewer.trace.bm25_count == viewer.trace.vector_count == 1


@pytest.mark.parametrize(
    "relation,values",
    [
        (claims, {"claim_status": "withdrawn"}),
        (claims, {"is_current": False}),
        (claims, {"freshness": "stale"}),
        (document_revisions, {"is_current": False}),
        (events, {"status": "superseded"}),
        (claim_evidence, {"validation_status": "unverified"}),
        (documents, {"visibility": "tenant", "tenant_id": "tenant-b"}),
    ],
)
def test_t30_c04_stale_or_hidden_authority_is_filtered_before_rerank(
    corpus, relation, values
) -> None:
    engine, indexer, retriever = corpus
    seed_fact(engine, "prompt injection synthetic risk")
    index_fact_set(engine, indexer)
    with engine.begin() as connection:
        connection.execute(update(relation).values(**values))
    result = retriever.retrieve(PUBLIC, HybridQuery("prompt injection", include_graph=False))
    assert not result.hits and result.partial
    assert "stale_candidates_filtered" in result.reasons
    assert result.trace.reranked_count == 0


def test_t30_c06_new_unindexed_exact_fact_uses_pg_and_marks_lag(corpus) -> None:
    engine, indexer, retriever = corpus
    seed_fact(engine, "first prompt injection fact")
    index_fact_set(engine, indexer)
    newest = seed_fact(engine, "CVE-2026-10002 newest prompt injection", cve="CVE-2026-10002")
    record_change(engine)
    result = retriever.retrieve(PUBLIC, HybridQuery("CVE-2026-10002", include_graph=False))
    assert result.hits[0].candidate.evidence_id == newest["evidence_id"]
    assert result.partial and "index_lag" in result.reasons


def test_replay_and_out_of_order_full_snapshot_do_not_regress_watermark(corpus) -> None:
    engine, indexer, _retriever = corpus
    seed_fact(engine, "first synthetic risk")
    old = record_change(engine)
    seed_fact(engine, "new synthetic risk")
    newer = record_change(engine)
    newest_receipt = indexer.refresh_scope(newer)
    older_receipt = indexer.refresh_scope(old)
    replay = indexer.refresh_scope(old)
    assert newest_receipt.indexed_epoch == older_receipt.indexed_epoch == replay.indexed_epoch == 2
    assert replay.replayed and not older_receipt.replayed
    with engine.connect() as connection:
        assert connection.scalar(select(hybrid_index_watermarks.c.indexed_epoch)) == 2
        assert connection.scalar(select(func.count()).select_from(hybrid_chunks)) == 2
        assert connection.scalar(select(func.count()).select_from(hybrid_index_receipts)) == 2


def test_os_failure_never_advances_pg_receipt_or_watermark(corpus, monkeypatch) -> None:
    engine, indexer, _retriever = corpus
    seed_fact(engine, "first synthetic risk")
    index_fact_set(engine, indexer)
    pending = record_change(engine)

    def fail_refresh(generation: IndexGeneration) -> None:
        raise HybridRetrievalError("opensearch_refresh_incomplete")

    monkeypatch.setattr(indexer.search, "refresh", fail_refresh)
    with pytest.raises(HybridRetrievalError, match="opensearch_refresh_incomplete"):
        indexer.refresh_scope(pending)
    with engine.connect() as connection:
        assert connection.scalar(select(hybrid_index_watermarks.c.indexed_epoch)) == 1
        assert connection.scalar(select(func.count()).select_from(hybrid_index_receipts)) == 1


def test_acl_epoch_change_during_rerank_invalidates_complete_selection(corpus, monkeypatch) -> None:
    engine, indexer, retriever = corpus
    seed_fact(engine, "synthetic risk")
    index_fact_set(engine, indexer)
    original = retriever.models.rerank

    def change_epoch(query: str, passages: tuple[str, ...]):
        with engine.begin() as connection:
            connection.execute(update(scope_epochs).values(epoch=scope_epochs.c.epoch + 1))
        return original(query, passages)

    monkeypatch.setattr(retriever.models, "rerank", change_epoch)
    result = retriever.retrieve(PUBLIC, HybridQuery("risk", include_graph=False))
    assert not result.hits
    assert result.partial and "scope_changed_during_retrieval" in result.reasons


def test_graph_not_configured_is_explicit_partial(corpus) -> None:
    engine, indexer, retriever = corpus
    seed_fact(engine, "synthetic risk")
    index_fact_set(engine, indexer)
    result = retriever.retrieve(PUBLIC, HybridQuery("risk"))
    assert result.hits and result.partial
    assert result.graph_status == "not_configured" and "graph_not_configured" in result.reasons


def test_concurrent_same_outbox_has_one_receipt_and_one_replay(corpus) -> None:
    engine, indexer, _retriever = corpus
    seed_fact(engine, "synthetic risk")
    change = record_change(engine)
    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(indexer.refresh_scope, (change, change)))
    assert sorted(item.replayed for item in receipts) == [False, True]
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(hybrid_index_receipts)) == 1


def test_wrong_outbox_scope_is_rejected_without_writes(corpus) -> None:
    engine, indexer, _retriever = corpus
    seed_fact(engine, "synthetic risk")
    change = record_change(engine)
    with pytest.raises(HybridRetrievalError, match="index_change_not_authoritative"):
        indexer.refresh_scope(IndexChange(change.outbox_id, "tenant:tenant-b"))
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(hybrid_index_receipts)) == 0


def test_scope_epoch_change_while_embedding_does_not_commit_watermark(corpus, monkeypatch) -> None:
    engine, indexer, _retriever = corpus
    seed_fact(engine, "synthetic risk")
    change = record_change(engine)
    original = indexer.models.embed_passages

    def bump_epoch(passages: tuple[str, ...]):
        with engine.begin() as connection:
            connection.execute(update(scope_epochs).values(epoch=scope_epochs.c.epoch + 1))
        return original(passages)

    monkeypatch.setattr(indexer.models, "embed_passages", bump_epoch)
    with pytest.raises(HybridRetrievalError, match="index_scope_changed_retry_required"):
        indexer.refresh_scope(change)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(hybrid_index_watermarks)) == 0
        assert connection.scalar(select(func.count()).select_from(hybrid_index_receipts)) == 0


def test_t30_c05_model_dimension_mismatch_cannot_commit_projection(corpus, monkeypatch) -> None:
    engine, indexer, _retriever = corpus
    seed_fact(engine, "synthetic risk")
    change = record_change(engine)

    def wrong_space(passages: tuple[str, ...]) -> EmbeddingResult:
        return EmbeddingResult(((1.0,) + (0.0,) * 382,), indexer.generation.model_version, 383)

    monkeypatch.setattr(indexer.models, "embed_passages", wrong_space)
    with pytest.raises(ModelContractError, match="embedding model space mismatch"):
        indexer.refresh_scope(change)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(hybrid_chunks)) == 0
        assert connection.scalar(select(func.count()).select_from(hybrid_index_receipts)) == 0


def test_exact_identifier_cannot_reveal_other_tenant_fact(corpus) -> None:
    engine, indexer, retriever = corpus
    seed_fact(
        engine, "CVE-2026-10003 synthetic private risk", tenant="tenant-b", cve="CVE-2026-10003"
    )
    index_fact_set(engine, indexer, "tenant:tenant-b")
    result = retriever.retrieve(PUBLIC, HybridQuery("CVE-2026-10003", include_graph=False))
    assert (
        not result.hits
        and result.trace.exact_count == result.trace.bm25_count == result.trace.vector_count == 0
    )
    assert result.partial and "no_supported_evidence" in result.reasons


def test_bm25_unavailable_returns_vector_evidence_with_explicit_partial(
    corpus, monkeypatch
) -> None:
    engine, indexer, retriever = corpus
    seed_fact(engine, "synthetic risk")
    index_fact_set(engine, indexer)

    def unavailable(*arguments):
        raise HybridRetrievalError("opensearch_unavailable")

    monkeypatch.setattr(retriever.bm25, "search", unavailable)
    result = retriever.retrieve(PUBLIC, HybridQuery("risk", include_graph=False))
    assert result.hits and result.partial and "bm25_unavailable" in result.reasons


def test_facts_changed_during_rerank_are_not_returned(corpus, monkeypatch) -> None:
    engine, indexer, retriever = corpus
    seed_fact(engine, "synthetic risk")
    index_fact_set(engine, indexer)
    original = retriever.models.rerank

    def withdraw(query: str, passages: tuple[str, ...]):
        with engine.begin() as connection:
            connection.execute(update(claims).values(claim_status="withdrawn"))
        return original(query, passages)

    monkeypatch.setattr(retriever.models, "rerank", withdraw)
    result = retriever.retrieve(PUBLIC, HybridQuery("risk", include_graph=False))
    assert not result.hits and "facts_changed_during_rerank" in result.reasons


def test_t30_c02_real_e5_and_reranker_retrieve_chinese_english_synonyms(corpus) -> None:
    engine, indexer, retriever = corpus
    cache = os.environ.get("R05_SEMANTIC_CACHE")
    if not cache:
        pytest.fail("blocked_live: verified R05_SEMANTIC_CACHE is required")
    models = LocalSemanticModels(Path(cache))
    indexer.models = models
    retriever.models = models
    english = seed_fact(
        engine,
        "Prompt injection makes a language model follow malicious instructions "
        "embedded in a document.",
    )
    chinese = seed_fact(engine, "提示注入使语言模型遵循文档中嵌入的恶意指令。")
    irrelevant = seed_fact(engine, "Steam rice in a pot with water until it is cooked.")
    index_fact_set(engine, indexer)
    for question in (
        "什么攻击会让模型听从文档里的恶意指令？",
        "What attack makes a model obey malicious document instructions?",
    ):
        result = retriever.retrieve(PUBLIC, HybridQuery(question, include_graph=False))
        assert result.hits[0].candidate.evidence_id in {
            english["evidence_id"],
            chinese["evidence_id"],
        }
        assert result.hits[0].candidate.evidence_id != irrelevant["evidence_id"]
        assert result.trace.vector_count == result.trace.reranked_count == 3
        encoded = models.embed_query(question)
        assert result.embedding_model == encoded.model_version
        with engine.connect() as connection:
            distance = hybrid_chunks.c.embedding.cosine_distance(list(encoded.vectors[0]))
            nearest = connection.scalar(
                select(hybrid_chunks.c.evidence_id)
                .order_by(distance, hybrid_chunks.c.chunk_id)
                .limit(1)
            )
        assert nearest in {english["evidence_id"], chinese["evidence_id"]}
        print(
            json.dumps(
                {
                    "data_mode": "synthetic_real_models",
                    "language": "zh" if question[0] == "什" else "en",
                    "trace": result.trace.__dict__,
                    "rerank_scores": [hit.rerank_score for hit in result.hits],
                }
            )
        )
