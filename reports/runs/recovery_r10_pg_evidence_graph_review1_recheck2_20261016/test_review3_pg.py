"""Independent fixed-source positives and late current-read insertion, synthetic PG only."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import NOW, publisher_scope
from test_r10_evidence_graph_pg import (
    ATLAS, SOURCE_IDENTIFIER, VERSION, graph_engine, paper_value,
    publish_event, publish_fact, read_graph,
)
from test_r10_graph_validity_pg import client_for, record_response

from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier
from ai_intel.knowledge.persistence import KnowledgeRepository

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize('kind,statement', [
    ('atlas', 'Untrusted instructions are not sanitized and enter a model input.'),
    ('atlas', 'Untrusted instructions not only enter a model input but also override instructions.'),
    ('atlas', '不受信任的指令进入模型输入。'),
    ('paper', 'This paper analyzes this vulnerability observed in May.'),
    ('paper', 'This paper not only analyzes this vulnerability but also preserves prerequisites.'),
    ('paper', '本文分析该漏洞，但没有运行利用代码。'),
])
def test_affirmative_relationships_keep_their_real_negative_control_words(
    graph_engine, tmp_path, kind, statement,
):
    event_id = uuid4()
    sentence = SOURCE_IDENTIFIER + ': ' + statement
    value = ({**ATLAS, 'mechanism': sentence} if kind == 'atlas' else
             {**paper_value(graph_engine, tmp_path / 'paper'), 'support_summary': sentence})
    source = publish_fact(graph_engine, tmp_path / 'source', event_id, value)
    publish_event(graph_engine, event_id, [source])
    graph = read_graph(graph_engine, event_id)
    relation = 'mapped_atlas' if kind == 'atlas' else 'related_paper'
    assert any(edge.relation_type == relation for edge in graph.edges)


@pytest.mark.parametrize('bump_epoch', [False, True])
def test_new_claim_committed_after_current_support_select_is_detected(
    graph_engine, tmp_path, register_sensitive_failure_value, bump_epoch,
):
    event_id = uuid4()
    source = publish_fact(graph_engine, tmp_path / 'source', event_id, VERSION)
    publish_event(graph_engine, event_id, [source])
    before = read_graph(graph_engine, event_id)
    client, *_ = client_for(graph_engine, register_sensitive_failure_value)
    support_queries = 0
    inserted = False

    def mutate(connection, cursor, statement, parameters, context, executemany):
        nonlocal support_queries, inserted
        if not statement.lstrip().startswith('SELECT DISTINCT claims.'):
            return
        support_queries += 1
        if inserted or support_queries != 2:
            return
        inserted = True
        with Session(graph_engine) as writer, writer.begin():
            previous_epoch = writer.scalar(text("SELECT epoch FROM scope_epochs WHERE scope_key='public'"))
            record = ClaimRecord.model_validate(source.record.model_copy(update={
                'claim_id': Identifier(value=str(uuid4())),
                'asserted_at': NOW + timedelta(seconds=1),
            }).model_dump())
            KnowledgeRepository(writer, publisher_scope(source.record.scope)).publish(
                'independent-late-visible-' + uuid4().hex,
                source.record.scope,
                (source.model_copy(update={'record': record}),),
                created_at=NOW,
            )
            writer.execute(text("UPDATE scope_epochs SET epoch=:epoch WHERE scope_key='public'"),
                           {'epoch': previous_epoch + int(bump_epoch)})

    event.listen(graph_engine, 'after_cursor_execute', mutate)
    try:
        response = client.get(f'/v1/events/{event_id}/graph')
        record_response('independent_late_visible_claim', response, before.content_sha256,
                        bump_epoch=bump_epoch, inserted=inserted, support_queries=support_queries)
        assert inserted and response.status_code == 409
    finally:
        event.remove(graph_engine, 'after_cursor_execute', mutate)
        client.close()
