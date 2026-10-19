"""Independent second lock ordering: reader owns parents before writer begins."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
import time
from uuid import uuid4

from sqlalchemy import text
from test_r10_evidence_graph_pg import VERSION, graph_engine, publish_fact, publish_event
from test_r10_graph_validity_pg import client_for
import ai_intel.api.graph_routes as graph_routes


def test_response_bytes_are_built_before_waiting_parent_writer_commits(
    graph_engine, tmp_path, register_sensitive_failure_value, monkeypatch,
):
    event_id = uuid4()
    source = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [source])
    client, *_ = client_for(graph_engine, register_sensitive_failure_value)
    attempted = Event()
    completed = Event()
    state = {}
    response_class = graph_routes.JSONResponse

    def write_parent_then_epoch():
        with graph_engine.begin() as connection:
            attempted.set()
            connection.execute(text("UPDATE sources SET name=name WHERE source_id=:id"), {'id': source.source_id.value})
            connection.execute(text("UPDATE scope_epochs SET epoch=epoch+1 WHERE scope_key='public'"))
        completed.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        def serialize(*args, **kwargs):
            state['writer'] = pool.submit(write_parent_then_epoch)
            assert attempted.wait(2)
            time.sleep(0.2)
            assert not completed.is_set()
            response = response_class(*args, **kwargs)
            state['bytes_before_writer_commit'] = isinstance(response.body, bytes) and not completed.is_set()
            return response

        monkeypatch.setattr(graph_routes, 'JSONResponse', serialize)
        try:
            response = client.get(f'/v1/events/{event_id}/graph')
            assert response.status_code == 200
            state['writer'].result(timeout=7)
            assert completed.is_set() and state['bytes_before_writer_commit']
        finally:
            client.close()
    (Path(__file__).parent / 'serialization_lock_observation.json').write_text(json.dumps({'status': response.status_code, 'writer_committed': completed.is_set(), 'bytes_before_writer_commit': state['bytes_before_writer_commit'], 'data_mode': 'fixture'}, indent=2), encoding='utf-8')
