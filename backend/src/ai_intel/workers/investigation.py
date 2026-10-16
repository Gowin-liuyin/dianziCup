"""Dedicated investigations release claim locks before graph IO and own their completion."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.actor_references import ActorReference, actor_reference_from_payload
from ai_intel.api.authentication import InvalidCredentialsError, SessionExpiredError
from ai_intel.domain.access import CrossTenantAccessError, PermissionDeniedError
from ai_intel.infrastructure.database import build_engine
from ai_intel.infrastructure.settings import ApplicationSettings, load_application_settings
from ai_intel.investigation.graph_contracts import WorkflowBudget
from ai_intel.investigation.runtime import build_investigation_service
from ai_intel.investigation.workflow_service import (
    JOB_TYPE,
    InvestigationWorkflowService,
    WorkflowBusyError,
    WorkflowChangedError,
    investigation_workflows,
)
from ai_intel.knowledge.models import job_runs
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError
from ai_intel.workers.jobs import (
    JobLeaseLostError,
    JobPayloadUnavailableError,
    claim_job,
    read_job_payload,
    require_job_lease,
    schedule_retry_or_fail,
)

INVESTIGATION_TASK = "ai_intel.investigations.execute"
INVESTIGATION_QUEUE = "ai_intel_investigations"
INVESTIGATION_SOFT_LIMIT_SECONDS = 610
INVESTIGATION_HARD_LIMIT_SECONDS = 620
INVESTIGATION_VISIBILITY_TIMEOUT_SECONDS = 660
WorkflowServiceFactory = Callable[[ActorReference], InvestigationWorkflowService]


def execute_investigation_job(
    engine: Engine,
    job_id: str,
    worker_id: str,
    service_factory: WorkflowServiceFactory,
    *,
    pause_after: tuple[str, ...] = (),
) -> str:
    """Claim only investigation jobs, then let the PG workflow finalize exactly once.

    Interruption leaves the original deadline, reservations and expiring lease intact.
    PG retry/outbox is the only retry authority; the graph never gets a new budget.
    """
    UUID(job_id)
    with Session(engine) as session, session.begin():
        job_type = session.scalar(
            select(job_runs.c.job_type).where(job_runs.c.job_id == job_id).with_for_update()
        )
        if job_type != JOB_TYPE:
            return "not_claimed"
        claimed = claim_job(session, job_id, worker_id, datetime.now(UTC))
    if claimed is None:
        return "not_claimed"
    attempt = claimed["attempt_count"]
    tenant = claimed["tenant_id"]
    if type(attempt) is not int or (tenant is not None and not isinstance(tenant, str)):
        raise RuntimeError("invalid investigation job context")
    context = JobExecutionContext(job_id, worker_id, attempt, tenant)
    failure: JobExecutionError
    try:
        with Session(engine) as session, session.begin():
            require_job_lease(
                session, job_id, worker_id, datetime.now(UTC), expected_attempt=attempt
            )
            read_job_payload(session, job_id, tenant)
            stored = session.scalar(
                select(investigation_workflows.c.actor_reference).where(
                    investigation_workflows.c.job_id == job_id,
                    investigation_workflows.c.tenant_id.is_not_distinct_from(tenant),
                )
            )
            if not isinstance(stored, dict):
                raise JobExecutionError("investigation_owner_unavailable", blocked=True)
            actor = actor_reference_from_payload(stored)
        result = service_factory(actor).execute(context, pause_after=pause_after)
        if result.status == "running":
            return "running"
        with Session(engine) as session, session.begin():
            status = session.scalar(
                select(job_runs.c.status).where(
                    job_runs.c.job_id == job_id,
                    job_runs.c.job_type == JOB_TYPE,
                    job_runs.c.attempt_count == attempt,
                )
            )
        if status not in {"partial", "failed", "waiting_approval", "succeeded"}:
            raise JobLeaseLostError("investigation finalization unavailable")
        return str(status)
    except JobLeaseLostError:
        return "lease_lost"
    except (PermissionDeniedError, InvalidCredentialsError, SessionExpiredError):
        failure = JobExecutionError("investigation_authorization_changed", blocked=True)
    except CrossTenantAccessError:
        failure = JobExecutionError("investigation_owner_unavailable", blocked=True)
    except (WorkflowChangedError, JobPayloadUnavailableError, ValueError):
        failure = JobExecutionError("investigation_input_invalid", permanent=True)
    except WorkflowBusyError:
        failure = JobExecutionError("investigation_busy")
    except (TimeoutError, SoftTimeLimitExceeded):
        failure = JobExecutionError("investigation_execution_timeout")
    except SQLAlchemyError:
        failure = JobExecutionError("database_operation_failed")
    except JobExecutionError as error:
        failure = error
    except Exception:
        failure = JobExecutionError("investigation_execution_failed")
    try:
        with Session(engine) as session, session.begin():
            return schedule_retry_or_fail(
                session,
                job_id,
                worker_id,
                failure.permanent,
                datetime.now(UTC),
                expected_attempt=attempt,
                error_code=failure.error_code,
                blocked=failure.blocked,
            )
    except JobLeaseLostError:
        return "lease_lost"


def configure_investigation_task(application: Celery) -> None:
    """Register a distinct budget/queue without changing existing task limits or handlers."""
    application.conf.task_routes = {
        **(application.conf.task_routes or {}),
        INVESTIGATION_TASK: {"queue": INVESTIGATION_QUEUE},
    }
    application.task(
        name=INVESTIGATION_TASK,
        queue=INVESTIGATION_QUEUE,
        ignore_result=True,
        autoretry_for=(),
        soft_time_limit=INVESTIGATION_SOFT_LIMIT_SECONDS,
        time_limit=INVESTIGATION_HARD_LIMIT_SECONDS,
        acks_late=True,
        reject_on_worker_lost=True,
    )(consume_investigation_job)


def consume_investigation_job(job_id: str) -> dict[str, str]:
    """The server chooses worker identity; this entry has no arbitrary handler or credential."""
    UUID(job_id)
    settings = load_application_settings()
    engine = build_engine(settings)
    try:
        outcome = execute_investigation_job(
            engine,
            job_id,
            "investigation-" + uuid4().hex,
            lambda actor: build_investigation_service(engine, settings, actor),
        )
        return {"job_id": job_id, "outcome": outcome}
    except SQLAlchemyError:
        return {"job_id": job_id, "outcome": "delivery_unavailable"}
    finally:
        engine.dispose()


def investigation_task_for_event(event: dict[str, str]) -> str | None:
    """The existing relay may route this fixed topic; consumers still verify PG job type."""
    return INVESTIGATION_TASK if event.get("topic") == "job." + JOB_TYPE else None


def validate_investigation_worker_settings(settings: ApplicationSettings) -> None:
    """A dedicated process uses a visibility timeout longer than the original maximum budget."""
    if settings.database_url is None or settings.redis_url is None:
        raise ValueError("investigation worker requires configured PostgreSQL and Redis")
    if WorkflowBudget(total_seconds=600.0).total_seconds > INVESTIGATION_SOFT_LIMIT_SECONDS:
        raise RuntimeError("investigation worker budget is inconsistent")


def build_investigation_celery_application(settings: ApplicationSettings) -> Celery:
    """A separate queue/process retains the ordinary worker's existing 25/30-second limits."""
    validate_investigation_worker_settings(settings)
    if settings.redis_url is None:
        raise ValueError("investigation Redis is not configured")
    application = Celery(
        "ai_intel_investigations", broker=settings.redis_url.get_secret_value(), backend=None
    )
    application.conf.update(
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        task_ignore_result=True,
        task_store_errors_even_if_ignored=False,
        task_default_queue=INVESTIGATION_QUEUE,
        worker_concurrency=1,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        broker_connection_timeout=settings.dependency_timeout_seconds,
        broker_connection_retry_on_startup=False,
        broker_transport_options={
            "visibility_timeout": INVESTIGATION_VISIBILITY_TIMEOUT_SECONDS,
            "socket_timeout": 3,
        },
        enable_utc=True,
        timezone="UTC",
    )
    configure_investigation_task(application)
    return application


def main() -> None:
    """Only the dedicated fixed queue is consumed; deployment owns the process deadline."""
    application = build_investigation_celery_application(load_application_settings())
    application.worker_main(
        ["worker", "--queues=" + INVESTIGATION_QUEUE, "--concurrency=1", "--loglevel=WARNING"]
    )


if __name__ == "__main__":
    main()
