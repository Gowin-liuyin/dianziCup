"""Independent synthetic recheck: natural identities, contradictory citations and tenant locks."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text, update

from test_r10_evidence_graph_pg import (
    ATLAS, VERSION, SOURCE_IDENTIFIER, graph_engine, paper_value, publish_fact,
    publish_event, read_graph, replace_source_body,
)
from test_r10_graph_validity_pg import client_for
from ai_intel.domain.values import VisibilityScope
from ai_intel.knowledge.models import document_revisions, documents
from ai_intel.knowledge.persistence_models import claims, event_external_ids

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize('kind', ['cve', 'ghsa'])
def test_natural_external_identifier_needs_no_internal_uuid(graph_engine, tmp_path, kind):
    event_id = uuid4()
    identifier = 'CVE-2026-424242' if kind == 'cve' else SOURCE_IDENTIFIER
    value = {**VERSION, 'raw_expression': VERSION['raw_expression'].replace(SOURCE_IDENTIFIER, identifier), 'vendor_fix': None, 'mitigations': []}
    source = publish_fact(graph_engine, tmp_path, event_id, value)
    publish_event(graph_engine, event_id, [source])
    with graph_engine.begin() as connection:
        connection.execute(event_external_ids.delete().where(event_external_ids.c.event_id == str(event_id)))
        connection.execute(event_external_ids.insert().values(event_id=str(event_id), id_type=kind, id_value=identifier.upper(), scope_key='public'))
    result = read_graph(graph_engine, event_id)
    assert {edge.relation_type for edge in result.edges} == {'same_event', 'affects_component_version', 'component_version_vulnerability'}
    assert str(event_id) not in value['raw_expression']


@pytest.mark.parametrize('summary', [
    'GHSA-2345-6789-cfgh: This paper does not analyze this vulnerability in fixture-package; it analyzes an unrelated package.',
    'GHSA-2345-6789-cfgh: Analysis of this vulnerability in fixture-package is unconfirmed; the mechanism is unknown.',
])
def test_negative_or_unknown_paper_citation_cannot_confirm_analysis(graph_engine, tmp_path, summary):
    event_id = uuid4()
    value = {**paper_value(graph_engine, tmp_path / 'paper'), 'support_summary': summary}
    source = publish_fact(graph_engine, tmp_path / 'source', event_id, value)
    publish_event(graph_engine, event_id, [source])
    result = read_graph(graph_engine, event_id)
    assert not any(edge.relation_type == 'related_paper' for edge in result.edges), 'Negative or unknown source statement cannot support a strong analysis relationship'


def test_negated_atlas_mechanism_cannot_confirm_attack_mapping(graph_engine, tmp_path):
    event_id = uuid4()
    value = {**ATLAS, 'mechanism': 'GHSA-2345-6789-cfgh: Untrusted instructions do not enter a model input.'}
    source = publish_fact(graph_engine, tmp_path, event_id, value)
    publish_event(graph_engine, event_id, [source])
    assert not any(edge.relation_type == 'mapped_atlas' for edge in read_graph(graph_engine, event_id).edges)


def test_invisible_unlinked_claim_is_not_locked_by_public_graph(
    graph_engine, tmp_path, register_sensitive_failure_value,
):
    event_id = uuid4()
    public = publish_fact(graph_engine, tmp_path / 'public', event_id, VERSION)
    publish_event(graph_engine, event_id, [public])
    hidden = publish_fact(graph_engine, tmp_path / 'hidden', event_id, VERSION,
        scope=VisibilityScope(visibility='tenant', tenant_id='other'))
    before = read_graph(graph_engine, event_id)
    assert before.edges and all(node.scope.visibility == 'public' for node in before.nodes)
    client, *_ = client_for(graph_engine, register_sensitive_failure_value)
    try:
        with graph_engine.connect() as writer, writer.begin():
            writer.execute(update(claims).where(claims.c.claim_id == hidden.record.claim_id.value).values(object_value=claims.c.object_value))
            response = client.get(f'/v1/events/{event_id}/graph')
        assert response.status_code == 200, 'A hidden tenant claim unrelated to event_documents must not block the public graph'
        assert response.json()['content_sha256'] == before.content_sha256
    finally:
        client.close()


@pytest.mark.parametrize('parent', ['source', 'document', 'revision'])
def test_request_local_target_memo_does_not_survive_acl_revocation(graph_engine, tmp_path, parent):
    event_id = uuid4()
    value = paper_value(graph_engine, tmp_path / 'target')
    source = publish_fact(graph_engine, tmp_path / 'source', event_id, value)
    publish_event(graph_engine, event_id, [source])
    assert any(edge.relation_type == 'related_paper' for edge in read_graph(graph_engine, event_id).edges)
    with graph_engine.begin() as connection:
        if parent == 'source':
            connection.execute(text("UPDATE sources SET visibility='tenant',tenant_id='other' WHERE source_id=(SELECT source_id FROM documents WHERE document_id=:id)"), {'id': value['target_document_id']})
        elif parent == 'document':
            connection.execute(update(documents).where(documents.c.document_id == value['target_document_id']).values(visibility='tenant', tenant_id='other'))
        else:
            connection.execute(update(document_revisions).where(document_revisions.c.revision_id == value['target_revision_id']).values(visibility='tenant', tenant_id='other'))
    assert not any(edge.relation_type == 'related_paper' for edge in read_graph(graph_engine, event_id).edges)
