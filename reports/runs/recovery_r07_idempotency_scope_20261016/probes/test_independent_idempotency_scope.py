"""Distinct authenticated subjects and event routes have distinct idempotency scopes."""

import hashlib
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend/tests/integration'))

from test_r07_enrichment_api_pg import ORIGIN, application_client, execution_engine
from test_r07_job_execution_pg import NOW, setup

from ai_intel.api.auth_routes import CSRF_HEADER_NAME
from ai_intel.api.auth_state import auth_sessions
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.knowledge.event_linking import EventRepository, EventSubmission
from ai_intel.knowledge.models import users


@pytest.fixture
def isolated_test_database_url():
    from scripts.dev import require_isolated_test_database

    return require_isolated_test_database()


def enqueue(client, event_id):
    return client.post(f'/v1/events/{event_id}/enrichment-jobs', json={'expected_event_version': 1, 'dimensions': ['cvss']}, headers={'origin': ORIGIN, CSRF_HEADER_NAME: 'synthetic-csrf', 'Idempotency-Key': 'same-client-key-different-scope'})


def test_two_authorized_public_actors_can_use_their_own_same_key(execution_engine, tmp_path):
    _, first_scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    actor = str(uuid4())
    second_scope = AccessScope.for_authenticated_user(actor, None, Role.SYSTEM_ADMIN)
    with execution_engine.begin() as connection:
        connection.execute(insert(users).values(user_id=actor, username='independent-public-admin-' + actor, password_hash='unusable synthetic hash', role='system_admin', tenant_id=None, created_at=NOW))
        connection.execute(insert(auth_sessions).values(session_hash=hashlib.sha256(('synthetic-r07-session:' + actor).encode()).hexdigest(), user_id=actor, csrf_token='synthetic-csrf', issued_at=NOW, expires_at=NOW + timedelta(hours=1)))
    with application_client(execution_engine, tmp_path, first_scope) as first:
        response = enqueue(first, event_id)
        assert response.status_code == 202
        initial = response.json()
    with application_client(execution_engine, tmp_path, second_scope) as second:
        response = enqueue(second, event_id)
        assert response.status_code == 202, response.json()['error']['code']
        assert response.json()['workflow_id'] != initial['workflow_id']


def test_same_actor_same_key_on_another_event_route_is_independent(execution_engine, tmp_path):
    _, scope, _, first_event, _, _ = setup(execution_engine, tmp_path)
    second_event = uuid4()
    with Session(execution_engine) as session, session.begin():
        revisions = EventRepository(session, scope).get_source_revisions(str(first_event))
        EventRepository(session, scope).publish_events('independent-second-route-event', VisibilityScope(visibility='public'), (EventSubmission(event_id=Identifier(value=str(second_event)), event_type='security_risk', title='Independent second route', scope=VisibilityScope(visibility='public'), source_revision_ids=tuple(Identifier(value=value) for value in revisions)),), NOW)
    with application_client(execution_engine, tmp_path, scope) as client:
        first = enqueue(client, first_event)
        assert first.status_code == 202
        second = enqueue(client, second_event)
        assert second.status_code == 202, second.json()['error']['code']
        assert second.json()['workflow_id'] != first.json()['workflow_id']
