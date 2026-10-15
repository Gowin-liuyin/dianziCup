"""Real PG regressions for whole-roster permissions and source/publication locks."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
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

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.enums import DimensionStatus
from ai_intel.domain.values import Identifier
from ai_intel.enrichment.contracts import DimensionAttempt
from ai_intel.enrichment.inputs import EnrichmentInputError, load_event_enrichment_inputs
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.enrichment.publication import EnrichmentPublicationError, publish_enrichment_attempts
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.ingestion.source_documents import SourceResponse, persist_source_response
from ai_intel.knowledge.event_linking import EventIdentifier, EventRepository, EventSubmission
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    job_runs,
    outbox_events,
    scope_epochs,
)
from ai_intel.knowledge.persistence_models import (
    change_events,
    claim_assertions,
    claim_evidence,
    claims,
    publication_receipts,
)

pytestmark = pytest.mark.real_pg


def inputs(engine, tmp_path, *, paired=False):
    store, event_id = seeded_event(engine, tmp_path)
    with Session(engine) as session:
        original = load_event_enrichment_inputs(session, store, ADMIN, event_id, "acl-lock-fix-1")
    if paired:
        job_id = queue(engine, "vllm_vendor")
        assert run(engine, job_id, handler_for(store, "vllm_vendor")) in {"succeeded", "partial"}
        with Session(engine) as session, session.begin():
            revision_ids = tuple(session.scalars(select(document_revisions.c.revision_id)))
            EventRepository(session, ADMIN).publish_events(
                "paired-acl-lock-" + str(uuid4()),
                original.scope,
                (
                    EventSubmission(
                        event_id=Identifier(value=str(event_id)),
                        event_type="vulnerability",
                        title="Synthetic paired ACL and lock fixture",
                        scope=original.scope,
                        external_ids=tuple(
                            EventIdentifier(id_type="cve", id_value=value)
                            for value in original.context.external_cve_ids
                        ),
                        source_revision_ids=tuple(
                            Identifier(value=value) for value in revision_ids
                        ),
                    ),
                ),
                original.documents[0].observed_at,
            )
        with Session(engine) as session:
            original = load_event_enrichment_inputs(
                session, store, ADMIN, event_id, "acl-lock-fix-1"
            )
    return store, original


def counts(engine):
    with Session(engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(table))
            for table in (
                claims,
                claim_assertions,
                claim_evidence,
                evidence,
                enrichment_results,
                change_events,
                publication_receipts,
                job_runs,
                outbox_events,
                scope_epochs,
            )
        )


def revoke(engine, loaded, level, owner="fixture-secret-owner"):
    document = loaded.documents[-1]
    with engine.begin() as connection:
        if level == "source":
            connection.execute(
                text("UPDATE sources SET visibility='tenant',tenant_id=:owner WHERE source_id=:id"),
                {"owner": owner, "id": str(document.source_id)},
            )
        elif level == "document":
            connection.execute(
                update(documents)
                .where(documents.c.document_id == str(document.document_id))
                .values(visibility="tenant", tenant_id=owner)
            )
        else:
            connection.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == str(document.revision_id))
                .values(visibility="tenant", tenant_id=owner)
            )


def publish(engine, loaded, attempts, request_id=None):
    with Session(engine) as session, session.begin():
        return publish_enrichment_attempts(
            session,
            ADMIN,
            loaded,
            attempts,
            request_id=request_id or uuid4(),
            recorded_at=loaded.documents[0].observed_at,
        )


@pytest.mark.parametrize("level", ["source", "document", "revision"])
def test_entire_roster_acl_precedes_the_first_object_read(catalog_engine, tmp_path, level):
    _, loaded = inputs(catalog_engine, tmp_path, paired=True)
    revoke(catalog_engine, loaded, level)

    class ForbiddenStore:
        def read_verified(self, digest):
            pytest.fail("No bytes may be read before every input ACL has passed")

    with (
        Session(catalog_engine) as session,
        pytest.raises((CrossTenantAccessError, EnrichmentInputError)),
    ):
        load_event_enrichment_inputs(
            session, ForbiddenStore(), ADMIN, loaded.context.event_id, "acl-lock-fix-1"
        )


@pytest.mark.parametrize("level", ["source", "document", "revision"])
def test_failed_empty_candidate_revalidates_every_input_acl(catalog_engine, tmp_path, level):
    _, loaded = inputs(catalog_engine, tmp_path, paired=True)
    revoke(catalog_engine, loaded, level)
    failed = DimensionAttempt(
        dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout"
    )
    before = counts(catalog_engine)
    with pytest.raises((CrossTenantAccessError, EnrichmentInputError, EnrichmentPublicationError)):
        publish(catalog_engine, loaded, (failed,))
    assert counts(catalog_engine) == before


@pytest.mark.parametrize("level", ["source", "document", "revision"])
def test_historical_receipt_still_requires_current_parent_permissions(
    catalog_engine, tmp_path, level
):
    _, loaded = inputs(catalog_engine, tmp_path)
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    request_id = uuid4()
    publish(catalog_engine, loaded, attempts, request_id)
    revoke(catalog_engine, loaded, level)
    before = counts(catalog_engine)
    with pytest.raises((CrossTenantAccessError, EnrichmentInputError, EnrichmentPublicationError)):
        publish(catalog_engine, loaded, attempts, request_id)
    assert counts(catalog_engine) == before


def test_visible_tenant_input_cannot_be_derived_into_a_public_event(catalog_engine, tmp_path):
    store, loaded = inputs(catalog_engine, tmp_path)
    revoke(catalog_engine, loaded, "source", "fixture-same-owner")
    owner = AccessScope.for_authenticated_user("owner", "fixture-same-owner", Role.TENANT_ADMIN)
    with (
        Session(catalog_engine) as session,
        pytest.raises((CrossTenantAccessError, EnrichmentInputError)),
    ):
        load_event_enrichment_inputs(
            session, store, owner, loaded.context.event_id, "acl-lock-fix-1"
        )


def test_forged_source_identity_does_not_choose_the_publisher_lock(catalog_engine, tmp_path):
    _, loaded = inputs(catalog_engine, tmp_path)
    actual_source = "source:" + str(loaded.documents[0].source_id)
    forged = replace(
        loaded,
        documents=(loaded.documents[0].model_copy(update={"source_id": uuid4()}),),
    )
    failed = DimensionAttempt(
        dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout"
    )
    acquired = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock" in statement:
            acquired.extend(
                key
                for key in parameters.values()
                if isinstance(key, str) and key.startswith("source:")
            )

    before = counts(catalog_engine)
    event.listen(catalog_engine, "after_cursor_execute", observe)
    try:
        with pytest.raises(EnrichmentPublicationError, match="revision_changed"):
            publish(catalog_engine, forged, (failed,))
    finally:
        event.remove(catalog_engine, "after_cursor_execute", observe)
    assert acquired == [actual_source]
    assert counts(catalog_engine) == before


@pytest.mark.parametrize("first_actor", ["writer", "publisher"])
@pytest.mark.parametrize("paired", [False, True])
def test_real_source_writer_and_publisher_complete_in_both_start_orders(
    catalog_engine, tmp_path, first_actor, paired
):
    store, loaded = inputs(catalog_engine, tmp_path, paired=paired)
    if paired:
        loaded = replace(loaded, documents=tuple(reversed(loaded.documents)))
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    request_id = uuid4()
    payload = json.loads(source_response("nvd_ollama")[0])
    payload["vulnerabilities"][0]["cve"]["descriptions"][0]["value"] += " Synthetic lock revision."
    response = SourceResponse(
        "nvd_ollama",
        json.dumps(payload).encode(),
        "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=20&startIndex=0",
        loaded.documents[0].observed_at + timedelta(seconds=1),
    )
    contended_source = "source:" + next(
        str(document.source_id)
        for document in loaded.documents
        if any(block.json_pointer == "/cve/id" for block in document.blocks)
    )
    first_has_lock = Event()
    second_attempted_lock = Event()
    release_first = Event()
    backend_pids = {}
    locks = {"writer": [], "publisher": []}

    def before_execute(connection, cursor, statement, parameters, context, executemany):
        actor = connection.info.get("acl_lock_actor")
        if actor is not None and "pg_advisory_xact_lock" in statement:
            key = next(iter(parameters.values()))
            if isinstance(key, str) and key.startswith("source:"):
                locks[actor].append(key)
                if actor != first_actor:
                    second_attempted_lock.set()

    def after_execute(connection, cursor, statement, parameters, context, executemany):
        actor = connection.info.get("acl_lock_actor")
        if (
            actor == first_actor
            and "pg_advisory_xact_lock" in statement
            and contended_source in parameters.values()
            and not first_has_lock.is_set()
        ):
            first_has_lock.set()
            assert release_first.wait(4), "first lock was never released by the observer"

    def invoke(actor):
        try:
            with Session(catalog_engine) as session, session.begin():
                session.connection().info["acl_lock_actor"] = actor
                backend_pids[actor] = session.scalar(select(func.pg_backend_pid()))
                if actor == "writer":
                    persist_source_response(
                        session, store, ADMIN, response, ingested_at=response.observed_at
                    )
                else:
                    publish_enrichment_attempts(
                        session,
                        ADMIN,
                        loaded,
                        attempts,
                        request_id=request_id,
                        recorded_at=response.observed_at,
                    )
            return "completed"
        except EnrichmentPublicationError as failure:
            assert str(failure) in {
                "enrichment_event_inputs_changed",
                "enrichment_source_revision_changed",
            }
            return "stale_snapshot_rejected"
        finally:
            with catalog_engine.connect() as connection:
                connection.info.pop("acl_lock_actor", None)

    event.listen(catalog_engine, "before_cursor_execute", before_execute)
    event.listen(catalog_engine, "after_cursor_execute", after_execute)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(invoke, first_actor)
            assert first_has_lock.wait(3), "first actor never acquired its advisory lock"
            second_actor = "publisher" if first_actor == "writer" else "writer"
            second = pool.submit(invoke, second_actor)
            try:
                assert second_attempted_lock.wait(3), "second actor never attempted its source lock"
                deadline = monotonic() + 2
                with catalog_engine.connect() as observer:
                    while not observer.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid=:pid "
                            "AND locktype='advisory' AND NOT granted)"
                        ),
                        {"pid": backend_pids[second_actor]},
                    ):
                        assert monotonic() < deadline, "second actor was not observed waiting in PG"
                        sleep(0.01)
            finally:
                release_first.set()
            outcomes = [first.result(timeout=12), second.result(timeout=12)]
    finally:
        event.remove(catalog_engine, "before_cursor_execute", before_execute)
        event.remove(catalog_engine, "after_cursor_execute", after_execute)
    assert outcomes == (
        ["completed", "stale_snapshot_rejected"]
        if first_actor == "writer"
        else ["completed", "completed"]
    )
    expected_source_locks = sorted(
        {"source:" + str(document.source_id) for document in loaded.documents}
    )
    assert locks["publisher"] == expected_source_locks
    with Session(catalog_engine) as session:
        results = tuple(
            session.execute(
                select(enrichment_results).where(
                    enrichment_results.c.publication_key.startswith(f"r07:{request_id}:")
                )
            ).mappings()
        )
        assert len(results) == (0 if first_actor == "writer" else len(attempts))
    if first_actor == "publisher":
        before = counts(catalog_engine)
        replay = publish(catalog_engine, loaded, attempts, request_id)
        assert all(result.reused for result in replay)
        assert counts(catalog_engine) == before
