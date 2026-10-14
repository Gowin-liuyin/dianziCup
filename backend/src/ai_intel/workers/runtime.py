"""真实Redis/Celery运行入口；PG记录执行观测，不使用Celery结果作为真相。"""

from datetime import UTC, datetime

from celery import Celery
from celery.beat import PersistentScheduler
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.infrastructure.database import build_engine
from ai_intel.infrastructure.runtime_observations import record_runtime_observation
from ai_intel.infrastructure.settings import ConfigurationError, load_application_settings


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
            "observe-worker": {
                "task": "ai_intel.runtime.observe_worker",
                "schedule": 10.0,
                "options": {"expires": 20},
            }
        },
    )
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


def observe_worker() -> dict[str, str]:
    """Celery实际消费后记录worker，不以调度发送或导入成功冒充执行。"""
    return observe_runtime_component("worker")


celery_app.task(name="ai_intel.runtime.observe_worker", ignore_result=True)(observe_worker)
