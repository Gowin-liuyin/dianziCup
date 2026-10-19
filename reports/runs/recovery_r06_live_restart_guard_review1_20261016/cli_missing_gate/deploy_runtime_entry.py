"""The original Celery app gains only owned stop and source row fences."""

from authorization import verify_live_authorization


def load_owned_application():
    verify_live_authorization()

    import os

    from owned_stop_watcher import install_owned_stop_watcher

    role = os.environ.get("DIANZI_OWNED_PROCESS_ROLE")
    if role == "worker":
        install_owned_stop_watcher("worker")
    elif role == "beat":
        install_owned_stop_watcher("beat")
    else:
        raise RuntimeError("owned source process role required")

    from ai_intel.infrastructure.database import build_engine
    from ai_intel.infrastructure.settings import load_application_settings
    from ai_intel.workers.runtime import celery_app, consume_job, poll_due_public_sources
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
    fence_engine = build_engine(settings)

    def owned_consume_job(job_id: str) -> dict[str, str]:
        require_producer_slot(fence_engine)
        return consume_job(job_id)

    def owned_poll_sources() -> dict[str, int | str]:
        require_producer_slot(fence_engine)
        return poll_due_public_sources()

    celery_app.tasks["ai_intel.jobs.execute"].run = owned_consume_job
    celery_app.tasks["ai_intel.sources.poll_due"].run = owned_poll_sources

    celery_app.conf.update(
        task_default_queue="r06_live_8a_20261016", task_default_routing_key="r06_live_8a_20261016"
    )
    celery_app.conf.broker_transport_options = {
        **celery_app.conf.broker_transport_options,
        "global_keyprefix": "r06-live-8a-20261016:",
    }
    return celery_app


if __name__ != "__main__":
    celery_app = load_owned_application()
else:
    verify_live_authorization()
