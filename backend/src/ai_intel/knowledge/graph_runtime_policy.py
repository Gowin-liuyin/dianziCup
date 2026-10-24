"""Bounded graph fanout over existing PG manifests; shared knowledge completion stays partial."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, PermissionDeniedError
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.evidence_graph import GRAPH_RULE_VERSION, GraphSnapshotChangedError
from ai_intel.knowledge.graph_projection import (
    GRAPH_APPLY_JOB_TYPE,
    MANIFEST_PAGE_SIZE,
    EpochMap,
    GraphProjectionBatch,
    GraphProjectionStore,
    Namespace,
    ProjectionCapacityError,
    ProjectionDigestConflict,
    ProjectionNotReady,
    ProjectionRecord,
    TaskScopeAuthorizer,
    begin_reconciliation,
    build_graph_apply_handler,
    capture_event_projection,
    partition_for_scope,
    read_manifest_page,
    read_projection_scope_epochs,
    read_reconciliation_manifest,
)
from ai_intel.knowledge.models import job_runs
from ai_intel.retrieval.runtime_policy import (
    KNOWLEDGE_CHANGE_JOB_TYPE,
    find_projection_change,
)
from ai_intel.workers.executor import (
    DetachedJobHandler,
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
    JobHandler,
)

GRAPH_RECONCILE_JOB_TYPE = "graph_reconcile"
GRAPH_CAPTURE_JOB_TYPE = "graph_capture"
DEFAULT_GRAPH_NAMESPACE = "knowledge-graph"


class GraphReconciliationRequest(ProjectionRecord):
    namespace: Namespace = DEFAULT_GRAPH_NAMESPACE
    generation_id: UUID
    scope_epochs: EpochMap
    page_number: int = Field(default=0, ge=0, le=99)
    max_events: int = Field(default=1000, ge=1, le=10000)
    max_pages: int = Field(default=10, ge=1, le=100)


class GraphCaptureRequest(ProjectionRecord):
    namespace: Namespace
    generation_id: UUID
    scope_epochs: EpochMap
    event_id: UUID


@dataclass(frozen=True)
class GraphRuntimePolicy:
    knowledge_change_handler: JobHandler
    job_handlers: dict[str, JobHandler | DetachedJobHandler]


def graph_generation_id(namespace: str, partition: str, epochs: EpochMap) -> UUID:
    """All changes for the same current graph scope converge on one immutable generation."""
    identity = json.dumps([namespace, partition, epochs, GRAPH_RULE_VERSION], separators=(",", ":"))
    return uuid5(NAMESPACE_URL, "ai-intel:graph:" + identity)


def _authorize_job(
    session: Session, context: JobExecutionContext, authorize: TaskScopeAuthorizer
) -> AccessScope:
    row = session.execute(
        select(job_runs.c.tenant_id, job_runs.c.job_type).where(job_runs.c.job_id == context.job_id)
    ).one_or_none()
    if (
        row is None
        or row.tenant_id != context.tenant_id
        or row.job_type
        not in {
            KNOWLEDGE_CHANGE_JOB_TYPE,
            GRAPH_RECONCILE_JOB_TYPE,
            GRAPH_CAPTURE_JOB_TYPE,
            GRAPH_APPLY_JOB_TYPE,
        }
    ):
        raise PermissionDeniedError("graph job scope denied")
    scope = authorize(session, context)
    partition = partition_for_scope(scope)
    if context.tenant_id != (scope.tenant_id if partition != "public" else None):
        raise PermissionDeniedError("graph job scope denied")
    return scope


def _require_generation(
    session: Session, scope: AccessScope, request: GraphReconciliationRequest | GraphCaptureRequest
) -> None:
    epochs = read_projection_scope_epochs(session, scope)
    if request.scope_epochs != epochs or request.generation_id != graph_generation_id(
        request.namespace, partition_for_scope(scope), epochs
    ):
        raise ProjectionNotReady("graph_manifest_epoch_changed")


def _enqueue_reconciliation(
    session: Session, tenant_id: str | None, request: GraphReconciliationRequest, now: datetime
) -> str:
    budget = f"{request.max_events}:{request.max_pages}"
    return enqueue_job(
        session,
        tenant_id,
        GRAPH_RECONCILE_JOB_TYPE,
        request.model_dump_json().encode(),
        now,
        idempotency_key=f"graph-reconcile:{request.generation_id}:{request.page_number}:{budget}",
    )


def _blocked_graph_job(
    session: Session, context: JobExecutionContext, payload: bytes
) -> JobExecutionResult:
    raise JobExecutionError("graph_projection_not_configured", blocked=True)


def build_graph_runtime_policy(
    engine: Engine,
    store: GraphProjectionStore | None,
    authorize: TaskScopeAuthorizer,
    *,
    namespace: str = DEFAULT_GRAPH_NAMESPACE,
    max_events: int = 1000,
    max_pages: int = 10,
) -> GraphRuntimePolicy:
    """Root supplies a real store and current PG task authorizer; this factory opens no network."""
    GraphReconciliationRequest(
        namespace=namespace,
        generation_id=UUID(int=0),
        scope_epochs=(),
        max_events=max_events,
        max_pages=max_pages,
    )
    if store is None:
        return GraphRuntimePolicy(
            _blocked_graph_job,
            {
                GRAPH_RECONCILE_JOB_TYPE: _blocked_graph_job,
                GRAPH_CAPTURE_JOB_TYPE: _blocked_graph_job,
                GRAPH_APPLY_JOB_TYPE: _blocked_graph_job,
            },
        )

    def schedule_change(
        session: Session, context: JobExecutionContext, payload: bytes
    ) -> JobExecutionResult:
        try:
            change = find_projection_change(session, context)
            scope = _authorize_job(session, context, authorize)
            if change.scope_key != partition_for_scope(scope):
                raise PermissionDeniedError("graph job scope denied")
            epochs = read_projection_scope_epochs(session, scope)
            request = GraphReconciliationRequest(
                namespace=namespace,
                generation_id=graph_generation_id(namespace, partition_for_scope(scope), epochs),
                scope_epochs=epochs,
                max_events=max_events,
                max_pages=max_pages,
            )
            job_id = _enqueue_reconciliation(session, context.tenant_id, request, datetime.now(UTC))
        except PermissionError:
            raise JobExecutionError("graph_projection_scope_denied", blocked=True) from None
        except ProjectionNotReady:
            raise JobExecutionError("graph_projection_state_unavailable", blocked=True) from None
        return JobExecutionResult(
            "partial", "pg:job:" + job_id, "knowledge_change_other_consumers_pending"
        )

    def reconcile(context: JobExecutionContext, payload: bytes) -> JobExecutionResult:
        request = GraphReconciliationRequest.model_validate_json(payload)
        if request.namespace != namespace:
            raise JobExecutionError("graph_projection_namespace_denied", blocked=True)
        now = datetime.now(UTC)
        try:
            with Session(engine) as session, session.begin():
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                lock_identity = f"graph-reconcile:{request.namespace}:{request.generation_id}"
                lock_id = int.from_bytes(
                    hashlib.sha256(lock_identity.encode()).digest()[:8], "big", signed=True
                )
                if session.scalar(select(func.pg_try_advisory_xact_lock(lock_id))) is not True:
                    raise JobExecutionError("graph_reconciliation_busy", retry_after_seconds=5.0)
                deadline = time.monotonic() + 20.0
                scope = _authorize_job(session, context, authorize)
                _require_generation(session, scope, request)
                if request.page_number == 0:
                    manifest = begin_reconciliation(
                        session,
                        scope,
                        request.namespace,
                        request.generation_id,
                        now,
                        max_events=request.max_events,
                    )
                else:
                    manifest = read_reconciliation_manifest(
                        session,
                        scope,
                        request.namespace,
                        request.generation_id,
                    )
                if (
                    manifest.event_count > request.max_events
                    or manifest.page_count > request.max_pages
                ):
                    return JobExecutionResult(
                        "partial",
                        "pg:job:" + context.job_id,
                        "graph_reconciliation_budget_exhausted",
                    )
                if manifest.event_count == 0:
                    return JobExecutionResult(
                        result_ref="pg:graph_generation:" + str(request.generation_id)
                    )
                if request.page_number >= manifest.page_count:
                    raise JobExecutionError("graph_reconciliation_page_invalid", blocked=True)
                page = read_manifest_page(
                    session, scope, request.namespace, request.generation_id, request.page_number
                )
                if len(page.entries) > MANIFEST_PAGE_SIZE:
                    raise ProjectionCapacityError("graph_projection_capacity_exceeded")
                for entry in page.entries:
                    if time.monotonic() >= deadline:
                        raise JobExecutionError("graph_reconciliation_deadline_exceeded")
                    capture_request = GraphCaptureRequest(
                        namespace=request.namespace,
                        generation_id=request.generation_id,
                        scope_epochs=request.scope_epochs,
                        event_id=entry.event_id,
                    )
                    enqueue_job(
                        session,
                        context.tenant_id,
                        GRAPH_CAPTURE_JOB_TYPE,
                        capture_request.model_dump_json().encode(),
                        now,
                        idempotency_key=f"graph-capture:{request.generation_id}:{entry.event_id}",
                    )
                next_job_id = None
                if request.page_number + 1 < manifest.page_count:
                    next_request = request.model_copy(
                        update={"page_number": request.page_number + 1}
                    )
                    next_job_id = _enqueue_reconciliation(
                        session, context.tenant_id, next_request, now
                    )
                if time.monotonic() >= deadline:
                    raise JobExecutionError("graph_reconciliation_deadline_exceeded")
        except PermissionError:
            raise JobExecutionError("graph_projection_scope_denied", blocked=True) from None
        except ProjectionCapacityError:
            return JobExecutionResult(
                "partial", "pg:job:" + context.job_id, "graph_reconciliation_budget_exhausted"
            )
        except ProjectionNotReady:
            raise JobExecutionError("graph_projection_epoch_changed", blocked=True) from None
        except ProjectionDigestConflict:
            raise JobExecutionError("graph_projection_digest_conflict", blocked=True) from None
        return JobExecutionResult(
            "partial",
            "pg:job:" + next_job_id
            if next_job_id
            else "pg:graph_generation:" + str(request.generation_id),
            "graph_projection_children_pending",
        )

    def capture(context: JobExecutionContext, payload: bytes) -> JobExecutionResult:
        request = GraphCaptureRequest.model_validate_json(payload)
        if request.namespace != namespace:
            raise JobExecutionError("graph_projection_namespace_denied", blocked=True)
        try:
            with Session(engine) as session, session.begin():
                scope = _authorize_job(session, context, authorize)
                _require_generation(session, scope, request)

            def authorize_capture(session: Session) -> AccessScope:
                current = _authorize_job(session, context, authorize)
                _require_generation(session, current, request)
                return current

            batch = capture_event_projection(
                engine,
                scope,
                request.namespace,
                request.generation_id,
                request.event_id,
                authorize=authorize_capture,
                captured_at=datetime.now(UTC),
            )
        except PermissionError:
            raise JobExecutionError("graph_projection_scope_denied", blocked=True) from None
        except (ProjectionNotReady, GraphSnapshotChangedError):
            raise JobExecutionError("graph_projection_epoch_changed", blocked=True) from None
        except ProjectionCapacityError:
            raise JobExecutionError("graph_projection_capacity_exceeded", blocked=True) from None
        except ProjectionDigestConflict:
            raise JobExecutionError("graph_projection_digest_conflict", blocked=True) from None
        return JobExecutionResult(
            "partial", "pg:graph_batch:" + str(batch.batch_id), "graph_projection_apply_pending"
        )

    def authorize_apply(session: Session, context: JobExecutionContext) -> AccessScope:
        return _authorize_job(session, context, authorize)

    def guard_apply_batch(
        session: Session, scope: AccessScope, batch: GraphProjectionBatch
    ) -> None:
        if batch.namespace != namespace:
            raise JobExecutionError("graph_projection_namespace_denied", blocked=True)
        partition = partition_for_scope(scope)
        if batch.partition_key != partition:
            raise JobExecutionError("graph_projection_scope_denied", blocked=True)
        if batch.generation_id != graph_generation_id(namespace, partition, batch.scope_epochs):
            raise JobExecutionError("graph_projection_generation_denied", blocked=True)

    return GraphRuntimePolicy(
        schedule_change,
        {
            GRAPH_RECONCILE_JOB_TYPE: DetachedJobHandler(reconcile),
            GRAPH_CAPTURE_JOB_TYPE: DetachedJobHandler(capture),
            GRAPH_APPLY_JOB_TYPE: build_graph_apply_handler(
                store, authorize_apply, batch_guard=guard_apply_batch
            ),
        },
    )
