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


@pytest.mark.parametrize(
    "kind,statement,supported",
    [
        ("atlas", "Untrusted instructions do not enter a model input.", False),
        ("atlas", "不可信指令不会进入模型输入。", False),
        ("atlas", "The mechanism is unconfirmed; the model input path is unknown.", False),
        ("atlas", "攻击机制尚未确认，输入路径未知。", False),
        ("atlas", "Untrusted instructions are not sanitized and enter a model input.", True),
        (
            "atlas",
            "Untrusted instructions not only enter a model input but also override instructions.",
            True,
        ),
        ("atlas", "未经过滤的外部指令进入模型输入。", True),
        ("atlas", "外部指令不仅进入模型输入，而且覆盖已有指令。", True),
        (
            "paper",
            "This paper does not analyze the vulnerability; it analyzes another package.",
            False,
        ),
        (
            "paper",
            "Analysis of this vulnerability is unconfirmed; the mechanism is unknown.",
            False,
        ),
        ("paper", "本文没有分析该漏洞，仅分析另一个组件。", False),
        ("paper", "该论文与本事件的分析关系尚未确认。", False),
        ("paper", "This paper analyzes the vulnerability but does not execute the PoC.", True),
        (
            "paper",
            "This paper not only analyzes the vulnerability but also preserves prerequisites.",
            True,
        ),
        ("paper", "本文分析该漏洞，但没有执行概念验证程序。", True),
        ("paper", "本文不仅分析该漏洞，也保留攻击前提。", True),
        (
            "paper",
            "This paper analyzes the vulnerability; the analysis is not supported by evidence.",
            False,
        ),
    ],
)
def test_source_relation_polarity_does_not_change_supported_pg_facts(
    graph_engine, tmp_path, kind, statement, supported
):
    event_id = uuid4()
    sentence = SOURCE_IDENTIFIER + ": " + statement
    value = (
        {**ATLAS, "mechanism": sentence}
        if kind == "atlas"
        else {**paper_value(graph_engine, tmp_path / "paper"), "support_summary": sentence}
    )
    source = publish_fact(graph_engine, tmp_path / "source", event_id, value)
    publish_event(graph_engine, event_id, [source])
    with graph_engine.connect() as reader:
        prior = (
            reader.execute(select(claims).where(claims.c.claim_id == source.record.claim_id.value))
            .mappings()
            .one()
        )
    snapshot = read_graph(graph_engine, event_id)
    relation = "mapped_atlas" if kind == "atlas" else "related_paper"
    assert any(edge.relation_type == relation for edge in snapshot.edges) is supported
    assert snapshot.rule_version == "r10-graph-1.2.0"
    with graph_engine.connect() as reader:
        row = (
            reader.execute(select(claims).where(claims.c.claim_id == source.record.claim_id.value))
            .mappings()
            .one()
        )
    assert row["claim_status"] == "supported" and row["object_json"] == prior["object_json"]


@pytest.mark.parametrize("kind", ["atlas", "paper"])
@pytest.mark.parametrize("language", ["english", "chinese"])
@pytest.mark.parametrize("retain_qualifier", [False, True])
def test_wrapped_relation_qualifiers_are_preserved_from_complete_source(
    graph_engine, tmp_path, kind, language, retain_qualifier
):
    event_id = uuid4()
    condition = (
        "Only when attacker can submit\nuntrusted input."
        if language == "english"
        else "仅当攻击者能够提交\n不可信输入时。"
    )
    if kind == "atlas":
        value = {**ATLAS, "prerequisites": [condition]}
    else:
        value = {
            **paper_value(graph_engine, tmp_path / "paper"),
            "support_summary": SOURCE_IDENTIFIER
            + ": This paper analyzes the vulnerability.\n"
            + condition,
        }
    source = publish_fact(graph_engine, tmp_path / "source", event_id, value)
    publish_event(graph_engine, event_id, [source])
    if not retain_qualifier:
        changed = (
            {**value, "prerequisites": [condition.splitlines()[0]]}
            if kind == "atlas"
            else {**value, "support_summary": value["support_summary"].splitlines()[0]}
        )
        with graph_engine.begin() as writer:
            writer.execute(
                update(claims)
                .where(claims.c.claim_id == source.record.claim_id.value)
                .values(object_json=changed)
            )
    relation = "mapped_atlas" if kind == "atlas" else "related_paper"
    result = read_graph(graph_engine, event_id)
    assert any(edge.relation_type == relation for edge in result.edges) is retain_qualifier


@pytest.mark.parametrize(
    "graph_private,role,hidden_visibility,hidden_tenant,linked",
    [
        (False, Role.VIEWER, "tenant", "other", False),
        (False, Role.ANALYST, "tenant", "other", False),
        (False, Role.ANALYST, "tenant", "owner", False),
        (False, Role.ANALYST, "public", None, False),
        (True, Role.ANALYST, "tenant", "other", False),
        (True, Role.ANALYST, "public", None, False),
        (False, Role.VIEWER, "tenant", "other", True),
        (True, Role.ANALYST, "tenant", "other", True),
    ],
)
def test_non_candidate_claim_writer_cannot_delay_visible_graph(
    graph_engine,
    tmp_path,
    register_sensitive_failure_value,
    graph_private,
    role,
    hidden_visibility,
    hidden_tenant,
    linked,
):
    event_id = uuid4()
    graph_scope = (
        VisibilityScope(visibility="tenant", tenant_id="owner")
        if graph_private
        else VisibilityScope(visibility="public")
    )
    source = publish_fact(graph_engine, tmp_path / "visible", event_id, VERSION, scope=graph_scope)
    publish_event(graph_engine, event_id, [source], scope=graph_scope)
    hidden = publish_fact(
        graph_engine,
        tmp_path / "hidden",
        event_id,
        VERSION,
        scope=VisibilityScope(visibility=hidden_visibility, tenant_id=hidden_tenant),
    )
    if linked:
        with graph_engine.begin() as writer:
            writer.execute(
                event_documents.insert().values(
                    event_id=str(event_id),
                    revision_id=hidden.revision_id.value,
                    active=True,
                    associated_at=NOW,
                )
            )
    client, _username, auth, token = client_for(
        graph_engine, register_sensitive_failure_value, role
    )
    before = read_graph(graph_engine, event_id, scope=auth.build_access_scope(token))
    assert before.edges
    statements = []
    sql_states = []

    def count(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT"):
            statements.append(statement)

    def error(context):
        sql_states.append(getattr(context.original_exception, "sqlstate", None))

    event.listen(graph_engine, "before_cursor_execute", count)
    event.listen(graph_engine, "handle_error", error)
    try:
        baseline = client.get(f"/v1/events/{event_id}/graph")
        assert baseline.status_code == 200
        baseline_selects = len(statements)
        statements.clear()
        with graph_engine.connect() as writer, writer.begin():
            writer.execute(
                update(claims)
                .where(claims.c.claim_id == hidden.record.claim_id.value)
                .values(object_value=claims.c.object_value)
            )
            started = time.perf_counter()
            response = client.get(f"/v1/events/{event_id}/graph")
            elapsed = time.perf_counter() - started
        assert response.status_code == 200 and elapsed < 3
        assert response.json()["content_sha256"] == before.content_sha256
        assert len(statements) == baseline_selects
        assert "40P01" not in sql_states and "55P03" not in sql_states
        record_response(
            "non_candidate_lock",
            response,
            before.content_sha256,
            graph_private=graph_private,
            role=role.value,
            hidden_visibility=hidden_visibility,
            hidden_tenant=hidden_tenant,
            linked=linked,
            elapsed_seconds=elapsed,
            selects=len(statements),
            baseline_selects=baseline_selects,
            sql_states=sql_states,
        )
    finally:
        event.remove(graph_engine, "before_cursor_execute", count)
        event.remove(graph_engine, "handle_error", error)
        client.close()


@pytest.mark.parametrize("addition", ["claim", "evidence", "association"])
@pytest.mark.parametrize("bump_epoch", [False, True])
def test_new_visible_input_after_rr_is_found_by_complete_fresh_read(
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

    def mutate(connection, cursor, statement, parameters, context, executemany):
        nonlocal inserted
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
        assert inserted and response.status_code == 409
        assert response.json()["error"]["code"] == "graph_snapshot_changed"
        assert "edges" not in response.json()
        record_response(
            "new_visible_" + addition, response, before.content_sha256, bump_epoch=bump_epoch
        )
    finally:
        event.remove(graph_engine, "after_cursor_execute", mutate)
        client.close()
