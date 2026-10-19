"""隔离真实 PG 的合成发布与只读 HTTP 回归；fixture 结果不计 live。"""

import hashlib
import secrets
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r02_knowledge_revisions import (
    NOW,
    prepared_submission,
    publish_submission,
    publisher_scope,
)
from test_r04_knowledge_api_pg import seed_event

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.graph_routes import build_graph_router
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.event_linking import EventIdentifier, EventRepository, EventSubmission
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService
from ai_intel.knowledge.models import document_revisions, documents, evidence, text_blocks
from ai_intel.knowledge.persistence import EvidenceLink
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
)
from ai_intel.knowledge.revisions import attach_evidence_span, register_response_content

pytestmark = pytest.mark.real_pg
SOURCE_IDENTIFIER = "GHSA-2345-6789-cfgh"
TAXONOMY_COMMIT = "a" * 40
FIXTURE_RAW_DIRECTORY = Path(tempfile.gettempdir()) / "dianzi-r10-graph-fixture-raw"
VERSION = {
    "kind": "version_assertion",
    "package_key": "fixture-package",
    "ecosystem": "PyPI",
    "scheme": "pep440",
    "raw_expression": "GHSA-2345-6789-cfgh PyPI fixture-package affected versions: >=1.0,<1.4.2",
    "intervals": [{"introduced": "1.0", "fixed": "1.4.2"}],
    "comparison_support": "supported",
    "vendor_fix": "Fixed in 1.4.2 for GHSA-2345-6789-cfgh.",
    "mitigations": ["Mitigation: limit untrusted inputs for GHSA-2345-6789-cfgh."],
}
ATLAS = {
    "kind": "atlas_mapping",
    "technique_id": "AML.T0051",
    "taxonomy_version": TAXONOMY_COMMIT,
    "mechanism": "GHSA-2345-6789-cfgh: Untrusted instructions enter a model input.",
    "prerequisites": ["Attacker can submit untrusted input."],
}


def store_fixture_original(connection, revision_id):
    blocks = list(
        connection.execute(
            select(text_blocks)
            .where(text_blocks.c.revision_id == revision_id)
            .order_by(text_blocks.c.start_offset)
        ).mappings()
    )
    normalized = ""
    for block in blocks:
        assert block["start_offset"] >= len(normalized)
        normalized += " " * (block["start_offset"] - len(normalized)) + block["block_text"]
    stored = register_response_content(
        connection, ContentStore(FIXTURE_RAW_DIRECTORY), normalized.encode(), NOW
    )
    connection.execute(
        update(document_revisions)
        .where(document_revisions.c.revision_id == revision_id)
        .values(
            content_hash=stored.content_hash,
            parser_version="fixture-text-1.1",
            normalizer_version="fixture-unicode-1.1",
        )
    )
    document_id = connection.scalar(
        select(document_revisions.c.document_id).where(
            document_revisions.c.revision_id == revision_id
        )
    )
    connection.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(content_hash=stored.content_hash)
    )


def replace_source_body(
    engine,
    submission,
    lines,
    *,
    kind="advisory",
    category="vendor_advisory",
    uri=None,
    source_version=None,
):
    body = "\n".join(lines)
    with engine.begin() as connection:
        first_evidence = submission.evidence_links[0].evidence_id.value
        block_id = connection.scalar(
            select(evidence.c.block_id).where(evidence.c.evidence_id == first_evidence)
        )
        connection.execute(
            update(text_blocks)
            .where(text_blocks.c.block_id == block_id)
            .values(
                block_text=body,
                text_sha256=hashlib.sha256(body.encode()).hexdigest(),
                end_offset=100 + len(body),
            )
        )
        connection.execute(
            update(evidence)
            .where(evidence.c.evidence_id == first_evidence)
            .values(
                quote=lines[0],
                quote_sha256=hashlib.sha256(lines[0].encode()).hexdigest(),
                end_offset=100 + len(lines[0]),
            )
        )
        links = [
            EvidenceLink(
                evidence_id={"value": first_evidence},
                support_kind="supports",
                validation_status="validated",
            )
        ]
        offset = 100 + len(lines[0]) + 1
        for line in lines[1:]:
            span_id = attach_evidence_span(
                connection,
                submission.revision_id.value,
                offset,
                offset + len(line),
                "fixture source line",
                line,
                True,
                submission.record.scope.visibility,
                submission.record.scope.tenant_id,
                NOW,
                block_id=block_id,
                verified_at=NOW,
            )
            links.append(
                EvidenceLink(
                    evidence_id={"value": span_id},
                    support_kind="supports",
                    validation_status="validated",
                )
            )
            offset += len(line) + 1
        connection.execute(
            update(documents)
            .where(documents.c.source_id == submission.source_id.value)
            .values(kind=kind)
        )
        connection.execute(
            text("UPDATE sources SET category=:category WHERE source_id=:id"),
            {"category": category, "id": submission.source_id.value},
        )
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == submission.revision_id.value)
            .values(
                parse_status="parsed",
                canonical_uri=uri
                or "https://example.invalid/advisory/" + submission.revision_id.value,
                source_metadata={
                    "is_synthetic": True,
                    "content_coverage": "full_text",
                    "blocks_complete": True,
                    "source_version": source_version,
                },
            )
        )
        store_fixture_original(connection, submission.revision_id.value)
    return submission.model_copy(update={"evidence_links": tuple(links)})


@pytest.fixture
def graph_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r06_catalog_r10_review2_20261016"
    assert url.database.startswith("test_dianzi_r06_catalog_")
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_r10_graph_" + uuid4().hex
    with base.begin() as connection:
        actual_database, actual_user = connection.execute(
            text("SELECT current_database(), current_user")
        ).one()
        assert actual_database == url.database and actual_user == url.username
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, connect_args={"connect_timeout": 5})
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def publish_fact(engine, path, event_id, value, *, scope=None, hypothesis=False):
    template = prepared_submission(
        engine,
        path,
        scope=scope,
        predicate=value["kind"],
        claim_status="unverified" if hypothesis else "supported",
        claim_origin="model_hypothesis" if hypothesis else "source_explicit",
    )
    record = ClaimRecord.model_validate(
        {
            **template.record.model_dump(),
            "schema_version": 3,
            "subject": str(event_id),
            "object_value": value,
        }
    )
    submission = template.model_copy(update={"record": record})
    if value["kind"] == "version_assertion":
        lines = [
            value["raw_expression"],
            *([value["vendor_fix"]] if value.get("vendor_fix") else []),
            *value.get("mitigations", []),
        ]
    elif value["kind"] == "atlas_mapping":
        lines = [value["mechanism"], *value["prerequisites"]]
        taxonomy = prepared_submission(engine, path / "taxonomy", scope=scope)
        replace_source_body(
            engine,
            taxonomy,
            ["AML.T0051: Prompt injection technique."],
            kind="standard",
            category="technical_standard",
            uri=f"https://raw.githubusercontent.com/mitre/atlas-data/{TAXONOMY_COMMIT}/dist/ATLAS.yaml",
            source_version=TAXONOMY_COMMIT,
        )
    elif value["kind"] == "literature_reference":
        lines = [value["support_summary"], value["title"] + " " + str(value["uri"])]
    else:
        lines = ["GHSA-2345-6789-cfgh: " + str(value)]
    submission = replace_source_body(engine, submission, lines)
    publish_submission(engine, submission)
    return submission


def publish_event(engine, event_id, submissions, *, scope=None):
    visibility = scope or VisibilityScope(visibility="public")
    revision_ids = [item.revision_id for item in submissions]
    with Session(engine) as reader:
        for revision_id in reader.scalars(
            select(document_revisions.c.revision_id).where(
                document_revisions.c.canonical_uri
                == f"https://raw.githubusercontent.com/mitre/atlas-data/{TAXONOMY_COMMIT}/dist/ATLAS.yaml",
                document_revisions.c.is_current.is_(True),
            )
        ):
            revision_ids.append({"value": revision_id})
    with Session(engine) as session, session.begin():
        EventRepository(session, publisher_scope(visibility)).publish_events(
            "fixture-r10-event-" + uuid4().hex,
            visibility,
            (
                EventSubmission(
                    event_id={"value": str(event_id)},
                    event_type="vulnerability",
                    title="合成证据图事件",
                    scope=visibility,
                    external_ids=(EventIdentifier(id_type="ghsa", id_value=SOURCE_IDENTIFIER),),
                    source_revision_ids=tuple(revision_ids),
                ),
            ),
            NOW,
        )


def read_graph(engine, event_id, *, scope=None, max_nodes=200, max_edges=400):
    scope = scope or AccessScope.for_authenticated_user("fixture-viewer", "owner", Role.VIEWER)
    with Session(engine) as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        return EvidenceGraphReadService(session, scope).event_graph(event_id, max_nodes, max_edges)


def paper_value(engine, path):
    target = prepared_submission(engine, path)
    replace_source_body(
        engine,
        target,
        [
            "合成分析论文",
            "Analysis of GHSA-2345-6789-cfgh in fixture-package: untrusted model input.",
        ],
        kind="paper",
        category="academic_paper",
        uri="https://example.invalid/fixture-paper",
    )
    with engine.begin() as connection:
        document_id = connection.scalar(
            select(document_revisions.c.document_id).where(
                document_revisions.c.revision_id == target.revision_id.value
            )
        )
        connection.execute(
            update(documents).where(documents.c.document_id == document_id).values(kind="paper")
        )
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == target.revision_id.value)
            .values(parse_status="parsed")
        )
    return {
        "kind": "literature_reference",
        "uri": "https://example.invalid/fixture-paper",
        "title": "合成分析论文",
        "reference_kind": "paper",
        "relation": "analysis",
        "support_summary": (
            "Analysis of GHSA-2345-6789-cfgh in fixture-package: untrusted model input."
        ),
        "target_document_id": document_id,
        "target_revision_id": target.revision_id.value,
    }


def test_six_relations_are_derived_from_published_pg_claims_and_preserve_reverse_support(
    graph_engine, tmp_path
):
    event_id = uuid4()
    values = [VERSION, ATLAS, paper_value(graph_engine, tmp_path / "paper"), VERSION]
    submissions = [
        publish_fact(graph_engine, tmp_path / str(index), event_id, value)
        for index, value in enumerate(values)
    ]
    publish_event(graph_engine, event_id, submissions)
    graph = read_graph(graph_engine, event_id)
    assert {edge.relation_type for edge in graph.edges} == {
        "same_event",
        "affects_component_version",
        "mapped_atlas",
        "related_paper",
        "remediated_by",
        "component_version_vulnerability",
    }
    assert graph.gaps == () and not graph.truncated and graph.business_version == 1
    forward = next(
        edge for edge in graph.edges if edge.relation_type == "affects_component_version"
    )
    reverse = next(
        edge for edge in graph.edges if edge.relation_type == "component_version_vulnerability"
    )
    assert (forward.subject_id, forward.object_id) == (reverse.object_id, reverse.subject_id)
    assert forward.supporting_claim_ids == reverse.supporting_claim_ids
    assert len(forward.supporting_claim_ids) == 2 and len(forward.source_revision_ids) == 2
    assert all(
        edge.status == "supported" and edge.evidence_span_ids and edge.reason
        for edge in graph.edges
    )
    assert graph == read_graph(graph_engine, event_id)
    replay_key = "fixture-r10-repeat-publish"
    publish_submission(graph_engine, submissions[0], replay_key)
    publish_submission(graph_engine, submissions[0], replay_key)
    assert graph == read_graph(graph_engine, event_id)
    with Session(graph_engine) as session:
        assert set(session.scalars(select(claims.c.claim_status))) == {"supported"}


@pytest.mark.parametrize(
    "altered",
    [
        "hypothesis",
        "disputed",
        "withdrawn",
        "unverified",
        "superseded",
        "conflict",
        "stale",
        "not_current",
        "old_revision",
        "inactive_association",
        "other_event",
        "unverified_span",
        "context",
        "wrong_assertion",
        "bad_hash",
        "bad_offset",
        "missing_block",
    ],
)
def test_invalid_or_unrelated_support_never_enters_effective_graph(graph_engine, tmp_path, altered):
    event_id = uuid4()
    submission = publish_fact(
        graph_engine, tmp_path, event_id, VERSION, hypothesis=altered == "hypothesis"
    )
    publish_event(graph_engine, event_id, [submission])
    claim_id = submission.record.claim_id.value
    evidence_id = submission.evidence_links[0].evidence_id.value
    with graph_engine.begin() as connection:
        claim_changes = {
            "disputed": {"claim_status": "disputed"},
            "withdrawn": {"claim_status": "withdrawn"},
            "unverified": {"claim_status": "unverified"},
            "superseded": {"claim_status": "superseded"},
            "conflict": {"condition_value": "conflict"},
            "stale": {"freshness": "stale"},
            "not_current": {"is_current": False},
            "other_event": {"subject": str(uuid4())},
        }
        if altered in claim_changes:
            connection.execute(
                update(claims).where(claims.c.claim_id == claim_id).values(**claim_changes[altered])
            )
        if altered == "old_revision":
            connection.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == submission.revision_id.value)
                .values(is_current=False)
            )
        if altered == "inactive_association":
            connection.execute(
                update(event_documents)
                .where(event_documents.c.event_id == str(event_id))
                .values(active=False)
            )
        if altered == "context":
            connection.execute(
                update(claim_evidence)
                .where(claim_evidence.c.claim_id == claim_id)
                .values(support_kind="context")
            )
        if altered == "wrong_assertion":
            connection.execute(
                update(claim_assertions)
                .where(claim_assertions.c.claim_id == claim_id)
                .values(assertion_kind="model_hypothesis")
            )
        span_changes = {
            "unverified_span": {"verified_at": None},
            "bad_hash": {"quote_sha256": "0" * 64},
            "bad_offset": {"start_offset": 99},
            "missing_block": {"block_id": None},
        }
        if altered in span_changes:
            connection.execute(
                update(evidence)
                .where(evidence.c.evidence_id == evidence_id)
                .values(**span_changes[altered])
            )
    graph = read_graph(graph_engine, event_id)
    assert graph.edges == () and len(graph.nodes) == 1 and len(graph.gaps) == 6
    assert all(gap.status == "unknown" for gap in graph.gaps)


def test_same_names_in_distinct_ecosystems_and_ranges_remain_separate(graph_engine, tmp_path):
    event_id = uuid4()
    values = [
        VERSION,
        {
            **VERSION,
            "ecosystem": "npm",
            "scheme": "semver",
            "raw_expression": (
                "GHSA-2345-6789-cfgh npm fixture-package affected versions: >=1.0,<1.4.2"
            ),
        },
        {
            **VERSION,
            "raw_expression": (
                "GHSA-2345-6789-cfgh PyPI fixture-package affected versions: >=2,<2.4"
            ),
            "intervals": [{"introduced": "2", "fixed": "2.4"}],
        },
    ]
    submissions = [
        publish_fact(graph_engine, tmp_path / str(index), event_id, value)
        for index, value in enumerate(values)
    ]
    publish_event(graph_engine, event_id, submissions)
    components = [
        node
        for node in read_graph(graph_engine, event_id).nodes
        if node.kind == "component_version"
    ]
    assert len({node.id for node in components}) == 3
    assert sum(node.label.startswith("PyPI:") for node in components) == 2
    assert sum(node.label.startswith("npm:") for node in components) == 1


@pytest.mark.parametrize(
    "change",
    [
        "background",
        "missing_target",
        "old_target",
        "private_source",
        "private_document",
        "private_revision",
    ],
)
def test_paper_relation_requires_visible_current_target_and_specific_support(
    graph_engine, tmp_path, change
):
    event_id = uuid4()
    value = paper_value(graph_engine, tmp_path / "target")
    if change == "background":
        value["relation"] = "background"
    if change == "missing_target":
        value.update(target_document_id=None, target_revision_id=None)
    submission = publish_fact(graph_engine, tmp_path / "source", event_id, value)
    publish_event(graph_engine, event_id, [submission])
    if change in {"old_target", "private_source", "private_document", "private_revision"}:
        with graph_engine.begin() as connection:
            if change == "old_target":
                connection.execute(
                    update(document_revisions)
                    .where(document_revisions.c.revision_id == value["target_revision_id"])
                    .values(is_current=False)
                )
            elif change == "private_source":
                connection.execute(
                    text(
                        "UPDATE sources SET visibility='tenant', tenant_id='other' "
                        "WHERE source_id=(SELECT source_id FROM documents WHERE document_id=:id)"
                    ),
                    {"id": value["target_document_id"]},
                )
            elif change == "private_document":
                connection.execute(
                    update(documents)
                    .where(documents.c.document_id == value["target_document_id"])
                    .values(visibility="tenant", tenant_id="other")
                )
            else:
                connection.execute(
                    update(document_revisions)
                    .where(document_revisions.c.revision_id == value["target_revision_id"])
                    .values(visibility="tenant", tenant_id="other")
                )
    graph = read_graph(graph_engine, event_id)
    assert not any(edge.relation_type == "related_paper" for edge in graph.edges)
    assert not any(node.kind == "paper" for node in graph.nodes)


def test_unknown_version_and_absent_action_preserve_gaps(graph_engine, tmp_path):
    event_id = uuid4()
    submission = publish_fact(
        graph_engine,
        tmp_path,
        event_id,
        {**VERSION, "comparison_support": "unknown", "vendor_fix": None, "mitigations": []},
    )
    publish_event(graph_engine, event_id, [submission])
    graph = read_graph(graph_engine, event_id)
    assert {edge.relation_type for edge in graph.edges} == {"same_event"}
    assert len(graph.gaps) == 5


def test_current_version_changed_withdrawal_and_truncation_do_not_resurrect_edges(
    graph_engine, tmp_path
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    graph = read_graph(graph_engine, event_id)
    assert len(graph.edges) == 5
    limited = read_graph(graph_engine, event_id, max_nodes=1, max_edges=1)
    assert limited.truncated and limited.edges == () and len(limited.nodes) == 1
    one_edge = read_graph(graph_engine, event_id, max_edges=1)
    assert one_edge.truncated and len(one_edge.edges) == 1
    assert all(
        edge.subject_id in {node.id for node in one_edge.nodes}
        and edge.object_id in {node.id for node in one_edge.nodes}
        for edge in one_edge.edges
    )
    with Session(graph_engine) as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        scope = AccessScope.for_authenticated_user("fixture-viewer", "owner", Role.VIEWER)
        reader = EvidenceGraphReadService(session, scope)
        frozen = reader.event_graph(event_id)
        with graph_engine.begin() as connection:
            connection.execute(
                text("UPDATE events SET business_version=business_version+1 WHERE event_id=:id"),
                {"id": str(event_id)},
            )
            connection.execute(
                update(claims)
                .where(claims.c.claim_id == submission.record.claim_id.value)
                .values(claim_status="withdrawn")
            )
        assert reader.event_graph(event_id) == frozen
    changed = read_graph(graph_engine, event_id)
    assert changed.business_version == 2 and changed.edges == () and not changed.truncated
    with graph_engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == submission.record.claim_id.value)
            .values(claim_status="supported")
        )
    restored = read_graph(graph_engine, event_id)
    assert restored.business_version == changed.business_version
    assert restored.content_sha256 != changed.content_sha256


def test_private_graph_and_nested_sources_do_not_cross_tenants_or_promote_scope(
    graph_engine, tmp_path
):
    event_id = uuid4()
    private = VisibilityScope(visibility="tenant", tenant_id="owner")
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION, scope=private)
    publish_event(graph_engine, event_id, [submission], scope=private)
    owner = AccessScope.for_authenticated_user("owner-user", "owner", Role.ANALYST)
    assert all(
        node.scope == private for node in read_graph(graph_engine, event_id, scope=owner).nodes
    )
    for tenant, role in [("other", Role.ANALYST), ("owner", Role.VIEWER)]:
        with pytest.raises(CrossTenantAccessError):
            read_graph(
                graph_engine,
                event_id,
                scope=AccessScope.for_authenticated_user("fixture-user", tenant, role),
            )
    public_id = UUID(
        seed_event(graph_engine, [submission.revision_id.value], external_id=SOURCE_IDENTIFIER)
    )
    assert read_graph(graph_engine, public_id).edges == ()
    with graph_engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == submission.record.claim_id.value)
            .values(subject=str(public_id))
        )
    private_edges = read_graph(graph_engine, public_id, scope=owner).edges
    assert private_edges and all(edge.scope == private for edge in private_edges)


@pytest.mark.parametrize("private_layer", ["source", "document", "revision", "evidence", "claim"])
def test_every_parent_acl_is_rechecked_and_private_support_stays_private(
    graph_engine, tmp_path, private_layer
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    with graph_engine.begin() as connection:
        if private_layer == "source":
            connection.execute(
                text(
                    "UPDATE sources SET visibility='tenant', tenant_id='owner' WHERE source_id=:id"
                ),
                {"id": submission.source_id.value},
            )
        else:
            relation, predicate = {
                "document": (
                    documents,
                    documents.c.source_id == submission.source_id.value,
                ),
                "revision": (
                    document_revisions,
                    document_revisions.c.revision_id == submission.revision_id.value,
                ),
                "evidence": (
                    evidence,
                    evidence.c.evidence_id == submission.evidence_links[0].evidence_id.value,
                ),
                "claim": (claims, claims.c.claim_id == submission.record.claim_id.value),
            }[private_layer]
            connection.execute(
                update(relation).where(predicate).values(visibility="tenant", tenant_id="owner")
            )
    assert read_graph(graph_engine, event_id).edges == ()
    owner = AccessScope.for_authenticated_user("owner-user", "owner", Role.ANALYST)
    result = read_graph(graph_engine, event_id, scope=owner)
    assert result.edges and all(edge.scope.visibility == "tenant" for edge in result.edges)
    assert all(node.scope.visibility == "tenant" for node in result.nodes if node.kind != "event")


def test_pg_session_role_revocation_removes_private_graph_access(
    graph_engine, tmp_path, register_sensitive_failure_value
):
    event_id = uuid4()
    scope = VisibilityScope(visibility="tenant", tenant_id="owner")
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION, scope=scope)
    publish_event(graph_engine, event_id, [submission], scope=scope)
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(graph_engine),
        ("http://localhost:5173",),
        False,
        state_store=PgAuthenticationStateStore(graph_engine),
    )
    username = "fixture-r10-revoke-" + uuid4().hex
    password = secrets.token_urlsafe(32)
    register_sensitive_failure_value(SecretStr(password))
    auth.create_precreated_user(username, password, "owner", Role.ANALYST)
    session_token, _ = auth.login(username, password, "http://localhost:5173", uuid4().hex)
    register_sensitive_failure_value(SecretStr(session_token))
    app = FastAPI()
    app.include_router(build_graph_router(lambda: auth, graph_engine), prefix="/v1")
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, session_token)
        path = f"/v1/events/{event_id}/graph"
        assert client.get(path).status_code == 200
        with graph_engine.begin() as connection:
            connection.execute(
                text("UPDATE users SET role='viewer' WHERE username=:username"),
                {"username": username},
            )
        assert client.get(path).status_code == 404


def test_real_session_rest_factory_bounds_acl_errors_and_database_failure(
    graph_engine, tmp_path, monkeypatch, register_sensitive_failure_value
):
    event_id = uuid4()
    submission = publish_fact(graph_engine, tmp_path, event_id, VERSION)
    publish_event(graph_engine, event_id, [submission])
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(graph_engine),
        ("http://localhost:5173",),
        False,
        state_store=PgAuthenticationStateStore(graph_engine),
    )
    username = "fixture-r10-user-" + uuid4().hex
    password = secrets.token_urlsafe(32)
    register_sensitive_failure_value(SecretStr(password))
    auth.create_precreated_user(username, password, "owner", Role.VIEWER)
    session_token, _ = auth.login(username, password, "http://localhost:5173", uuid4().hex)
    register_sensitive_failure_value(SecretStr(session_token))
    app = FastAPI()
    app.include_router(build_graph_router(lambda: auth, graph_engine), prefix="/v1")
    path = f"/v1/events/{event_id}/graph"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        client.cookies.set(SESSION_COOKIE_NAME, session_token)
        response = client.get(path)
        assert response.status_code == 200 and response.json()["business_version"] == 1
        assert response.json()["rule_version"] == "r10-graph-1.1.0"
        assert client.get(f"/v1/events/{uuid4()}/graph").status_code == 404
        assert client.get("/v1/events/not-a-uuid/graph").status_code == 422
        for parameters in (
            {"max_nodes": 201},
            {"max_edges": 0},
            {"depth": 20},
            {"tenant_id": "other"},
            {"query": "MATCH(n) RETURN n"},
        ):
            assert client.get(path, params=parameters).status_code == 422
        original = auth.build_access_scope
        monkeypatch.setattr(
            auth, "build_access_scope", lambda token: AccessScope("denied", "owner", Role.VIEWER)
        )
        assert client.get(path).status_code == 403
        monkeypatch.setattr(auth, "build_access_scope", original)

        def fail_graph_query(connection, cursor, statement, parameters, context, executemany):
            if "FROM events" in statement:
                raise SQLAlchemyError("fixture-private-error-secret")

        event.listen(graph_engine, "before_cursor_execute", fail_graph_query)
        try:
            failure = client.get(path)
            assert (
                failure.status_code == 503
                and failure.headers["content-type"] == "application/problem+json"
            )
            assert "fixture-private-error-secret" not in failure.text
        finally:
            event.remove(graph_engine, "before_cursor_execute", fail_graph_query)
        auth.logout(session_token)
        assert client.get(path).status_code == 401

