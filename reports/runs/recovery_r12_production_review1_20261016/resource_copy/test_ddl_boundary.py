"""Exercise persisted constraint failures through actual PostgreSQL SQL inputs."""

import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import DataError, IntegrityError
from test_independent_negative import projection_counts, seed_indexed
from test_r12_production_indexing import corpus

from ai_intel.retrieval.hybrid_schema import hybrid_chunks


@pytest.mark.parametrize('values', [{'indexed_epoch': -1}, {'start_offset': -1}, {'end_offset': 0}])
def test_invalid_offsets_or_epoch_cannot_be_persisted(corpus, values):
    engine, _, _, _ = seed_indexed(corpus)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(update(hybrid_chunks).values(**values))
    assert projection_counts(engine) == (1, 1, 1)


def test_pg_rejects_vector383_before_commit(corpus):
    engine, _, _, _ = seed_indexed(corpus)
    with pytest.raises(DataError), engine.begin() as connection:
        connection.execute(text('UPDATE hybrid_chunks SET embedding=CAST(:vector AS vector)'), {'vector': '[' + ','.join(['1'] + ['0'] * 382) + ']'})
    assert projection_counts(engine) == (1, 1, 1)
