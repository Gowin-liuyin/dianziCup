"""Route only this run's actual worker and beat to its isolated Redis queue."""

from ai_intel.workers.runtime import celery_app

celery_app.conf.update(task_default_queue="r06_integrated_live_1156", task_default_routing_key="r06_integrated_live_1156")
celery_app.conf.broker_transport_options = {
    **celery_app.conf.broker_transport_options,
    "global_keyprefix": "r06-integrated-live-1156:",
}
