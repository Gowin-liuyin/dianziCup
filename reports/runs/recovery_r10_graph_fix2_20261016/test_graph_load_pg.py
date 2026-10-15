"""One synthetic event tests the fixed 2000 support-row bound and actual query count."""

import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from test_original_graph_pg import graph_engine, paper_value, publish_event, read_graph
from test_independent_graph_pg import publish_exact_fixture_fact
from ai_intel.knowledge.models import evidence
from ai_intel.knowledge.persistence_models import claim_evidence

pytestmark = pytest.mark.real_pg


def test_support_row_cap_and_repeated_paper_target_lookups(graph_engine, tmp_path):
    event_id = uuid4()
    value = paper_value(graph_engine, tmp_path / 'paper')
    submission = publish_exact_fixture_fact(graph_engine, tmp_path / 'support', event_id, value)
    publish_event(graph_engine, event_id, [submission])
    with graph_engine.begin() as connection:
        original = dict(connection.execute(select(evidence).where(
            evidence.c.evidence_id == submission.evidence_links[0].evidence_id.value,
        )).mappings().one())
        evidence_rows = [{**original, 'evidence_id': str(uuid4())} for _ in range(2000)]
        connection.execute(evidence.insert(), evidence_rows)
        connection.execute(claim_evidence.insert(), [
            {'claim_id': submission.record.claim_id.value, 'evidence_id': row['evidence_id'], 'support_kind': 'supports', 'validation_status': 'validated'}
            for row in evidence_rows
        ])
    counts = {'sql': 0, 'paper_target': 0}

    def count_query(connection, cursor, statement, parameters, context, executemany):
        counts['sql'] += 1
        if 'FROM document_revisions JOIN documents' in statement and 'documents.kind =' in statement:
            counts['paper_target'] += 1

    event.listen(graph_engine, 'before_cursor_execute', count_query)
    started = perf_counter()
    try:
        result = read_graph(graph_engine, event_id, max_nodes=1, max_edges=1)
    finally:
        elapsed = perf_counter() - started
        event.remove(graph_engine, 'before_cursor_execute', count_query)
    observation = {**counts, 'elapsed_seconds': elapsed, 'input_support_rows': 2001, 'selected_nodes': len(result.nodes), 'selected_edges': len(result.edges), 'truncated': result.truncated, 'scope': 'isolated synthetic local observation; not a performance acceptance score'}
    (Path(__file__).parent / 'graph_load_observation.json').write_text(json.dumps(observation, indent=2), encoding='utf-8')
    assert result.truncated and len(result.nodes) == 1 and len(result.edges) == 0
    assert counts['paper_target'] <= 1, 'Same target document/revision should require one bounded lookup, not one per support span'
