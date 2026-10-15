"""真实 PG 源/目标覆盖不完整不能支撑论文强边；保留业务事实，输入均为 fixture。"""

from uuid import uuid4

import pytest
from sqlalchemy import select, update
from test_r10_evidence_graph_pg import graph_engine as graph_engine
from test_r10_evidence_graph_pg import paper_value, publish_event, publish_fact, read_graph

from ai_intel.knowledge.models import document_revisions
from ai_intel.knowledge.persistence_models import claims

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize("parent", ["source", "target"])
@pytest.mark.parametrize("coverage", ["metadata_only", "excerpt", "unknown", "full_text"])
def test_incomplete_paper_source_or_target_remains_unknown_without_changing_fact(
    graph_engine, tmp_path, parent, coverage
):
    event_id = uuid4()
    value = paper_value(graph_engine, tmp_path / "paper")
    source = publish_fact(graph_engine, tmp_path / "source", event_id, value)
    publish_event(graph_engine, event_id, [source])
    assert any(
        edge.relation_type == "related_paper" for edge in read_graph(graph_engine, event_id).edges
    )
    revision_id = source.revision_id.value if parent == "source" else value["target_revision_id"]
    with graph_engine.begin() as writer:
        metadata = writer.scalar(
            select(document_revisions.c.source_metadata).where(
                document_revisions.c.revision_id == revision_id
            )
        )
        writer.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == revision_id)
            .values(
                source_metadata={**metadata, "content_coverage": coverage, "blocks_complete": False}
            )
        )
        prior = dict(
            writer.execute(select(claims).where(claims.c.claim_id == source.record.claim_id.value))
            .mappings()
            .one()
        )
    result = read_graph(graph_engine, event_id)
    assert not any(edge.relation_type == "related_paper" for edge in result.edges)
    assert any(
        gap.relation_type == "related_paper" and gap.status == "unknown" for gap in result.gaps
    )
    with graph_engine.connect() as reader:
        current = dict(
            reader.execute(select(claims).where(claims.c.claim_id == source.record.claim_id.value))
            .mappings()
            .one()
        )
    assert current == prior and current["claim_status"] == "supported"
