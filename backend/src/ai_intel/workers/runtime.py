"""真实Redis/Celery运行入口；PG记录执行观测，不使用Celery结果作为真相。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from celery import Celery
from celery.beat import PersistentScheduler
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.job_handlers import make_enrichment_job_handlers
from ai_intel.enrichment.runtime_policy import build_enrichment_job_service
from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.database import build_engine
from ai_intel.infrastructure.outbox import relay_pending_events
from ai_intel.infrastructure.runtime_observations import record_runtime_observation
from ai_intel.infrastructure.settings import ConfigurationError, load_application_settings
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, build_source_page_handler
from ai_intel.ingestion.source_polling import enqueue_due_source_collections
from ai_intel.workers.executor import JobHandler, execute_job, record_source_fetch_failure
from ai_intel.workers.jobs import recover_expired_job_deliveries


def build_celery_application() -> Celery:
    """缺PG/Redis配置立即失败；仅JSON任务、单队列、受控并发与超时。"""
    settings = load_application_settings()
    if settings.database_url is None or settings.redis_url is None:
        raise ConfigurationError("DATABASE_URL and REDIS_URL are required for workers")
    application = Celery("ai_intel", broker=settings.redis_url.get_secret_value(), backend=None)
    application.conf.update(
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        task_ignore_result=True,
        task_store_errors_even_if_ignored=False,
        task_default_queue="ai_intel",
        worker_concurrency=1,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_soft_time_limit=25,
        task_time_limit=30,
        broker_connection_timeout=settings.dependency_timeout_seconds,
        broker_connection_retry_on_startup=False,
        broker_transport_options={"visibility_timeout": 120, "socket_timeout": 3},
        enable_utc=True,
        timezone="UTC",
        beat_max_loop_interval=10,
        beat_scheduler="ai_intel.workers.runtime:ObservedScheduler",
        beat_schedule={
            "dispatch-durable-jobs": {
                "task": "ai_intel.jobs.dispatch_pending",
                "schedule": 5.0,
                "options": {"expires": 10},
            },
            "observe-worker": {
                "task": "ai_intel.runtime.observe_worker",
                "schedule": 10.0,
                "options": {"expires": 20},
            },
        },
    )
    if settings.source_polling_enabled:
        application.conf.beat_schedule["poll-public-sources"] = {
            "task": "ai_intel.sources.poll_due",
            "schedule": 60.0,
            "options": {"expires": 120},
        }
    return application


def observe_runtime_component(component: str) -> dict[str, str]:
    """运行进程完成实际PG查询再提交观测；失败只返回固定错误类别。"""
    engine = build_engine(load_application_settings())
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
        record_runtime_observation(engine, component, datetime.now(UTC))
        return {"component": component, "state": "observed"}
    except SQLAlchemyError:
        raise RuntimeError("runtime database unavailable") from None
    finally:
        engine.dispose()


class ObservedScheduler(PersistentScheduler):
    """复用Celery持久化调度器；每次实际tick完成后提交scheduler观测。"""

    def tick(self) -> float:
        delay = super().tick()
        observe_runtime_component("scheduler")
        return float(delay)


celery_app = build_celery_application()
source_settings = load_application_settings()
EXECUTION_HANDLERS: dict[str, JobHandler] = {
    "record_source_fetch_failure": record_source_fetch_failure,
    SOURCE_JOB_TYPE: build_source_page_handler(
        build_content_storage(source_settings), dns_resolver=source_settings.dns_resolver
    ),
}


def publish_job_event(event: dict[str, str]) -> None:
    """消息只含UUID，topic不决定可执行函数；禁用broker额外重试。"""
    job_id = str(UUID(event["job_id"]))
    celery_app.send_task("ai_intel.jobs.execute", args=[job_id], retry=False)


def dispatch_pending_jobs() -> dict[str, int]:
    """实际beat经PG到期时间投递，恢复死亡worker不读取Celery业务结果。"""
    engine = build_engine(load_application_settings())
    try:
        with Session(engine) as session, session.begin():
            recovered = recover_expired_job_deliveries(session, datetime.now(UTC))
            released = relay_pending_events(session, datetime.now(UTC), publisher=publish_job_event)
        return {"published": len(released), "recovered": recovered}
    except SQLAlchemyError:
        raise RuntimeError("runtime database unavailable") from None
    finally:
        engine.dispose()


def consume_job(job_id: str) -> dict[str, str]:
    """实际Celery消费受控handler；worker身份不由队列请求参数提供。"""
    UUID(job_id)
    settings = load_application_settings()
    engine = build_engine(settings)
    try:
        handlers = dict(EXECUTION_HANDLERS)
        enrichment = build_enrichment_job_service(engine, settings)
        if enrichment is not None:
            handlers.update(make_enrichment_job_handlers(enrichment))
        outcome = execute_job(engine, job_id, "celery-" + uuid4().hex, handlers)
        return {"job_id": job_id, "outcome": outcome}
    except SQLAlchemyError:
        raise RuntimeError("runtime database unavailable") from None
    finally:
        engine.dispose()


def observe_worker() -> dict[str, str]:
    """Celery实际消费后记录worker，不以调度发送或导入成功冒充执行。"""
    return observe_runtime_component("worker")


def poll_due_public_sources() -> dict[str, int | str]:
    """Trusted opt-in schedules only fixed public sources; disabled runs never connect PG."""
    settings = load_application_settings()
    if not settings.source_polling_enabled:
        return {"state": "disabled", "queued": 0}
    engine = build_engine(settings)
    try:
        scope = AccessScope.for_authenticated_user("source-poller", None, Role.SYSTEM_ADMIN)
        with Session(engine) as session, session.begin():
            result = enqueue_due_source_collections(session, scope, datetime.now(UTC))
        return {
            "state": "scheduled",
            "queued": len(result.queued_job_ids),
            "already_scheduled": result.already_scheduled,
            "busy": len(result.busy_sources),
        }
    except SQLAlchemyError:
        raise RuntimeError("source polling database unavailable") from None
    finally:
        engine.dispose()


celery_app.task(name="ai_intel.runtime.observe_worker", ignore_result=True)(observe_worker)
celery_app.task(name="ai_intel.jobs.execute", ignore_result=True, autoretry_for=())(consume_job)
celery_app.task(name="ai_intel.jobs.dispatch_pending", ignore_result=True)(dispatch_pending_jobs)
celery_app.task(name="ai_intel.sources.poll_due", ignore_result=True, autoretry_for=())(
    poll_due_public_sources
)
