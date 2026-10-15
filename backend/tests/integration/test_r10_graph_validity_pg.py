"""真实 PG 原文关系、提交前撤权围栏与请求内目标缓存；输入均为合成 fixture。"""

import hashlib
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event, select, text, update
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import (
    NOW,
    prepared_submission,
    publish_submission,
    publisher_scope,
)
from test_r10_evidence_graph_pg import (
    ATLAS,
    FIXTURE_RAW_DIRECTORY,
    SOURCE_IDENTIFIER,
    VERSION,
    paper_value,
    publish_event,
    publish_fact,
    read_graph,
    replace_source_body,
    store_fixture_original,
)
from test_r10_evidence_graph_pg import (
    graph_engine as graph_engine,
)

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.graph_routes import build_graph_router
from ai_intel.domain.access import Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import document_revisions, documents, evidence
from ai_intel.knowledge.persistence import EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import claims, event_external_ids
from ai_intel.knowledge.revisions import add_text_block, attach_evidence_span

pytestmark = pytest.mark.real_pg


def test_semantic_fixture_original_bytes_match_all_published_quote_coordinates(
    graph_engine, tmp_path
):
    event_id = uuid4()
    source = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    with Session(graph_engine) as reader:
        content_hash = reader.scalar(
            select(document_revisions.c.content_hash).where(
                document_revisions.c.revision_id == source.revision_id.value
            )
        )
        spans = list(
            reader.execute(
                select(evidence.c.start_offset, evidence.c.end_offset, evidence.c.quote).where(
                    evidence.c.revision_id == source.revision_id.value
                )
            )
        )
    original = ContentStore(FIXTURE_RAW_DIRECTORY).read_verified(content_hash).decode()
    assert all(original[start:end] == quote for start, end, quote in spans)
    assert SOURCE_IDENTIFIER in original and "fixture-package" in original
    assert str(event_id) not in original


def client_for(engine, register, role=Role.VIEWER):
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(engine),
        ("http://localhost:5173",),
        False,
        state_store=PgAuthenticationStateStore(engine),
    )
    username = "fixture-r10-validity-" + uuid4().hex
    password = secrets.token_urlsafe(32)
    register(SecretStr(password))
    auth.create_precreated_user(username, password, "owner", role)
    session_token, _ = auth.login(username, password, "http://localhost:5173", uuid4().hex)
    register(SecretStr(session_token))
    app = FastAPI()
    app.include_router(build_graph_router(lambda: auth, engine), prefix="/v1")
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, session_token)
    return client, username, auth, session_token


def record_response(case, response, before_hash, **fields):
    path = os.environ.get("R10_OBSERVATIONS_PATH")
    if path:
        value = {
            "case": case,
            "recorded_at": datetime.now().astimezone().isoformat(),
            "status": response.status_code,
            "body": response.json(),
            "body_sha256": hashlib.sha256(response.content).hexdigest(),
            "candidate_content_sha256": before_hash,
            **fields,
        }
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


@pytest.mark.parametrize(
    "change", ["source", "document", "revision", "claim", "epoch", "event_version"]
)
@pytest.mark.parametrize("bump_epoch", [False, True])
def test_committed_mutation_after_rr_event_read_cannot_escape_http_fence(
    graph_engine, tmp_path, register_sensitive_failure_value, change, bump_epoch
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    before = read_graph(graph_engine, event_id)
    assert before.edges
    client, _username, _auth, _session_token = client_for(
        graph_engine, register_sensitive_failure_value
    )
    changed = False

    def mutate(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if changed or not statement.lstrip().startswith("SELECT events."):
            return
        changed = True
        with graph_engine.begin() as writer:
            if change == "source":
                writer.execute(
                    text(
                        "UPDATE sources SET visibility='tenant',tenant_id='other' "
                        "WHERE source_id=:id"
                    ),
                    {"id": submission.source_id.value},
                )
            elif change == "document":
                writer.execute(
                    update(documents)
                    .where(documents.c.source_id == submission.source_id.value)
                    .values(visibility="tenant", tenant_id="other")
                )
            elif change == "revision":
                writer.execute(
                    update(document_revisions)
                    .where(document_revisions.c.revision_id == submission.revision_id.value)
                    .values(visibility="tenant", tenant_id="other")
                )
            elif change == "claim":
                writer.execute(
                    update(claims)
                    .where(claims.c.claim_id == submission.record.claim_id.value)
                    .values(claim_status="withdrawn")
                )
            elif change == "event_version":
                writer.execute(
                    text(
                        "UPDATE events SET business_version=business_version+1 WHERE event_id=:id"
                    ),
                    {"id": str(event_id)},
                )
            if bump_epoch or change == "epoch":
                writer.execute(
                    text("UPDATE scope_epochs SET epoch=epoch+1 WHERE scope_key='public'")
                )

    event.listen(graph_engine, "after_cursor_execute", mutate)
    try:
        response = client.get(f"/v1/events/{event_id}/graph")
    finally:
        event.remove(graph_engine, "after_cursor_execute", mutate)
        client.close()
    assert changed and response.status_code == 409
    assert response.json()["error"]["code"] == "graph_snapshot_changed"
    assert "edges" not in response.json()
    record_response("fresh_" + change, response, before.content_sha256, bump_epoch=bump_epoch)


@pytest.mark.parametrize("change", ["role", "tenant", "session"])
def test_authentication_mutation_during_candidate_read_denies_private_http(
    graph_engine, tmp_path, register_sensitive_failure_value, change
):
    event_id = uuid4()
    private = VisibilityScope(visibility="tenant", tenant_id="owner")
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION, scope=private)
    publish_event(graph_engine, event_id, [submission], scope=private)
    client, username, auth, session_token = client_for(
        graph_engine, register_sensitive_failure_value, Role.ANALYST
    )
    changed = False

    def mutate(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if changed or not statement.lstrip().startswith("SELECT events."):
            return
        changed = True
        if change == "session":
            auth.logout(session_token)
        else:
            assignment = "role='viewer'" if change == "role" else "tenant_id='other'"
            with graph_engine.begin() as writer:
                writer.execute(
                    text("UPDATE users SET " + assignment + " WHERE username=:username"),
                    {"username": username},
                )

    event.listen(graph_engine, "after_cursor_execute", mutate)
    try:
        response = client.get(f"/v1/events/{event_id}/graph")
    finally:
        event.remove(graph_engine, "after_cursor_execute", mutate)
        client.close()
    assert changed and response.status_code == (401 if change == "session" else 403)
    assert "edges" not in response.json()
    record_response("authentication_" + change, response, None)


def test_parent_writer_can_commit_epoch_while_reader_waits_without_inverse_lock_order(
    graph_engine, tmp_path, register_sensitive_failure_value
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    client, *_ = client_for(graph_engine, register_sensitive_failure_value)
    reached_parent_lock = Event()
    sql_states = []

    def observe_error(context):
        code = getattr(context.original_exception, "sqlstate", None)
        if isinstance(code, str):
            sql_states.append(code)

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "FROM sources" in statement and "FOR SHARE" in statement:
            reached_parent_lock.set()

    event.listen(graph_engine, "before_cursor_execute", observe)
    event.listen(graph_engine, "handle_error", observe_error)
    started = time.perf_counter()
    try:
        with graph_engine.connect() as writer, ThreadPoolExecutor(max_workers=1) as pool:
            transaction = writer.begin()
            writer.execute(
                text("UPDATE sources SET name=name WHERE source_id=:id"),
                {"id": submission.source_id.value},
            )
            future = pool.submit(client.get, f"/v1/events/{event_id}/graph")
            assert reached_parent_lock.wait(3)
            writer.execute(
                update(documents)
                .where(documents.c.source_id == submission.source_id.value)
                .values(visibility="tenant", tenant_id="other")
            )
            writer.execute(text("UPDATE scope_epochs SET epoch=epoch+1 WHERE scope_key='public'"))
            transaction.commit()
            response = future.result(timeout=10)
        assert response.status_code == 409
        assert "40P01" not in sql_states
        record_response(
            "parent_then_epoch",
            response,
            None,
            elapsed_seconds=time.perf_counter() - started,
            sql_states=sql_states,
        )
    finally:
        event.remove(graph_engine, "before_cursor_execute", observe)
        event.remove(graph_engine, "handle_error", observe_error)
        client.close()


def test_parent_lock_timeout_returns_bounded_unavailable_without_fake_success(
    graph_engine, tmp_path, register_sensitive_failure_value
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    client, *_ = client_for(graph_engine, register_sensitive_failure_value)
    started = time.perf_counter()
    sql_states = []

    def observe_error(context):
        code = getattr(context.original_exception, "sqlstate", None)
        if isinstance(code, str):
            sql_states.append(code)

    event.listen(graph_engine, "handle_error", observe_error)
    try:
        with graph_engine.connect() as writer, writer.begin():
            writer.execute(
                text("UPDATE sources SET name=name WHERE source_id=:id"),
                {"id": submission.source_id.value},
            )
            response = client.get(f"/v1/events/{event_id}/graph")
        assert response.status_code == 503
        assert sql_states == ["55P03"]
        assert "edges" not in response.json()
        record_response(
            "parent_lock_timeout",
            response,
            None,
            elapsed_seconds=time.perf_counter() - started,
            sql_states=sql_states,
        )
    finally:
        client.close()
        event.remove(graph_engine, "handle_error", observe_error)


@pytest.mark.parametrize(
    "change", ["package", "boundary", "wrapped_condition", "fix", "other_event"]
)
def test_typed_version_requires_matching_contextual_source_lines(graph_engine, tmp_path, change):
    event_id = uuid4()
    submission = prepared_submission(graph_engine, tmp_path, predicate="version_assertion")
    value = dict(VERSION)
    lines = [value["raw_expression"], value["vendor_fix"], *value["mitigations"]]
    if change == "other_event":
        value["raw_expression"] = value["raw_expression"].replace(
            SOURCE_IDENTIFIER, "GHSA-cccc-ffff-gggg"
        )
        lines[0] = value["raw_expression"]
        lines.append("Background reference " + SOURCE_IDENTIFIER + ".")
    elif change == "package":
        lines[0] = lines[0].replace("fixture-package", "other-package")
    elif change == "boundary":
        lines[0] = lines[0].replace("<1.4.2", "<1.5.0")
    elif change == "wrapped_condition":
        lines.append("Only when remote tools are enabled.")
    else:
        lines[1] = "No fix is available for GHSA-2345-6789-cfgh."
    record = ClaimRecord.model_validate(
        {
            **submission.record.model_dump(),
            "schema_version": 3,
            "subject": str(event_id),
            "object_value": value,
        }
    )
    submission = replace_source_body(
        graph_engine, submission.model_copy(update={"record": record}), lines
    )
    publish_submission(graph_engine, submission)
    publish_event(graph_engine, event_id, [submission])
    assert read_graph(graph_engine, event_id).edges == ()


def test_atlas_cannot_drop_prerequisites_present_in_source_block(graph_engine, tmp_path):
    event_id = uuid4()
    value = {**ATLAS, "prerequisites": []}
    submission = publish_fact(graph_engine, tmp_path, event_id, value)
    replace_source_body(
        graph_engine, submission, [value["mechanism"], "Attacker can submit untrusted input."]
    )
    publish_event(graph_engine, event_id, [submission])
    assert read_graph(graph_engine, event_id).edges == ()


def test_precise_source_owner_field_binds_a_rule_fact_without_internal_uuid_in_text(
    graph_engine, tmp_path
):
    event_id = uuid4()
    value = {**VERSION, "raw_expression": "PyPI fixture-package affected versions: >=1.0,<1.4.2"}
    template = prepared_submission(
        graph_engine, tmp_path, predicate="version_assertion", claim_origin="rule_derived"
    )
    record = ClaimRecord.model_validate(
        {
            **template.record.model_dump(),
            "schema_version": 3,
            "subject": str(event_id),
            "object_value": value,
        }
    )
    source = replace_source_body(
        graph_engine,
        template.model_copy(update={"record": record}),
        [value["raw_expression"], value["vendor_fix"], *value["mitigations"]],
    )
    with graph_engine.begin() as writer:
        block_id = add_text_block(
            writer,
            source.revision_id.value,
            2,
            500,
            500 + len(SOURCE_IDENTIFIER),
            SOURCE_IDENTIFIER,
        )
        writer.execute(
            text("UPDATE text_blocks SET json_pointer='/ghsa_id' WHERE block_id=:id"),
            {"id": block_id},
        )
        span_id = attach_evidence_span(
            writer,
            source.revision_id.value,
            500,
            500 + len(SOURCE_IDENTIFIER),
            "/ghsa_id",
            SOURCE_IDENTIFIER,
            True,
            "public",
            None,
            NOW,
            block_id=block_id,
            verified_at=NOW,
        )
        store_fixture_original(writer, source.revision_id.value)
    owner_record = ClaimRecord.model_validate(
        {
            **template.record.model_dump(),
            "claim_id": {"value": str(uuid4())},
            "subject": str(event_id),
            "predicate": "source_identifier",
            "object_value": SOURCE_IDENTIFIER,
        }
    )
    owner = template.model_copy(
        update={
            "record": owner_record,
            "json_path": "/ghsa_id",
            "evidence_links": (
                EvidenceLink(
                    evidence_id={"value": span_id},
                    support_kind="supports",
                    validation_status="validated",
                ),
            ),
        }
    )
    publish_submission(graph_engine, source)
    publish_submission(graph_engine, owner)
    publish_event(graph_engine, event_id, [source])
    result = read_graph(graph_engine, event_id)
    assert any(edge.relation_type == "affects_component_version" for edge in result.edges)
    with Session(graph_engine) as reader:
        row = reader.execute(
            select(claims.c.claim_origin, claims.c.object_json).where(
                claims.c.claim_id == source.record.claim_id.value
            )
        ).one()
    assert (
        row.claim_origin == "rule_derived" and row.object_json["comparison_support"] == "supported"
    )
    assert str(event_id) not in "\n".join(
        [value["raw_expression"], value["vendor_fix"], *value["mitigations"], SOURCE_IDENTIFIER]
    )


def test_published_static_poc_presence_is_not_a_remediation_or_lab_verification(
    graph_engine, tmp_path
):
    event_id = uuid4()
    value = {
        "kind": "artifact_reference",
        "uri": "https://example.invalid/static-poc",
        "title": "Fixture PoC",
        "artifact_kind": "poc",
        "static_status": "static_reviewed",
    }
    template = prepared_submission(graph_engine, tmp_path, predicate="artifact_reference")
    record = ClaimRecord.model_validate(
        {
            **template.record.model_dump(),
            "schema_version": 3,
            "subject": str(event_id),
            "object_value": value,
        }
    )
    source = replace_source_body(
        graph_engine,
        template.model_copy(update={"record": record}),
        [
            "GHSA-2345-6789-cfgh: Fixture PoC https://example.invalid/static-poc "
            "proof of concept; not executed."
        ],
    )
    publish_submission(graph_engine, source)
    publish_event(graph_engine, event_id, [source])
    result = read_graph(graph_engine, event_id)
    assert {edge.relation_type for edge in result.edges} == {"same_event"}
    assert not any("lab_verified" in node.label for node in result.nodes)
    with Session(graph_engine) as reader:
        stored = reader.scalar(
            select(claims.c.object_json).where(claims.c.claim_id == source.record.claim_id.value)
        )
    assert stored["static_status"] == "static_reviewed"


@pytest.mark.parametrize("descriptor", ["matching", "missing", "ordinary"])
def test_non_cve_binding_uses_primary_source_product_and_security_descriptor(
    graph_engine, tmp_path, descriptor
):
    event_id = uuid4()
    value = {
        **VERSION,
        "raw_expression": "PyPI fixture-package affected versions: >=1.0,<1.4.2",
        "vendor_fix": None,
        "mitigations": [],
    }
    template = prepared_submission(graph_engine, tmp_path, predicate="version_assertion")
    excerpt = (
        "Advisory AI-2026-01: fixture-package is vulnerable to untrusted model input."
        if descriptor != "ordinary"
        else "Advisory AI-2026-01: fixture-package has a new colour theme."
    )
    lines = [value["raw_expression"], excerpt, "fixture-package"]
    record = ClaimRecord.model_validate(
        {
            **template.record.model_dump(),
            "schema_version": 3,
            "subject": str(event_id),
            "object_value": value,
        }
    )
    source = replace_source_body(
        graph_engine, template.model_copy(update={"record": record}), lines
    )
    publish_submission(graph_engine, source)
    if descriptor != "missing":
        for index, predicate, object_value in (
            (1, "source_excerpt", excerpt),
            (2, "affected_product", "fixture-package"),
        ):
            bound = ClaimRecord.model_validate(
                {
                    **template.record.model_dump(),
                    "claim_id": {"value": str(uuid4())},
                    "subject": str(event_id),
                    "predicate": predicate,
                    "object_value": object_value,
                }
            )
            publish_submission(
                graph_engine,
                template.model_copy(
                    update={"record": bound, "evidence_links": (source.evidence_links[index],)}
                ),
            )
    publish_event(graph_engine, event_id, [source])
    with graph_engine.begin() as writer:
        writer.execute(
            event_external_ids.delete().where(event_external_ids.c.event_id == str(event_id))
        )
    result = read_graph(graph_engine, event_id)
    assert any(edge.relation_type == "affects_component_version" for edge in result.edges) == (
        descriptor == "matching"
    )
    assert str(event_id) not in "\n".join(lines)


def test_2000_support_rows_share_one_request_local_paper_acl_lookup(graph_engine, tmp_path):
    event_id = uuid4()
    value = paper_value(graph_engine, tmp_path / "target")
    template = prepared_submission(
        graph_engine, tmp_path / "source", predicate="literature_reference"
    )
    record = ClaimRecord.model_validate(
        {
            **template.record.model_dump(),
            "schema_version": 3,
            "subject": str(event_id),
            "object_value": value,
        }
    )
    lines = [
        value["support_summary"],
        value["title"] + " " + value["uri"],
        *("Source context paragraph " + str(index) + "." for index in range(18)),
    ]
    source = replace_source_body(
        graph_engine, template.model_copy(update={"record": record}), lines
    )
    submissions = tuple(
        source.model_copy(
            update={
                "record": record.model_copy(
                    update={
                        "claim_id": Identifier(value=str(uuid4())),
                        "asserted_at": NOW + timedelta(seconds=index),
                    }
                )
            }
        )
        for index in range(100)
    )
    submissions = tuple(
        item.model_copy(update={"record": ClaimRecord.model_validate(item.record.model_dump())})
        for item in submissions
    )
    with Session(graph_engine) as session, session.begin():
        KnowledgeRepository(session, publisher_scope(source.record.scope)).publish(
            "fixture-r10-2000", source.record.scope, submissions, created_at=NOW
        )
    publish_event(graph_engine, event_id, [source])
    counts = {"selects": 0, "target_acl": 0}

    def count(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT"):
            counts["selects"] += 1
            if "JOIN sources" in statement and value["target_revision_id"] in parameters.values():
                counts["target_acl"] += 1

    event.listen(graph_engine, "before_cursor_execute", count)
    started = time.perf_counter()
    try:
        result = read_graph(graph_engine, event_id, max_nodes=1, max_edges=1)
    finally:
        event.remove(graph_engine, "before_cursor_execute", count)
    assert result.truncated and len(result.nodes) == 1 and result.edges == ()
    assert counts["target_acl"] == 1 and counts["selects"] <= 12
    path = os.environ.get("R10_OBSERVATIONS_PATH")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "case": "2000_support_rows",
                        "input_claims": 100,
                        "input_support_rows": 2000,
                        "selects": counts["selects"],
                        "target_acl_selects": counts["target_acl"],
                        "elapsed_seconds": time.perf_counter() - started,
                        "snapshot": result.model_dump(mode="json"),
                        "data_mode": "fixture",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    with graph_engine.begin() as writer:
        writer.execute(
            update(documents)
            .where(documents.c.document_id == value["target_document_id"])
            .values(visibility="tenant", tenant_id="other")
        )
    assert not any(
        edge.relation_type == "related_paper" for edge in read_graph(graph_engine, event_id).edges
    )
