"""Independent deterministic real-PG revocation window after the final scope read."""
import json
import pytest
from sqlalchemy import select, update
from test_review_probes import vector_database, isolated_test_database_url, setup_case
from ai_intel.retrieval.persistence_models import grounded_answers
from ai_intel.knowledge.models import users

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize('case', ['session_revoked', 'owner_tenant_changed'])
def test_permission_change_commits_after_final_scope_read_before_answer_commit(vector_database, monkeypatch, case):
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch)
    original_require_current = service.retriever.require_current
    owner_id = auth.build_access_scope(token).user_id
    changed = []
    def mutate_after_scope_read(session, scope, event_id, epoch, citations, *, lock_epoch=False):
        if lock_epoch:
            if case == 'session_revoked':
                auth.logout(token)
            else:
                with vector_database.begin() as connection:
                    connection.execute(update(users).where(users.c.user_id == owner_id).values(tenant_id='other-review-tenant'))
            changed.append(True)
        return original_require_current(session, scope, event_id, epoch, citations, lock_epoch=lock_epoch)
    monkeypatch.setattr(service.retriever, 'require_current', mutate_after_scope_read)
    with http:
        response = http.post('/v1/questions', json=payload.model_dump(mode='json'), headers={**headers, 'idempotency-key': 'review-final-auth-' + case})
    with vector_database.connect() as connection:
        row = connection.execute(select(grounded_answers)).mappings().one()
    print('post_reauth_commit_race_observed=' + json.dumps({'case': case, 'http_status': response.status_code, 'response_kind': response.json().get('kind'), 'answer_pg_kind': row['response']['kind'], 'simulated_wire_calls': len(calls), 'revocation_committed_before_answer': bool(changed)}))
    assert changed == [True]
    assert response.status_code == (401 if case == 'session_revoked' else 404)
    assert 'answer_text' not in response.json()
    assert row['response']['kind'] == 'failed'
