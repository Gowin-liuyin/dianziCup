"""Populate legacy R05 rows before reusing the unchanged full-table forward proof."""

import hashlib
from uuid import uuid4

import test_r12_production_schema as history
from sqlalchemy import select
from tests.r12_hybrid_fixtures import NOW, record_change, seed_fact

from ai_intel.knowledge.models import users
from ai_intel.retrieval.persistence_models import grounded_answers, retrieval_chunks


def test_forward0019_to0020_keeps_populated_legacy_vectors_answers_and_jobs(isolated_test_database_url, monkeypatch):
    touched = []

    def with_legacy_rows(engine, body):
        identities = seed_fact(engine, body)
        record_change(engine)
        user_id = str(uuid4())
        with engine.begin() as connection:
            connection.execute(users.insert().values(user_id=user_id, username=user_id, password_hash='synthetic-opaque-hash', tenant_id='tenant-a', role='viewer', created_at=NOW))
            connection.execute(retrieval_chunks.insert().values(chunk_id=str(uuid4()), evidence_id=identities['evidence_id'], revision_id=identities['revision_id'], start_offset=0, end_offset=len(body), chunk_text=body, text_sha256=hashlib.sha256(body.encode()).hexdigest(), model_version='synthetic-legacy-fixed-384', embedding=[1.0] + [0.0] * 383, indexed_at=NOW))
            connection.execute(grounded_answers.insert().values(answer_id=str(uuid4()), user_id=user_id, tenant_id='tenant-a', question_text='Independent synthetic legacy question', response={'status': 'synthetic-history'}, scope_epochs={'public': 1}, model_trace={'data_mode': 'synthetic'}, created_at=NOW))
            assert connection.scalar(select(retrieval_chunks.c.model_version)) == 'synthetic-legacy-fixed-384'
            assert connection.scalar(select(grounded_answers.c.response)) == {'status': 'synthetic-history'}
        touched.append(identities)
        return identities

    monkeypatch.setattr(history, 'seed_fact', with_legacy_rows)
    history.test_forward_upgrade_preserves_all_0019_rows(isolated_test_database_url, monkeypatch)
    assert len(touched) == 1
