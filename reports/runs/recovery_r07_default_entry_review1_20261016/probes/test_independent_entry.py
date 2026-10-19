"""Independent negative cases use actual PG and default factory, with synthetic inputs."""

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend/tests/integration'))

from test_r07_enrichment_api_pg import application_client, execution_engine, worker_runtime
from test_r07_job_execution_pg import NOW, children, run, setup

from ai_intel.api.auth_routes import CSRF_HEADER_NAME
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy, EventEnrichmentRequest
from ai_intel.enrichment.job_models import enrichment_job_steps
from ai_intel.enrichment.job_service import ENRICHMENT_PARENT_JOB_TYPE
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import document_revisions, job_payloads, job_runs, users
from ai_intel.knowledge.persistence_models import events


@pytest.fixture
def isolated_test_database_url():
    from scripts.dev import require_isolated_test_database

    return require_isolated_test_database()


def workflow_result_count(engine):
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(enrichment_results).where(enrichment_results.c.publication_key.like('r07:%')))


@pytest.mark.parametrize('mutation', ['role', 'source_version'])
def test_actual_registered_worker_blocks_changed_input_before_child(execution_engine, tmp_path, monkeypatch, mutation):
    service, scope, _, _, _, receipt = setup(execution_engine, tmp_path)
    runtime = worker_runtime(execution_engine, tmp_path, monkeypatch)
    assert runtime.consume_job(str(receipt.parent_job_id))['outcome'] == 'succeeded'
    child = next(item for item in children(service) if item['dimension'] == 'cvss')
    with execution_engine.begin() as connection:
        if mutation == 'role':
            connection.execute(update(users).where(users.c.user_id == scope.user_id).values(role='tenant_admin', tenant_id='independent-role-change'))
        else:
            connection.execute(update(document_revisions).values(normalizer_version='independent-source-v2', source_metadata={'version_label': 'independent-source-v2'}))
    assert runtime.consume_job(child['job_id'])['outcome'] == 'blocked'
    assert workflow_result_count(execution_engine) == 0
    with execution_engine.connect() as connection:
        step = connection.execute(select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child['job_id'])).mappings().one()
        assert step['result_payload'] is None and step['model_call_reserved_at'] is None


@pytest.mark.parametrize('extra', [{'tenant_id': 'forged'}, {'source_url': 'http://127.0.0.1/'}, {'binding_sha256': 'a' * 64}])
def test_forged_queue_payload_never_creates_children(execution_engine, tmp_path, monkeypatch, extra):
    _, _, _, _, _, receipt = setup(execution_engine, tmp_path)
    with execution_engine.begin() as connection:
        payload = json.loads(bytes(connection.scalar(select(job_payloads.c.payload).where(job_payloads.c.job_id == str(receipt.parent_job_id)))))
        payload.update(extra)
        raw = json.dumps(payload).encode()
        connection.execute(update(job_payloads).where(job_payloads.c.job_id == str(receipt.parent_job_id)).values(payload=raw))
        connection.execute(update(job_runs).where(job_runs.c.job_id == str(receipt.parent_job_id)).values(payload_sha256=hashlib.sha256(raw).hexdigest()))
    runtime = worker_runtime(execution_engine, tmp_path, monkeypatch)
    assert runtime.consume_job(str(receipt.parent_job_id))['outcome'] == 'blocked'
    with execution_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(enrichment_job_steps)) == 0
        assert connection.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == str(receipt.parent_job_id))) in {'invalid_job_payload', 'enrichment_workflow_binding_invalid'}
    assert workflow_result_count(execution_engine) == 0


def test_reservation_replay_only_one_claims_no_new_result(execution_engine, tmp_path):
    service, _, _, _, _, receipt = setup(execution_engine, tmp_path)
    assert run(service, receipt.parent_job_id) == 'succeeded'
    child = next(item for item in children(service) if item['dimension'] == 'versions')
    with ThreadPoolExecutor(max_workers=3) as workers:
        observed = list(workers.map(lambda _: service._reserve_model_call(child['job_id'], NOW), range(3)))
    assert sorted(observed) == [False, False, True]
    assert workflow_result_count(execution_engine) == 0
    with execution_engine.connect() as connection:
        saved = connection.execute(select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child['job_id'])).mappings().one()
        assert saved['model_call_reserved_at'] == NOW and saved['model_call_completed_at'] is None and saved['model_trace'] == []


def test_private_server_egress_denial_remains_before_client_factory(execution_engine, tmp_path):
    from ai_intel.domain.access import AccessScope, Role

    policy = EnrichmentExecutionPolicy(generation_enabled=True, generation_provider='openai', approved_model='fixture-model', data_mode='fixture')
    service, public_scope, session_hash, event_id, _, _ = setup(execution_engine, tmp_path, policy=policy)
    private = AccessScope.for_authenticated_user(public_scope.user_id, 'independent-private-owner', Role.TENANT_ADMIN)
    with execution_engine.begin() as connection:
        connection.execute(update(users).where(users.c.user_id == private.user_id).values(role='tenant_admin', tenant_id=private.tenant_id))
        connection.execute(update(events).where(events.c.event_id == str(event_id)).values(visibility='tenant', tenant_id=private.tenant_id))
    with Session(execution_engine) as session, session.begin():
        receipt = service.enqueue(session, private, event_id, EventEnrichmentRequest(expected_event_version=1, dimensions=('versions',)), actor_session_hash=session_hash, idempotency_key='independent-private-egress', created_at=NOW)
    def forbidden():
        raise AssertionError('private egress denial must happen before factory')
    service.generation_client_factory = forbidden
    assert run(service, receipt.parent_job_id) == 'succeeded'
    child = next(item for item in children(service) if item['workflow_id'] == str(receipt.workflow_id) and item['dimension'] == 'versions')
    assert run(service, child['job_id']) == 'blocked'
    with execution_engine.connect() as connection:
        assert connection.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == child['job_id'])) == 'model_egress_denied'
        assert connection.scalar(select(enrichment_job_steps.c.model_call_reserved_at).where(enrichment_job_steps.c.job_id == child['job_id'])) is None


@pytest.mark.parametrize('prefix', ['/v1', '/api/v1'])
def test_default_graph_current_scope_and_asset_role_denial(execution_engine, tmp_path, prefix):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    with application_client(execution_engine, tmp_path, scope) as client:
        assert client.get(prefix + f'/events/{event_id}/graph').status_code == 200
        with execution_engine.begin() as connection:
            connection.execute(update(events).where(events.c.event_id == str(event_id)).values(visibility='tenant', tenant_id='independent-secret-tenant'))
            connection.execute(update(users).where(users.c.user_id == scope.user_id).values(role='viewer', tenant_id='independent-viewer-tenant'))
        assert client.get(prefix + f'/events/{event_id}/graph').status_code == 404
        assert client.get(prefix + '/assets').status_code == 403
        response = client.post(prefix + '/asset-snapshots', json={'tenant_id': 'forged', 'snapshot': {}}, headers={'origin': 'http://127.0.0.1:25173', CSRF_HEADER_NAME: 'synthetic-csrf', 'Idempotency-Key': 'independent-viewer-import'})
        assert response.status_code == 403


def test_source_job_admin_only_and_private_workflow_crossscope_denial(execution_engine, tmp_path):
    from ai_intel.domain.access import AccessScope, Role
    from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE

    service, scope, session_hash, event_id, _, _ = setup(execution_engine, tmp_path)
    with Session(execution_engine) as session, session.begin():
        source_job = enqueue_job(session, None, SOURCE_JOB_TYPE, b'{}', NOW)
    with application_client(execution_engine, tmp_path, scope) as client:
        assert client.get('/v1/jobs/' + source_job).status_code == 200
        with execution_engine.begin() as connection:
            connection.execute(update(users).where(users.c.user_id == scope.user_id).values(role='tenant_admin', tenant_id='independent-workflow-owner'))
            connection.execute(update(events).where(events.c.event_id == str(event_id)).values(visibility='tenant', tenant_id='independent-workflow-owner'))
        private = AccessScope.for_authenticated_user(scope.user_id, 'independent-workflow-owner', Role.TENANT_ADMIN)
        with Session(execution_engine) as session, session.begin():
            receipt = service.enqueue(session, private, event_id, EventEnrichmentRequest(expected_event_version=1, dimensions=('cvss',)), actor_session_hash=session_hash, idempotency_key='independent-private-reader', created_at=NOW)
        assert client.get('/v1/jobs/' + str(receipt.parent_job_id)).status_code == 200
        assert client.get('/v1/jobs/' + source_job).status_code == 403
        with execution_engine.begin() as connection:
            connection.execute(update(users).where(users.c.user_id == scope.user_id).values(tenant_id='independent-other-tenant'))
        assert client.get('/v1/enrichment-workflows/' + str(receipt.workflow_id)).status_code == 404
        assert client.get('/v1/jobs/' + str(receipt.parent_job_id)).status_code == 403
