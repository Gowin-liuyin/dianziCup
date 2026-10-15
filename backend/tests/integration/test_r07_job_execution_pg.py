"""Real isolated PG tests use offline source/model fixtures, never billable services."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r07_enrichment_inputs_pg import seeded_event

from ai_intel.api.auth_state import auth_sessions
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy, EventEnrichmentRequest
from ai_intel.enrichment.job_handlers import make_enrichment_job_handlers
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import EnrichmentJobService
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.models.generation import GenerationLimits
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.event_linking import EventRepository, EventSubmission
from ai_intel.knowledge.models import document_revisions, job_runs, outbox_events, users
from ai_intel.knowledge.persistence_models import events
from ai_intel.workers.executor import execute_job
from ai_intel.workers.jobs import claim_job, recover_expired_job_deliveries

pytestmark = pytest.mark.real_pg
NOW = datetime.now(UTC)


@pytest.fixture
def execution_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database.startswith("test_dianzi_r07_execution_")
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_r07_execution_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, connect_args={"connect_timeout": 5})
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def setup(engine, tmp_path, *, policy=None, product_query_id=None, source_kind="nvd_ollama"):
    if source_kind == "synthetic_bounded_paper":
        from test_r06_catalog_documents_pg import ADMIN, paper, save

        store = ContentStore(tmp_path)
        event_id = uuid4()
        saved = save(engine, store, (paper(),))
        with Session(engine) as session, session.begin():
            EventRepository(session, ADMIN).publish_events(
                "synthetic-bounded-paper-" + str(event_id),
                VisibilityScope(visibility="public"),
                (
                    EventSubmission(
                        event_id=Identifier(value=str(event_id)),
                        event_type="security_risk",
                        title="Synthetic bounded extraction source",
                        scope=VisibilityScope(visibility="public"),
                        source_revision_ids=tuple(
                            Identifier(value=revision) for revision in saved.revision_ids
                        ),
                    ),
                ),
                NOW,
            )
    else:
        store, event_id = seeded_event(engine, tmp_path, source_kind)
    actor = str(uuid4())
    session_hash = sha256(("synthetic-r07-session:" + actor).encode()).hexdigest()
    scope = AccessScope.for_authenticated_user(actor, None, Role.SYSTEM_ADMIN)
    with engine.begin() as connection:
        connection.execute(
            insert(users).values(
                user_id=actor,
                username="synthetic-r07-" + actor,
                password_hash="unusable synthetic hash",
                role=scope.role.value,
                tenant_id=None,
                created_at=NOW,
            )
        )
        connection.execute(
            insert(auth_sessions).values(
                session_hash=session_hash,
                user_id=actor,
                csrf_token="synthetic-csrf",
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
        )
    frozen_policy = policy or EnrichmentExecutionPolicy(data_mode="fixture")
    service = EnrichmentJobService(
        engine, store, execution_policy=lambda: frozen_policy, clock=lambda: NOW
    )
    request = EventEnrichmentRequest(expected_event_version=1, product_query_id=product_query_id)
    with Session(engine) as session, session.begin():
        receipt = service.enqueue(
            session,
            scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="synthetic-request",
            created_at=NOW,
        )
    return service, scope, session_hash, event_id, request, receipt


def run(service, job_id, worker="synthetic-r07-worker", at=NOW):
    return execute_job(
        service.engine, str(job_id), worker, make_enrichment_job_handlers(service), clock=lambda: at
    )


def children(service):
    with Session(service.engine) as session:
        return tuple(
            session.execute(
                select(enrichment_job_steps).order_by(enrichment_job_steps.c.step_key)
            ).mappings()
        )


def view(service, scope, session_hash, receipt):
    with Session(service.engine) as session:
        return service.read_workflow(
            session, scope, receipt.workflow_id, actor_session_hash=session_hash, at=NOW
        )


def test_parent_scheduling_is_not_workflow_completion_and_nine_results_publish_atomically(
    execution_engine, tmp_path
):
    service, scope, session_hash, event_id, request, receipt = setup(execution_engine, tmp_path)
    assert run(service, receipt.parent_job_id) == "succeeded"
    scheduled = view(service, scope, session_hash, receipt)
    assert scheduled.scheduling_complete and not scheduled.workflow_complete
    assert len(scheduled.logical_dimensions) == 9 and len(scheduled.steps) == 11
    rows = children(service)
    publication = next(row for row in rows if row["step_key"] == "publication")
    for row in rows:
        if row["dimension"] is not None:
            assert run(service, row["job_id"]) in {"succeeded", "partial", "blocked"}
    with Session(execution_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(enrichment_results)
                .where(enrichment_results.c.publication_key.like("r07:%"))
            )
            == 0
        )
        assert (
            session.scalar(
                select(events.c.business_version).where(events.c.event_id == str(event_id))
            )
            == 1
        )
    assert run(service, publication["job_id"]) == "partial"
    complete = view(service, scope, session_hash, receipt)
    assert complete.workflow_complete and complete.publication_status == "partial"
    exposure = next(item for item in complete.logical_dimensions if item.dimension == "exposure")
    assert exposure.error_code == "exposure_unknown" and exposure.result_status == "pending"
    with Session(execution_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(enrichment_results)
                .where(enrichment_results.c.publication_key.like("r07:%"))
            )
            == 9
        )
        workflow_job_ids = [str(receipt.parent_job_id), *(row["job_id"] for row in rows)]
        assert (
            session.scalar(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.job_id.in_(workflow_job_ids))
            )
            == 12
        )
        assert (
            session.scalar(
                select(events.c.business_version).where(events.c.event_id == str(event_id))
            )
            == 1
        )
    with Session(execution_engine) as session, session.begin():
        replay = service.enqueue(
            session,
            scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="synthetic-request",
            created_at=NOW,
        )
    assert replay.reused and replay.parent_job_id == receipt.parent_job_id
    assert run(service, publication["job_id"]) == "not_claimed"


def test_concurrent_enqueue_reuses_one_parent_and_policy_or_session_changes_conflict(
    execution_engine, tmp_path
):
    service, scope, session_hash, event_id, request, first = setup(execution_engine, tmp_path)

    def enqueue():
        with Session(execution_engine) as session, session.begin():
            return service.enqueue(
                session,
                scope,
                event_id,
                request,
                actor_session_hash=session_hash,
                idempotency_key="synthetic-request",
                created_at=NOW,
            )

    with ThreadPoolExecutor(max_workers=2) as workers:
        receipts = list(workers.map(lambda _: enqueue(), range(2)))
    assert all(
        receipt.parent_job_id == first.parent_job_id and receipt.reused for receipt in receipts
    )
    service.execution_policy = lambda: EnrichmentExecutionPolicy(data_mode="live")
    with (
        pytest.raises(IdempotencyConflictError),
        Session(execution_engine) as session,
        session.begin(),
    ):
        service.enqueue(
            session,
            scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="synthetic-request",
            created_at=NOW,
        )


def test_model_reservation_update_does_not_wait_for_executor_job_lock(execution_engine, tmp_path):
    service, _, _, _, _, receipt = setup(execution_engine, tmp_path)
    assert run(service, receipt.parent_job_id) == "succeeded"
    child = next(row for row in children(service) if row["dimension"] == "versions")
    with Session(execution_engine) as locked, locked.begin():
        locked.execute(
            select(job_runs).where(job_runs.c.job_id == child["job_id"]).with_for_update()
        ).one()
        with ThreadPoolExecutor(max_workers=1) as worker:
            assert worker.submit(service._reserve_model_call, child["job_id"], NOW).result(
                timeout=5
            )
    assert not service._reserve_model_call(child["job_id"], NOW)
    with Session(execution_engine) as session:
        persisted = (
            session.execute(
                select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child["job_id"])
            )
            .mappings()
            .one()
        )
        assert persisted["model_call_reserved_at"] == NOW and persisted["model_trace"] == []


@pytest.mark.parametrize(
    "mutation",
    ["revoked", "expired", "role", "tenant", "policy", "source_acl", "revision", "snapshot"],
)
def test_changed_authority_or_frozen_parent_never_publishes(execution_engine, tmp_path, mutation):
    service, scope, session_hash, _, _, receipt = setup(execution_engine, tmp_path)
    assert run(service, receipt.parent_job_id) == "succeeded"
    rows = children(service)
    for row in rows:
        if row["dimension"] is not None:
            run(service, row["job_id"])
    with execution_engine.begin() as connection:
        if mutation == "revoked":
            connection.execute(update(auth_sessions).values(revoked_at=NOW))
        elif mutation == "expired":
            connection.execute(
                update(auth_sessions).values(issued_at=NOW - timedelta(seconds=1), expires_at=NOW)
            )
        elif mutation == "role":
            connection.execute(update(users).values(role="analyst", tenant_id="synthetic-tenant"))
        elif mutation == "tenant":
            connection.execute(update(users).values(tenant_id="synthetic-changed-tenant"))
        elif mutation == "source_acl":
            connection.execute(
                text("UPDATE sources SET visibility='tenant', tenant_id='synthetic-secret-tenant'")
            )
        elif mutation == "revision":
            connection.execute(update(document_revisions).values(is_current=False))
        elif mutation == "snapshot":
            connection.execute(update(enrichment_workflows).values(input_fingerprint="a" * 64))
    if mutation == "policy":
        service.execution_policy = lambda: EnrichmentExecutionPolicy(data_mode="live")
    publication = next(row for row in rows if row["step_key"] == "publication")
    assert run(service, publication["job_id"]) == "blocked"
    with Session(execution_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(enrichment_results)
                .where(enrichment_results.c.publication_key.like("r07:%"))
            )
            == 0
        )
    if mutation in {"revoked", "expired"}:
        with pytest.raises(PermissionDeniedError):
            view(service, scope, session_hash, receipt)


def test_interrupted_paid_reservation_is_visible_and_never_resubmitted(execution_engine, tmp_path):
    service, scope, session_hash, _, _, receipt = setup(execution_engine, tmp_path)
    assert run(service, receipt.parent_job_id) == "succeeded"
    child = next(row for row in children(service) if row["dimension"] == "versions")
    with Session(execution_engine) as session, session.begin():
        assert claim_job(session, child["job_id"], "worker-before-crash", NOW)
    assert service._reserve_model_call(child["job_id"], NOW)
    with Session(execution_engine) as session, session.begin():
        recover_expired_job_deliveries(session, NOW + timedelta(seconds=61))
    assert run(service, child["job_id"], at=NOW + timedelta(seconds=61)) == "not_claimed"
    observed = view(service, scope, session_hash, receipt)
    step = next(item for item in observed.steps if str(item.job_id) == child["job_id"])
    assert step.status == "failed" and step.model_call_state == "incomplete_interrupted"
    assert step.model_attempts == ()
    for row in children(service):
        if row["dimension"] is not None and row["job_id"] != child["job_id"]:
            run(service, row["job_id"])
    publication = next(row for row in children(service) if row["step_key"] == "publication")
    assert run(service, publication["job_id"]) == "partial"
    final = view(service, scope, session_hash, receipt)
    assert (
        next(item for item in final.logical_dimensions if item.dimension == "versions").error_code
        == "incomplete_interrupted"
    )


def test_unknown_product_query_makes_no_exposure_client_calls_and_view_hides_sensitive_fields(
    execution_engine, tmp_path
):
    service, scope, session_hash, _, _, receipt = setup(execution_engine, tmp_path)

    class ForbiddenExposure:
        def collect_aggregate(self, *args, **kwargs):
            raise AssertionError("unknown product must make zero calls")

    service.exposure_client = ForbiddenExposure()
    assert run(service, receipt.parent_job_id) == "succeeded"
    for row in children(service):
        if row["dimension"] == "exposure":
            assert run(service, row["job_id"]) == "partial"
    encoded = view(service, scope, session_hash, receipt).model_dump_json()
    assert session_hash not in encoded
    assert all(
        forbidden not in encoded
        for forbidden in (
            "csrf_token",
            "actor_session_hash",
            "raw_prompt",
            "credential",
            "input_context",
        )
    )
    outsider = AccessScope.for_authenticated_user("unknown-user", "other", Role.ANALYST)
    with pytest.raises(CrossTenantAccessError), Session(execution_engine) as session:
        service.read_workflow(
            session, outsider, receipt.workflow_id, actor_session_hash=session_hash, at=NOW
        )


def test_offline_real_generation_codec_receipts_survive_new_service_and_no_repeat(
    execution_engine, tmp_path, monkeypatch
):
    from tests.unit.test_r07_single_model_dimension import prepared_transport

    policy = EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="openai",
        approved_model="fixture-model",
        data_mode="fixture",
    )
    service, scope, session_hash, _, _, receipt = setup(
        execution_engine, tmp_path, policy=policy, source_kind="synthetic_bounded_paper"
    )
    created = []
    wire_calls = []

    def factory():
        client, calls = prepared_transport(
            monkeypatch,
            outputs={
                dimension: {"candidates": []}
                for dimension in ("atlas", "versions", "literature", "poc")
            },
        )
        client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
        created.append(client)
        wire_calls.append(calls)
        return client

    service.generation_client_factory = factory
    assert run(service, receipt.parent_job_id) == "succeeded"
    for row in children(service):
        if row["dimension"] in {"atlas", "versions", "literature", "poc"}:
            outcome = run(service, row["job_id"])
            with Session(execution_engine) as session:
                error_code = session.scalar(
                    select(job_runs.c.error_code).where(job_runs.c.job_id == row["job_id"])
                )
            assert outcome == "partial", (row["dimension"], outcome, error_code)
            assert run(service, row["job_id"]) == "not_claimed"
    restarted = EnrichmentJobService(
        execution_engine, service.store, execution_policy=lambda: policy
    )
    observed = view(restarted, scope, session_hash, receipt)
    attempts = [attempt for step in observed.steps for attempt in step.model_attempts]
    assert len(created) == 4 and len({id(client) for client in created}) == 4
    assert sum(len(calls) for calls in wire_calls) == len(attempts) == 3
    assert all(
        attempt.fee == "unknown"
        and attempt.usage.total_tokens == 21
        and attempt.response_model == "fixture-model"
        and len(attempt.prompt_sha256) == 64
        for attempt in attempts
    )
    assert all(
        0 < call[2] <= 20 and call[1]["max_completion_tokens"] == 1024
        for calls in wire_calls
        for call in calls
    )


def test_expired_parent_worker_is_taken_over_once_and_publication_waits(execution_engine, tmp_path):
    service, _, _, _, _, receipt = setup(execution_engine, tmp_path)
    with Session(execution_engine) as session, session.begin():
        assert claim_job(session, str(receipt.parent_job_id), "crashed-parent-worker", NOW)
    recovered_at = NOW + timedelta(seconds=61)
    with Session(execution_engine) as session, session.begin():
        recover_expired_job_deliveries(session, recovered_at)
    assert (
        run(service, receipt.parent_job_id, "replacement-parent-worker", recovered_at)
        == "succeeded"
    )
    publication = next(row for row in children(service) if row["step_key"] == "publication")
    assert run(service, publication["job_id"], at=recovered_at) == "retry_wait"
    with Session(execution_engine) as session:
        row = (
            session.execute(select(job_runs).where(job_runs.c.job_id == str(receipt.parent_job_id)))
            .mappings()
            .one()
        )
        assert row["attempt_count"] == 2
        assert session.scalar(select(func.count()).select_from(enrichment_job_steps)) == 11
        publication_row = (
            session.execute(select(job_runs).where(job_runs.c.job_id == publication["job_id"]))
            .mappings()
            .one()
        )
        assert publication_row["next_retry_at"] == recovered_at + timedelta(seconds=20)


@pytest.mark.parametrize("product_query_id", ["ollama", "vllm"])
def test_registered_query_without_client_is_explicitly_blocked(
    execution_engine, tmp_path, product_query_id
):
    service, _, _, _, _, receipt = setup(
        execution_engine,
        tmp_path,
        policy=EnrichmentExecutionPolicy(aggregate_enabled=True, data_mode="fixture"),
        product_query_id=product_query_id,
    )
    assert run(service, receipt.parent_job_id) == "succeeded"
    for row in children(service):
        if row["dimension"] == "exposure":
            assert run(service, row["job_id"]) == "blocked"


def test_full_recorded_nvd_budget_failure_is_retained_without_wire_or_losing_other_dimensions(
    execution_engine, tmp_path, monkeypatch
):
    from tests.unit.test_r07_single_model_dimension import prepared_transport

    policy = EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="openai",
        approved_model="fixture-model",
        data_mode="fixture",
    )
    service, scope, session_hash, _, _, receipt = setup(execution_engine, tmp_path, policy=policy)
    calls = []

    def factory():
        client, wire = prepared_transport(monkeypatch)
        client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
        calls.append(wire)
        return client

    service.generation_client_factory = factory
    assert run(service, receipt.parent_job_id) == "succeeded"
    with Session(execution_engine) as session:
        snapshot = session.scalar(select(enrichment_workflows.c.input_context))
    block_count = sum(len(document["blocks"]) for document in snapshot["documents"])
    assert block_count > 50
    for row in children(service):
        if row["dimension"] is not None:
            outcome = run(service, row["job_id"])
            if row["dimension"] in {"atlas", "versions", "literature", "poc"}:
                assert outcome == "failed"
    assert sum(len(wire) for wire in calls) == 0
    publication = next(row for row in children(service) if row["step_key"] == "publication")
    assert run(service, publication["job_id"]) == "partial"
    observed = view(service, scope, session_hash, receipt)
    model_steps = [
        step
        for step in observed.steps
        if step.dimension in {"atlas", "versions", "literature", "poc"}
    ]
    assert all(
        step.error_code == "field_input_budget_exhausted" and step.model_attempts == ()
        for step in model_steps
    )
    assert (
        next(item for item in observed.logical_dimensions if item.dimension == "cvss").result_status
        == "available"
    )
    evidence = {
        "data_mode": "fixture",
        "source": "recorded_nvd_public",
        "document_count": len(snapshot["documents"]),
        "block_count": block_count,
        "wire_calls": 0,
        "publication_status": observed.publication_status,
        "model_steps": [
            {"dimension": step.dimension, "status": step.status, "error_code": step.error_code}
            for step in model_steps
        ],
    }
    path = (
        Path(__file__).resolve().parents[3]
        / "reports/runs/recovery_r07_enrichment_execution_20261016"
        / "nvd_input_budget_observation.json"
    )
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


def test_revocation_during_offline_wire_keeps_actual_receipt_but_discards_result(
    execution_engine, tmp_path, monkeypatch
):
    from tests.unit.test_r07_single_model_dimension import prepared_transport

    policy = EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="openai",
        approved_model="fixture-model",
        data_mode="fixture",
    )
    service, _, _, _, _, receipt = setup(
        execution_engine, tmp_path, policy=policy, source_kind="synthetic_bounded_paper"
    )
    calls = []

    def factory():
        client, wire = prepared_transport(monkeypatch, outputs={"versions": {"candidates": []}})
        client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
        original_request = client._gateway._transport.request

        def revoke_then_return(*args, **kwargs):
            with execution_engine.begin() as connection:
                connection.execute(update(auth_sessions).values(revoked_at=NOW))
            return original_request(*args, **kwargs)

        monkeypatch.setattr(client._gateway._transport, "request", revoke_then_return)
        calls.append(wire)
        return client

    service.generation_client_factory = factory
    assert run(service, receipt.parent_job_id) == "succeeded"
    child = next(row for row in children(service) if row["dimension"] == "versions")
    assert run(service, child["job_id"]) == "blocked"
    assert sum(len(wire) for wire in calls) == 1
    with Session(execution_engine) as session:
        row = (
            session.execute(
                select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child["job_id"])
            )
            .mappings()
            .one()
        )
        assert row["result_payload"] is None and row["model_call_completed_at"] is not None
        assert len(row["model_trace"]) == 1 and row["model_trace"][0]["fee"] == "unknown"
        assert (
            session.scalar(
                select(func.count())
                .select_from(enrichment_results)
                .where(enrichment_results.c.publication_key.like("r07:%"))
            )
            == 0
        )


def test_private_event_without_server_egress_does_not_construct_model_client(
    execution_engine, tmp_path
):
    policy = EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="openai",
        approved_model="fixture-model",
        data_mode="fixture",
    )
    service, scope, session_hash, event_id, request, _ = setup(
        execution_engine, tmp_path, policy=policy
    )
    tenant_id = "synthetic-private-tenant"
    private_scope = AccessScope.for_authenticated_user(scope.user_id, tenant_id, Role.TENANT_ADMIN)
    with execution_engine.begin() as connection:
        connection.execute(update(users).values(tenant_id=tenant_id, role="tenant_admin"))
        connection.execute(update(events).values(visibility="tenant", tenant_id=tenant_id))

    def forbidden_client():
        raise AssertionError("private egress denial must precede client creation")

    service.generation_client_factory = forbidden_client
    with Session(execution_engine) as session, session.begin():
        receipt = service.enqueue(
            session,
            private_scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="synthetic-private-request",
            created_at=NOW,
        )
    assert run(service, receipt.parent_job_id) == "succeeded"
    for row in children(service):
        if row["workflow_id"] == str(receipt.workflow_id) and row["dimension"] in {
            "atlas",
            "versions",
            "literature",
            "poc",
        }:
            assert run(service, row["job_id"]) == "blocked"
    observed = view(service, private_scope, session_hash, receipt)
    assert all(step.model_call_state == "not_reserved" for step in observed.steps)
    assert all(
        step.error_code == "model_egress_denied"
        for step in observed.steps
        if step.dimension in {"atlas", "versions", "literature", "poc"}
    )


def test_structured_child_takeover_and_exhaustion_preserve_pg_failure_without_erasing_batch(
    execution_engine, tmp_path
):
    service, scope, session_hash, _, _, receipt = setup(execution_engine, tmp_path)
    assert run(service, receipt.parent_job_id) == "succeeded"
    rows = children(service)
    cvss = next(row for row in rows if row["dimension"] == "cvss")
    with Session(execution_engine) as session, session.begin():
        assert claim_job(session, cvss["job_id"], "crashed-structure-worker", NOW)
    assert run(service, cvss["job_id"], at=NOW + timedelta(seconds=61)) == "succeeded"
    epss = next(row for row in rows if row["dimension"] == "epss")
    for attempt in range(3):
        with Session(execution_engine) as session, session.begin():
            assert claim_job(
                session,
                epss["job_id"],
                "crashed-epss-worker",
                NOW + timedelta(seconds=61 * attempt),
            )
    with Session(execution_engine) as session, session.begin():
        recover_expired_job_deliveries(session, NOW + timedelta(seconds=61 * 3))
    for row in rows:
        if row["dimension"] is not None and row["dimension"] not in {"cvss", "epss"}:
            run(service, row["job_id"])
    publication = next(row for row in rows if row["step_key"] == "publication")
    assert run(service, publication["job_id"]) == "partial"
    observed = view(service, scope, session_hash, receipt)
    epss_view = next(item for item in observed.logical_dimensions if item.dimension == "epss")
    assert epss_view.status == "failed" and epss_view.error_code == "attempts_exhausted"
    assert (
        next(item for item in observed.logical_dimensions if item.dimension == "cvss").result_status
        == "available"
    )
    with Session(execution_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(enrichment_results)
                .where(enrichment_results.c.publication_key.like("r07:%"))
            )
            == 9
        )
