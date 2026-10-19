"""Route only this run's actual worker and beat to its isolated Redis queue."""

from ai_intel.workers.runtime import celery_app

celery_app.conf.update(task_default_queue="r06_document_live_0a45185", task_default_routing_key="r06_document_live_0a45185")
