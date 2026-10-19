"""Explicit offline source fixture for real isolated beat/worker process review."""

import json
import os
import sys
from pathlib import Path

assert os.environ['APP_ENV']=='test' and os.environ['DATA_MODE']=='fixture'

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, SourcePageRequest, build_source_page_handler
from ai_intel.workers.executor import JobExecutionError
from ai_intel.workers.runtime import celery_app, EXECUTION_HANDLERS

assert SOURCE_JOB_TYPE in EXECUTION_HANDLERS
assert 'ai_intel.sources.poll_due' in celery_app.tasks
expected=os.environ['SOURCE_POLLING_ENABLED']=='true'
assert ('poll-public-sources' in celery_app.conf.beat_schedule)==expected
if expected:
    assert celery_app.conf.beat_schedule['poll-public-sources']['schedule']==60.0
print(json.dumps({'default_source_handler_registered':True,'poll_task_registered':True,'automatic_schedule':expected,'fixture_transport':True}),flush=True)


def offline_read(url):
    raise AssertionError('GET transport is outside the selected fixture source')


def offline_post(url,body):
    assert url=='https://api.osv.dev/v1/query'
    assert json.loads(body)=={'package':{'ecosystem':'Go','name':'github.com/ollama/ollama'}}
    return FetchResult(url,200,'application/json',b'{"vulns":[]}')


source_handler=build_source_page_handler(ContentStore(Path(os.environ['RAW_CONTENT_DIRECTORY'])),fetcher=offline_read,poster=offline_post)


def selected_fixture_source(session,context,payload):
    request=SourcePageRequest.model_validate_json(payload)
    if request.source_kind!='osv_ollama':
        raise JobExecutionError('fixture_unselected_source',blocked=True)
    return source_handler(session,context,payload)


EXECUTION_HANDLERS[SOURCE_JOB_TYPE]=selected_fixture_source
celery_app.conf.task_default_queue=os.environ['REVIEW_QUEUE']
celery_app.conf.broker_transport_options['global_keyprefix']=os.environ['REVIEW_BROKER_PREFIX']
celery_app.start(sys.argv[1:])
