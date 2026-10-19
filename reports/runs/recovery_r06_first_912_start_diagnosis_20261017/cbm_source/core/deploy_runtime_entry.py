"""The original Celery app gains only owned stop and source row fences."""

from __future__ import annotations

from typing import TYPE_CHECKING

from authorization import verify_live_authorization
from run_binding import (
    QUEUE,
    REDIS_PREFIX,
    require_cumulative_producer_slot,
    validate_service_urls,
    verify_database_connection,
)

if TYPE_CHECKING:
    from celery import Celery


def load_owned_application() -> Celery:
    binding = verify_live_authorization()

    import os

    from owned_stop_watcher import install_owned_stop_watcher

    role = os.environ.get("DIANZI_OWNED_PROCESS_ROLE")
    if role not in ("worker", "beat"):
        raise RuntimeError("owned source process role required")

    from ai_intel.infrastructure.database import build_engine
    from ai_intel.infrastructure.settings import load_application_settings
    from sqlalchemy import text
    from task_fence import require_producer_slot

    settings = load_application_settings()
    if (
        not settings.source_polling_enabled
        or settings.data_mode != "live"
        or settings.content_store_backend != "minio"
    ):
        raise RuntimeError("live source configuration differs from reviewed scope")
    if settings.generation_api_key and settings.generation_api_key.get_secret_value():
        raise RuntimeError("model requests are not authorized")
    validate_service_urls(
        settings.database_url.get_secret_value() if settings.database_url else None,
        settings.redis_url.get_secret_value() if settings.redis_url else None,
    )
    fence_engine = build_engine(settings)
    with fence_engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        verify_database_connection(connection, binding)
    if role == "worker":
        install_owned_stop_watcher("worker")
    else:
        install_owned_stop_watcher("beat")

    from ai_intel.workers.runtime import celery_app, consume_job, poll_due_public_sources

    def owned_consume_job(job_id: str) -> dict[str, str]:
        require_producer_slot(fence_engine)
        require_cumulative_producer_slot(fence_engine, binding)
        return consume_job(job_id)

    def owned_poll_sources() -> dict[str, int | str]:
        require_producer_slot(fence_engine)
        require_cumulative_producer_slot(fence_engine, binding)
        return poll_due_public_sources()

    celery_app.tasks["ai_intel.jobs.execute"].run = owned_consume_job
    celery_app.tasks["ai_intel.sources.poll_due"].run = owned_poll_sources

    celery_app.conf.update(task_default_queue=QUEUE, task_default_routing_key=QUEUE)
    celery_app.conf.broker_transport_options = {
        **celery_app.conf.broker_transport_options,
        "global_keyprefix": REDIS_PREFIX,
    }
    if (
        celery_app.conf.task_default_queue != QUEUE
        or celery_app.conf.task_default_routing_key != QUEUE
        or celery_app.conf.broker_transport_options.get("global_keyprefix") != REDIS_PREFIX
    ):
        raise RuntimeError("actual Celery queue or prefix differs")
    return celery_app


if __name__ != "__main__":
    celery_app = load_owned_application()
else:
    verify_live_authorization()
