"""Explicit offline IO fixtures verify graph scheduling decisions without claiming PG execution."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.knowledge import graph_runtime_policy as policy
from ai_intel.knowledge.graph_projection import (
    GraphSnapshotChangedError,
    ManifestEntry,
    ManifestPage,
    ProjectionCapacityError,
    ProjectionDigestConflict,
    ProjectionNotReady,
    ReconciliationManifest,
)
from ai_intel.workers.executor import DetachedJobHandler, JobExecutionContext, JobExecutionError

PUBLIC = AccessScope.for_authenticated_user("offline-projector", None, Role.VIEWER)
EPOCHS = (("public", 4),)
GENERATION = policy.graph_generation_id(policy.DEFAULT_GRAPH_NAMESPACE, "public", EPOCHS)
CONTEXT = JobExecutionContext(str(uuid4()), "offline-worker", 1, None)


def request(**changes):
    return policy.GraphReconciliationRequest(
        generation_id=GENERATION,
        scope_epochs=EPOCHS,
        **changes,
    )


def manifest(count, **changes):
    return ReconciliationManifest(
        namespace=policy.DEFAULT_GRAPH_NAMESPACE,
        partition_key="public",
        generation_id=GENERATION,
        scope_epochs=EPOCHS,
        manifest_sha256="a" * 64,
        event_count=count,
        page_count=(count + 99) // 100,
        status="ready" if count == 0 else "pending",
        **changes,
    )


@pytest.fixture
def offline_runtime(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    session.begin.return_value = nullcontext()
    session.scalar.return_value = True
    row = SimpleNamespace(tenant_id=None, job_type="graph_reconcile")
    session.execute.return_value.one_or_none.return_value = row
    monkeypatch.setattr(policy, "Session", lambda _engine: session)
    monkeypatch.setattr(policy, "read_projection_scope_epochs", lambda _session, _scope: EPOCHS)
    scheduled = []

    def enqueue(_session, tenant_id, job_type, payload, now, **options):
        scheduled.append((tenant_id, job_type, payload, options))
        return str(UUID(int=len(scheduled)))

    monkeypatch.setattr(policy, "enqueue_job", enqueue)
    runtime = policy.build_graph_runtime_policy(MagicMock(), MagicMock(), lambda _s, _c: PUBLIC)
    return runtime, session, row, scheduled


def detached(runtime, job_type):
    handler = runtime.job_handlers[job_type]
    assert isinstance(handler, DetachedJobHandler)
    return handler.handler


def test_generation_is_stable_but_changes_with_partition_epoch_or_namespace():
    assert policy.graph_generation_id("knowledge-graph", "public", EPOCHS) == GENERATION
    assert policy.graph_generation_id("knowledge-graph", "public", (("public", 5),)) != GENERATION
    assert policy.graph_generation_id("other-graph", "public", EPOCHS) != GENERATION
    assert policy.graph_generation_id("knowledge-graph", "tenant:other", EPOCHS) != GENERATION


@pytest.mark.parametrize(
    "changes",
    [
        {"max_events": 0},
        {"max_events": 10001},
        {"max_events": True},
        {"max_pages": 0},
        {"max_pages": 101},
        {"page_number": -1},
        {"page_number": 100},
        {"namespace": "Bad namespace"},
        {"unknown": 1},
    ],
)
def test_reconciliation_budget_and_payload_are_strict(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_missing_store_registers_explicit_blocked_handlers_without_io():
    engine, authorizer = MagicMock(), MagicMock()
    runtime = policy.build_graph_runtime_policy(engine, None, authorizer)
    assert set(runtime.job_handlers) == {"graph_reconcile", "graph_capture", "graph_apply"}
    for handler in [runtime.knowledge_change_handler, *runtime.job_handlers.values()]:
        with pytest.raises(JobExecutionError, match="graph_projection_not_configured") as failure:
            handler(MagicMock(), CONTEXT, b"{}")
        assert failure.value.blocked
    engine.assert_not_called()
    authorizer.assert_not_called()


def test_scheduling_preserves_shared_partial_and_current_scope(monkeypatch, offline_runtime):
    runtime, session, row, scheduled = offline_runtime
    row.job_type = "knowledge_change"
    monkeypatch.setattr(
        policy, "find_projection_change", lambda _s, _c: SimpleNamespace(scope_key="public")
    )
    result = runtime.knowledge_change_handler(session, CONTEXT, b"not used as authority")
    assert result.outcome == "partial"
    assert result.error_code == "knowledge_change_other_consumers_pending"
    assert result.result_ref == "pg:job:" + str(UUID(int=1))
    assert len(scheduled) == 1 and scheduled[0][1] == "graph_reconcile"
    queued = policy.GraphReconciliationRequest.model_validate_json(scheduled[0][2])
    assert queued.generation_id == GENERATION and queued.scope_epochs == EPOCHS


@pytest.mark.parametrize("tenant,job_type", [("other", "graph_reconcile"), (None, "source_page")])
def test_graph_job_authority_rejects_mismatched_tenant_and_type(offline_runtime, tenant, job_type):
    runtime, _session, row, scheduled = offline_runtime
    row.tenant_id, row.job_type = tenant, job_type
    with pytest.raises(JobExecutionError, match="graph_projection_scope_denied"):
        detached(runtime, "graph_reconcile")(CONTEXT, request().model_dump_json().encode())
    assert not scheduled


def test_one_page_schedules_only_bounded_captures_and_one_continuation(
    monkeypatch, offline_runtime
):
    runtime, _session, _row, scheduled = offline_runtime
    entries = tuple(
        ManifestEntry(event_id=UUID(int=value), business_version=1) for value in range(1, 101)
    )
    monkeypatch.setattr(policy, "begin_reconciliation", lambda *_a, **_kw: manifest(101))
    monkeypatch.setattr(
        policy, "read_manifest_page", lambda *_a: ManifestPage(page_number=0, entries=entries)
    )
    result = detached(runtime, "graph_reconcile")(CONTEXT, request().model_dump_json().encode())
    assert result.outcome == "partial" and result.error_code == "graph_projection_children_pending"
    assert [item[1] for item in scheduled] == ["graph_capture"] * 100 + ["graph_reconcile"]
    continuation = policy.GraphReconciliationRequest.model_validate_json(scheduled[-1][2])
    assert continuation.page_number == 1 and continuation.generation_id == GENERATION
    assert len({item[3]["idempotency_key"] for item in scheduled}) == 101


def test_last_page_returns_manifest_reference_and_reuses_capture_identity(
    monkeypatch, offline_runtime
):
    runtime, _session, _row, scheduled = offline_runtime
    event_id = uuid4()
    monkeypatch.setattr(policy, "read_reconciliation_manifest", lambda *_a: manifest(101))
    monkeypatch.setattr(
        policy,
        "read_manifest_page",
        lambda *_a: ManifestPage(page_number=1, entries=(ManifestEntry(event_id=event_id),)),
    )
    handler = detached(runtime, "graph_reconcile")
    payload = request(page_number=1).model_dump_json().encode()
    first, second = handler(CONTEXT, payload), handler(CONTEXT, payload)
    assert first == second and first.result_ref == "pg:graph_generation:" + str(GENERATION)
    assert [item[1] for item in scheduled] == ["graph_capture", "graph_capture"]
    assert scheduled[0][3]["idempotency_key"] == scheduled[1][3]["idempotency_key"]


def test_empty_manifest_is_confirmed_ready_without_capture_jobs(monkeypatch, offline_runtime):
    runtime, _session, _row, scheduled = offline_runtime
    monkeypatch.setattr(policy, "begin_reconciliation", lambda *_a, **_kw: manifest(0))
    result = detached(runtime, "graph_reconcile")(CONTEXT, request().model_dump_json().encode())
    assert result.outcome == "succeeded" and not scheduled


@pytest.mark.parametrize("count,changes", [(101, {"max_pages": 1}), (2, {"max_events": 1})])
def test_budget_exhaustion_does_not_queue_a_truncated_complete_graph(
    monkeypatch,
    offline_runtime,
    count,
    changes,
):
    runtime, _session, _row, scheduled = offline_runtime
    monkeypatch.setattr(policy, "begin_reconciliation", lambda *_a, **_kw: manifest(count))
    result = detached(runtime, "graph_reconcile")(
        CONTEXT, request(**changes).model_dump_json().encode()
    )
    assert (
        result.outcome == "partial" and result.error_code == "graph_reconciliation_budget_exhausted"
    )
    assert not scheduled


def test_epoch_change_blocks_old_generation_before_manifest_or_child_io(
    monkeypatch, offline_runtime
):
    runtime, _session, _row, scheduled = offline_runtime
    begin = MagicMock()
    monkeypatch.setattr(policy, "begin_reconciliation", begin)
    stale = request().model_copy(update={"scope_epochs": (("public", 3),)})
    with pytest.raises(JobExecutionError, match="graph_projection_epoch_changed") as failure:
        detached(runtime, "graph_reconcile")(CONTEXT, stale.model_dump_json().encode())
    assert failure.value.blocked and not scheduled
    begin.assert_not_called()


def test_single_event_capture_reauthorizes_inside_existing_pg_fence(monkeypatch, offline_runtime):
    runtime, _session, row, _scheduled = offline_runtime
    row.job_type = "graph_capture"
    batch_id, event_id = uuid4(), uuid4()
    observed = []

    def capture(_engine, scope, namespace, generation, event, *, authorize, captured_at):
        observed.append((scope, namespace, generation, event))
        assert authorize(_session) == PUBLIC
        return SimpleNamespace(batch_id=batch_id)

    monkeypatch.setattr(policy, "capture_event_projection", capture)
    payload = (
        policy.GraphCaptureRequest(
            namespace="knowledge-graph",
            generation_id=GENERATION,
            scope_epochs=EPOCHS,
            event_id=event_id,
        )
        .model_dump_json()
        .encode()
    )
    result = detached(runtime, "graph_capture")(CONTEXT, payload)
    assert observed == [(PUBLIC, "knowledge-graph", GENERATION, event_id)]
    assert result.outcome == "partial" and result.result_ref == "pg:graph_batch:" + str(batch_id)
    assert result.error_code == "graph_projection_apply_pending"


@pytest.mark.parametrize(
    "failure,code",
    [
        (PermissionDeniedError("fixture revoked"), "graph_projection_scope_denied"),
        (GraphSnapshotChangedError("fixture changed"), "graph_projection_epoch_changed"),
        (ProjectionNotReady("fixture stale"), "graph_projection_epoch_changed"),
        (ProjectionCapacityError("fixture full"), "graph_projection_capacity_exceeded"),
        (ProjectionDigestConflict("fixture corrupt"), "graph_projection_digest_conflict"),
    ],
)
def test_capture_failures_remain_explicit(monkeypatch, offline_runtime, failure, code):
    runtime, _session, row, _scheduled = offline_runtime
    row.job_type = "graph_capture"
    monkeypatch.setattr(policy, "capture_event_projection", MagicMock(side_effect=failure))
    payload = (
        policy.GraphCaptureRequest(
            namespace="knowledge-graph",
            generation_id=GENERATION,
            scope_epochs=EPOCHS,
            event_id=uuid4(),
        )
        .model_dump_json()
        .encode()
    )
    with pytest.raises(JobExecutionError, match=code) as caught:
        detached(runtime, "graph_capture")(CONTEXT, payload)
    assert caught.value.blocked


def test_connection_failure_is_not_converted_into_graph_success(monkeypatch, offline_runtime):
    runtime, _session, row, _scheduled = offline_runtime
    row.job_type = "graph_capture"
    monkeypatch.setattr(
        policy, "capture_event_projection", MagicMock(side_effect=ConnectionError())
    )
    payload = (
        policy.GraphCaptureRequest(
            namespace="knowledge-graph",
            generation_id=GENERATION,
            scope_epochs=EPOCHS,
            event_id=uuid4(),
        )
        .model_dump_json()
        .encode()
    )
    with pytest.raises(ConnectionError):
        detached(runtime, "graph_capture")(CONTEXT, payload)


def test_busy_reconciliation_uses_existing_bounded_retry(offline_runtime):
    runtime, session, _row, scheduled = offline_runtime
    session.scalar.return_value = False
    with pytest.raises(JobExecutionError, match="graph_reconciliation_busy") as failure:
        detached(runtime, "graph_reconcile")(CONTEXT, request().model_dump_json().encode())
    assert failure.value.retry_after_seconds == 5.0 and not failure.value.blocked
    assert not scheduled


def test_reconciliation_deadline_aborts_before_child_scheduling(monkeypatch, offline_runtime):
    runtime, _session, _row, scheduled = offline_runtime
    monkeypatch.setattr(policy, "begin_reconciliation", lambda *_a, **_kw: manifest(1))
    monkeypatch.setattr(
        policy,
        "read_manifest_page",
        lambda *_a: ManifestPage(
            page_number=0,
            entries=(ManifestEntry(event_id=uuid4()),),
        ),
    )
    monkeypatch.setattr(policy.time, "monotonic", MagicMock(side_effect=[1.0, 21.0]))
    with pytest.raises(JobExecutionError, match="graph_reconciliation_deadline_exceeded"):
        detached(runtime, "graph_reconcile")(CONTEXT, request().model_dump_json().encode())
    assert not scheduled


@pytest.mark.parametrize("job_type", ["graph_reconcile", "graph_capture"])
def test_other_runtime_namespace_is_rejected_before_pg_reads(offline_runtime, job_type):
    runtime, session, _row, scheduled = offline_runtime
    if job_type == "graph_reconcile":
        payload = request(namespace="other-graph").model_dump_json().encode()
    else:
        payload = (
            policy.GraphCaptureRequest(
                namespace="other-graph",
                generation_id=GENERATION,
                scope_epochs=EPOCHS,
                event_id=uuid4(),
            )
            .model_dump_json()
            .encode()
        )
    with pytest.raises(JobExecutionError, match="graph_projection_namespace_denied"):
        detached(runtime, job_type)(CONTEXT, payload)
    session.execute.assert_not_called()
    assert not scheduled


def test_generation_changed_inside_capture_fence_blocks_batch(monkeypatch, offline_runtime):
    runtime, _session, row, _scheduled = offline_runtime
    row.job_type = "graph_capture"
    reads = iter([EPOCHS, (("public", 5),)])
    monkeypatch.setattr(policy, "read_projection_scope_epochs", lambda _s, _c: next(reads))

    def capture(_engine, _scope, _namespace, _generation, _event, *, authorize, captured_at):
        authorize(_session)
        raise AssertionError("stale generation reached batch commit")

    monkeypatch.setattr(policy, "capture_event_projection", capture)
    payload = (
        policy.GraphCaptureRequest(
            namespace="knowledge-graph",
            generation_id=GENERATION,
            scope_epochs=EPOCHS,
            event_id=uuid4(),
        )
        .model_dump_json()
        .encode()
    )
    with pytest.raises(JobExecutionError, match="graph_projection_epoch_changed"):
        detached(runtime, "graph_capture")(CONTEXT, payload)


@pytest.mark.parametrize(
    "change,exception",
    [
        ({"namespace": "other-graph"}, ProjectionDigestConflict),
        ({"scope_epochs": (("public", 3),)}, ProjectionNotReady),
        ({"status": "stale"}, ProjectionNotReady),
    ],
)
def test_current_manifest_read_rejects_identity_or_epoch_drift(monkeypatch, change, exception):
    from ai_intel.knowledge import graph_projection as projection

    stored = manifest(1).model_copy(update=change)
    monkeypatch.setattr(projection, "_state_row", lambda *_a, **_kw: {})
    monkeypatch.setattr(projection, "_body", lambda *_a: stored)
    monkeypatch.setattr(projection, "_manifest_entries", lambda *_a: ())
    monkeypatch.setattr(projection, "_epochs", lambda *_a: EPOCHS)
    with pytest.raises(exception):
        projection.read_reconciliation_manifest(MagicMock(), PUBLIC, "knowledge-graph", GENERATION)
