"""The real PG namespace separates API scopes while preserving legacy jobs and reservations."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session
from tests.r07_idempotency_scope_helpers import (
    NOW,
    create_actor,
    create_event,
    queue,
    queue_legacy,
    setup_scope,
)
from tests.r07_idempotency_scope_helpers import (
    scope_engine as scope_engine,
)

from ai_intel.api.auth_state import auth_sessions
from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy
from ai_intel.enrichment.job_handlers import make_enrichment_job_handlers
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import ENRICHMENT_PARENT_JOB_TYPE
from ai_intel.infrastructure.outbox import IdempotencyConflictError, enqueue_job
from ai_intel.knowledge.models import job_runs, outbox_events, users
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg


def parent_count(engine):
    with Session(engine) as session:
        return session.scalar(
            select(func.count())
            .select_from(job_runs)
            .where(job_runs.c.job_type == ENRICHMENT_PARENT_JOB_TYPE)
        )


def test_same_scope_replay_and_two_concurrent_calls_reuse_one_parent(scope_engine, tmp_path):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    with ThreadPoolExecutor(max_workers=2) as workers:
        receipts = list(
            workers.map(lambda _: queue(service, scope, session_hash, event_id, request), range(2))
        )
    assert receipts[0].parent_job_id == receipts[1].parent_job_id
    assert sorted(receipt.reused for receipt in receipts) == [False, True]
    assert queue(service, scope, session_hash, event_id, request).reused
    assert parent_count(scope_engine) == 1
    with Session(scope_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.job_id == str(receipts[0].parent_job_id))
            )
            == 1
        )


def test_two_actors_and_two_event_routes_each_have_an_independent_same_key(scope_engine, tmp_path):
    service, first_scope, first_session, first_event, request = setup_scope(scope_engine, tmp_path)
    second_scope, second_session = create_actor(scope_engine)
    second_event = create_event(scope_engine, service.store, first_scope)
    receipts = [
        queue(service, actor, session_hash, event_id, request)
        for actor, session_hash in ((first_scope, first_session), (second_scope, second_session))
        for event_id in (first_event, second_event)
    ]
    assert len({receipt.workflow_id for receipt in receipts}) == 4
    assert len({receipt.parent_job_id for receipt in receipts}) == 4
    assert parent_count(scope_engine) == 4 and all(not receipt.reused for receipt in receipts)


@pytest.mark.parametrize("change", ["body", "policy", "session"])
@pytest.mark.parametrize("legacy", [False, True])
def test_same_scope_changed_binding_still_conflicts(scope_engine, tmp_path, change, legacy):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    if legacy:
        queue_legacy(service, scope, session_hash, event_id, request)
    else:
        queue(service, scope, session_hash, event_id, request)
    if change == "body":
        request = request.model_copy(update={"dimensions": ("cvss",)})
    elif change == "policy":
        service.execution_policy = lambda: EnrichmentExecutionPolicy(data_mode="live")
    else:
        session_hash = hashlib.sha256(
            ("synthetic-new-session:" + scope.user_id).encode()
        ).hexdigest()
        with scope_engine.begin() as connection:
            connection.execute(
                insert(auth_sessions).values(
                    session_hash=session_hash,
                    user_id=scope.user_id,
                    csrf_token="synthetic-new-csrf",
                    issued_at=NOW,
                    expires_at=NOW + timedelta(hours=1),
                )
            )
    with pytest.raises(IdempotencyConflictError):
        queue(service, scope, session_hash, event_id, request)
    assert parent_count(scope_engine) == 1


def test_auth_tenant_null_and_literal_public_are_distinct_but_job_scope_stays_event_scope(
    scope_engine, tmp_path
):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    first = queue(service, scope, session_hash, event_id, request)
    with scope_engine.begin() as connection:
        connection.execute(
            update(users).where(users.c.user_id == scope.user_id).values(tenant_id="public")
        )
    tenant_scope = AccessScope.for_authenticated_user(scope.user_id, "public", Role.SYSTEM_ADMIN)
    second = queue(service, tenant_scope, session_hash, event_id, request)
    assert first.parent_job_id != second.parent_job_id
    with Session(scope_engine) as session:
        assert set(session.execute(select(enrichment_workflows.c.actor_tenant_id)).scalars()) == {
            None,
            "public",
        }
        assert set(
            session.execute(
                select(job_runs.c.tenant_id).where(
                    job_runs.c.job_type == ENRICHMENT_PARENT_JOB_TYPE
                )
            ).scalars()
        ) == {None}


def test_maximum_unicode_and_delimiter_keys_have_bounded_distinct_pg_namespaces(
    scope_engine, tmp_path
):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    receipts = [
        queue(service, scope, session_hash, event_id, request, key)
        for key in ("actor|route:key", "actor:route|key", "🙂" * 200, "a" * 200)
    ]
    assert len({receipt.parent_job_id for receipt in receipts}) == 4
    with Session(scope_engine) as session:
        keys = tuple(
            session.execute(
                select(job_runs.c.idempotency_key).where(
                    job_runs.c.job_type == ENRICHMENT_PARENT_JOB_TYPE
                )
            ).scalars()
        )
    assert all(len(key.encode()) == 77 for key in keys)


def test_legacy_exact_replay_keeps_original_uuid_jobs_and_paid_reservation(scope_engine, tmp_path):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    workflow_id, parent_id = queue_legacy(service, scope, session_hash, event_id, request)
    assert (
        execute_job(
            scope_engine,
            str(parent_id),
            "synthetic-legacy-worker",
            make_enrichment_job_handlers(service),
            clock=lambda: NOW,
        )
        == "succeeded"
    )
    with Session(scope_engine) as session:
        child_id = session.scalar(
            select(enrichment_job_steps.c.job_id).where(
                enrichment_job_steps.c.dimension == "versions"
            )
        )
    assert service._reserve_model_call(child_id, NOW)
    with Session(scope_engine) as session:
        before = dict(
            session.execute(
                select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child_id)
            )
            .mappings()
            .one()
        )
    replay = queue(service, scope, session_hash, event_id, request)
    assert replay.reused and replay.workflow_id == workflow_id and replay.parent_job_id == parent_id
    with Session(scope_engine) as session:
        after = dict(
            session.execute(
                select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child_id)
            )
            .mappings()
            .one()
        )
        assert before == after and after["model_call_reserved_at"] == NOW
        assert session.scalar(select(func.count()).select_from(enrichment_workflows)) == 1
    assert parent_count(scope_engine) == 1


@pytest.mark.parametrize("other_scope", ["actor", "event"])
def test_valid_legacy_other_scope_is_retained_while_v2_operation_is_independent(
    scope_engine, tmp_path, other_scope
):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    legacy_workflow, legacy_parent = queue_legacy(service, scope, session_hash, event_id, request)
    with Session(scope_engine) as session:
        before = dict(session.execute(select(enrichment_workflows)).mappings().one())
    if other_scope == "actor":
        scope, session_hash = create_actor(scope_engine)
    else:
        event_id = create_event(scope_engine, service.store, scope)
    created = queue(service, scope, session_hash, event_id, request)
    assert not created.reused and created.workflow_id != legacy_workflow
    assert created.parent_job_id != legacy_parent and parent_count(scope_engine) == 2
    with Session(scope_engine) as session:
        assert before == dict(
            session.execute(
                select(enrichment_workflows).where(
                    enrichment_workflows.c.workflow_id == str(legacy_workflow)
                )
            )
            .mappings()
            .one()
        )


def test_same_legacy_actor_route_changed_auth_tenant_is_a_binding_conflict(scope_engine, tmp_path):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    queue_legacy(service, scope, session_hash, event_id, request)
    with scope_engine.begin() as connection:
        connection.execute(update(users).values(tenant_id="public"))
    changed = AccessScope.for_authenticated_user(scope.user_id, "public", Role.SYSTEM_ADMIN)
    with pytest.raises(IdempotencyConflictError):
        queue(service, changed, session_hash, event_id, request)
    assert parent_count(scope_engine) == 1


def test_non_enrichment_source_same_raw_key_is_ignored_and_untouched(scope_engine, tmp_path):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    with Session(scope_engine) as session, session.begin():
        source_job = enqueue_job(
            session,
            None,
            "collect_public_source_page",
            b'{"synthetic":"source-only"}',
            NOW,
            idempotency_key="synthetic-shared-key",
        )
    with Session(scope_engine) as session:
        before = dict(
            session.execute(select(job_runs).where(job_runs.c.job_id == source_job))
            .mappings()
            .one()
        )
    created = queue(service, scope, session_hash, event_id, request)
    assert not created.reused and str(created.parent_job_id) != source_job
    with Session(scope_engine) as session:
        assert before == dict(
            session.execute(select(job_runs).where(job_runs.c.job_id == source_job))
            .mappings()
            .one()
        )


def test_valid_v2_internal_key_used_as_new_raw_key_does_not_alias(scope_engine, tmp_path):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    first = queue(service, scope, session_hash, event_id, request)
    with Session(scope_engine) as session:
        internal_key = session.scalar(
            select(job_runs.c.idempotency_key).where(job_runs.c.job_id == str(first.parent_job_id))
        )
    second = queue(service, scope, session_hash, event_id, request, internal_key)
    assert second.parent_job_id != first.parent_job_id and parent_count(scope_engine) == 2
