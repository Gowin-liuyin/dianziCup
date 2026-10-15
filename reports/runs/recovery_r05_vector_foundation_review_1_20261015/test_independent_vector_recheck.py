"""Retest rejected underflow and observable stored float32 values against the repair SHA."""

import math
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
        assert actual[0] == 2**-149
        assert any(actual)
        if normal_coordinate:
            assert math.isfinite(distance) and distance == pytest.approx(0.0, abs=1e-6)
