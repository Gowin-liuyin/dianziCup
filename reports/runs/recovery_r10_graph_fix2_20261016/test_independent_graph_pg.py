"""Synthetic independent PG counterexamples; no external assets or source calls."""

import hashlib
import json
import secrets
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event, select, text, update

from test_original_graph_pg import (
    ATLAS,
    VERSION,
    graph_engine,
    paper_value,
    publish_event,
    publish_fact,
    read_graph,
)
from test_r02_knowledge_revisions import prepared_submission, publish_submission

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.graph_routes import build_graph_router
from ai_intel.domain.access import Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.domain.records import ClaimRecord
from ai_intel.knowledge.models import document_revisions, documents, evidence, text_blocks
from ai_intel.knowledge.persistence_models import claims

pytestmark = pytest.mark.real_pg


def publish_exact_fixture_fact(engine, path, event_id, value):
    submission = prepared_submission(engine, path, predicate=value['kind'])
    quote = 'Event ' + str(event_id) + ' explicitly states ' + json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    record = ClaimRecord.model_validate({**submission.record.model_dump(), 'schema_version': 3, 'subject': str(event_id), 'object_value': value})
    submission = submission.model_copy(update={'record': record})
    with engine.begin() as connection:
        evidence_id = submission.evidence_links[0].evidence_id.value
        block_id = connection.scalar(select(evidence.c.block_id).where(evidence.c.evidence_id == evidence_id))
        connection.execute(update(text_blocks).where(text_blocks.c.block_id == block_id).values(block_text=quote, text_sha256=hashlib.sha256(quote.encode()).hexdigest(), end_offset=100 + len(quote)))
        connection.execute(update(evidence).where(evidence.c.evidence_id == evidence_id).values(quote=quote, quote_sha256=hashlib.sha256(quote.encode()).hexdigest(), end_offset=100 + len(quote)))
        connection.execute(update(document_revisions).where(document_revisions.c.revision_id == submission.revision_id.value).values(parse_status='parsed'))
    publish_submission(engine, submission)
    return submission


@pytest.mark.parametrize('relation', [
    'same_event', 'affects_component_version', 'component_version_vulnerability',
    'mapped_atlas', 'related_paper', 'remediated_by',
])
def test_exact_fixture_fields_produce_each_supported_relation(graph_engine, tmp_path, relation):
    event_id = uuid4()
    value = ATLAS if relation == 'mapped_atlas' else VERSION
    if relation == 'related_paper':
        value = paper_value(graph_engine, tmp_path / 'paper')
    submission = publish_exact_fixture_fact(graph_engine, tmp_path / 'support', event_id, value)
    publish_event(graph_engine, event_id, [submission])
    matching = [edge for edge in read_graph(graph_engine, event_id).edges if edge.relation_type == relation]
    assert matching
    assert all(edge.supporting_claim_ids == (UUID(submission.record.claim_id.value),) for edge in matching)


@pytest.mark.parametrize('relation', [
    'same_event', 'affects_component_version', 'component_version_vulnerability',
    'mapped_atlas', 'related_paper', 'remediated_by',
])
def test_unknown_condition_never_becomes_each_supported_relation(graph_engine, tmp_path, relation):
    event_id = uuid4()
    value = ATLAS if relation == 'mapped_atlas' else VERSION
    if relation == 'related_paper':
        value = paper_value(graph_engine, tmp_path / 'paper')
    submission = publish_exact_fixture_fact(graph_engine, tmp_path / 'support', event_id, value)
    publish_event(graph_engine, event_id, [submission])
    with graph_engine.begin() as connection:
        connection.execute(update(claims).where(claims.c.claim_id == submission.record.claim_id.value).values(condition_value='unknown'))
    assert not any(edge.relation_type == relation for edge in read_graph(graph_engine, event_id).edges)


def make_client(engine, register, role=Role.VIEWER):
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(engine),
        ('http://localhost:5173',),
        False,
        state_store=PgAuthenticationStateStore(engine),
    )
    username = 'independent-r10-' + uuid4().hex
    password = secrets.token_urlsafe(32)
    register(SecretStr(password))
    auth.create_precreated_user(username, password, 'owner', role)
    session_token, _ = auth.login(username, password, 'http://localhost:5173', uuid4().hex)
    register(SecretStr(session_token))
    app = FastAPI()
    app.include_router(build_graph_router(lambda: auth, engine), prefix='/v1')
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, session_token)
    return client, username


@pytest.mark.parametrize('relation', [
    'same_event', 'affects_component_version', 'component_version_vulnerability',
    'mapped_atlas', 'related_paper', 'remediated_by',
])
def test_unrelated_quote_cannot_become_supported_relation(graph_engine, tmp_path, relation):
    event_id = uuid4()
    value = ATLAS if relation == 'mapped_atlas' else VERSION
    if relation == 'related_paper':
        value = paper_value(graph_engine, tmp_path / 'paper')
    submission = publish_fact(graph_engine, tmp_path / 'support', event_id, value)
    publish_event(graph_engine, event_id, [submission])
    with graph_engine.connect() as connection:
        quote = connection.scalar(select(evidence.c.quote).where(
            evidence.c.evidence_id == submission.evidence_links[0].evidence_id.value,
        ))
    assert quote == 'explicit source'
    assert all(token not in quote for token in ('fixture-package', '1.4.2', 'AML.T0051'))
    assert not any(edge.relation_type == relation for edge in read_graph(graph_engine, event_id).edges), (
        'An unrelated exact quote has no value or event identity binding and cannot support ' + relation
    )


@pytest.mark.parametrize('change', ['source_acl', 'document_acl', 'revision_acl', 'claim_withdrawn', 'event_version'])
def test_http_does_not_return_snapshot_invalidated_before_response(
    graph_engine, tmp_path, register_sensitive_failure_value, change,
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    client, _ = make_client(graph_engine, register_sensitive_failure_value)
    changed = False

    def invalidate(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if changed or not statement.lstrip().startswith('SELECT events.'):
            return
        changed = True
        with graph_engine.begin() as writer:
            if change == 'source_acl':
                writer.execute(text("UPDATE sources SET visibility='tenant', tenant_id='other' WHERE source_id=:id"), {'id': submission.source_id.value})
            if change == 'document_acl':
                writer.execute(update(documents).where(documents.c.source_id == submission.source_id.value).values(visibility='tenant', tenant_id='other'))
            if change == 'revision_acl':
                writer.execute(update(document_revisions).where(document_revisions.c.revision_id == submission.revision_id.value).values(visibility='tenant', tenant_id='other'))
            if change == 'claim_withdrawn':
                writer.execute(update(claims).where(claims.c.claim_id == submission.record.claim_id.value).values(claim_status='withdrawn'))
            writer.execute(text('UPDATE events SET business_version=business_version+1 WHERE event_id=:id'), {'id': str(event_id)})
            writer.execute(text("UPDATE scope_epochs SET epoch=epoch+1 WHERE scope_key='public'"))

    event.listen(graph_engine, 'after_cursor_execute', invalidate)
    try:
        response = client.get(f'/v1/events/{event_id}/graph')
    finally:
        event.remove(graph_engine, 'after_cursor_execute', invalidate)
        client.close()
    assert changed
    if response.status_code == 200:
        if change == 'event_version':
            assert response.json()['business_version'] == 2, 'HTTP returned an event version known invalid before serialization'
        else:
            assert response.json()['edges'] == [], 'HTTP returned supported edges after committed withdrawal or parent ACL revocation'
    else:
        assert response.status_code in (404, 409, 503)


def test_http_rechecks_current_role_before_returning_private_graph(
    graph_engine, tmp_path, register_sensitive_failure_value,
):
    event_id = uuid4()
    visibility = VisibilityScope(visibility='tenant', tenant_id='owner')
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION, scope=visibility)
    publish_event(graph_engine, event_id, [submission], scope=visibility)
    client, username = make_client(graph_engine, register_sensitive_failure_value, Role.ANALYST)
    changed = False

    def revoke(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if changed or not statement.lstrip().startswith('SELECT events.'):
            return
        changed = True
        with graph_engine.begin() as writer:
            writer.execute(text("UPDATE users SET role='viewer' WHERE username=:username"), {'username': username})

    event.listen(graph_engine, 'after_cursor_execute', revoke)
    try:
        response = client.get(f'/v1/events/{event_id}/graph')
    finally:
        event.remove(graph_engine, 'after_cursor_execute', revoke)
        client.close()
    assert changed
    assert response.status_code in (401, 403, 404), 'Private graph escaped after committed role revocation'


@pytest.mark.parametrize('max_nodes,max_edges', [(1, 1), (2, 400), (200, 1), (200, 400)])
def test_selected_graph_is_bounded_deterministic_and_canonical(graph_engine, tmp_path, max_nodes, max_edges):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    result = read_graph(graph_engine, event_id, max_nodes=max_nodes, max_edges=max_edges)
    assert len(result.nodes) <= max_nodes and len(result.edges) <= max_edges
    ids = {node.id for node in result.nodes}
    assert all(edge.subject_id in ids and edge.object_id in ids for edge in result.edges)
    payload = result.model_dump(mode='json', exclude={'content_sha256'})
    expected = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert result.content_sha256 == expected
    assert result == read_graph(graph_engine, event_id, max_nodes=max_nodes, max_edges=max_edges)
    assert result.truncated == (max_nodes < 6 or max_edges < 5)


@pytest.mark.parametrize('corruption', ['predicate', 'object_schema', 'block_hash'])
def test_corrupt_rows_never_produce_supported_non_same_event_edges(
    graph_engine, tmp_path, register_sensitive_failure_value, corruption,
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    with graph_engine.begin() as connection:
        if corruption == 'predicate':
            connection.execute(update(claims).where(claims.c.claim_id == submission.record.claim_id.value).values(predicate='atlas_mapping'))
        elif corruption == 'object_schema':
            connection.execute(update(claims).where(claims.c.claim_id == submission.record.claim_id.value).values(object_json={'kind': 'version_assertion'}))
        else:
            block_id = connection.scalar(select(evidence.c.block_id).where(evidence.c.evidence_id == submission.evidence_links[0].evidence_id.value))
            connection.execute(update(text_blocks).where(text_blocks.c.block_id == block_id).values(text_sha256='0' * 64))
    client, _ = make_client(graph_engine, register_sensitive_failure_value)
    try:
        response = client.get(f'/v1/events/{event_id}/graph')
    finally:
        client.close()
    assert response.status_code == (200 if corruption == 'block_hash' else 503)
    if response.status_code == 200:
        assert response.json()['edges'] == []


def test_poc_reference_does_not_become_remediation_or_verification(graph_engine, tmp_path):
    event_id = uuid4()
    value = {'kind': 'artifact_reference', 'uri': 'https://example.invalid/static-poc', 'title': 'Synthetic static PoC', 'artifact_kind': 'poc', 'static_status': 'static_reviewed'}
    submission = publish_fact(graph_engine, tmp_path, event_id, value)
    publish_event(graph_engine, event_id, [submission])
    result = read_graph(graph_engine, event_id)
    assert {edge.relation_type for edge in result.edges} == {'same_event'}
    assert not any('lab_verified' in node.label for node in result.nodes)
