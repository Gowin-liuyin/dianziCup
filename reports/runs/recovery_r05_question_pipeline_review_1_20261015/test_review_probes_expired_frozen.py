"""Independent probes: real isolated PostgreSQL; synthetic trusted generation wire only."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import insert, select, update

WT = Path('D:/wt/r05-pipe-review')
sys.path.insert(0, str(WT / 'backend/tests'))
sys.path.insert(0, str(WT / 'backend/tests/integration'))
from conftest import isolated_test_database_url
from test_r05_vector_persistence import vector_database, FixtureSemanticModels, public_event_id
from ai_intel.answering.service import GroundedQuestionService, QuestionFailure
from ai_intel.api.app import create_application
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME, CSRF_HEADER_NAME
from ai_intel.api import question_routes
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import Role
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.network import FetchResult
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.retrieval.persistence_models import grounded_answers
from ai_intel.retrieval.service import EventEvidenceRetriever

pytestmark = pytest.mark.real_pg
ORIGIN = 'http://localhost:5173'


def trusted_wire(monkeypatch, on_second=None):
    client = GenerationClient('deepseek_openai', 'deepseek-flash', SecretStr('review-explicit-synthetic-generation-credential'), limits=GenerationLimits(total_timeout_seconds=30.0, max_calls=1))
    calls = []
    def post(url, body, *, protocol_headers, deadline):
        request = json.loads(body)
        calls.append(request)
        content = json.loads(request['messages'][1]['content'])
        if len(calls) % 2 == 1:
            quoted = json.loads(content['untrusted_evidence'][0])
            reply = {'claims': [{'text': quoted['quote'], 'kind': 'source_fact', 'support_ids': [quoted['evidence_id']]}], 'citations': [{'evidence_id': quoted['evidence_id'], 'quote': quoted['quote']}]}
        else:
            if on_second is not None:
                on_second()
            reply = {'verdicts': [{'claim_index': 1, 'verdict': 'supported', 'numbers_match': True, 'states_preserved': True, 'suggestion_only': False}]}
        wire = {'id': 'fixture-review-' + str(len(calls)), 'object': 'chat.completion', 'model': 'deepseek-flash', 'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(reply, ensure_ascii=False)}}]}
        return FetchResult(url, 200, 'application/json', json.dumps(wire).encode())
    monkeypatch.setattr(client._gateway, 'post_json', post)
    return client, calls


def setup_case(engine, monkeypatch, on_second=None):
    auth = AuthenticationSessionService(DatabaseUserDirectory(engine), (ORIGIN,), False, state_store=PgAuthenticationStateStore(engine))
    account = auth.create_precreated_user('review-fixture-reader', 'review-synthetic-password-only', 'review-tenant', Role.VIEWER)
    token, record = auth.login(account.username, 'review-synthetic-password-only', ORIGIN, 'review-client')
    client, calls = trusted_wire(monkeypatch, on_second)
    service = GroundedQuestionService(engine, EventEvidenceRetriever(engine, FixtureSemanticModels()), client, data_mode='fixture')
    settings = ApplicationSettings(app_env='test', data_mode='fixture', database_url=SecretStr(engine.url.render_as_string(hide_password=False)))
    monkeypatch.setattr(question_routes, 'build_question_service', lambda engine, settings: service)
    app = create_application(auth, settings=settings)
    http = TestClient(app)
    http.cookies.set(SESSION_COOKIE_NAME, token)
    payload = QuestionRequest(question='逐字给出本事件当前原文', event_ids=(public_event_id(engine),), mode='library')
    headers = {CSRF_HEADER_NAME: record.csrf_token, 'origin': ORIGIN}
    return auth, token, service, http, payload, headers, calls


def test_missing_idempotency_key_rejects_before_any_paid_call(vector_database, monkeypatch):
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch)
    with http:
        first = http.post('/v1/questions', json=payload.model_dump(mode='json'), headers=headers)
        second = http.post('/api/v1/questions', json=payload.model_dump(mode='json'), headers=headers)
    observed = {'first_status': first.status_code, 'second_status': second.status_code, 'simulated_paid_wire_calls': len(calls), 'first_kind': first.json().get('kind'), 'second_kind': second.json().get('kind')}
    print('missing_key_observed=' + json.dumps(observed))
    assert first.status_code == second.status_code == 422
    assert not calls


def test_abrupt_process_exit_then_restart_has_terminal_indeterminate_state(vector_database, monkeypatch):
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch)
    key = 'review-crash-key'
    scope = auth.build_access_scope(token)
    worker = Path(__file__).with_name('crash_worker.py')
    child_environment = os.environ.copy()
    child_environment['REVIEW_ISOLATED_DATABASE_URL'] = vector_database.url.render_as_string(hide_password=False)
    child_environment['REVIEW_USER_ID'] = scope.user_id
    child_environment['REVIEW_TENANT_ID'] = scope.tenant_id
    child_environment['REVIEW_PAYLOAD'] = json.dumps(payload.model_dump(mode='json'), ensure_ascii=False)
    child_environment['REVIEW_KEY'] = key
    exited = subprocess.run([sys.executable, str(worker)], env=child_environment, capture_output=True, text=True, timeout=30)
    assert exited.returncode == 73
    with vector_database.begin() as connection:
        connection.execute(update(grounded_answers).values(created_at=datetime.now(UTC) - timedelta(hours=1)))
    with vector_database.connect() as connection:
        row = connection.execute(select(grounded_answers)).mappings().one()
        before = {'kind': row['response']['kind'], 'attempts_count': len(row['model_trace']['attempts']), 'fee': row['model_trace']['fee']}
    replacement = GroundedQuestionService(vector_database, service.retriever, service.client, data_mode='fixture')
    try:
        replacement.ask(payload, lambda: auth.build_access_scope(token), key)
        actual = 'completed'
    except QuestionFailure as error:
        actual = error.code
    with vector_database.connect() as connection:
        after_kind = connection.execute(select(grounded_answers.c.response)).scalar_one()['kind']
    print('crash_restart_observed=' + json.dumps({'before': before, 'restart_code': actual, 'after_kind': after_kind, 'new_simulated_calls': len(calls)}))
    assert after_kind == 'failed', 'a dead owner must become a tracked terminal indeterminate failure without another paid call'
    assert actual == 'answer_failed'
    assert not calls


def test_real_session_revoked_during_second_paid_wire_does_not_return_answer(vector_database, monkeypatch):
    holder = {}
    def revoke():
        holder['auth'].logout(holder['token'])
    auth, token, service, http, payload, headers, calls = setup_case(vector_database, monkeypatch, revoke)
    holder.update(auth=auth, token=token)
    with http:
        response = http.post('/v1/questions', json=payload.model_dump(mode='json'), headers={**headers, 'idempotency-key': 'review-revoked'})
    assert response.status_code == 401
    assert len(calls) == 2
    assert 'answer_text' not in response.json()
    with vector_database.connect() as connection:
        row = connection.execute(select(grounded_answers)).mappings().one()
    assert row['response']['kind'] == 'failed'
    assert len(row['model_trace']['attempts']) == 2
    assert row['model_trace']['fee'] == 'unknown'

