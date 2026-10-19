"""Directed synthetic recheck with full state snapshots and actual PG lock observation."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, text, update
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r06_source_worker_pg import handler_for, queue, run
from test_r07_enrichment_inputs_pg import ADMIN, seeded_event
from tests.r06_source_worker_fixtures import source_response

from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.enums import DimensionStatus
from ai_intel.domain.values import Identifier
from ai_intel.enrichment.contracts import DimensionAttempt
from ai_intel.enrichment.inputs import EnrichmentInputError, load_event_enrichment_inputs
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.enrichment.publication import EnrichmentPublicationError, publish_enrichment_attempts
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.ingestion.source_documents import SourceResponse, persist_source_response
from ai_intel.knowledge.event_linking import EventIdentifier, EventRepository, EventSubmission
from ai_intel.knowledge.models import document_revisions, documents, evidence, job_runs, outbox_events, scope_epochs
from ai_intel.knowledge.persistence_models import claim_assertions, claim_evidence, claims, change_events, publication_receipts, event_documents, events

pytest_plugins = ("tests.conftest",)
pytestmark = pytest.mark.real_pg
RAW = Path(__file__).resolve().parent
RULE = "independent-dc04-rule-label-001"


def inputs(engine, tmp_path, paired=False):
    store, event_id = seeded_event(engine, tmp_path)
    if paired:
        job = queue(engine, "vllm_vendor")
        assert run(engine, job, handler_for(store, "vllm_vendor")) in {"succeeded", "partial"}
        with Session(engine) as session, session.begin():
            original = load_event_enrichment_inputs(session, store, ADMIN, event_id, RULE)
            revisions = tuple(session.scalars(select(document_revisions.c.revision_id).where(document_revisions.c.is_current.is_(True))))
            EventRepository(session, ADMIN).publish_events("review-pair-" + uuid4().hex, original.scope,
                (EventSubmission(event_id=Identifier(value=str(event_id)), event_type="vulnerability", title="Independent synthetic paired event", scope=original.scope,
                    external_ids=tuple(EventIdentifier(id_type="cve", id_value=value) for value in original.context.external_cve_ids),
                    source_revision_ids=tuple(Identifier(value=value) for value in revisions)),), original.documents[0].observed_at)
    with Session(engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, event_id, RULE)
    return store, loaded


def snapshot(engine):
    with Session(engine) as session:
        result = {}
        for table in (claims, claim_assertions, claim_evidence, evidence, enrichment_results, change_events,
                      publication_receipts, job_runs, outbox_events, scope_epochs, documents, document_revisions, event_documents, events):
            encoded_rows = sorted(json.dumps(dict(row), sort_keys=True, default=str) for row in session.execute(select(table)).mappings())
            result[table.name] = hashlib.sha256("\n".join(encoded_rows).encode()).hexdigest()
        return result


def revoke(engine, loaded, level):
    member = loaded.documents[-1]
    with engine.begin() as connection:
        if level == "source":
            connection.execute(text("UPDATE sources SET visibility='tenant',tenant_id='independent-private-owner' WHERE source_id=:id"), {"id": str(member.source_id)})
        elif level == "document":
            connection.execute(update(documents).where(documents.c.document_id == str(member.document_id)).values(visibility="tenant", tenant_id="independent-private-owner"))
        else:
            connection.execute(update(document_revisions).where(document_revisions.c.revision_id == str(member.revision_id)).values(visibility="tenant", tenant_id="independent-private-owner"))


def publish(engine, loaded, attempts, request_id=None, scope=ADMIN):
    with Session(engine) as session, session.begin():
        return publish_enrichment_attempts(session, scope, loaded, attempts, request_id=request_id or uuid4(), recorded_at=loaded.documents[0].observed_at)


@pytest.mark.parametrize("level", ["source", "document", "revision"])
def test_second_parent_acl_is_checked_before_any_first_object_read(catalog_engine, tmp_path, level):
    _, loaded = inputs(catalog_engine, tmp_path, paired=True)
    revoke(catalog_engine, loaded, level)
    reads = []

    class AuditStore:
        def read_verified(self, digest):
            reads.append(digest)
            raise AssertionError("no object IO before whole-roster ACL")

    with Session(catalog_engine) as session, pytest.raises((CrossTenantAccessError, EnrichmentInputError)):
        load_event_enrichment_inputs(session, AuditStore(), ADMIN, loaded.context.event_id, RULE)
    assert reads == []


@pytest.mark.parametrize("level", ["source", "document", "revision"])
def test_empty_failed_dimension_rejects_every_revoked_parent_without_any_state_change(catalog_engine, tmp_path, level):
    _, loaded = inputs(catalog_engine, tmp_path, paired=True)
    revoke(catalog_engine, loaded, level)
    before = snapshot(catalog_engine)
    with pytest.raises((CrossTenantAccessError, EnrichmentInputError, EnrichmentPublicationError)):
        publish(catalog_engine, loaded, (DimensionAttempt(dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout"),))
    assert snapshot(catalog_engine) == before


@pytest.mark.parametrize("level", ["source", "document", "revision"])
def test_historical_replay_rechecks_parent_acl_and_leaves_full_state_unchanged(catalog_engine, tmp_path, level):
    _, loaded = inputs(catalog_engine, tmp_path)
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    request_id = uuid4()
    publish(catalog_engine, loaded, attempts, request_id)
    revoke(catalog_engine, loaded, level)
    before = snapshot(catalog_engine)
    with pytest.raises((CrossTenantAccessError, EnrichmentInputError, EnrichmentPublicationError)):
        publish(catalog_engine, loaded, attempts, request_id)
    assert snapshot(catalog_engine) == before


@pytest.mark.parametrize("forgery", ["missing", "duplicated"])
def test_full_two_source_roster_cannot_be_forged_even_for_failed_attempt(catalog_engine, tmp_path, forgery):
    _, loaded = inputs(catalog_engine, tmp_path, paired=True)
    forged = replace(loaded, documents=loaded.documents[:1] if forgery == "missing" else loaded.documents * 2)
    before = snapshot(catalog_engine)
    with pytest.raises(EnrichmentPublicationError, match="roster_changed"):
        publish(catalog_engine, forged, (DimensionAttempt(dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout"),))
    assert snapshot(catalog_engine) == before


def test_matching_tenant_parents_remain_usable_for_the_authenticated_owner(catalog_engine, tmp_path):
    store, loaded = inputs(catalog_engine, tmp_path)
    with catalog_engine.begin() as connection:
        connection.execute(text("UPDATE sources SET visibility='tenant',tenant_id='independent-owner'"))
        for table in (documents, document_revisions, events):
            connection.execute(update(table).values(visibility="tenant", tenant_id="independent-owner"))
    owner = AccessScope.for_authenticated_user("review-owner", "independent-owner", Role.TENANT_ADMIN)
    with Session(catalog_engine) as session:
        owned = load_event_enrichment_inputs(session, store, owner, loaded.context.event_id, RULE)
    results = publish(catalog_engine, owned, enrich_structured_fields(owned.context, owned.documents), scope=owner)
    assert results[0].claim_ids


def test_readable_provenance_survives_replay_and_rule_identity_cannot_change(catalog_engine, tmp_path):
    _, loaded = inputs(catalog_engine, tmp_path, paired=True)
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    request_id = uuid4()
    first = publish(catalog_engine, loaded, attempts, request_id)
    before = snapshot(catalog_engine)
    second = publish(catalog_engine, loaded, attempts, request_id)
    assert [(item.result_id, item.claim_ids) for item in first] == [(item.result_id, item.claim_ids) for item in second]
    assert snapshot(catalog_engine) == before
    with Session(catalog_engine) as session:
        row = session.execute(select(change_events.c.payload).join(publication_receipts, publication_receipts.c.change_id == change_events.c.change_id).where(publication_receipts.c.publication_key == "enrichment:" + str(request_id))).scalar_one()
    assert row["schema_version"] == 2
    assert row["context"]["rule_version"] == RULE
    assert row["context"]["event_id"] == str(loaded.context.event_id)
    assert set(row["context"]["revision_ids"]) == {str(document.revision_id) for document in loaded.documents}
    assert row["context"]["expected_event_version"] == loaded.context.expected_event_version
    assert row["context"]["external_cve_ids"] == list(loaded.context.external_cve_ids)
    forged = replace(loaded, context=loaded.context.model_copy(update={"rule_version": "independent-other-rule"}))
    with pytest.raises(IdempotencyConflictError):
        publish(catalog_engine, forged, attempts, request_id)
    assert snapshot(catalog_engine) == before


@pytest.mark.parametrize("leader", ["writer", "publisher"])
@pytest.mark.parametrize("paired", [False, True])
def test_actual_writer_document_phase_and_pg_source_wait_prevent_old_cycle(catalog_engine, tmp_path, leader, paired):
    store, loaded = inputs(catalog_engine, tmp_path, paired=paired)
    if paired:
        loaded = replace(loaded, documents=tuple(reversed(loaded.documents)))
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    request_id = uuid4()
    payload = json.loads(source_response("nvd_ollama")[0])
    payload["vulnerabilities"][0]["cve"]["descriptions"][0]["value"] += " Independent recheck revision."
    response = SourceResponse("nvd_ollama", json.dumps(payload).encode(), "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=20&startIndex=0", loaded.documents[0].observed_at + timedelta(seconds=1))
    target_source = "source:" + str(next(document.source_id for document in loaded.documents if any(block.json_pointer == "/cve/id" for block in document.blocks)))
    first_doc_held, follower_attempted, release = Event(), Event(), Event()
    pids, phases, source_lock_order = {}, [], {"writer": [], "publisher": []}

    def before_execute(connection, cursor, statement, parameters, context, executemany):
        actor = connection.info.get("independent_actor")
        if actor in source_lock_order and "pg_advisory_xact_lock" in statement:
            key = next(iter(parameters.values()))
            if key == target_source and actor != leader:
                follower_attempted.set()

    def after_execute(connection, cursor, statement, parameters, context, executemany):
        actor = connection.info.get("independent_actor")
        if actor not in source_lock_order:
            return
        if "pg_advisory_xact_lock" in statement:
            key = next(iter(parameters.values()))
            if isinstance(key, str) and key.startswith("source:"):
                phases.append((actor, "source"))
                source_lock_order[actor].append(key)
            elif isinstance(key, str) and key.startswith("knowledge-publication:"):
                phases.append((actor, "scope"))
        is_doc_phase = "FOR UPDATE" in statement and "documents" in statement and ((actor == "writer" and "SELECT documents." in statement) or (actor == "publisher" and "FOR UPDATE OF" in statement))
        if is_doc_phase:
            phases.append((actor, "document"))
            if actor == leader and not first_doc_held.is_set():
                first_doc_held.set()
                assert release.wait(4), "observer did not release the leader"

    def invoke(actor):
        try:
            with Session(catalog_engine) as session, session.begin():
                session.connection().info["independent_actor"] = actor
                pids[actor] = session.scalar(select(func.pg_backend_pid()))
                if actor == "writer":
                    persist_source_response(session, store, ADMIN, response, ingested_at=response.observed_at)
                else:
                    publish_enrichment_attempts(session, ADMIN, loaded, attempts, request_id=request_id, recorded_at=response.observed_at)
            return {"actor": actor, "outcome": "completed", "sqlstate": None}
        except EnrichmentPublicationError as failure:
            return {"actor": actor, "outcome": "snapshot_rejected", "reason": str(failure), "sqlstate": None}
        except Exception as failure:
            return {"actor": actor, "outcome": type(failure).__name__, "sqlstate": getattr(getattr(failure, "orig", None), "sqlstate", None)}

    event.listen(catalog_engine, "before_cursor_execute", before_execute)
    event.listen(catalog_engine, "after_cursor_execute", after_execute)
    observed = []
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(invoke, leader)
            assert first_doc_held.wait(3), "leader never reached its real document lock"
            follower = "publisher" if leader == "writer" else "writer"
            second = pool.submit(invoke, follower)
            try:
                assert follower_attempted.wait(3), "follower did not attempt the shared source lock"
                deadline = monotonic() + 1.5
                with catalog_engine.connect() as observer:
                    while True:
                        rows = observer.execute(text("SELECT pid,granted,classid::bigint AS classid,objid::bigint AS objid,objsubid FROM pg_locks WHERE pid=:pid AND locktype='advisory'"), {"pid": pids[follower]}).mappings().all()
                        target_hash = observer.scalar(select(func.hashtextextended(target_source, 0)))
                        observed = [dict(row) for row in rows]
                        waiting = [row for row in rows if not row["granted"] and row["classid"] == (target_hash >> 32) & 0xFFFFFFFF and row["objid"] == target_hash & 0xFFFFFFFF]
                        if waiting:
                            assert observer.scalar(text("SELECT :blocker=ANY(pg_blocking_pids(:waiter))"), {"blocker": pids[leader], "waiter": pids[follower]})
                            break
                        assert monotonic() < deadline, "no real PG wait on the exact source key"
                        sleep(0.01)
            finally:
                release.set()
            outcomes = [first.result(timeout=15), second.result(timeout=15)]
    finally:
        event.remove(catalog_engine, "before_cursor_execute", before_execute)
        event.remove(catalog_engine, "after_cursor_execute", after_execute)
    artifact = {"leader": leader, "paired": paired, "outcomes": outcomes, "phases": phases, "source_locks": source_lock_order, "observed_pg_locks": observed}
    (RAW / (f"actual_lock_{leader}_{paired}_v2.json")).write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    assert [row["outcome"] for row in outcomes] == (["completed", "snapshot_rejected"] if leader == "writer" else ["completed", "completed"]), artifact
    assert source_lock_order["publisher"] == sorted({"source:" + str(document.source_id) for document in loaded.documents})
    for actor in ("writer", "publisher"):
        assert phases.index((actor, "source")) < phases.index((actor, "document")) < phases.index((actor, "scope"))
    with Session(catalog_engine) as session:
        count = session.scalar(select(func.count()).select_from(enrichment_results).where(enrichment_results.c.publication_key.startswith("r07:" + str(request_id) + ":")))
        assert count == (0 if leader == "writer" else len(attempts))
    if leader == "publisher":
        before = snapshot(catalog_engine)
        replay = publish(catalog_engine, loaded, attempts, request_id)
        assert all(result.reused for result in replay)
        assert snapshot(catalog_engine) == before
        with pytest.raises(EnrichmentPublicationError):
            publish(catalog_engine, loaded, attempts)
        assert snapshot(catalog_engine) == before
        with Session(catalog_engine) as session:
            detail = KnowledgeReadService(session, ADMIN, "fixture").event_detail(loaded.context.event_id)
            old_results = list(session.execute(select(enrichment_results).where(enrichment_results.c.publication_key.startswith("r07:" + str(request_id) + ":"))).mappings())
            assert len(old_results) == len(attempts)
            assert all(row["event_version"] == loaded.context.expected_event_version for row in old_results)
            stale_dimensions = {row["dimension"] for row in old_results if row["is_current"]}
            assert stale_dimensions
            assert all(item.freshness == "stale" for item in detail.dimensions if item.dimension in stale_dimensions)
            cvss = next(item for item in detail.dimensions if item.dimension == "cvss")
            assert cvss.status == "available" and cvss.freshness != "stale"
