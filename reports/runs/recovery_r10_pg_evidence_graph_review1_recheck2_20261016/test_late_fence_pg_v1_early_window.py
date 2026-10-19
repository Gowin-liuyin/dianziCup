"""PG 完整原文极性和可见读锁集合；全部合成 fixture，实际独立事务与 HTTP factory。"""

import time
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import NOW, publisher_scope
from test_r10_evidence_graph_pg import (
    ATLAS,
    SOURCE_IDENTIFIER,
    VERSION,
    paper_value,
    publish_event,
    publish_fact,
    read_graph,
)
from test_r10_evidence_graph_pg import graph_engine as graph_engine
from test_r10_graph_validity_pg import client_for, record_response

from ai_intel.domain.access import Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.knowledge.models import evidence
from ai_intel.knowledge.persistence import KnowledgeRepository
from ai_intel.knowledge.persistence_models import claim_evidence, claims, event_documents
from ai_intel.knowledge.revisions import attach_evidence_span

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize("addition", ["claim", "evidence", "association"])
@pytest.mark.parametrize("bump_epoch", [False, True])
def test_late_visible_input_after_current_support_read(
    graph_engine, tmp_path, register_sensitive_failure_value, addition, bump_epoch
):
    event_id = uuid4()
    source = publish_fact(graph_engine, tmp_path / "source", event_id, VERSION)
    publish_event(graph_engine, event_id, [source])
    extra = (
        publish_fact(graph_engine, tmp_path / "extra", event_id, VERSION)
        if addition == "association"
        else None
    )
    before = read_graph(graph_engine, event_id)
    assert before.edges
    client, *_ = client_for(graph_engine, register_sensitive_failure_value)
    inserted = False
    support_queries = 0

    def mutate(connection, cursor, statement, parameters, context, executemany):
        nonlocal inserted, support_queries
        if inserted or not statement.lstrip().startswith("SELECT events."):
            return
        inserted = True
        with Session(graph_engine) as writer, writer.begin():
            previous_epoch = writer.scalar(
                text("SELECT epoch FROM scope_epochs WHERE scope_key='public'")
            )
            if addition == "claim":
                record = ClaimRecord.model_validate(
                    source.record.model_copy(
                        update={
                            "claim_id": Identifier(value=str(uuid4())),
                            "asserted_at": NOW + timedelta(seconds=1),
                        }
                    ).model_dump()
                )
                KnowledgeRepository(writer, publisher_scope(source.record.scope)).publish(
                    "fixture-new-visible-" + uuid4().hex,
                    source.record.scope,
                    (source.model_copy(update={"record": record}),),
                    created_at=NOW,
                )
            elif addition == "evidence":
                span = (
                    writer.execute(
                        select(evidence).where(
                            evidence.c.evidence_id == source.evidence_links[0].evidence_id.value
                        )
                    )
                    .mappings()
                    .one()
                )
                saved = attach_evidence_span(
                    writer.connection(),
                    span["revision_id"],
                    span["start_offset"],
                    span["end_offset"],
                    span["locator"],
                    span["quote"],
                    True,
                    span["visibility"],
                    span["tenant_id"],
                    NOW,
                    block_id=span["block_id"],
                    verified_at=NOW,
                )
                assert saved != span["evidence_id"]
                writer.execute(
                    claim_evidence.insert().values(
                        claim_id=source.record.claim_id.value,
                        evidence_id=saved,
                        support_kind="supports",
                        validation_status="validated",
                    )
                )
            else:
                writer.execute(
                    event_documents.insert().values(
                        event_id=str(event_id),
                        revision_id=extra.revision_id.value,
                        active=True,
                        associated_at=NOW,
                    )
                )
            writer.execute(
                text("UPDATE scope_epochs SET epoch=:epoch WHERE scope_key='public'"),
                {"epoch": previous_epoch + int(bump_epoch)},
            )

    event.listen(graph_engine, "after_cursor_execute", mutate)
    try:
        response = client.get(f"/v1/events/{event_id}/graph")
        after = read_graph(graph_engine, event_id)
        assert after.content_sha256 != before.content_sha256
        record_response("independent_late_" + addition, response, before.content_sha256,
                        bump_epoch=bump_epoch, after_digest=after.content_sha256,
                        support_queries=support_queries, inserted=inserted)
        assert inserted and response.status_code == 409
        assert response.json()["error"]["code"] == "graph_snapshot_changed"
        assert "edges" not in response.json()
        record_response(
            "new_visible_" + addition, response, before.content_sha256, bump_epoch=bump_epoch
        )
    finally:
        event.remove(graph_engine, "after_cursor_execute", mutate)
        client.close()
