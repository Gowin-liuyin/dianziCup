"""Independent API/transaction checks; synthetic wire, real isolated PG, no live score."""
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update
from test_review_probes import vector_database, isolated_test_database_url, setup_case, ORIGIN
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.domain.access import Role
from ai_intel.knowledge.models import document_revisions, evidence, scope_epochs, users
from ai_intel.knowledge.persistence_models import claims
from ai_intel.retrieval.persistence_models import grounded_answers

pytestmark = pytest.mark.real_pg


def test_same_key_completed_replay_then_conflict_is_not_paid_again(vector_database, monkeypatch):
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch)
    headers['idempotency-key'] = 'review-replay'
    with http:
        first = http.post('/v1/questions', json=payload.model_dump(mode='json'), headers=headers)
        replay = http.post('/api/v1/questions', json=payload.model_dump(mode='json'), headers=headers)
        changed = http.post('/v1/questions', json={**payload.model_dump(mode='json'), 'question': '改动的问题'}, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert len(calls) == 2
    assert changed.status_code == 409
    assert changed.json()['error']['code'] == 'idempotency_conflict'


@pytest.mark.parametrize('case', ['epoch_changed', 'evidence_unverified', 'revision_not_current', 'claims_withdrawn', 'owner_tenant_changed'])
def test_fact_or_owner_change_during_paid_wire_prevents_return(vector_database, monkeypatch, case):
    holder = {}
    def mutate():
        with vector_database.begin() as connection:
            if case == 'epoch_changed':
                connection.execute(update(scope_epochs).where(scope_epochs.c.scope_key == 'public').values(epoch=scope_epochs.c.epoch + 1))
            elif case == 'evidence_unverified':
                connection.execute(update(evidence).values(verified_at=None))
            elif case == 'revision_not_current':
                connection.execute(update(document_revisions).values(is_current=False))
            elif case == 'claims_withdrawn':
                connection.execute(update(claims).values(claim_status='withdrawn'))
            else:
                connection.execute(update(users).where(users.c.user_id == holder['user_id']).values(tenant_id='new-review-tenant'))
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch, mutate)
    holder['user_id'] = auth.build_access_scope(token).user_id
    with http:
        response = http.post('/v1/questions', json=payload.model_dump(mode='json'), headers={**headers, 'idempotency-key': case})
    assert response.status_code == (404 if case == 'owner_tenant_changed' else 503)
    assert 'answer_text' not in response.json()
    assert len(calls) == 2
    with vector_database.connect() as connection:
        row = connection.execute(select(grounded_answers)).mappings().one()
    assert row['response']['kind'] == 'failed'
    assert len(row['model_trace']['attempts']) == 2
    assert row['model_trace']['fee'] == 'unknown'


def test_other_owner_in_same_tenant_cannot_get_answer_and_history_stays_stale(vector_database, monkeypatch):
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch)
    with http:
        first = http.post('/v1/questions', json=payload.model_dump(mode='json'), headers={**headers, 'idempotency-key': 'review-own'})
        assert first.status_code == 200
        answer_id = first.json()['answer_id']
        other = auth.create_precreated_user('review-other-owner', 'review-other-synthetic-password', 'review-tenant', Role.VIEWER)
        other_token, _ = auth.login(other.username, 'review-other-synthetic-password', ORIGIN, 'review-other-client')
        http.cookies.set(SESSION_COOKIE_NAME, other_token)
        denied = http.get('/v1/answers/' + answer_id)
        assert denied.status_code == 404
        http.cookies.set(SESSION_COOKIE_NAME, token)
        with vector_database.begin() as connection:
            connection.execute(update(document_revisions).values(is_current=False))
            connection.execute(update(scope_epochs).where(scope_epochs.c.scope_key == 'public').values(epoch=scope_epochs.c.epoch + 1))
        history = http.get('/api/v1/answers/' + answer_id)
    assert history.status_code == 200
    assert history.json()['freshness'] == 'stale'
    assert history.json()['answer_text'] == first.json()['answer_text']
    with vector_database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1
    assert len(calls) == 2


@pytest.mark.parametrize('changes', [{'conversation_id': str(uuid4())}, {'asset_ids': [str(uuid4())]}, {'known_at': '2026-10-15T08:00:00Z'}, {'valid_at': '2026-10-15T08:00:00Z'}, {'mode': 'investigate'}, {'event_ids': []}])
def test_r12_scope_explicitly_422_without_reservation_or_paid_call(vector_database, monkeypatch, changes):
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch)
    with http:
        response = http.post('/v1/questions', json={**payload.model_dump(mode='json'), **changes}, headers={**headers, 'idempotency-key': 'review-unsupported'})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'question_scope_not_supported'
    with vector_database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 0
    assert not calls
