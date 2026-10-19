"""Default HTTP and registered worker exercise private legacy and canonical route boundaries."""

import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend/tests/integration'))

from test_r07_enrichment_api_pg import ORIGIN, application_client, execution_engine, worker_runtime
from test_r07_job_execution_pg import NOW, setup

from ai_intel.api.auth_routes import CSRF_HEADER_NAME
from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.job_contracts import EventEnrichmentRequest
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import ENRICHMENT_PARENT_JOB_TYPE, RULE_VERSION, _digest
from ai_intel.enrichment.job_types import EnrichmentJobPayload, json_payload
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import job_runs, users
from ai_intel.knowledge.persistence_models import events


@pytest.fixture
def isolated_test_database_url():
    from scripts.dev import require_isolated_test_database

    return require_isolated_test_database()


def post(client, event, key, dimensions, prefix='/v1'):
    return client.post(prefix + f'/events/{event}/enrichment-jobs', json={'expected_event_version': 1, 'dimensions': dimensions}, headers={'origin': ORIGIN, CSRF_HEADER_NAME: 'synthetic-csrf', 'Idempotency-Key': key})


def test_uppercase_event_id_and_alias_canonicalize_to_the_same_operation(execution_engine, tmp_path):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    with application_client(execution_engine, tmp_path, scope) as client:
        first = post(client, event_id, 'independent-uppercase-key', ['cvss'])
        replay = post(client, str(event_id).upper(), 'independent-uppercase-key', ['cvss'], '/api/v1')
        assert first.status_code == replay.status_code == 202
        assert replay.json()['reused'] is True
        assert replay.json()['parent_job_id'] == first.json()['parent_job_id']


@pytest.mark.parametrize('tenant', ['independent-private-legacy-owner', 'public'])
def test_private_legacy_exact_http_replay_keeps_worker_reservation(execution_engine, tmp_path, monkeypatch, tenant):
    service, initial_scope, session_hash, event_id, _, _ = setup(execution_engine, tmp_path)
    with execution_engine.begin() as connection:
        connection.execute(update(users).where(users.c.user_id == initial_scope.user_id).values(role='tenant_admin', tenant_id=tenant))
        connection.execute(update(events).where(events.c.event_id == str(event_id)).values(visibility='tenant', tenant_id=tenant))
    scope = AccessScope.for_authenticated_user(initial_scope.user_id, tenant, Role.TENANT_ADMIN)
    request = EventEnrichmentRequest(expected_event_version=1, dimensions=('versions',))
    raw_key = 'independent-private-legacy-key'
    workflow = uuid5(NAMESPACE_URL, 'ai-intel:enrichment:' + repr((tenant, raw_key)))
    policy = service.execution_policy()
    binding = {'event_id': str(event_id), 'actor_user_id': scope.user_id, 'actor_session_hash': session_hash, 'actor_tenant_id': tenant, 'actor_role': scope.role.value, 'actor_permission_version': scope.permission_version, 'request_sha256': _digest(request.model_dump(mode='json')), 'execution_policy_sha256': _digest(policy.model_dump(mode='json')), 'rule_version': RULE_VERSION}
    with Session(execution_engine) as session, session.begin():
        parent = enqueue_job(session, tenant, ENRICHMENT_PARENT_JOB_TYPE, json_payload(EnrichmentJobPayload(workflow_id=workflow, binding_sha256=_digest(binding))), NOW, idempotency_key=raw_key, max_attempts=3)
        session.execute(insert(enrichment_workflows).values(**binding, workflow_id=str(workflow), parent_job_id=parent, visibility='tenant', tenant_id=tenant, request_payload=request.model_dump(mode='json'), execution_policy=policy.model_dump(mode='json'), created_at=NOW))
    runtime = worker_runtime(execution_engine, tmp_path, monkeypatch)
    with application_client(execution_engine, tmp_path, scope) as client:
        first = post(client, event_id, raw_key, ['versions'])
        assert first.status_code == 202 and first.json()['reused'] is True
        assert first.json()['workflow_id'] == str(workflow) and first.json()['parent_job_id'] == parent
        assert runtime.consume_job(parent)['outcome'] == 'succeeded'
        with execution_engine.connect() as connection:
            child = connection.scalar(select(enrichment_job_steps.c.job_id).where(enrichment_job_steps.c.workflow_id == str(workflow), enrichment_job_steps.c.dimension == 'versions'))
        assert service._reserve_model_call(child, NOW)
        with execution_engine.connect() as connection:
            before = dict(connection.execute(select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child)).mappings().one())
            original_job_ids = set(connection.scalars(select(job_runs.c.job_id)))
        replay = post(client, event_id, raw_key, ['versions'], '/api/v1')
        assert replay.status_code == 202 and replay.json()['reused'] is True
        assert replay.json()['workflow_id'] == str(workflow) and replay.json()['parent_job_id'] == parent
        assert service._reserve_model_call(child, NOW) is False
        with execution_engine.connect() as connection:
            assert dict(connection.execute(select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child)).mappings().one()) == before
            assert set(connection.scalars(select(job_runs.c.job_id))) == original_job_ids


def test_corrupt_v2_pg_reference_rejects_replay_without_another_parent(execution_engine, tmp_path):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    with application_client(execution_engine, tmp_path, scope) as client:
        first = post(client, event_id, 'independent-v2-corrupt-reference', ['cvss'])
        assert first.status_code == 202
        parent = first.json()['parent_job_id']
        with execution_engine.begin() as connection:
            original_job_ids = set(connection.scalars(select(job_runs.c.job_id)))
            connection.execute(update(job_runs).where(job_runs.c.job_id == parent).values(payload_ref='pg:job:' + str(uuid4())))
        replay = post(client, event_id, 'independent-v2-corrupt-reference', ['cvss'])
        assert replay.status_code == 409 and replay.json()['error']['code'] == 'idempotency_conflict'
        with execution_engine.connect() as connection:
            assert set(connection.scalars(select(job_runs.c.job_id))) == original_job_ids
