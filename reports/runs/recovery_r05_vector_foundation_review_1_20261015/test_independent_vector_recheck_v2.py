"""Retest rejected underflow and observable stored float32 values against the repair SHA."""

import math
import struct
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

FROZEN_ROOT = Path('C:/Users/yinha/.codex/worktrees/recovery-r05-vector-foundation-review-1/dianzi')
sys.path.insert(0, str(FROZEN_ROOT / 'backend/tests/integration'))
from test_r05_vector_persistence import chunk_values, vector_database

from ai_intel.infrastructure.models.clients import ModelContractError, validate_embedding_batch
from ai_intel.retrieval.persistence_models import retrieval_chunks


@pytest.fixture
def isolated_test_database_url() -> str:
    from scripts.dev import require_isolated_test_database

    return require_isolated_test_database()


@pytest.mark.parametrize('row', [[1e-50] * 384, [-1e-50] * 384, [0.0] * 383 + [1e-50]])
def test_underflow_is_rejected_before_pg_write(vector_database, row) -> None:
    with pytest.raises(ModelContractError):
        validate_embedding_batch([row], 1, 384, 'review-underflow-recheck')
    with Session(vector_database) as session:
        assert session.scalar(select(func.count()).select_from(retrieval_chunks)) == 0


@pytest.mark.parametrize('normal_coordinate', [0.0, 1.0])
def test_subnormal_coordinate_is_preserved_in_real_pg(vector_database, normal_coordinate) -> None:
    row = [2**-149, normal_coordinate] + [0.0] * 382
    result = validate_embedding_batch([row], 1, 384, 'review-subnormal-recheck')
    assert result.vectors[0][0] == 2**-149
    with Session(vector_database) as session:
        values = chunk_values(session, 1.0, result.model_version)
        values['embedding'] = list(result.vectors[0])
        session.execute(insert(retrieval_chunks).values(values))
        actual = session.scalar(select(retrieval_chunks.c.embedding))
        distance = session.scalar(select(retrieval_chunks.c.embedding.cosine_distance(row)))
        print({'kind': 'subnormal_recheck', 'normal_coordinate': normal_coordinate,
               'stored_coordinate': actual[0], 'cosine_distance': str(distance)})
        assert struct.pack('!f', actual[0]) == bytes.fromhex('00000001')
        assert any(actual)
        if normal_coordinate:
            assert math.isfinite(distance) and distance == pytest.approx(0.0, abs=1e-6)


def test_original_pg_underflow_diagnostic_now_stops_before_insert(vector_database) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_independent_vector_foundation_v2 import test_validated_underflow_roundtrip_keeps_nonzero_cosine_semantics

    with pytest.raises(ModelContractError, match='zero embedding'):
        test_validated_underflow_roundtrip_keeps_nonzero_cosine_semantics(vector_database)
    with Session(vector_database) as session:
        assert session.scalar(select(func.count()).select_from(retrieval_chunks)) == 0


@pytest.mark.parametrize('coordinate', [2**-149, 1e20])
def test_vector_scales_with_undefined_real_pg_cosine_are_refused(coordinate) -> None:
    with pytest.raises(ModelContractError):
        validate_embedding_batch([[coordinate] * 384], 1, 384, 'review-norm-range-v1')


@pytest.mark.parametrize('coordinate', [2**-149, 1e20])
def test_raw_pg_demonstrates_nonzero_scale_self_cosine_nan(vector_database, coordinate) -> None:
    row = [coordinate] * 384
    with Session(vector_database) as session:
        values = chunk_values(session, 1.0, 'review-raw-norm-range-v1')
        values['embedding'] = row
        session.execute(insert(retrieval_chunks).values(values))
        actual = session.scalar(select(retrieval_chunks.c.embedding))
        distance = session.scalar(select(retrieval_chunks.c.embedding.cosine_distance(row)))
        print({'kind': 'raw_pg_nonzero_norm', 'input_coordinate': coordinate,
               'stored_coordinate': actual[0], 'stored_nonzero': any(actual), 'self_cosine_distance': str(distance)})
        assert any(actual)
        assert math.isnan(distance)
