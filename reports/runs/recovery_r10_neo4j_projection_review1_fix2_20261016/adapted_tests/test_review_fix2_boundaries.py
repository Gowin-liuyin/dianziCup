"""Owned real PG/Neo4j checks for empty manifests and valid generation writes."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from test_r10_neo4j_projection import apply, neo4j_store
from test_r10_projection_pg import PUBLIC, capture, manifest_for, projection_engine, published_fixture

from ai_intel.knowledge.graph_projection import ProjectionNotReady, encode_projection_batch, read_projection_candidates
from ai_intel.knowledge.revisions import bump_scope_epoch

pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]


def test_genuinely_empty_manifest_returns_stable_empty_on_actual_neo4j(projection_engine, neo4j_store):
    namespace, generation = "r10_review1_fix2_" + uuid4().hex, uuid4()
    with projection_engine.begin() as connection:
        bump_scope_epoch(connection, "public", datetime.now(UTC))
    manifest = manifest_for(projection_engine, generation, namespace=namespace)
    assert manifest.event_count == 0 and manifest.page_count == 0 and manifest.status == "ready"
    with Session(projection_engine) as session:
        found = read_projection_candidates(session, PUBLIC, namespace, generation, (uuid4(),), neo4j_store)
    assert not found.candidates and not found.truncated and found.requires_pg_revalidation


def test_absent_generation_blocks_before_external_io(projection_engine):
    namespace, generation = "r10_review1_fix2_" + uuid4().hex, uuid4()
    with projection_engine.begin() as connection:
        bump_scope_epoch(connection, "public", datetime.now(UTC))

    class NeverCalled:
        def find_candidates(self, *_arguments):
            pytest.fail("absent generation reached external IO")

    with Session(projection_engine) as session, pytest.raises(ProjectionNotReady):
        read_projection_candidates(session, PUBLIC, namespace, generation, (uuid4(),), NeverCalled())


def test_legal_other_generation_write_during_read_preserves_selected_generation(
    projection_engine, neo4j_store, tmp_path
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = "r10_review1_fix2_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    first = capture(projection_engine, generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, first)
    second_generation = uuid4()
    created = []

    class OtherGenerationWriter:
        def find_candidates(self, *arguments):
            found = neo4j_store.find_candidates(*arguments)
            manifest_for(projection_engine, second_generation, namespace=namespace)
            value = capture(projection_engine, second_generation, event_id, namespace=namespace)
            apply(projection_engine, neo4j_store, value)
            created.append(value)
            return found

    with Session(projection_engine) as session:
        old_result = read_projection_candidates(session, PUBLIC, namespace, generation, (event_id,), OtherGenerationWriter())
    with Session(projection_engine) as session:
        new_result = read_projection_candidates(session, PUBLIC, namespace, second_generation, (event_id,), neo4j_store)
    assert {item.edge_id for item in old_result.candidates} == {edge.id for edge in first.edges}
    assert {item.payload_sha256 for item in old_result.candidates} == {encode_projection_batch(first)[1]}
    assert {item.edge_id for item in new_result.candidates} == {edge.id for edge in created[0].edges}
    assert {item.payload_sha256 for item in new_result.candidates} == {encode_projection_batch(created[0])[1]}
