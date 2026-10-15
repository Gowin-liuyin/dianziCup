"""Verify scale rejection, nonzero mixed subnormals and finite real-PG cosine after the norm fix."""

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


@pytest.mark.parametrize('coordinate', [2**-149, 1e-23, 1e20, 1e-50, -1e-50, 2**-75])
def test_bad_scale_refused_before_database_write(vector_database, coordinate) -> None:
    with pytest.raises(ModelContractError):
        validate_embedding_batch([[coordinate] * 384], 1, 384, 'review-final-invalid-norm')
    with Session(vector_database) as session:
        assert session.scalar(select(func.count()).select_from(retrieval_chunks)) == 0


@pytest.mark.parametrize('coordinate', [2**-74, 1.0, 1e17, 1e19])
def test_allowed_scale_preserves_values_and_finite_self_cosine(vector_database, coordinate) -> None:
    row = [coordinate] + [0.0] * 383
    result = validate_embedding_batch([row], 1, 384, 'review-final-valid-norm')
    assert result.vectors == (tuple(row),)
    with Session(vector_database) as session:
        values = chunk_values(session, 1.0, result.model_version)
        values['embedding'] = list(result.vectors[0])
        session.execute(insert(retrieval_chunks).values(values))
        actual = session.scalar(select(retrieval_chunks.c.embedding))
        distance = session.scalar(select(retrieval_chunks.c.embedding.cosine_distance(row)))
        print({'kind': 'final_valid_norm', 'input_coordinate': coordinate, 'stored_coordinate': actual[0],
               'self_cosine_distance': distance})
        assert any(actual)
        assert math.isfinite(distance) and distance == pytest.approx(0.0, abs=1e-6)
