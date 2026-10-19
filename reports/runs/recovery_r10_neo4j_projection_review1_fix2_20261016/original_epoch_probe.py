"""Exercise actual epoch movement during candidate IO for matches and empty results."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from test_r10_neo4j_projection import apply, neo4j_store
from test_r10_projection_pg import PUBLIC, capture, manifest_for, projection_engine, published_fixture

from ai_intel.knowledge.graph_projection import ProjectionNotReady, read_projection_candidates
from ai_intel.knowledge.revisions import bump_scope_epoch


@pytest.mark.real_pg
@pytest.mark.real_services
@pytest.mark.parametrize("has_candidates", [True, False])
def test_epoch_movement_during_candidate_io_blocks_matches_and_empty_results(
    projection_engine, neo4j_store, tmp_path, has_candidates
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = "r10_review1_fix1_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, value)
    seed = event_id if has_candidates else uuid4()

    class EpochMovingStore:
        def find_candidates(self, *arguments):
            found = neo4j_store.find_candidates(*arguments)
            assert bool(found.candidates) == has_candidates
            with projection_engine.begin() as connection:
                bump_scope_epoch(connection, "public", datetime.now(UTC))
            return found

    with Session(projection_engine) as session, pytest.raises(ProjectionNotReady):
        read_projection_candidates(session, PUBLIC, namespace, generation, (seed,), EpochMovingStore())
