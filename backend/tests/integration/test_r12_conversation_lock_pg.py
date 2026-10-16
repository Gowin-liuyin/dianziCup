"""Actual PG waiting and hidden-scope controls; no manual epoch mutation in writer cases."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID

import pytest
from sqlalchemy import select, text
from tests.integration.test_r12_evidence_bundle_pg import bundle, legal_publication, public_epochs
from tests.r12_conversation_fixtures import context_identity as context_identity
from tests.r12_conversation_fixtures import conversation_database as conversation_database
from tests.r12_hybrid_fixtures import record_change, seed_fact

from ai_intel.answering import evidence_bundle
from ai_intel.knowledge.models import scope_epochs

pytestmark = pytest.mark.real_pg


def wait_for_lock(engine, pid):
    end = time.monotonic() + 2
    while time.monotonic() < end:
        with engine.connect() as connection:
            waiting = connection.scalar(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}
            )
        if waiting == "Lock":
            return
        time.sleep(0.02)
    pytest.fail("owned writer did not enter the expected real PG Lock wait")


def test_pg_final_epoch_lock_holds_legal_withdrawal_until_bundle_construction(
    context_identity, monkeypatch
):
    engine = context_identity[0]
    fact = seed_fact(engine, "Synthetic source contains withdrawal context.")
    public_epochs(engine)
    constructing, release, writer_connected = Event(), Event(), Event()
    original = evidence_bundle.QuestionEvidenceBundle
    writer_pids = []

    def construct_while_locked(*args, **kwargs):
        constructing.set()
        assert release.wait(timeout=4)
        return original(*args, **kwargs)

    def connected(session):
        writer_pids.append(session.scalar(text("SELECT pg_backend_pid()")))
        writer_connected.set()

    monkeypatch.setattr(evidence_bundle, "QuestionEvidenceBundle", construct_while_locked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(bundle, context_identity, events=(UUID(fact["event_id"]),))
        assert constructing.wait(timeout=3)
        writing = pool.submit(
            legal_publication,
            engine,
            fact,
            predicate="source_status",
            value="withdrawn",
            on_connection=connected,
        )
        try:
            assert writer_connected.wait(timeout=2)
            wait_for_lock(engine, writer_pids[0])
            assert not writing.done()
        finally:
            release.set()
        before = reading.result(timeout=3)
        receipt = writing.result(timeout=3)
    assert before.citations and not before.partial
    assert dict(before.scope_watch.scope_epochs)["public"] == 1
    assert receipt.epoch == 2
    monkeypatch.setattr(evidence_bundle, "QuestionEvidenceBundle", original)
    after = bundle(context_identity, events=(UUID(fact["event_id"]),))
    assert after.citations == () and after.partial
    assert "source_withdrawn" in {gap.reason_code for gap in after.gaps}


def test_pg_hidden_tenant_epoch_lock_does_not_block_owned_bundle(context_identity):
    engine = context_identity[0]
    fact = seed_fact(engine, "Synthetic public fact.")
    public_epochs(engine)
    record_change(engine, "tenant:tenant-b")
    with engine.begin() as connection:
        connection.execute(
            select(scope_epochs)
            .where(scope_epochs.c.scope_key == "tenant:tenant-b")
            .with_for_update()
        ).all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(bundle, context_identity, events=(UUID(fact["event_id"]),)).result(
                timeout=1.5
            )
    assert result.citations
    assert "tenant:tenant-b" not in dict(result.scope_watch.scope_epochs)


def test_pg_enrichment_parent_then_event_order_does_not_deadlock_bundle(
    context_identity, tmp_path, monkeypatch
):
    from sqlalchemy.orm import Session
    from test_r07_enrichment_inputs_pg import ADMIN, seeded_event

    from ai_intel.domain.enums import DimensionStatus
    from ai_intel.enrichment import publication
    from ai_intel.enrichment.contracts import DimensionAttempt
    from ai_intel.enrichment.inputs import load_event_enrichment_inputs
    from ai_intel.enrichment.signals import enrich_structured_fields

    engine = context_identity[0]
    store, event_id = seeded_event(engine, tmp_path)
    with Session(engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, event_id, "r12-lock-order")
    attempts = enrich_structured_fields(loaded.context, loaded.documents)

    def publish(selected_attempts=attempts):
        from uuid import uuid4

        with Session(engine) as session, session.begin():
            return publication.publish_enrichment_attempts(
                session,
                ADMIN,
                loaded,
                selected_attempts,
                request_id=uuid4(),
                recorded_at=loaded.documents[0].observed_at,
            )

    assert publish()
    parents_locked, reader_acquiring = Event(), Event()
    lock_parents = publication._lock_input_parents
    lock_candidates = evidence_bundle.lock_candidate_authorities

    def pause_after_parent_locks(session, inputs):
        lock_parents(session, inputs)
        parents_locked.set()
        assert reader_acquiring.wait(timeout=4)

    def announce_reader_locks(session, scope, candidates):
        reader_acquiring.set()
        lock_candidates(session, scope, candidates)

    monkeypatch.setattr(publication, "_lock_input_parents", pause_after_parent_locks)
    monkeypatch.setattr(evidence_bundle, "lock_candidate_authorities", announce_reader_locks)
    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(
            publish, (DimensionAttempt(dimension="literature", status=DimensionStatus.PENDING),)
        )
        assert parents_locked.wait(timeout=3)
        reading = pool.submit(bundle, context_identity, events=(event_id,))
        writer_result = writing.result(timeout=6)
        result = reading.result(timeout=6)
        assert writer_result
    assert result.partial
    assert {"scope_changed_during_bundle", "bundle_inputs_changed"}.intersection(
        gap.reason_code for gap in result.gaps
    )
