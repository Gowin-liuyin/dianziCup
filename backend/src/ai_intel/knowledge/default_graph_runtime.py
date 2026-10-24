"""Compose durable graph dispatch with the existing hybrid consumer and bounded Neo4j IO."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from neo4j import AsyncGraphDatabase
from neo4j.exceptions import DriverError, Neo4jError
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope, Role
from ai_intel.infrastructure.neo4j_projection import (
    Neo4jProjectionStore,
    require_synchronous_projection_context,
)
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.graph_projection import (
    GRAPH_APPLY_JOB_TYPE,
    GraphProjectionBatch,
    GraphProjectionStore,
    ProjectionReceipt,
)
from ai_intel.knowledge.graph_runtime_policy import (
    DEFAULT_GRAPH_NAMESPACE,
    GRAPH_CAPTURE_JOB_TYPE,
    GRAPH_RECONCILE_JOB_TYPE,
    GraphRuntimePolicy,
    build_graph_runtime_policy,
)
from ai_intel.retrieval.runtime_policy import (
    KNOWLEDGE_CHANGE_JOB_TYPE,
    build_projection_job_handlers,
)
from ai_intel.workers.executor import (
    DetachedJobHandler,
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
    JobHandler,
)
from ai_intel.workers.jobs import JobLeaseLostError, read_job_payload, require_job_lease


class _SchemaInitializedProjectionStore(Neo4jProjectionStore):
    """Schema IO follows PG batch authorization and occurs only during a real apply."""

    schema_initialized = False

    def apply_batch(self, batch: GraphProjectionBatch, digest: str) -> ProjectionReceipt:
        if batch.namespace != DEFAULT_GRAPH_NAMESPACE:
            raise JobExecutionError("graph_projection_namespace_denied", blocked=True)
        try:
            if not self.schema_initialized:
                self.initialize_schema()
                self.schema_initialized = True
            return super().apply_batch(batch, digest)
        except (DriverError, Neo4jError, OSError):
            raise JobExecutionError("graph_projection_unavailable") from None


def _database_time(session: Session) -> datetime:
    now = session.scalar(select(func.clock_timestamp()))
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise RuntimeError("database clock violates execution contract")
    return now


def _authorize_task(
    session: Session,
    context: JobExecutionContext,
    payload: bytes,
    job_type: str,
) -> AccessScope:
    """Bind a minimal service scope to the locked canonical job, lease and exact payload."""
    if (
        type(context.attempt_count) is not int
        or not 1 <= context.attempt_count <= 10
        or not isinstance(context.job_id, str)
        or not isinstance(context.worker_id, str)
        or not context.worker_id.strip()
        or len(context.worker_id) > 200
        or not isinstance(payload, bytes)
        or (
            context.tenant_id is not None
            and (
                not isinstance(context.tenant_id, str)
                or not context.tenant_id.strip()
                or len(context.tenant_id) > 200
            )
        )
    ):
        raise JobExecutionError("graph_projection_context_invalid", blocked=True)
    try:
        if str(UUID(context.job_id)) != context.job_id:
            raise ValueError
    except ValueError:
        raise JobExecutionError("graph_projection_context_invalid", blocked=True) from None
    row = require_job_lease(
        session,
        context.job_id,
        context.worker_id,
        _database_time(session),
        expected_attempt=context.attempt_count,
    )
    expires_at = row["lease_expires_at"]
    if (
        not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or expires_at <= _database_time(session)
    ):
        raise JobLeaseLostError("job lease unavailable")
    if row["job_type"] != job_type or row["tenant_id"] != context.tenant_id:
        raise JobExecutionError("graph_projection_scope_denied", blocked=True)
    if read_job_payload(session, context.job_id, context.tenant_id) != payload:
        raise JobExecutionError("graph_projection_payload_changed", blocked=True)
    permissions = frozenset({READ_PUBLIC})
    role = Role.VIEWER
    if context.tenant_id is not None:
        permissions = frozenset({READ_PUBLIC, READ_ASSET})
        role = Role.ANALYST
    return AccessScope(context.worker_id, context.tenant_id, role, permissions)


def _bound_policy(
    engine: Engine,
    store: GraphProjectionStore | None,
    payload: bytes,
    job_type: str,
) -> GraphRuntimePolicy:
    def authorize(session: Session, current: JobExecutionContext) -> AccessScope:
        return _authorize_task(session, current, payload, job_type)

    return build_graph_runtime_policy(engine, store, authorize)


def _graph_handler(
    engine: Engine, store: GraphProjectionStore | None, job_type: str
) -> JobHandler | DetachedJobHandler:
    if store is None or job_type == GRAPH_APPLY_JOB_TYPE:

        def apply(
            session: Session, context: JobExecutionContext, payload: bytes
        ) -> JobExecutionResult:
            handler = _bound_policy(engine, store, payload, job_type).job_handlers[job_type]
            if isinstance(handler, DetachedJobHandler):
                raise RuntimeError("graph apply handler violates execution contract")
            return handler(session, context, payload)

        return apply

    def run(context: JobExecutionContext, payload: bytes) -> JobExecutionResult:
        handler = _bound_policy(engine, store, payload, job_type).job_handlers[job_type]
        if not isinstance(handler, DetachedJobHandler):
            raise RuntimeError("graph detached handler violates execution contract")
        return handler.handler(context, payload)

    def guard(
        session: Session, context: JobExecutionContext, payload: bytes, result: JobExecutionResult
    ) -> None:
        _authorize_task(session, context, payload, job_type)

    return DetachedJobHandler(run, completion_guard=guard)


def _knowledge_change_handler(
    engine: Engine, store: GraphProjectionStore, hybrid: JobHandler
) -> DetachedJobHandler:
    def project_change(context: JobExecutionContext, payload: bytes) -> JobExecutionResult:
        with Session(engine) as session, session.begin():
            policy = _bound_policy(engine, store, payload, KNOWLEDGE_CHANGE_JOB_TYPE)
            policy.knowledge_change_handler(session, context, payload)
        with Session(engine) as session, session.begin():
            _authorize_task(session, context, payload, KNOWLEDGE_CHANGE_JOB_TYPE)
            return hybrid(session, context, payload)

    def guard(
        session: Session, context: JobExecutionContext, payload: bytes, result: JobExecutionResult
    ) -> None:
        _authorize_task(session, context, payload, KNOWLEDGE_CHANGE_JOB_TYPE)

    return DetachedJobHandler(project_change, completion_guard=guard)


@contextmanager
def build_default_graph_job_handlers(
    engine: Engine, settings: ApplicationSettings
) -> Iterator[dict[str, JobHandler | DetachedJobHandler]]:
    """Driver construction has no network IO; only authorized graph apply initializes schema."""
    with build_projection_job_handlers(engine, settings) as hybrid_handlers:
        driver = None
        try:
            store = None
            if settings.neo4j_uri is not None:
                require_synchronous_projection_context()
                if settings.neo4j_username is None or settings.neo4j_password is None:
                    raise RuntimeError("graph settings violate execution contract")
                origin = urlsplit(settings.neo4j_uri)
                if origin.hostname is None:
                    raise RuntimeError("graph settings violate execution contract")
                timeout = settings.dependency_timeout_seconds
                driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password.get_secret_value()),
                    max_connection_pool_size=2,
                    connection_timeout=timeout,
                    connection_write_timeout=timeout,
                    connection_acquisition_timeout=timeout,
                    liveness_check_timeout=timeout,
                    max_transaction_retry_time=0.0,
                    telemetry_disabled=True,
                )
                store = _SchemaInitializedProjectionStore(
                    driver,
                    timeout_seconds=timeout,
                    dns_origin=(origin.hostname, origin.port or 7687),
                )
            handlers: dict[str, JobHandler | DetachedJobHandler] = dict(hybrid_handlers)
            if store is not None:
                handlers[KNOWLEDGE_CHANGE_JOB_TYPE] = _knowledge_change_handler(
                    engine, store, hybrid_handlers[KNOWLEDGE_CHANGE_JOB_TYPE]
                )
            for job_type in (
                GRAPH_RECONCILE_JOB_TYPE,
                GRAPH_CAPTURE_JOB_TYPE,
                GRAPH_APPLY_JOB_TYPE,
            ):
                handlers[job_type] = _graph_handler(engine, store, job_type)
            yield handlers
        finally:
            if store is not None:
                store.close_driver()
