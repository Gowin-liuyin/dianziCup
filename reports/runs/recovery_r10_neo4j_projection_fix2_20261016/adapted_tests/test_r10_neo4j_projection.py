"""Real owned Neo4j + PG on synthetic published fixtures; no third-party/live claims."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import NOW
from test_r10_evidence_graph_pg import ATLAS, VERSION, paper_value, publish_event, publish_fact
from test_r10_projection_pg import (
    PUBLIC,
    capture,
    header,
    manifest_for,
    published_fixture,
)
from test_r10_projection_pg import (
    projection_engine as projection_engine,
)

from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.neo4j_projection import Neo4jProjectionStore
from ai_intel.knowledge.evidence_graph import RELATION_TYPES
from ai_intel.knowledge.graph_projection import (
    ProjectionDigestConflict,
    ProjectionNotReady,
    apply_projection_batch,
    encode_projection_batch,
    read_projection_candidates,
)
from ai_intel.knowledge.models import job_runs
from ai_intel.knowledge.persistence_models import claims, events
from ai_intel.knowledge.revisions import bump_scope_epoch

pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]
RESOURCE_PATH = Path("D:/dianzi-private/r10-neo4j-test-20261016.dpapi")
PWSH = Path(
    "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
)


@pytest.fixture
def neo4j_store(register_sensitive_failure_value):
    if not RESOURCE_PATH.is_file():
        raise pytest.UsageError("blocked: owned Neo4j resource reference unavailable")
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise pytest.UsageError("blocked: root-owned Neo4j driver dependency unavailable") from None
    result = subprocess.run(
        [
            str(PWSH),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; $value=(Get-Content -LiteralPath "
            "'D:/dianzi-private/r10-neo4j-test-20261016.dpapi' -Raw).Trim() "
            "| ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText "
            "| ConvertFrom-Json; [Console]::Write(($value | Select-Object "
            "NEO4J_TEST_BOLT_URL,NEO4J_TEST_USERNAME,NEO4J_TEST_PASSWORD,resource_id,deadline "
            "| ConvertTo-Json -Compress))",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    if result.returncode:
        raise pytest.UsageError("blocked: private Neo4j resource decryption failed")
    resource = json.loads(result.stdout)
    password = SecretStr(resource["NEO4J_TEST_PASSWORD"])
    register_sensitive_failure_value(password)
    if (
        resource["NEO4J_TEST_BOLT_URL"] != "bolt://127.0.0.1:27687"
        or resource["resource_id"] != "dianzi-r10-neo4j-test-20261016"
        or datetime.fromisoformat(resource["deadline"]) <= datetime.now(UTC)
    ):
        raise pytest.UsageError("blocked: Neo4j target identity mismatch")
    driver = GraphDatabase.driver(
        resource["NEO4J_TEST_BOLT_URL"],
        auth=(resource["NEO4J_TEST_USERNAME"], password.get_secret_value()),
        connection_timeout=2,
        connection_acquisition_timeout=2,
        max_connection_pool_size=4,
        max_transaction_retry_time=0,
        telemetry_disabled=True,
    )
    try:
        driver.verify_connectivity()
        store = Neo4jProjectionStore(driver)
        store.initialize_schema()
        yield store
    finally:
        driver.close()


def apply(engine, store, batch, scope=PUBLIC):
    with Session(engine) as session, session.begin():
        return apply_projection_batch(session, scope, batch.batch_id, store, NOW)


def candidates(engine, store, batch, scope=PUBLIC):
    with Session(engine) as session:
        return read_projection_candidates(
            session, scope, batch.namespace, batch.generation_id, (batch.event_id,), store
        )


def test_real_six_relations_are_projected_and_duplicate_receipts_do_not_add_edges(
    projection_engine, neo4j_store, tmp_path
):
    event_id = uuid4()
    sources = [
        publish_fact(projection_engine, tmp_path / "version", event_id, VERSION),
        publish_fact(projection_engine, tmp_path / "atlas", event_id, ATLAS),
        publish_fact(
            projection_engine,
            tmp_path / "analysis",
            event_id,
            paper_value(projection_engine, tmp_path / "paper"),
        ),
    ]
    publish_event(projection_engine, event_id, sources)
    generation, namespace = uuid4(), "r10_fix2_" + uuid4().hex
    manifest_for(projection_engine, generation, namespace=namespace)
    batch = capture(projection_engine, generation, event_id, namespace=namespace)
    assert {edge.relation_type for edge in batch.edges} == set(RELATION_TYPES)
    first = apply(projection_engine, neo4j_store, batch)
    second = apply(projection_engine, neo4j_store, batch)
    assert first.outcome == "applied" and second.outcome == "already_applied"
    found = candidates(projection_engine, neo4j_store, batch)
    assert {value.edge_id for value in found.candidates} == {edge.id for edge in batch.edges}
    assert found.requires_pg_revalidation and not found.truncated
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 1


def test_real_neo4j_commit_survives_pg_ack_rollback_and_replays(
    projection_engine, neo4j_store, tmp_path
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation, namespace = uuid4(), "r10_fix2_" + uuid4().hex
    manifest_for(projection_engine, generation, namespace=namespace)
    batch = capture(projection_engine, generation, event_id, namespace=namespace)
    with (
        pytest.raises(RuntimeError, match="injected"),
        Session(projection_engine) as session,
        session.begin(),
    ):
        apply_projection_batch(session, PUBLIC, batch.batch_id, neo4j_store, NOW)
        raise RuntimeError("injected PG acknowledgment rollback after real Neo4j commit")
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 0
    receipt = apply(projection_engine, neo4j_store, batch)
    assert receipt.outcome == "already_applied"
    assert len(candidates(projection_engine, neo4j_store, batch).candidates) == len(batch.edges)


def test_real_server_error_rolls_back_edges_and_leaves_pg_ack_pending(
    projection_engine, neo4j_store, tmp_path, monkeypatch
):
    from neo4j.exceptions import CypherSyntaxError

    from ai_intel.infrastructure import neo4j_projection

    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation, namespace = uuid4(), "r10_fix2_" + uuid4().hex
    manifest_for(projection_engine, generation, namespace=namespace)
    batch = capture(projection_engine, generation, event_id, namespace=namespace)
    with monkeypatch.context() as fault:
        fault.setattr(neo4j_projection, "COMMIT_SLOT", "RETURN")
        with pytest.raises(CypherSyntaxError):
            apply(projection_engine, neo4j_store, batch)
    manifest = header(projection_engine, generation, namespace=namespace)
    assert manifest.acknowledged_count == 0 and manifest.status == "pending"
    found = neo4j_store.find_candidates(
        PUBLIC, namespace, generation, (event_id,), RELATION_TYPES, 2
    )
    assert not found.candidates
    assert apply(projection_engine, neo4j_store, batch).outcome == "applied"
    assert candidates(projection_engine, neo4j_store, batch).candidates


def test_real_two_workers_and_out_of_order_write_cannot_regress_marker(
    projection_engine, neo4j_store, tmp_path
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation, namespace = uuid4(), "r10_fix2_" + uuid4().hex
    manifest_for(projection_engine, generation, namespace=namespace)
    batch = capture(projection_engine, generation, event_id, namespace=namespace)
    barrier = Barrier(2)

    def worker():
        barrier.wait(timeout=10)
        return apply(projection_engine, neo4j_store, batch)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(result.outcome for result in results) == ["already_applied", "applied"]
    newer = batch.model_copy(update={"sequence": 2, "batch_id": uuid4()})
    digest = encode_projection_batch(newer)[1]
    assert neo4j_store.apply_batch(newer, digest).outcome == "applied"
    assert neo4j_store.apply_batch(batch, encode_projection_batch(batch)[1]).outcome == "superseded"
    changed = newer.model_copy(update={"input_sha256": "c" * 64})
    with pytest.raises(ProjectionDigestConflict):
        neo4j_store.apply_batch(changed, encode_projection_batch(changed)[1])
    found = neo4j_store.find_candidates(
        PUBLIC, namespace, generation, (event_id,), RELATION_TYPES, 2
    )
    assert found.candidates and all(candidate.sequence == 2 for candidate in found.candidates)


def test_real_withdrawal_and_tombstone_generation_does_not_resurrect_history(
    projection_engine, neo4j_store, tmp_path
):
    event_id, source = published_fixture(projection_engine, tmp_path)
    namespace = "r10_fix2_" + uuid4().hex
    old_generation = uuid4()
    manifest_for(projection_engine, old_generation, namespace=namespace)
    old = capture(projection_engine, old_generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, old)
    with projection_engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == source.record.claim_id.value)
            .values(claim_status="withdrawn")
        )
        bump_scope_epoch(connection, "public", NOW)
    generation = uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    empty = capture(projection_engine, generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, empty)
    assert not candidates(projection_engine, neo4j_store, empty).candidates
    with pytest.raises(ProjectionNotReady):
        candidates(projection_engine, neo4j_store, old)
    with projection_engine.begin() as connection:
        connection.execute(
            update(events).where(events.c.event_id == str(event_id)).values(status="merged")
        )
        bump_scope_epoch(connection, "public", NOW)
    tombstone_generation = uuid4()
    manifest_for(projection_engine, tombstone_generation, namespace=namespace)
    tombstone = capture(projection_engine, tombstone_generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, tombstone)
    assert (
        tombstone.kind == "tombstone"
        and not candidates(projection_engine, neo4j_store, tombstone).candidates
    )


def test_real_tenant_and_viewer_candidates_are_pre_filtered(
    projection_engine, neo4j_store, tmp_path
):
    owner = AccessScope.for_authenticated_user("owner", "owner", Role.ANALYST)
    visibility = VisibilityScope(visibility="tenant", tenant_id="owner")
    event_id, _source = published_fixture(projection_engine, tmp_path, visibility)
    with projection_engine.begin() as connection:
        bump_scope_epoch(connection, "public", NOW)
    namespace, generation = "r10_fix2_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, owner, namespace)
    batch = capture(projection_engine, generation, event_id, owner, namespace)
    apply(projection_engine, neo4j_store, batch, owner)
    assert candidates(projection_engine, neo4j_store, batch, owner).candidates
    for denied in (
        PUBLIC,
        AccessScope.for_authenticated_user("owner-viewer", "owner", Role.VIEWER),
        AccessScope.for_authenticated_user("other", "other", Role.ANALYST),
    ):
        result = neo4j_store.find_candidates(
            denied, namespace, generation, (event_id,), RELATION_TYPES, 2
        )
        assert not result.candidates


def test_real_pg_job_execution_uses_registered_narrow_handler(
    projection_engine, neo4j_store, tmp_path
):
    from ai_intel.knowledge.graph_projection import GRAPH_APPLY_JOB_TYPE, build_graph_apply_handler
    from ai_intel.workers.executor import execute_job

    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = "r10_fix2_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    batch = capture(projection_engine, generation, event_id, namespace=namespace)
    with projection_engine.connect() as connection:
        job_id = connection.scalar(
            select(job_runs.c.job_id).where(job_runs.c.job_type == GRAPH_APPLY_JOB_TYPE)
        )
    handler = build_graph_apply_handler(neo4j_store, lambda _session, _context: PUBLIC)
    outcome = execute_job(
        projection_engine,
        job_id,
        "owned-fixture-worker",
        {GRAPH_APPLY_JOB_TYPE: handler},
        clock=lambda: datetime.now(UTC),
    )
    assert outcome == "succeeded"
    assert candidates(projection_engine, neo4j_store, batch).candidates
