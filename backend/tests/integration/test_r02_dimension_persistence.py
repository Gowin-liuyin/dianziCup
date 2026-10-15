"""真实PG维度发布、历史、回滚、权限和重复并发；合成资料不计live。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import prepared_submission, publish_submission, publisher_scope

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.records import ScoreValue
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.persistence import (
    DimensionPublicationError,
    DimensionRepository,
    DimensionSubmission,
)
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.event_linking import EventRepository, EventSubmission
from ai_intel.knowledge.persistence_models import events

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 3, 30, tzinfo=UTC)


def prepared_result(engine: Engine, tmp_path: Path, scope: VisibilityScope | None = None):
    claim = prepared_submission(
        engine,
        tmp_path,
        scope=scope,
        predicate="cvss_score",
        value=ScoreValue(score=7.5, authority="test-vendor"),
        scoring_authority="test-vendor",
    )
    publish_submission(engine, claim)
    event_id = uuid4()
    with Session(engine) as session, session.begin():
        EventRepository(session, publisher_scope(claim.record.scope)).publish_events(
            str(uuid4()),
            claim.record.scope,
            (
                EventSubmission(
                    event_id=Identifier(value=str(event_id)),
                    event_type="vulnerability",
                    title="test dimension event",
                    scope=claim.record.scope,
                    source_revision_ids=(claim.revision_id,),
                ),
            ),
            NOW,
        )
    submission = DimensionSubmission(
        event_id=event_id,
        dimension="cvss",
        status="available",
        expected_event_version=1,
        input_fingerprint="a" * 64,
        claim_ids=(UUID(claim.record.claim_id.value),),
        reference_ids=(UUID(claim.evidence_links[0].evidence_id.value),),
        source_ids=(UUID(claim.source_id.value),),
        observed_at=NOW,
        freshness="current",
    )
    return submission, publisher_scope(claim.record.scope)


def test_failure_then_success_same_input_retains_both_attempts(migrated_engine, tmp_path):
    success, scope = prepared_result(migrated_engine, tmp_path)
    failed = DimensionSubmission(
        event_id=success.event_id,
        dimension="cvss",
        status="failed",
        error_code="upstream_timeout",
        expected_event_version=1,
        input_fingerprint="a" * 64,
    )
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        first = repository.publish("attempt-1", failed, NOW)
        second = repository.publish("attempt-2", success, NOW + timedelta(seconds=1))
    migrated_engine.dispose()
    with Session(migrated_engine) as session:
        history = DimensionRepository(session, scope).read_results(
            str(success.event_id), include_history=True
        )
        assert [(row["status"], row["is_current"]) for row in history] == [
            ("failed", False),
            ("available", True),
        ]
        assert history[1]["input_fingerprint"] == history[0]["input_fingerprint"]
        assert first.result_id != second.result_id
        assert history[1]["observed_at"] == NOW


def test_same_publication_reuses_result_and_changed_payload_conflicts(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        first = repository.publish("same-attempt", submission, NOW)
        again = repository.publish("same-attempt", submission, NOW + timedelta(seconds=1))
        assert again.reused and first.result_id == again.result_id
        with pytest.raises(IdempotencyConflictError):
            repository.publish(
                "same-attempt", submission.model_copy(update={"source_version": "changed"}), NOW
            )


def test_outer_rollback_keeps_result_and_outbox_unpublished(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with (
        pytest.raises(RuntimeError, match="abort after save"),
        Session(migrated_engine) as session,
        session.begin(),
    ):
        DimensionRepository(session, scope).publish("rolled-back", submission, NOW)
        raise RuntimeError("abort after save")
    with Session(migrated_engine) as session:
        assert not DimensionRepository(session, scope).read_results(str(submission.event_id))
        saved = DimensionRepository(session, scope).publish("rolled-back", submission, NOW)
        assert not saved.reused
        session.rollback()


def test_concurrent_same_attempt_produces_one_result(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    barrier = Barrier(2)

    def publish():
        barrier.wait(timeout=10)
        with Session(migrated_engine) as session, session.begin():
            return DimensionRepository(session, scope).publish("concurrent", submission, NOW)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: publish(), range(2)))
    assert results[0].result_id == results[1].result_id
    assert sorted(result.reused for result in results) == [False, True]


def test_late_event_version_cannot_replace_current_result(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        original = repository.publish("current", submission, NOW)
        session.execute(
            update(events)
            .where(events.c.event_id == str(submission.event_id))
            .values(business_version=2)
        )
        with pytest.raises(DimensionPublicationError, match="event version changed"):
            repository.publish("late", submission, NOW + timedelta(seconds=1))
        assert (
            repository.read_results(str(submission.event_id))[0]["result_id"] == original.result_id
        )


def test_tenant_dimensions_and_history_are_invisible_to_other_tenant_and_viewer(
    migrated_engine, tmp_path
):
    submission, scope = prepared_result(
        migrated_engine, tmp_path, VisibilityScope(visibility="tenant", tenant_id="test-tenant-a")
    )
    with Session(migrated_engine) as session, session.begin():
        DimensionRepository(session, scope).publish("private", submission, NOW)
    for reader in (
        AccessScope.for_authenticated_user("other", "test-tenant-b", Role.TENANT_ADMIN),
        AccessScope.for_authenticated_user("viewer", "test-tenant-a", Role.VIEWER),
    ):
        with Session(migrated_engine) as session, pytest.raises(CrossTenantAccessError):
            DimensionRepository(session, reader).read_results(
                str(submission.event_id), include_history=True
            )


def test_unrelated_event_evidence_rejected_before_any_result(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    other, _ = prepared_result(migrated_engine, tmp_path)
    changed = submission.model_copy(update={"reference_ids": other.reference_ids})
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        with pytest.raises(DimensionPublicationError, match="not active on this event"):
            repository.publish("unrelated", changed, NOW)
        assert not repository.read_results(str(submission.event_id))


def test_failed_dimension_does_not_remove_other_dimension_or_prior_claims(
    migrated_engine, tmp_path
):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        repository.publish("cvss", submission, NOW)
        repository.publish(
            "epss-failure",
            DimensionSubmission(
                event_id=submission.event_id,
                dimension="epss",
                status="failed",
                error_code="timeout",
                expected_event_version=1,
                input_fingerprint="b" * 64,
            ),
            NOW + timedelta(seconds=1),
        )
        rows = repository.read_results(str(submission.event_id))
        assert [(row["dimension"], row["status"]) for row in rows] == [
            ("cvss", "available"),
            ("epss", "failed"),
        ]
        assert rows[0]["claim_ids"] == list(map(str, submission.claim_ids))


def test_outbox_sql_failure_rolls_back_attempt_and_can_retry_key(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        original = repository.publish("original", submission, NOW)

        def fail_outbox(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT INTO OUTBOX_EVENTS"):
                connection.exec_driver_sql("SELECT 1/0")

        event.listen(migrated_engine, "before_cursor_execute", fail_outbox)
        try:
            with pytest.raises(DBAPIError):
                repository.publish("retryable", submission, NOW + timedelta(seconds=1))
        finally:
            event.remove(migrated_engine, "before_cursor_execute", fail_outbox)
        rows = repository.read_results(str(submission.event_id), include_history=True)
        assert [row["result_id"] for row in rows] == [original.result_id]
        assert rows[0]["is_current"]
        replay = repository.publish("retryable", submission, NOW + timedelta(seconds=1))
        assert not replay.reused and replay.result_id != original.result_id
