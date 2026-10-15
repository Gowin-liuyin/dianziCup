"""Synthetic fixtures against dedicated real PG; review actors are not live human evidence."""

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import auth_sessions
from ai_intel.assessment.assessment_persistence import assessment_results, assessment_scope_watches
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.conditions import parse_condition_tree
from ai_intel.assessment.persistence_contracts import RuleSupportBinding
from ai_intel.assessment.rule_persistence import (
    RulePersistenceError,
    condition_rule_versions,
    rule_leaf_reviews,
    rule_validation_receipts,
)
from ai_intel.assessment.rule_service import RuleService
from ai_intel.assessment.rules import ConditionRule
from ai_intel.assets.inventory import InventoryService
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import document_revisions, documents, evidence, scope_epochs, users
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import event_documents, events
from ai_intel.knowledge.revisions import (
    SourceRevisionBlock,
    attach_evidence_span,
    register_response_content,
    register_source_revision_blocks,
    save_document_revision,
)

pytestmark = pytest.mark.real_pg
STAMP = datetime(2026, 10, 16, tzinfo=UTC)


@pytest.fixture(scope="module")
def pg_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r11_assessment_20261016"
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
    assert os.environ["DIANZI_TEST_RUN_ID"] == "r11_assessment_20261016"
    engine = create_engine(url, hide_parameters=True, pool_size=8)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")).startswith("r11_assessment_")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0019_aggregate_observations"
        )
    yield engine
    engine.dispose()


def actor(engine, tenant, role=Role.TENANT_ADMIN):
    identity, token = str(uuid4()), "fixture-session-" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            insert(users).values(
                user_id=identity,
                username="fixture-" + identity,
                password_hash="synthetic-unused-hash",
                tenant_id=tenant,
                role=role.value,
                created_at=STAMP,
            )
        )
        connection.execute(
            insert(auth_sessions).values(
                session_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=identity,
                csrf_token="fixture-unused",
                issued_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
            )
        )
    return AccessScope.for_authenticated_user(identity, tenant, role), token


def seed(engine, directory, *, leaf=None, origin="source_explicit", public=False):
    tenant = "fixture-tenant-" + uuid4().hex
    author, author_token = actor(
        engine, None if public else tenant, Role.SYSTEM_ADMIN if public else Role.TENANT_ADMIN
    )
    reviewer, reviewer_token = actor(
        engine, None if public else tenant, Role.SYSTEM_ADMIN if public else Role.TENANT_ADMIN
    )
    asset_actor, asset_token = actor(engine, tenant)
    source_id, document_id, event_id, claim_id = (str(uuid4()) for _ in range(4))
    scope = VisibilityScope(
        visibility="public" if public else "tenant", tenant_id=None if public else tenant
    )
    store = ContentStore(directory)
    quote = "😀必要条件：组件 fixture 版本 [1.0,1.4.2)，完整受影响范围。"
    body = "前缀：" + quote + "后缀。"
    payload = body.encode()
    with Session(engine) as session, session.begin():
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES (:id,:name,'vendor_advisory','https://example.invalid',:visibility,:tenant,:time)"
            ),
            dict(
                id=source_id,
                name="fixture-source-" + source_id,
                visibility=scope.visibility,
                tenant=scope.tenant_id,
                time=STAMP,
            ),
        )
        content = register_response_content(session, store, payload, STAMP)
        session.execute(
            insert(documents).values(
                document_id=document_id,
                source_id=source_id,
                kind="advisory",
                title="Synthetic rule evidence",
                retrieved_at=STAMP,
                content_hash=content.content_hash,
                visibility=scope.visibility,
                tenant_id=scope.tenant_id,
                schema_version=2,
            )
        )
        revision = save_document_revision(
            session, store, document_id, payload, scope.visibility, scope.tenant_id, STAMP
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == revision.revision_id)
            .values(parse_status="parsed")
        )
        block_id = register_source_revision_blocks(
            session,
            revision.revision_id,
            (
                SourceRevisionBlock(
                    0,
                    0,
                    len(body),
                    body,
                    hashlib.sha256(payload).hexdigest(),
                    "paragraph",
                    None,
                    None,
                ),
            ),
            scope.visibility,
            scope.tenant_id,
            STAMP,
            attach_full_block_evidence=False,
        )[0]
        start = len("前缀：")
        span_id = attach_evidence_span(
            session,
            revision.revision_id,
            start,
            start + len(quote),
            "fixture:block",
            quote,
            True,
            scope.visibility,
            scope.tenant_id,
            STAMP,
            block_id,
            hashlib.sha256(quote.encode()).hexdigest(),
            STAMP,
        )
        session.execute(
            insert(events).values(
                event_id=event_id,
                event_type="vulnerability",
                title="Synthetic event",
                scope_key="public" if public else "tenant:" + tenant,
                visibility=scope.visibility,
                tenant_id=scope.tenant_id,
                status="active",
                first_seen_at=STAMP,
                business_version=1,
            )
        )
        session.execute(
            insert(event_documents).values(
                event_id=event_id,
                revision_id=revision.revision_id,
                active=True,
                associated_at=STAMP,
            )
        )
        record = ClaimRecord(
            schema_version=2,
            claim_id=Identifier(value=claim_id),
            subject="event:" + event_id,
            predicate="necessary_condition",
            object_value=quote,
            claim_status="unverified" if origin == "model_hypothesis" else "supported",
            claim_origin=origin,
            condition_value="unknown",
            freshness="unknown",
            asserted_at=STAMP,
            scope=scope,
        )
        KnowledgeRepository(session, author).publish(
            "fixture-claim-" + claim_id,
            scope,
            (
                ClaimSubmission(
                    record=record,
                    source_id=Identifier(value=source_id),
                    revision_id=Identifier(value=revision.revision_id),
                    json_path="fixture:block",
                    evidence_links=(
                        EvidenceLink(
                            evidence_id=Identifier(value=span_id),
                            support_kind="supports",
                            validation_status="validated",
                        ),
                    ),
                ),
            ),
            created_at=STAMP,
        )
    node = leaf or dict(
        node_id="version",
        kind="version_in_range",
        range_complete=True,
        assertion=dict(
            kind="version_assertion",
            package_key="fixture",
            ecosystem="PyPI",
            scheme="pep440",
            raw_expression="[1.0,1.4.2)",
            intervals=[dict(introduced="1.0", fixed="1.4.2")],
            comparison_support="supported",
        ),
    )
    rule = ConditionRule(
        rule_id=str(uuid4()),
        version=1,
        event_id=event_id,
        rule_kind="software_applicability",
        condition_ast=parse_condition_tree(node),
        supporting_claim_ids=(claim_id,),
        source_span_ids=(span_id,),
        scope=scope,
        status="candidate",
    )
    binding = RuleSupportBinding(node_id=node["node_id"], claim_id=claim_id, evidence_id=span_id)
    service = RuleService(engine, author_token, store)
    service.create_candidate(rule, (binding,))
    return dict(
        tenant=tenant,
        author=author,
        author_token=author_token,
        reviewer=reviewer,
        reviewer_token=reviewer_token,
        asset_actor=asset_actor,
        asset_token=asset_token,
        source_id=source_id,
        document_id=document_id,
        revision_id=revision.revision_id,
        event_id=event_id,
        claim_id=claim_id,
        evidence_id=span_id,
        rule=rule,
        binding=binding,
        store=store,
        service=service,
    )


def publish(engine, seeded):
    reviewer = RuleService(engine, seeded["reviewer_token"], seeded["store"])
    reviewer.record_leaf_review(
        seeded["rule"].rule_id,
        1,
        seeded["binding"],
        decision="supports",
        reason="Synthetic fixture reviewer confirms exact necessary condition and complete range.",
        range_completeness_confirmed=True,
    )
    seeded["service"].validate(seeded["rule"].rule_id, 1)
    return reviewer.publish(seeded["rule"].rule_id, 1)


def asset(engine, seeded, version="1.4.1", *, asset_id=None, **extra):
    raw = json.dumps(
        dict(
            format_version=1,
            components=[dict(ecosystem="PyPI", package_name="fixture", version=version)],
            **extra,
        )
    ).encode()
    with Session(engine) as session, session.begin():
        return InventoryService(session, seeded["asset_actor"]).import_manifest(
            raw,
            manifest_format="json_manifest_v1",
            display_name="Synthetic assessment asset",
            source_version="fixture-manifest-1",
            observed_at=STAMP,
            idempotency_key=uuid4().hex,
            asset_id=asset_id,
        )


def assessor(engine, seeded):
    return AssessmentService(engine, seeded["asset_token"], seeded["store"])


def count(engine, table):
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(table))


def test_t27_semantic_pending_independent_review_and_lifecycle(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    validated = seeded["service"].validate(seeded["rule"].rule_id, 1)
    assert not validated.validation.eligible
    assert validated.supports[0].semantic_status == "pending"
    with pytest.raises(PermissionDeniedError, match="independent"):
        seeded["service"].record_leaf_review(
            seeded["rule"].rule_id,
            1,
            seeded["binding"],
            decision="supports",
            reason="Author cannot approve themselves.",
        )
    rule = publish(pg_engine, seeded)
    assert rule.status == "published"
    assert seeded["service"].validate(rule.rule_id, 1).rule.status == "published"
    reviewer = RuleService(pg_engine, seeded["reviewer_token"], seeded["store"])
    assert reviewer.retire(rule.rule_id, 1).status == "retired"
    assert seeded["service"].validate(rule.rule_id, 1).rule.status == "retired"
    with pytest.raises(RulePersistenceError):
        reviewer.publish(rule.rule_id, 1)
    assert count(pg_engine, rule_leaf_reviews) >= 1


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.4.1", "supported_applicability"),
        ("1.4.2", "excluded_with_evidence"),
        (None, "insufficient_evidence"),
    ],
)
def test_t28_c01_versions_evidence_and_scope_snapshot(pg_engine, tmp_path, version, expected):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded, version)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    result = service.commit(prepared)
    assert result.status == expected and result.freshness == "current"
    assert result.knowledge_epoch == prepared.inputs.scope_epoch_map["public"]
    assert result.rule_result.evaluation_tree.asset_field_refs
    assert result.rule_result.evaluation_tree.evidence_ids == (seeded["evidence_id"],)
    assert result.prepared.inputs.supports[0].evidence.quote_text.startswith("😀")
    assert result.prepared.inputs.supports[0].evidence.start_offset == 3
    assert result.prepared.inputs.sources[0].content_sha256
    assert result.exploit_evidence_status == "not_verified"
    with pg_engine.connect() as connection:
        watch = (
            connection.execute(
                select(assessment_scope_watches).where(
                    assessment_scope_watches.c.assessment_id == result.assessment_id
                )
            )
            .mappings()
            .one()
        )
        assert watch["package_keys"] == ["PyPI:fixture"] and not watch["no_published_rule"]


def test_t28_c02_replay_cross_connections_does_not_restore_current(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.commit(prepared), range(2)))
    assert len({result.assessment_id for result in results}) == 1
    asset(pg_engine, seeded, "1.4.2", asset_id=imported.asset_id)
    replay = assessor(pg_engine, seeded).commit(prepared)
    assert (
        replay.reused and replay.freshness == "stale" and replay.status == "supported_applicability"
    )


def test_t28_c03_revision_between_prepare_and_commit_saves_stale(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    with Session(pg_engine) as session, session.begin():
        save_document_revision(
            session,
            seeded["store"],
            seeded["document_id"],
            b"Changed synthetic source",
            "tenant",
            seeded["tenant"],
            STAMP + timedelta(seconds=1),
        )
    result = service.commit(prepared)
    assert result.freshness == "stale" and result.status == "supported_applicability"
    assert service.read(result.assessment_id).freshness == "stale"


def test_t28_c04_software_match_keeps_network_path_independent(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded, network_exposure=dict(public_endpoint=False))
    service = assessor(pg_engine, seeded)
    result = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    assert result.status == "supported_applicability" and result.exposure_result == "not_evaluated"
    assert "absolute_safety" in result.limitations[0]


def test_t28_c05_unpublished_and_model_claim_never_confirm(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path, origin="model_hypothesis")
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    result = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    assert result.status == "insufficient_evidence" and result.missing_requirements == (
        "unsupported_rule",
    )
    assert result.prepared.scope_watch.no_published_rule
    with pytest.raises(RulePersistenceError):
        publish(pg_engine, seeded)


def test_security_t28_c06_cross_tenant_and_viewer_do_not_leak(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    result = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    _, other_token = actor(pg_engine, "fixture-other-tenant")
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        AssessmentService(pg_engine, other_token, seeded["store"]).read(result.assessment_id)
    _, viewer_token = actor(pg_engine, seeded["tenant"], Role.VIEWER)
    with pytest.raises(PermissionDeniedError):
        AssessmentService(pg_engine, viewer_token, seeded["store"]).read(result.assessment_id)


def test_security_role_change_and_forged_preparation_write_no_result(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    before = count(pg_engine, assessment_results)
    with pytest.raises(RulePersistenceError, match="receipt_mismatch"):
        service.commit(prepared.model_copy(update={"input_digest": "f" * 64}))
    with pg_engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == seeded["asset_actor"].user_id)
            .values(role="viewer")
        )
    with pytest.raises(PermissionDeniedError):
        service.commit(prepared)
    assert count(pg_engine, assessment_results) == before


def test_security_source_acl_changes_block_current_and_history(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path, public=True)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    result = service.commit(prepared)
    before = count(pg_engine, assessment_results)
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE sources SET visibility='tenant',tenant_id=:tenant WHERE source_id=:source"
            ),
            dict(tenant="fixture-unrelated-private", source=seeded["source_id"]),
        )
    with pytest.raises(CrossTenantAccessError):
        service.commit(prepared)
    with pytest.raises(CrossTenantAccessError):
        service.read(result.assessment_id)
    assert count(pg_engine, assessment_results) == before


def test_security_unicode_quote_tamper_rolls_back_candidate(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    with pg_engine.begin() as connection:
        connection.execute(
            update(evidence)
            .where(evidence.c.evidence_id == seeded["evidence_id"])
            .values(start_offset=4)
        )
    before = count(pg_engine, rule_validation_receipts)
    with pytest.raises(RulePersistenceError, match="coordinates_invalid"):
        seeded["service"].validate(seeded["rule"].rule_id, 1)
    assert count(pg_engine, rule_validation_receipts) == before


def test_rule_content_and_result_immutable(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(
            update(condition_rule_versions)
            .where(condition_rule_versions.c.rule_id == seeded["rule"].rule_id)
            .values(condition_sha256="f" * 64)
        )
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(
            update(condition_rule_versions)
            .where(condition_rule_versions.c.rule_id == seeded["rule"].rule_id)
            .values(status="candidate", published_at=None, published_by=None)
        )
    other = seeded["rule"].model_copy(
        update={
            "condition_ast": parse_condition_tree(
                dict(
                    node_id="other",
                    kind="component_matches",
                    ecosystem="PyPI",
                    package_key="fixture",
                )
            )
        }
    )
    with pytest.raises(RulePersistenceError):
        seeded["service"].create_candidate(other, (seeded["binding"],))


def test_assessment_transaction_rollback_leaves_no_partial_output(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    before = count(pg_engine, assessment_results)

    def fail_watch(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO assessment_scope_watches"):
            raise RuntimeError("synthetic rollback fault")

    event.listen(pg_engine, "before_cursor_execute", fail_watch)
    try:
        with pytest.raises(RuntimeError, match="rollback fault"):
            service.commit(prepared)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_watch)
    assert count(pg_engine, assessment_results) == before


def test_concurrent_normal_inventory_writer_serializes_then_old_commit_is_stale(
    pg_engine, tmp_path
):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    held, release = Event(), Event()

    def pause_writer(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE assets SET"):
            held.set()
            assert release.wait(5)

    event.listen(pg_engine, "after_cursor_execute", pause_writer)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(asset, pg_engine, seeded, "1.4.2", asset_id=imported.asset_id)
            assert held.wait(5)
            pending = pool.submit(service.commit, prepared)
            release.set()
            changed = writer.result(timeout=10)
            result = pending.result(timeout=10)
        assert (
            result.freshness == "stale" and changed.snapshot.snapshot_id != result.asset_snapshot_id
        )
    finally:
        release.set()
        event.remove(pg_engine, "after_cursor_execute", pause_writer)


@pytest.mark.parametrize(
    "configured,expected",
    [
        (True, "supported_applicability"),
        (False, "excluded_with_evidence"),
        (None, "insufficient_evidence"),
    ],
)
def test_configured_assets_produce_distinct_four_state_results(
    pg_engine, tmp_path, configured, expected
):
    seeded = seed(
        pg_engine,
        tmp_path,
        leaf=dict(
            node_id="configuration",
            kind="configuration_equals",
            field="trust_remote_code",
            expected=True,
        ),
    )
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded, configuration=dict(trust_remote_code=configured))
    service = assessor(pg_engine, seeded)
    result = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    assert result.status == expected
    assert result.rule_result.evaluation_tree.asset_field_refs


def test_two_conflicting_component_versions_remain_conflict(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    raw = json.dumps(
        dict(
            format_version=1,
            components=[
                dict(ecosystem="PyPI", package_name="fixture", version="1.4.1"),
                dict(ecosystem="PyPI", package_name="fixture", version="1.4.2"),
            ],
        )
    ).encode()
    with Session(pg_engine) as session, session.begin():
        imported = InventoryService(session, seeded["asset_actor"]).import_manifest(
            raw,
            manifest_format="json_manifest_v1",
            display_name="Synthetic two-version asset",
            source_version="fixture-1",
            observed_at=STAMP,
            idempotency_key=uuid4().hex,
        )
    service = assessor(pg_engine, seeded)
    result = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    assert result.status == "conflicting_evidence"
    assert len(result.conflicts) == 2


def test_refuted_review_and_missing_range_completeness_block_publication(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    reviewer = RuleService(pg_engine, seeded["reviewer_token"], seeded["store"])
    reviewer.record_leaf_review(
        seeded["rule"].rule_id,
        1,
        seeded["binding"],
        decision="supports",
        reason="Synthetic reviewer confirms necessity, without confirming complete affected range.",
    )
    validation = seeded["service"].validate(seeded["rule"].rule_id, 1)
    assert not validation.validation.eligible
    assert "range_completeness_evidence:version" in validation.validation.missing_requirements
    reviewer.record_leaf_review(
        seeded["rule"].rule_id,
        1,
        seeded["binding"],
        decision="refutes",
        reason="Synthetic independent reviewer disputes this necessary condition.",
    )
    validation = seeded["service"].validate(seeded["rule"].rule_id, 1)
    assert "refuted_condition:version" in validation.validation.conflicts
    assert not validation.validation.eligible


def test_all_event_source_roster_change_invalidates_previous_assessment(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    second = seed(pg_engine, tmp_path / "second")
    with pg_engine.begin() as connection:
        connection.execute(
            update(events)
            .where(events.c.event_id == second["event_id"])
            .values(
                visibility="tenant",
                tenant_id=seeded["tenant"],
                scope_key="tenant:" + seeded["tenant"],
            )
        )
        connection.execute(
            text("UPDATE sources SET tenant_id=:tenant WHERE source_id=:source"),
            dict(tenant=seeded["tenant"], source=second["source_id"]),
        )
        connection.execute(
            update(documents)
            .where(documents.c.document_id == second["document_id"])
            .values(tenant_id=seeded["tenant"])
        )
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == second["revision_id"])
            .values(tenant_id=seeded["tenant"])
        )
        connection.execute(
            insert(event_documents).values(
                event_id=seeded["event_id"],
                revision_id=second["revision_id"],
                active=True,
                associated_at=STAMP,
            )
        )
    result = service.commit(prepared)
    assert result.freshness == "stale"


def test_concurrent_normal_revision_writer_commits_before_stale_assessment(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    written, release = Event(), Event()

    def revise():
        with Session(pg_engine) as session, session.begin():
            changed = save_document_revision(
                session,
                seeded["store"],
                seeded["document_id"],
                b"Synthetic revised source",
                "tenant",
                seeded["tenant"],
                STAMP + timedelta(seconds=2),
            )
            written.set()
            assert release.wait(5)
            return changed

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(revise)
        assert written.wait(5)
        pending = pool.submit(service.commit, prepared)
        release.set()
        changed = writer.result(timeout=10)
        result = pending.result(timeout=10)
    assert changed.revision_id != seeded["revision_id"] and result.freshness == "stale"


@pytest.mark.parametrize("changing", ["role", "source_acl"])
def test_security_concurrent_role_or_acl_change_blocks_commit(pg_engine, tmp_path, changing):
    seeded = seed(pg_engine, tmp_path, public=changing == "source_acl")
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    before = count(pg_engine, assessment_results)
    attempting = Event()

    def observe_read(connection, cursor, statement, parameters, context, executemany):
        if (
            changing == "role"
            and "FROM auth_sessions JOIN users" in statement
            and "FOR SHARE" in statement
        ):
            attempting.set()
        if changing == "source_acl" and "FROM sources" in statement and "FOR SHARE" in statement:
            attempting.set()

    event.listen(pg_engine, "before_cursor_execute", observe_read)
    try:
        with pg_engine.connect() as connection, connection.begin():
            if changing == "role":
                connection.execute(
                    update(users)
                    .where(users.c.user_id == seeded["asset_actor"].user_id)
                    .values(role="viewer")
                )
            else:
                connection.execute(
                    text(
                        "UPDATE sources SET visibility='tenant',tenant_id=:tenant "
                        "WHERE source_id=:source"
                    ),
                    dict(tenant="fixture-different-tenant", source=seeded["source_id"]),
                )
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(service.commit, prepared)
                assert attempting.wait(5)
                connection.commit()
                with pytest.raises(
                    PermissionDeniedError if changing == "role" else CrossTenantAccessError
                ):
                    pending.result(timeout=10)
        assert count(pg_engine, assessment_results) == before
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe_read)


def test_security_revoked_session_cannot_validate_or_commit(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    before = count(pg_engine, assessment_results)
    with pg_engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.user_id == seeded["asset_actor"].user_id)
            .values(revoked_at=datetime.now(UTC))
        )
    with pytest.raises(PermissionError):
        service.commit(prepared)
    assert count(pg_engine, assessment_results) == before


def test_public_rule_assessment_tracks_private_tenant_epoch(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path, public=True)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    assert "tenant:" + seeded["tenant"] in prepared.inputs.scope_epoch_map
    with pg_engine.begin() as connection:
        connection.execute(
            update(scope_epochs)
            .where(scope_epochs.c.scope_key == "tenant:" + seeded["tenant"])
            .values(epoch=scope_epochs.c.epoch + 1)
        )
    assert service.commit(prepared).freshness == "stale"


def test_security_source_blob_corruption_blocks_preparation(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    with pg_engine.connect() as connection:
        digest = connection.scalar(
            select(document_revisions.c.content_hash).where(
                document_revisions.c.revision_id == seeded["revision_id"]
            )
        )
    seeded["store"].object_path_for_hash(digest).write_bytes(b"corrupt synthetic evidence")
    before = count(pg_engine, rule_validation_receipts)
    with pytest.raises(ValueError, match="hash mismatch"):
        assessor(pg_engine, seeded).prepare(
            imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
        )
    assert count(pg_engine, rule_validation_receipts) == before


def test_security_private_source_cannot_widen_into_public_rule(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path, public=True)
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE sources SET visibility='tenant',tenant_id=:tenant WHERE source_id=:source"
            ),
            dict(tenant="fixture-private", source=seeded["source_id"]),
        )
    before = count(pg_engine, rule_validation_receipts)
    with pytest.raises(CrossTenantAccessError):
        seeded["service"].validate(seeded["rule"].rule_id, 1)
    assert count(pg_engine, rule_validation_receipts) == before


def test_security_foreign_rule_identity_is_hidden_on_candidate_collision(pg_engine, tmp_path):
    first = seed(pg_engine, tmp_path / "first")
    second = seed(pg_engine, tmp_path / "second")
    collided = second["rule"].model_copy(update={"rule_id": first["rule"].rule_id})
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        second["service"].create_candidate(collided, (second["binding"],))
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        second["service"].create_candidate(
            collided.model_copy(update={"version": 2}), (second["binding"],)
        )


def test_publication_rolls_back_lifecycle_receipt_and_outbox_together(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    reviewer = RuleService(pg_engine, seeded["reviewer_token"], seeded["store"])
    reviewer.record_leaf_review(
        seeded["rule"].rule_id,
        1,
        seeded["binding"],
        decision="supports",
        reason="Synthetic fixture review.",
        range_completeness_confirmed=True,
    )
    seeded["service"].validate(seeded["rule"].rule_id, 1)
    before = count(pg_engine, rule_validation_receipts)

    def fail_outbox(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO outbox_events"):
            raise RuntimeError("synthetic publication rollback")

    event.listen(pg_engine, "before_cursor_execute", fail_outbox)
    try:
        with pytest.raises(RuntimeError, match="publication rollback"):
            reviewer.publish(seeded["rule"].rule_id, 1)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_outbox)
    with pg_engine.connect() as connection:
        status = connection.scalar(
            select(condition_rule_versions.c.status).where(
                condition_rule_versions.c.rule_id == seeded["rule"].rule_id
            )
        )
    assert status == "validated" and count(pg_engine, rule_validation_receipts) == before


def test_existing_assessment_becomes_stale_after_rule_retirement(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    published = publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    result = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, published.rule_id, 1)
    )
    RuleService(pg_engine, seeded["reviewer_token"], seeded["store"]).retire(published.rule_id, 1)
    assert service.read(result.assessment_id).freshness == "stale"
    assert service.read(result.assessment_id).status == "supported_applicability"
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(
            update(assessment_results)
            .where(assessment_results.c.assessment_id == result.assessment_id)
            .values(status="excluded_with_evidence")
        )


def test_family_requires_explicit_retirement_before_publishing_new_version(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    old = publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    service = assessor(pg_engine, seeded)
    original = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, old.rule_id, 1)
    )
    new = seeded["rule"].model_copy(update={"version": 2})
    seeded["service"].create_candidate(new, (seeded["binding"],))
    reviewer = RuleService(pg_engine, seeded["reviewer_token"], seeded["store"])
    reviewer.record_leaf_review(
        new.rule_id,
        2,
        seeded["binding"],
        decision="supports",
        reason="Synthetic review of a separate immutable version.",
        range_completeness_confirmed=True,
    )
    seeded["service"].validate(new.rule_id, 2)
    with pytest.raises(RulePersistenceError, match="requires_retirement"):
        reviewer.publish(new.rule_id, 2)
    reviewer.retire(old.rule_id, 1)
    assert reviewer.publish(new.rule_id, 2).status == "published"
    assert service.read(original.assessment_id).freshness == "stale"
    assert service.read(original.assessment_id).rule_version == 1


def test_two_concurrent_publishers_cannot_publish_two_family_versions(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    reviewer = RuleService(pg_engine, seeded["reviewer_token"], seeded["store"])
    for version in (1, 2):
        seeded["service"].create_candidate(
            seeded["rule"].model_copy(update={"version": version}), (seeded["binding"],)
        )
        reviewer.record_leaf_review(
            seeded["rule"].rule_id,
            version,
            seeded["binding"],
            decision="supports",
            reason="Synthetic concurrent publication review.",
            range_completeness_confirmed=True,
        )
        seeded["service"].validate(seeded["rule"].rule_id, version)

    def attempt(version):
        try:
            return reviewer.publish(seeded["rule"].rule_id, version).version
        except RulePersistenceError as error:
            assert str(error) == "rule_requires_retirement_of_published_version"
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (1, 2)))
    assert sum(result is not None for result in results) == 1
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(condition_rule_versions)
                .where(
                    condition_rule_versions.c.rule_id == seeded["rule"].rule_id,
                    condition_rule_versions.c.status == "published",
                )
            )
            == 1
        )
    remaining = next(version for version in (1, 2) if version not in results)
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(
            update(condition_rule_versions)
            .where(
                condition_rule_versions.c.rule_id == seeded["rule"].rule_id,
                condition_rule_versions.c.version == remaining,
            )
            .values(
                status="published",
                published_at=datetime.now(UTC),
                published_by=seeded["reviewer"].user_id,
            )
        )
