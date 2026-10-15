"""Independent synthetic boundary probes on the exclusively authorized PostgreSQL database."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4
import json
import os
import subprocess
import sys

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_r02_dimension_persistence import NOW, prepared_result
from test_r02_knowledge_revisions import prepared_submission, publish_submission, publisher_scope

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.records import ScoreValue
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.persistence import DimensionPublicationError, DimensionRepository
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.knowledge.event_linking import EventRepository, EventSubmission
from ai_intel.knowledge.models import evidence, job_runs, outbox_events, scope_epochs
from ai_intel.knowledge.persistence_models import change_events, claim_evidence, claims, publication_receipts

pytestmark = pytest.mark.real_pg


def result_count(session, event_id):
    return session.scalar(select(func.count()).select_from(enrichment_results).where(
        enrichment_results.c.event_id == str(event_id)))


def test_two_connections_create_exactly_one_result_receipt_change_job_and_outbox(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    barrier = Barrier(2)
    with Session(migrated_engine) as session:
        before_epoch = session.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public"))

    def publish(_):
        barrier.wait(timeout=10)
        with Session(migrated_engine) as session, session.begin():
            return DimensionRepository(session, scope).publish("independent-concurrent", submission, NOW)

    with ThreadPoolExecutor(max_workers=2) as executor:
        saved = list(executor.map(publish, range(2)))
    assert sorted(item.reused for item in saved) == [False, True]
    assert saved[0].result_id == saved[1].result_id
    receipt = saved[0].publication
    with Session(migrated_engine) as session:
        assert result_count(session, submission.event_id) == 1
        assert session.scalar(select(func.count()).select_from(publication_receipts).where(
            publication_receipts.c.publication_key == receipt.publication_key)) == 1
        assert session.scalar(select(func.count()).select_from(job_runs).where(job_runs.c.job_id == receipt.job_id)) == 1
        assert session.scalar(select(func.count()).select_from(outbox_events).where(outbox_events.c.job_id == receipt.job_id)) == 1
        assert session.scalar(select(func.count()).select_from(change_events).where(change_events.c.change_id == receipt.change_id)) == 1
        assert session.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public")) == before_epoch + 1


def test_outbox_sql_failure_restores_old_current_and_leaves_no_receipt_epoch_or_claim_change(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        prior = repository.publish("independent-prior", submission, NOW)
        before_epoch = session.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public"))
        before_claim = session.execute(select(claims).where(claims.c.claim_id == str(submission.claim_ids[0]))).mappings().one()
        before_jobs = session.scalar(select(func.count()).select_from(job_runs))
        before_outbox = session.scalar(select(func.count()).select_from(outbox_events))
        before_changes = session.scalar(select(func.count()).select_from(change_events))

        def fail_outbox(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT INTO OUTBOX_EVENTS"):
                connection.exec_driver_sql("SELECT 1/0")

        event.listen(migrated_engine, "before_cursor_execute", fail_outbox)
        try:
            with pytest.raises(DBAPIError):
                repository.publish("independent-retry", submission, NOW + timedelta(seconds=1))
        finally:
            event.remove(migrated_engine, "before_cursor_execute", fail_outbox)
        assert result_count(session, submission.event_id) == 1
        assert repository.read_results(str(submission.event_id))[0]["result_id"] == prior.result_id
        assert session.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public")) == before_epoch
        assert session.scalar(select(func.count()).select_from(job_runs)) == before_jobs
        assert session.scalar(select(func.count()).select_from(outbox_events)) == before_outbox
        assert session.scalar(select(func.count()).select_from(change_events)) == before_changes
        after_claim = session.execute(select(claims).where(claims.c.claim_id == str(submission.claim_ids[0]))).mappings().one()
        assert dict(before_claim) == dict(after_claim)
        assert not repository.publish("independent-retry", submission, NOW + timedelta(seconds=1)).reused


@pytest.mark.parametrize("claim_change", [
    {"claim_origin": "model_hypothesis", "claim_status": "unverified"},
    {"provenance_status": "legacy_unverified"},
    {"is_current": False},
    {"claim_status": "withdrawn"},
])
def test_hypothesis_legacy_historical_and_withdrawn_claim_cannot_be_available(migrated_engine, tmp_path, claim_change):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        session.execute(update(claims).where(claims.c.claim_id == str(submission.claim_ids[0])).values(**claim_change))
        with pytest.raises(DimensionPublicationError, match="current supported source claim"):
            DimensionRepository(session, scope).publish("independent-invalid-claim", submission, NOW)
        assert result_count(session, submission.event_id) == 0


@pytest.mark.parametrize("reference_change", [
    {"verified_at": None}, {"supports_claim": False},
])
def test_unverified_or_non_supporting_reference_is_rejected(migrated_engine, tmp_path, reference_change):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        session.execute(update(evidence).where(evidence.c.evidence_id == str(submission.reference_ids[0])).values(**reference_change))
        with pytest.raises(DimensionPublicationError, match="not supported"):
            DimensionRepository(session, scope).publish("independent-invalid-reference", submission, NOW)
        assert result_count(session, submission.event_id) == 0


@pytest.mark.parametrize("support_change", [
    {"support_kind": "context"}, {"validation_status": "unverified"},
])
def test_context_or_unvalidated_claim_link_is_rejected(migrated_engine, tmp_path, support_change):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        session.execute(update(claim_evidence).where(claim_evidence.c.claim_id == str(submission.claim_ids[0])).values(**support_change))
        with pytest.raises(DimensionPublicationError, match="not supported"):
            DimensionRepository(session, scope).publish("independent-invalid-support", submission, NOW)
        assert result_count(session, submission.event_id) == 0


@pytest.mark.parametrize("field", ["reference_ids", "source_ids", "claim_ids"])
def test_private_inputs_cannot_be_promoted_into_a_public_dimension(migrated_engine, tmp_path, field):
    public, public_scope = prepared_result(migrated_engine, tmp_path)
    private, _ = prepared_result(migrated_engine, tmp_path, VisibilityScope(visibility="tenant", tenant_id="test-independent-private"))
    changed = public.model_copy(update={field: getattr(private, field)})
    with Session(migrated_engine) as session, session.begin():
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            DimensionRepository(session, public_scope).publish("independent-private-input", changed, NOW)
        assert result_count(session, public.event_id) == 0


def test_job_tenant_must_equal_event_tenant(migrated_engine, tmp_path):
    public, public_scope = prepared_result(migrated_engine, tmp_path)
    private, private_scope = prepared_result(migrated_engine, tmp_path, VisibilityScope(visibility="tenant", tenant_id="test-independent-job"))
    with Session(migrated_engine) as session, session.begin():
        private_saved = DimensionRepository(session, private_scope).publish("independent-private-job", private, NOW)
        changed = public.model_copy(update={"last_job_id": UUID(private_saved.publication.job_id)})
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            DimensionRepository(session, public_scope).publish("independent-wrong-job", changed, NOW)
        assert result_count(session, public.event_id) == 0


def test_public_viewer_cannot_write_a_dimension(migrated_engine, tmp_path):
    submission, _ = prepared_result(migrated_engine, tmp_path)
    viewer = AccessScope.for_authenticated_user("independent-viewer", None, Role.VIEWER)
    with Session(migrated_engine) as session, session.begin():
        with pytest.raises(PermissionDeniedError):
            DimensionRepository(session, viewer).publish("independent-viewer-write", submission, NOW)
        assert result_count(session, submission.event_id) == 0


def test_real_event_merge_rejects_late_source_and_target_versions(migrated_engine, tmp_path):
    source, scope = prepared_result(migrated_engine, tmp_path)
    target, _ = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        repository.publish("independent-premerge-source", source, NOW)
        repository.publish("independent-premerge-target", target, NOW)
        EventRepository(session, scope).merge_events("independent-merge-" + uuid4().hex,
                                                   str(source.event_id), str(target.event_id),
                                                   "independent synthetic merge", NOW)
        for submission in (source, target):
            with pytest.raises(DimensionPublicationError, match="event version changed"):
                repository.publish("independent-late-merge", submission, NOW)
            assert result_count(session, submission.event_id) == 1


def test_matching_tenant_expired_job_is_not_a_lease_fence_in_this_slice(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        first = repository.publish("independent-job-first", submission, NOW)
        session.execute(update(job_runs).where(job_runs.c.job_id == first.publication.job_id).values(
            status="running", lease_owner="previous-owner", lease_expires_at=NOW - timedelta(seconds=1)))
        late = submission.model_copy(update={"last_job_id": UUID(first.publication.job_id)})
        saved = repository.publish("independent-expired-job-boundary", late, NOW)
        assert not saved.reused
        assert result_count(session, submission.event_id) == 2


def test_saved_dimension_is_readable_after_a_fresh_python_process_starts(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        saved = DimensionRepository(session, scope).publish("independent-restart", submission, NOW)
    code = """import json,os,sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from ai_intel.domain.access import AccessScope,Role
from ai_intel.enrichment.persistence import DimensionRepository
e=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':5})
s=AccessScope.for_authenticated_user('independent-restarted',None,Role.SYSTEM_ADMIN)
with Session(e) as session:
 rows=DimensionRepository(session,s).read_results(sys.argv[1])
 print(json.dumps([[r['result_id'],r['status'],r['is_current']] for r in rows]))
e.dispose()"""
    child = subprocess.run([sys.executable, "-c", code, str(submission.event_id)],
                           env=os.environ.copy(), capture_output=True, text=True, timeout=15)
    assert child.returncode == 0
    assert json.loads(child.stdout) == [[saved.result_id, "available", True]]


def test_available_with_unknown_source_time_remains_unknown_in_pg(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    unknown = submission.model_copy(update={"observed_at": None, "freshness": FreshnessStatus.UNKNOWN})
    with Session(migrated_engine) as session, session.begin():
        repository = DimensionRepository(session, scope)
        repository.publish("independent-time-unknown", unknown, NOW)
        row = repository.read_results(str(submission.event_id))[0]
        assert row["status"] == "available"
        assert row["observed_at"] is None and row["source_version"] is None
        assert row["freshness"] == "unknown"


def test_all_seven_states_persist_independent_history_without_rewriting_claims(migrated_engine, tmp_path):
    submission, scope = prepared_result(migrated_engine, tmp_path)
    additional = prepared_submission(migrated_engine, tmp_path, predicate="cvss_score",
                                    value=ScoreValue(score=8.7, authority="test-vendor"),
                                    scoring_authority="test-vendor")
    publish_submission(migrated_engine, additional)
    with Session(migrated_engine) as session, session.begin():
        EventRepository(session, scope).publish_events(
            "independent-state-revisions-" + uuid4().hex, VisibilityScope(visibility="public"),
            (EventSubmission(event_id=Identifier(value=str(submission.event_id)),
                             event_type="vulnerability", title="test dimension event",
                             scope=VisibilityScope(visibility="public"),
                             source_revision_ids=(additional.revision_id,)),), NOW)
        claim_id = UUID(additional.record.claim_id.value)
        reference_id = UUID(additional.evidence_links[0].evidence_id.value)
        repository = DimensionRepository(session, scope)
        statuses = ("available", "not_found", "not_applicable", "conflict", "blocked", "failed", "pending")
        for index, status in enumerate(statuses):
            state = submission.model_dump()
            state.update(status=status, expected_event_version=2, claim_ids=(), reference_ids=(),
                         observed_at=None, freshness="unknown", error_code=None,
                         searched_at=None, source_ids=())
            if status in {"available", "conflict"}:
                state.update(claim_ids=submission.claim_ids, reference_ids=submission.reference_ids)
            if status == "conflict":
                state.update(claim_ids=(*submission.claim_ids, claim_id),
                             reference_ids=(*submission.reference_ids, reference_id))
            if status == "not_found":
                state.update(searched_at=NOW, source_ids=submission.source_ids)
            if status in {"blocked", "failed"}:
                state.update(error_code="test_failure")
            repository.publish("independent-state-" + status,
                               type(submission).model_validate(state), NOW + timedelta(seconds=index))
        history = repository.read_results(str(submission.event_id), include_history=True)
        assert tuple(row["status"] for row in history) == statuses
        assert [row["status"] for row in repository.read_results(str(submission.event_id))] == ["pending"]
        assert session.scalar(select(claims.c.is_current).where(claims.c.claim_id == str(submission.claim_ids[0])))
        assert session.scalar(select(claims.c.is_current).where(claims.c.claim_id == str(claim_id)))
