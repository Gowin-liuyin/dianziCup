"""New observable negative inputs against the forward-migrated projection."""

from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from test_r12_production_indexing import corpus
from tests.r12_hybrid_fixtures import record_change, seed_fact

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.models.clients import EmbeddingResult, ModelContractError
from ai_intel.knowledge.persistence_models import event_documents, events
from ai_intel.retrieval.hybrid_contracts import HybridQuery, HybridRetrievalError
from ai_intel.retrieval.hybrid_schema import (
    hybrid_chunks,
    hybrid_index_receipts,
    hybrid_index_watermarks,
)

PUBLIC = AccessScope.for_authenticated_user('independent-review', 'tenant-a', Role.VIEWER)


def projection_counts(engine):
    with engine.connect() as connection:
        return tuple(connection.scalar(select(func.count()).select_from(table)) for table in (hybrid_chunks, hybrid_index_receipts, hybrid_index_watermarks))


def seed_indexed(corpus):
    engine, indexer, retriever = corpus
    parent = seed_fact(engine, 'Independent synthetic prompt injection risk with valid permanent evidence.')
    change = record_change(engine)
    indexer.refresh_scope(change)
    return engine, indexer, retriever, parent


@pytest.mark.parametrize('column', ['evidence_id', 'revision_id', 'document_id', 'source_id', 'event_id', 'claim_id'])
def test_each_orphan_fact_reference_rejected_and_transaction_rolled_back(corpus, column):
    engine, _, _, _ = seed_indexed(corpus)
    before = projection_counts(engine)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(update(hybrid_chunks).values({column: str(uuid4())}))
    assert projection_counts(engine) == before == (1, 1, 1)
    with engine.connect() as connection:
        assert connection.scalar(select(hybrid_chunks.c.indexed_epoch)) == 1


@pytest.mark.parametrize('values', [
    {'visibility': 'public', 'tenant_id': 'tenant-a', 'scope_key': 'public'},
    {'visibility': 'tenant', 'tenant_id': None, 'scope_key': 'public'},
    {'visibility': 'tenant', 'tenant_id': 'tenant-a', 'scope_key': 'tenant:tenant-b'},
    {'visibility': 'invented', 'tenant_id': None, 'scope_key': 'public'},
])
def test_invalid_derived_scope_is_rejected(corpus, values):
    engine, _, _, _ = seed_indexed(corpus)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(update(hybrid_chunks).values(**values))
    with engine.connect() as connection:
        row = connection.execute(select(hybrid_chunks.c.visibility, hybrid_chunks.c.tenant_id, hybrid_chunks.c.scope_key)).one()
    assert tuple(row) == ('public', None, 'public')


@pytest.mark.parametrize('column', ['source_id', 'document_id', 'revision_id', 'claim_id', 'event_id', 'evidence_id'])
def test_existing_but_wrong_fact_parent_cannot_return_evidence(corpus, column):
    engine, _, retriever, _ = seed_indexed(corpus)
    other = seed_fact(engine, 'Another independent source record with a different evidence identity.')
    with engine.begin() as connection:
        connection.execute(update(hybrid_chunks).values({column: other[column]}))
    result = retriever.retrieve(PUBLIC, HybridQuery('prompt injection', include_graph=False))
    assert not result.hits
    reason = 'stale_candidates_filtered' if column == 'evidence_id' else 'index_projection_changed'
    assert result.partial and reason in result.reasons
    assert result.trace.reranked_count == 0


@pytest.mark.parametrize('stage', ['upsert', 'remove_older_scope', 'second_refresh'])
def test_new_os_failure_inputs_keep_old_pg_projection_and_watermark(corpus, monkeypatch, stage):
    engine, indexer, _, _ = seed_indexed(corpus)
    before = projection_counts(engine)
    seed_fact(engine, 'New independent synthetic risk not yet indexed.')
    change = record_change(engine)

    def unavailable(*arguments, **keywords):
        raise HybridRetrievalError('independent_os_failure')

    if stage == 'second_refresh':
        previous = indexer.search.refresh
        calls = 0

        def second_refresh(generation):
            nonlocal calls
            calls += 1
            if calls == 2:
                unavailable()
            previous(generation)

        monkeypatch.setattr(indexer.search, 'refresh', second_refresh)
    else:
        monkeypatch.setattr(indexer.search, stage, unavailable)
    with pytest.raises(HybridRetrievalError, match='independent_os_failure'):
        indexer.refresh_scope(change)
    assert projection_counts(engine) == before == (1, 1, 1)
    with engine.connect() as connection:
        assert connection.scalar(select(hybrid_index_watermarks.c.indexed_epoch)) == 1
        assert connection.scalar(select(hybrid_index_receipts.c.outbox_id)) != change.outbox_id


def test_production_tables_and_fact_foreign_keys_belong_to_own_schema(corpus):
    engine, _, _ = corpus
    with engine.connect() as connection:
        schema = connection.scalar(text('SELECT current_schema()'))
        assert schema.startswith('test_r12_production_')
        namespaces = connection.execute(text("SELECT c.relname, n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid IN (to_regclass('hybrid_chunks'),to_regclass('hybrid_index_receipts'),to_regclass('hybrid_index_generations'),to_regclass('hybrid_index_watermarks'))")).all()
        assert len(namespaces) == 4 and all(row.nspname == schema for row in namespaces)
    references = inspect(engine).get_foreign_keys('hybrid_chunks', schema=schema)
    assert len(references) == 7
    assert all(reference['referred_schema'] == schema for reference in references)


def test_wrong_model_metadata_is_excluded_from_vector_branch(corpus):
    engine, _, retriever, _ = seed_indexed(corpus)
    with engine.begin() as connection:
        connection.execute(update(hybrid_chunks).values(model_version='different-vector-space'))
    result = retriever.retrieve(PUBLIC, HybridQuery('prompt injection', include_graph=False))
    assert result.trace.vector_count == 0
    assert result.trace.bm25_count == 1
    assert len(result.hits) == 1


def test_wrong_embedding_model_version_cannot_write_projection(corpus, monkeypatch):
    engine, indexer, _, _ = seed_indexed(corpus)
    change = record_change(engine)

    def wrong_model(passages):
        return EmbeddingResult(tuple((1.0,) + (0.0,) * 383 for _ in passages), 'wrong-model-version', 384)

    monkeypatch.setattr(indexer.models, 'embed_passages', wrong_model)
    with pytest.raises(ModelContractError, match='embedding model space mismatch'):
        indexer.refresh_scope(change)
    assert projection_counts(engine) == (1, 1, 1)
    with engine.connect() as connection:
        assert connection.scalar(select(hybrid_index_watermarks.c.indexed_epoch)) == 1


def test_actual_scope_capacity_10001_facts_fails_without_watermark(corpus):
    engine, indexer, _ = corpus
    parent = seed_fact(engine, 'Independent synthetic capacity witness.')
    with engine.begin() as connection:
        base = connection.execute(select(events)).mappings().one()
        for batch in range(10):
            event_ids = [str(uuid4()) for _ in range(1000)]
            connection.execute(events.insert(), [dict(base, event_id=identity) for identity in event_ids])
            connection.execute(event_documents.insert(), [{'event_id': identity, 'revision_id': parent['revision_id'], 'active': True, 'associated_at': base['first_seen_at']} for identity in event_ids])
    change = record_change(engine)
    with pytest.raises(HybridRetrievalError, match='index_scope_capacity_exceeded'):
        indexer.refresh_scope(change)
    assert projection_counts(engine) == (0, 0, 0)
