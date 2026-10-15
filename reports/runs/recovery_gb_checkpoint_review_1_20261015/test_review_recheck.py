"""Independent fix probes: synthetic model wire, real isolated PG and real child processes."""
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import func, select, text, update
from test_r05_question_api_pg import question_api, post_question, stored_answer, assert_problem, vector_database
from ai_intel.answering import service as answer_service
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.knowledge.models import users
from ai_intel.retrieval.persistence_models import grounded_answers

pytestmark = pytest.mark.real_pg
RUN = Path(__file__).resolve().parent


def change_expiry(api):
    with api['engine'].begin() as connection:
        row = connection.execute(select(grounded_answers)).mappings().one()
        trace = dict(row['model_trace'])
        trace['reservation_expires_at'] = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
        connection.execute(update(grounded_answers).where(grounded_answers.c.answer_id == row['answer_id']).values(model_trace=trace))
    return row['answer_id']


def child_environment(api):
    environment = os.environ.copy()
    environment['REVIEW_ISOLATED_DATABASE_URL'] = api['engine'].url.render_as_string(hide_password=False)
    environment['REVIEW_SESSION_TOKEN'] = api['client'].cookies[SESSION_COOKIE_NAME]
    environment['REVIEW_PAYLOAD'] = json.dumps(api['payload'], ensure_ascii=False)
    environment['REVIEW_KEY'] = 'review-independent-process-key'
    return environment


def test_hard_exit_expired_pending_get_is_terminal_without_another_call(question_api):
    api = question_api
    environment = child_environment(api)
    exited = subprocess.run([sys.executable, str(RUN / 'parallel_worker.py'), 'crash'], env=environment, capture_output=True, text=True, timeout=20)
    assert exited.returncode == 73
    row = stored_answer(api)
    assert row['response']['kind'] == 'pending'
    assert row['model_trace']['reservation_id']
    answer_id = change_expiry(api)
    response = api['client'].get('/v1/answers/' + answer_id)
    assert_problem(response, 409, 'answer_failed')
    row = stored_answer(api)
    assert row['response'] == {'kind': 'failed', 'error_code': 'answer_interrupted'}
    assert row['model_trace']['usage_status'] == 'incomplete_interrupted'
    assert row['model_trace']['fee'] == 'unknown'
    assert row['model_trace']['attempts'] == []
    replay = post_question(api, key=environment['REVIEW_KEY'])
    assert_problem(replay, 409, 'answer_failed')
    assert not api['wire'].calls


def test_late_writer_cannot_overwrite_expired_terminal_but_keeps_known_attempts(question_api):
    api = question_api
    def expire_and_recover():
        answer_id = change_expiry(api)
        response = api['client'].get('/api/v1/answers/' + answer_id)
        assert_problem(response, 409, 'answer_failed')
    api['wire'].before_verification = expire_and_recover
    response = post_question(api, key='review-late-writer')
    assert_problem(response, 409, 'answer_failed')
    row = stored_answer(api)
    assert row['response'] == {'kind': 'failed', 'error_code': 'answer_interrupted'}
    assert row['model_trace']['reservation_state'] == 'expired'
    assert row['model_trace']['usage_status'] == 'recorded_after_terminal'
    assert len(row['model_trace']['attempts']) == 2
    assert row['model_trace']['fee'] == 'unknown'
    replay = post_question(api, key='review-late-writer')
    assert_problem(replay, 409, 'answer_failed')
    assert len(api['wire'].calls) == 2


def test_pg_expiry_fence_rejects_writer_even_without_prior_recovery(question_api):
    api = question_api
    api['wire'].before_verification = lambda: change_expiry(api)
    response = post_question(api, key='review-pg-expiry')
    assert_problem(response, 409, 'answer_failed')
    row = stored_answer(api)
    assert row['response']['kind'] == 'failed'
    assert len(row['model_trace']['attempts']) == 2
    assert row['model_trace']['fee'] == 'unknown'


def test_two_process_same_key_only_one_generation_pair(question_api):
    api = question_api
    environment = child_environment(api)
    owner = subprocess.Popen([sys.executable, str(RUN / 'parallel_worker.py'), 'block'], env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert owner.stdout.readline().strip() == 'SIMULATED_WIRE_REACHED'
        duplicate = subprocess.run([sys.executable, str(RUN / 'parallel_worker.py'), 'normal'], env=environment, capture_output=True, text=True, timeout=20)
        assert duplicate.returncode == 0
        duplicate_result = json.loads(duplicate.stdout)
        assert duplicate_result == {'status': 'answer_in_progress', 'calls': 0}
        owner.stdin.write('release\n')
        owner.stdin.flush()
        stdout, stderr = owner.communicate(timeout=20)
        assert owner.returncode == 0
        owner_result = json.loads(stdout)
        assert owner_result['status'] == 'completed' and owner_result['calls'] == 2
        assert stored_answer(api)['response']['kind'] == 'completed'
        with api['engine'].connect() as connection:
            assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1
        print('real_process_same_key=' + json.dumps({'owner_calls': owner_result['calls'], 'duplicate_calls': duplicate_result['calls'], 'pg_rows': 1}))
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.communicate(timeout=10)


@pytest.mark.parametrize('change', ['logout', 'tenant'])
def test_authorization_change_committed_before_final_auth_lock_prevents_answer(question_api, monkeypatch, change):
    api = question_api
    original = answer_service._lock_answer_scope
    changed = []
    def mutate_before_lock(session, scope, session_token):
        if not changed:
            if change == 'logout':
                api['auth'].logout(api['client'].cookies[SESSION_COOKIE_NAME])
            else:
                with api['engine'].begin() as connection:
                    connection.execute(update(users).where(users.c.user_id == api['identity']['user_id']).values(tenant_id='review-new-tenant'))
            changed.append(True)
        return original(session, scope, session_token)
    monkeypatch.setattr(answer_service, '_lock_answer_scope', mutate_before_lock)
    response = post_question(api, key='review-auth-before-lock-' + change)
    assert_problem(response, 401 if change == 'logout' else 404, 'session_expired' if change == 'logout' else 'not_found')
    assert stored_answer(api)['response']['kind'] == 'failed'
    assert len(stored_answer(api)['model_trace']['attempts']) == 2
    assert stored_answer(api)['model_trace']['fee'] == 'unknown'


@pytest.mark.parametrize('change', ['logout', 'tenant'])
def test_auth_locked_answer_commit_finishes_before_waiting_permission_writer(question_api, monkeypatch, change):
    api = question_api
    original = answer_service._lock_answer_scope
    lock_acquired = Event()
    release = Event()
    writer_started = Event()
    holder = {}
    def hold_lock(session, scope, session_token):
        current = original(session, scope, session_token)
        holder['pid'] = session.scalar(text('SELECT pg_backend_pid()'))
        lock_acquired.set()
        assert release.wait(10)
        return current
    monkeypatch.setattr(answer_service, '_lock_answer_scope', hold_lock)
    def permission_writer():
        writer_started.set()
        if change == 'logout':
            api['auth'].logout(api['client'].cookies[SESSION_COOKIE_NAME])
        else:
            with api['engine'].begin() as connection:
                connection.execute(update(users).where(users.c.user_id == api['identity']['user_id']).values(tenant_id='review-tenant-after-commit'))
    with ThreadPoolExecutor(max_workers=2) as executor:
        request_future = executor.submit(post_question, api, key='review-auth-lock-' + change)
        writer_future = None
        try:
            assert lock_acquired.wait(10)
            writer_future = executor.submit(permission_writer)
            assert writer_started.wait(5)
            deadline = time.monotonic() + 5
            blocked = []
            while time.monotonic() < deadline:
                with api['engine'].connect() as connection:
                    blocked = list(connection.scalars(text('SELECT pid FROM pg_stat_activity WHERE :blocker = ANY(pg_blocking_pids(pid))'), {'blocker': holder['pid']}))
                if blocked:
                    break
                time.sleep(0.02)
            assert blocked, 'permission writer must actually wait on the authenticated transaction'
            assert not writer_future.done()
            print('auth_lock_order=' + json.dumps({'change': change, 'permission_writer_waited_in_pg': True, 'answer_pid': holder['pid'], 'blocked_writer_count': len(blocked)}))
        finally:
            release.set()
        response = request_future.result(timeout=15)
        if writer_future is not None:
            writer_future.result(timeout=15)
    assert response.status_code == 200
    assert stored_answer(api)['response']['kind'] == 'completed'
    if change == 'logout':
        assert api['client'].get('/v1/answers/' + response.json()['answer_id']).status_code == 401
    else:
        assert api['client'].get('/v1/answers/' + response.json()['answer_id']).status_code == 404

