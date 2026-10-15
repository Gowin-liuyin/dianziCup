"""Independent observable tests for the frozen vector foundation, without product changes."""

import hashlib
import os
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

FROZEN_ROOT = Path('C:/Users/yinha/.codex/worktrees/recovery-r05-vector-foundation-review-1/dianzi')
sys.path.insert(0, str(FROZEN_ROOT / 'backend/tests/integration'))
from test_r05_vector_persistence import chunk_values, vector_database

from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.models.clients import ModelContractError, validate_embedding_batch
from ai_intel.knowledge.models import users
from ai_intel.retrieval.persistence_models import grounded_answers, retrieval_chunks


@pytest.fixture
def isolated_test_database_url() -> str:
    from scripts.dev import require_isolated_test_database

    return require_isolated_test_database()


def test_float32_underflow_is_rejected_before_becoming_a_zero_vector() -> None:
    with pytest.raises(ModelContractError):
        validate_embedding_batch([[1e-50, -1e-50]], 1, 2, 'review-f32-v1')


def test_small_representable_float32_is_not_confused_with_zero() -> None:
    result = validate_embedding_batch([[2**-149, 0.0]], 1, 2, 'review-f32-v1')
    assert struct.unpack('!f', struct.pack('!f', result.vectors[0][0]))[0] != 0.0


def test_validated_underflow_roundtrip_keeps_nonzero_cosine_semantics(vector_database) -> None:
    result = validate_embedding_batch([[1e-50] * 384], 1, 384, 'review-underflow-v1')
    with Session(vector_database) as session:
        values = chunk_values(session, 1.0, result.model_version)
        values['embedding'] = list(result.vectors[0])
        session.execute(insert(retrieval_chunks).values(values))
        actual = session.scalar(select(retrieval_chunks.c.embedding))
        distance = session.scalar(select(retrieval_chunks.c.embedding.cosine_distance([1.0] * 384)))
        print({'kind': 'validated_float32_roundtrip', 'python_nonzero': any(result.vectors[0]),
               'stored_nonzero': any(actual), 'stored_coordinate': actual[0], 'cosine_distance': str(distance)})
        assert any(actual), 'validated nonzero vector became a stored zero vector'


def test_migration_replay_keeps_rows_and_answer_owner_audit(vector_database) -> None:
    at = datetime.now(UTC)
    user_id, answer_id = (str(uuid4()) for _ in range(2))
    with Session(vector_database) as session, session.begin():
        values = chunk_values(session, 1.0)
        session.execute(insert(retrieval_chunks).values(values))
        session.execute(insert(users).values(user_id=user_id, username=user_id, password_hash='synthetic-noncredential',
                                            tenant_id='tenant-review', role='viewer', created_at=at))
        session.execute(insert(grounded_answers).values(answer_id=answer_id, user_id=user_id, tenant_id='tenant-review',
                                                       question_text='history question', response={'evidence': [values['evidence_id']]},
                                                       scope_epochs={'tenant:tenant-review': 1}, model_trace={'cost': 'unknown'}, created_at=at))
    run_migrations(vector_database.url.render_as_string(hide_password=False))
    run_migrations(vector_database.url.render_as_string(hide_password=False))
    with vector_database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(retrieval_chunks)) == 1
        answer = connection.execute(select(grounded_answers).where(grounded_answers.c.answer_id == answer_id)).one()
        assert answer.user_id == user_id and answer.tenant_id == 'tenant-review'
        assert answer.response == {'evidence': [values['evidence_id']]}
        assert answer.scope_epochs == {'tenant:tenant-review': 1}
        assert answer.model_trace == {'cost': 'unknown'}


@pytest.mark.parametrize('invalid_field', ['response', 'scope_epochs', 'model_trace'])
def test_answer_audit_json_arrays_are_refused(vector_database, invalid_field) -> None:
    user_id = str(uuid4())
    with Session(vector_database) as session:
        session.execute(insert(users).values(user_id=user_id, username=user_id, password_hash='synthetic-noncredential',
                                            tenant_id=None, role='viewer', created_at=datetime.now(UTC)))
        values = dict(answer_id=str(uuid4()), user_id=user_id, tenant_id=None, question_text='question',
                      response={}, scope_epochs={}, model_trace={}, created_at=datetime.now(UTC))
        values[invalid_field] = []
        with pytest.raises(IntegrityError):
            session.execute(insert(grounded_answers).values(values))
        session.rollback()
        assert session.scalar(select(func.count()).select_from(grounded_answers)) == 0


def test_owner_fk_refuses_orphan_answer(vector_database) -> None:
    with Session(vector_database) as session:
        with pytest.raises(IntegrityError):
            session.execute(insert(grounded_answers).values(answer_id=str(uuid4()), user_id='review-owner-does-not-exist',
                                                           tenant_id=None, question_text='question', response={},
                                                           scope_epochs={}, model_trace={}, created_at=datetime.now(UTC)))
        session.rollback()
        assert session.scalar(select(func.count()).select_from(grounded_answers)) == 0


def test_concurrent_duplicate_chunk_space_has_one_committed_row(vector_database) -> None:
    with Session(vector_database) as session:
        original = chunk_values(session, 1.0)

    def insert_once(index: int) -> str:
        values = dict(original, chunk_id=f'{original["chunk_id"]}-{index}')
        try:
            with Session(vector_database) as session, session.begin():
                session.execute(insert(retrieval_chunks).values(values))
            return 'committed'
        except IntegrityError:
            return 'duplicate_rejected'

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(insert_once, range(2)))
    assert outcomes == ['committed', 'duplicate_rejected']
    with Session(vector_database) as session:
        assert session.scalar(select(func.count()).select_from(retrieval_chunks)) == 1


def test_schema_only_migration_upgrades_and_replays_without_public_tables(isolated_test_database_url) -> None:
    base = create_engine(isolated_test_database_url)
    schema = 'test_r05_review_only_' + uuid4().hex
    with base.begin() as connection:
        assert connection.scalar(text('SELECT current_database()')) == 'test_dianzi_r05_pgvector_20261015'
        connection.execute(CreateSchema(schema))
    isolated = base.url.update_query_dict({'options': f'-c search_path={schema} -c statement_timeout=15000'})
    engine = create_engine(isolated)
    try:
        run_migrations(isolated.render_as_string(hide_password=False))
        run_migrations(isolated.render_as_string(hide_password=False))
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT current_schema()')) == schema
            assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0014_grounded_answer_vectors'
            assert connection.scalar(text('SELECT to_regclass(:qualified)'), {'qualified': schema + '.retrieval_chunks'}) is not None
            assert connection.scalar(text('SELECT to_regclass(:qualified)'), {'qualified': schema + '.grounded_answers'}) is not None
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def test_schema_only_search_path_vector_operator_visibility_is_documented(vector_database) -> None:
    schema = vector_database.url.query['options'].split('search_path=')[1].split(',')[0]
    with vector_database.connect() as connection:
        connection.execute(text("SELECT set_config('search_path', :schema, true)"), {'schema': schema})
        with pytest.raises(DBAPIError) as failure:
            connection.scalar(select(retrieval_chunks.c.embedding.cosine_distance([1.0] * 384)))
        assert getattr(failure.value.orig, 'sqlstate', None) == '42883'
        connection.rollback()
