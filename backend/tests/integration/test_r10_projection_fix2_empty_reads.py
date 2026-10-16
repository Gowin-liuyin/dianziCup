"""Real owned services with synthetic supports; empty/readiness/input IO boundaries."""

from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session
from test_r10_neo4j_projection import apply
from test_r10_neo4j_projection import neo4j_store as neo4j_store
from test_r10_projection_pg import PUBLIC, capture, manifest_for, published_fixture
from test_r10_projection_pg import projection_engine as projection_engine

from ai_intel.knowledge.graph_projection import ProjectionNotReady, read_projection_candidates

pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]


@pytest.fixture(autouse=True)
def register_owned_dsn(register_sensitive_failure_value, isolated_test_database_url):
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))


@pytest.mark.parametrize("ready", [True, False])
def test_stable_empty_result_requires_ready_and_preserves_io_boundary(
    projection_engine, neo4j_store, tmp_path, ready
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = "r10_fix2_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    if ready:
        apply(projection_engine, neo4j_store, value)
    calls = []

    class CountingStore:
        def find_candidates(self, *arguments):
            calls.append(arguments)
            return neo4j_store.find_candidates(*arguments)

    with Session(projection_engine) as session:
        if ready:
            found = read_projection_candidates(
                session, PUBLIC, namespace, generation, (uuid4(),), CountingStore()
            )
            assert not found.candidates and not found.truncated and found.requires_pg_revalidation
            assert len(calls) == 1
        else:
            with pytest.raises(ProjectionNotReady):
                read_projection_candidates(
                    session, PUBLIC, namespace, generation, (uuid4(),), CountingStore()
                )
            assert not calls


@pytest.mark.parametrize("invalid", ["empty_seeds", "boolean_hops", "unknown_relation"])
def test_invalid_candidate_request_fails_before_external_io(
    projection_engine, neo4j_store, tmp_path, invalid
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = "r10_fix2_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, value)

    class NeverCalled:
        def find_candidates(self, *_arguments):
            pytest.fail("invalid input reached Neo4j")

    seeds = () if invalid == "empty_seeds" else (event_id,)
    hops = True if invalid == "boolean_hops" else 2
    relations = ("invented",) if invalid == "unknown_relation" else ("same_event",)
    with Session(projection_engine) as session, pytest.raises(ValueError):
        read_projection_candidates(
            session,
            PUBLIC,
            namespace,
            generation,
            seeds,
            NeverCalled(),
            max_hops=hops,
            relation_types=relations,
        )
