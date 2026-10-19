"""Bind the original Celery application to this segment's queue and Redis prefix."""

from common import PREFIX, QUEUE
from ai_intel.workers.runtime import celery_app

celery_app.conf.update(task_default_queue=QUEUE, task_default_routing_key=QUEUE)
celery_app.conf.broker_transport_options = {**celery_app.conf.broker_transport_options, "global_keyprefix": PREFIX}
