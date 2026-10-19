"""Route the frozen Celery application into this observation's isolated queue."""

from ai_intel.workers.runtime import celery_app

celery_app.conf.update(task_default_queue="gb_collection_1927", task_default_routing_key="gb_collection_1927")
