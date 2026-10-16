"""Generic isolated PG fixtures with real source/graph and R11 production service chains."""

import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_r11_pg_assessments import actor, assessor, asset, publish, seed

from ai_intel.assets.inventory import InventoryService
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.event_linking import EventIdentifier, EventRepository, EventSubmission
from ai_intel.knowledge.models import document_revisions, documents, scope_epochs, users
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import claims, event_documents, events
from ai_intel.knowledge.revisions import (
    SourceRevisionBlock,
    attach_evidence_span,
    register_response_content,
    register_source_revision_blocks,
    save_document_revision,
)
from ai_intel.recommendations.persistence_models import (
    R15_TABLES,
    r15_generations,
    r15_recommendations,
    r15_reports,
    r15_subscriptions,
)
from ai_intel.recommendations.service import RecommendationService
from ai_intel.recommendations.service_contracts import (
    RecommendationConflictError,
    SubscriptionSpec,
    canonical_json_bytes,
    content_sha256,
)

pytestmark = pytest.mark.real_pg
STAMP = datetime.now(UTC) - timedelta(hours=1)


@pytest.fixture(scope="module")
def r15_pg_engine():
    """Runner provisions schema and migrations; test code contains no private credentials."""
    run_id = os.environ.get("DIANZI_TEST_RUN_ID", "")
    database_url = os.environ.get("TEST_DATABASE_URL", "")
    if not database_url or re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", run_id) is None:
        raise pytest.UsageError("blocked: TEST_DATABASE_URL and DIANZI_TEST_RUN_ID required")
    url = make_url(database_url)
    if url.database is None or not url.database.startswith("test_"):
        raise pytest.UsageError("blocked: isolated test database required")
    engine = create_engine(url, hide_parameters=True, pool_size=2, max_overflow=0)
    with engine.connect() as connection:
        actual_database, schema = connection.execute(
            text("SELECT current_database(),current_schema()")
        ).one()
        assert actual_database == url.database and schema.startswith("test_") and schema != "public"
        assert all(
            connection.scalar(text("SELECT to_regclass(:name)"), {"name": table.name})
            for table in R15_TABLES
        )
    yield engine
    engine.dispose()


def service(engine, token, store):
    return RecommendationService(engine, token, store, data_mode="fixture")


def semantic_source(engine, store, *, package="alpha", scope=None):
    """Actual immutable bytes, source coordinates, typed claims and event publication."""
    scope = scope or VisibilityScope(visibility="public")
    event_id, source_id, document_id = (str(uuid4()) for _ in range(3))
    alphabet = "23456789cfghjmpqrvwx"
    identity = "".join(alphabet[int(value, 16)] for value in uuid4().hex[:12])
    source_identifier = f"GHSA-{identity[:4]}-{identity[4:8]}-{identity[8:]}"
    body = f"{source_identifier} PyPI {package} affected versions: >=1.0,<1.4.2"
    value = dict(
        kind="version_assertion",
        package_key=package,
        ecosystem="PyPI",
        scheme="pep440",
        raw_expression=body,
        intervals=[dict(introduced="1.0", fixed="1.4.2")],
        comparison_support="supported",
    )
    publisher = AccessScope.for_authenticated_user(
        "fixture-publisher",
        scope.tenant_id,
        Role.SYSTEM_ADMIN if scope.visibility == "public" else Role.TENANT_ADMIN,
    )
    with Session(engine) as session, session.begin():
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) VALUES "
                "(:id,:id,'vendor_advisory','https://example.invalid',:visibility,:tenant,:time)"
            ),
            dict(id=source_id, visibility=scope.visibility, tenant=scope.tenant_id, time=STAMP),
        )
        stored = register_response_content(session, store, body.encode(), STAMP)
        session.execute(
            insert(documents).values(
                document_id=document_id,
                source_id=source_id,
                kind="advisory",
                title="Synthetic typed source",
                retrieved_at=STAMP,
                content_hash=stored.content_hash,
                visibility=scope.visibility,
                tenant_id=scope.tenant_id,
                schema_version=2,
            )
        )
        revision = save_document_revision(
            session, store, document_id, body.encode(), scope.visibility, scope.tenant_id, STAMP
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == revision.revision_id)
            .values(
                parse_status="parsed",
                canonical_uri="https://example.invalid/advisory/" + document_id,
                first_observed_at=STAMP,
                source_modified_at=STAMP - timedelta(days=30),
                source_metadata=dict(
                    is_synthetic=True, content_coverage="full_text", blocks_complete=True
                ),
                parser_version="fixture-text-1",
                normalizer_version="fixture-unicode-1",
            )
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
                    hashlib.sha256(body.encode()).hexdigest(),
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
        evidence_id = attach_evidence_span(
            session,
            revision.revision_id,
            0,
            len(body),
            "synthetic whole source",
            body,
            True,
            scope.visibility,
            scope.tenant_id,
            STAMP,
            block_id,
            hashlib.sha256(body.encode()).hexdigest(),
            STAMP,
        )
        EventRepository(session, publisher).publish_events(
            uuid4().hex,
            scope,
            (
                EventSubmission(
                    event_id=Identifier(value=event_id),
                    event_type="vulnerability",
                    title="Synthetic " + package,
                    scope=scope,
                    external_ids=(EventIdentifier(id_type="ghsa", id_value=source_identifier),),
                    source_revision_ids=(Identifier(value=revision.revision_id),),
                ),
            ),
            STAMP,
        )
        claim = ClaimRecord(
            schema_version=3,
            claim_id=Identifier(value=str(uuid4())),
            subject=event_id,
            predicate="version_assertion",
            object_value=value,
            claim_status="supported",
            claim_origin="source_explicit",
            condition_value="true",
            freshness="current",
            asserted_at=STAMP,
            observed_at=STAMP,
            scope=scope,
        )
        KnowledgeRepository(session, publisher).publish(
            uuid4().hex,
            scope,
            (
                ClaimSubmission(
                    record=claim,
                    source_id=Identifier(value=source_id),
                    revision_id=Identifier(value=revision.revision_id),
                    json_path="fixture:version",
                    evidence_links=(
                        EvidenceLink(
                            evidence_id=Identifier(value=evidence_id),
                            support_kind="supports",
                            validation_status="validated",
                        ),
                    ),
                ),
            ),
            created_at=STAMP,
        )
    return dict(
        event_id=UUID(event_id),
        source_id=source_id,
        document_id=document_id,
        revision_id=revision.revision_id,
        evidence_id=evidence_id,
        claim_id=claim.claim_id.value,
        scope=scope,
        store=store,
        body=body,
        value=value,
        source_identifier=source_identifier,
    )


def add_withdrawal(engine, source):
    scope = source["scope"]
    actor_scope = AccessScope.for_authenticated_user(
        "fixture-publisher",
        scope.tenant_id,
        Role.SYSTEM_ADMIN if scope.visibility == "public" else Role.TENANT_ADMIN,
    )
    with Session(engine) as session, session.begin():
        now = datetime.now(UTC)
        notice = "Status: withdrawn."
        body = source["body"] + "\n" + notice
        revision = save_document_revision(
            session,
            source["store"],
            source["document_id"],
            body.encode(),
            scope.visibility,
            scope.tenant_id,
            now,
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == revision.revision_id)
            .values(
                parse_status="parsed",
                canonical_uri="https://example.invalid/advisory/" + source["document_id"],
                first_observed_at=now,
                source_modified_at=now,
                source_metadata=dict(
                    is_synthetic=True, content_coverage="full_text", blocks_complete=True
                ),
                parser_version="fixture-text-1",
                normalizer_version="fixture-unicode-1",
            )
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
                    hashlib.sha256(body.encode()).hexdigest(),
                    "paragraph",
                    None,
                    None,
                ),
            ),
            scope.visibility,
            scope.tenant_id,
            now,
            attach_full_block_evidence=False,
        )[0]
        proof_ids = []
        for quote, start in ((source["body"], 0), (notice, len(source["body"]) + 1)):
            proof_ids.append(
                attach_evidence_span(
                    session,
                    revision.revision_id,
                    start,
                    start + len(quote),
                    "synthetic source field",
                    quote,
                    True,
                    scope.visibility,
                    scope.tenant_id,
                    now,
                    block_id,
                    hashlib.sha256(quote.encode()).hexdigest(),
                    now,
                )
            )
        EventRepository(session, actor_scope).publish_events(
            uuid4().hex,
            scope,
            (
                EventSubmission(
                    event_id=Identifier(value=str(source["event_id"])),
                    event_type="vulnerability",
                    title="Synthetic withdrawn source",
                    scope=scope,
                    external_ids=(
                        EventIdentifier(id_type="ghsa", id_value=source["source_identifier"]),
                    ),
                    source_revision_ids=(Identifier(value=revision.revision_id),),
                ),
            ),
            now,
        )
        product = ClaimRecord(
            schema_version=3,
            claim_id=Identifier(value=str(uuid4())),
            subject=str(source["event_id"]),
            predicate="version_assertion",
            object_value=source["value"],
            claim_status="supported",
            claim_origin="source_explicit",
            condition_value="true",
            freshness="current",
            asserted_at=now,
            observed_at=now,
            scope=scope,
        )
        record = ClaimRecord(
            claim_id=Identifier(value=str(uuid4())),
            subject=str(source["event_id"]),
            predicate="source_status",
            object_value="withdrawn",
            claim_status="supported",
            claim_origin="source_explicit",
            condition_value="true",
            freshness="current",
            asserted_at=now,
            observed_at=now,
            scope=scope,
        )
        KnowledgeRepository(session, actor_scope).publish(
            uuid4().hex,
            scope,
            (
                ClaimSubmission(
                    record=product,
                    source_id=Identifier(value=source["source_id"]),
                    revision_id=Identifier(value=revision.revision_id),
                    json_path="fixture:version",
                    evidence_links=(
                        EvidenceLink(
                            evidence_id=Identifier(value=proof_ids[0]),
                            support_kind="supports",
                            validation_status="validated",
                        ),
                    ),
                ),
                ClaimSubmission(
                    record=record,
                    source_id=Identifier(value=source["source_id"]),
                    revision_id=Identifier(value=revision.revision_id),
                    json_path="fixture:withdrawal",
                    evidence_links=(
                        EvidenceLink(
                            evidence_id=Identifier(value=proof_ids[1]),
                            support_kind="supports",
                            validation_status="validated",
                        ),
                    ),
                ),
            ),
            created_at=now,
        )


def test_owner_cas_disable_and_illegal_body_tenant(r15_pg_engine, tmp_path):
    store = ContentStore(tmp_path)
    owner, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    _, other_cookie = actor(r15_pg_engine, owner.tenant_id)
    _, cross_cookie = actor(r15_pg_engine, "fixture-other-" + uuid4().hex)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    assert current.read_subscription(sub.subscription_id) == sub
    for denied_cookie in (other_cookie, cross_cookie):
        denied = service(r15_pg_engine, denied_cookie, store)
        with pytest.raises(CrossTenantAccessError):
            denied.read_subscription(sub.subscription_id)
        assert denied.list_subscriptions().items == ()
    changed = current.replace_subscription(
        sub.subscription_id, expected_version=1, spec=SubscriptionSpec(product_keys=("PyPI:beta",))
    )
    assert changed.version == 2
    with pytest.raises(RecommendationConflictError, match="version_changed"):
        current.set_enabled(sub.subscription_id, expected_version=1, enabled=False)
    disabled = current.set_enabled(sub.subscription_id, expected_version=2, enabled=False)
    stopped = current.generate(sub.subscription_id, expected_version=disabled.version, event_ids=())
    assert stopped.content.batch.stop_reason == "disabled" and not stopped.recommendation_ids
    ignored = current.generate(
        sub.subscription_id, expected_version=disabled.version, event_ids=(uuid4(),)
    )
    assert ignored.content.event_ids == () and ignored.content.batch.stop_reason == "disabled"
    with pytest.raises(ValidationError):
        SubscriptionSpec.model_validate(dict(product_keys=["x"], tenant_id=owner.tenant_id))


def test_actual_product_interests_differ_and_duplicate_material_is_not_resent(
    r15_pg_engine, tmp_path
):
    store = ContentStore(tmp_path)
    source = semantic_source(r15_pg_engine, store)
    tenant = "fixture-tenant-" + uuid4().hex
    beta_source = semantic_source(r15_pg_engine, store, package="beta")
    roster = (source["event_id"], beta_source["event_id"])
    _, alpha_cookie = actor(r15_pg_engine, tenant, Role.VIEWER)
    _, beta_cookie = actor(r15_pg_engine, tenant)
    alpha, beta = (
        service(r15_pg_engine, alpha_cookie, store),
        service(r15_pg_engine, beta_cookie, store),
    )
    alpha_sub = alpha.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    beta_sub = beta.create_subscription(SubscriptionSpec(product_keys=("PyPI:beta",)))
    prepared = alpha.prepare_generation(
        alpha_sub.subscription_id, expected_version=1, event_ids=roster
    )
    generation = alpha.commit_generation(prepared)
    assert tuple(generation.content.scope_epochs) == ("public",)
    assert len(generation.recommendation_ids) == 1
    candidate = generation.content.batch.candidates[0]
    assert (
        candidate.kind == "intelligence_update" and candidate.reasons[0].matched_key == "PyPI:alpha"
    )
    assert alpha.commit_generation(prepared).reused
    beta_generation = beta.generate(beta_sub.subscription_id, expected_version=1, event_ids=roster)
    assert len(beta_generation.recommendation_ids) == 1
    assert beta_generation.content.batch.candidates[0].key.event_id == str(beta_source["event_id"])
    assert candidate.key.event_id == str(source["event_id"])
    repeated = alpha.generate(alpha_sub.subscription_id, expected_version=1, event_ids=roster)
    assert not repeated.recommendation_ids and repeated.content.report_batch.candidates
    first = alpha.mark_read(alpha_sub.subscription_id, generation.recommendation_ids[0])
    second = alpha.mark_read(alpha_sub.subscription_id, generation.recommendation_ids[0])
    assert first.read_at == second.read_at and first.current_status == "current"


def test_report_immutable_history_source_withdrawal_and_role_acl(r15_pg_engine, tmp_path):
    store = ContentStore(tmp_path)
    owner, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    source = semantic_source(r15_pg_engine, store)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    generation = current.generate(
        sub.subscription_id, expected_version=1, event_ids=(source["event_id"],)
    )
    report = current.create_report(sub.subscription_id, generation.generation_id, frequency="day")
    original = canonical_json_bytes(report.content.model_dump(mode="json"))
    assert (
        report.content.report.intelligence_updates[0].source_changed_at
        < report.content.report.window_start
    )
    assert current.create_report(
        sub.subscription_id, generation.generation_id, frequency="day"
    ).reused
    add_withdrawal(r15_pg_engine, source)
    history = current.read_report(sub.subscription_id, report.report_id)
    assert history.current_status == "withdrawn"
    assert canonical_json_bytes(history.content.model_dump(mode="json")) == original
    assert history.content_sha256 == report.content_sha256
    assert current.list_recommendations(sub.subscription_id).items[0].current_status == "withdrawn"
    current.set_enabled(sub.subscription_id, expected_version=1, enabled=False)
    assert (
        current.read_report(sub.subscription_id, report.report_id).content_sha256
        == report.content_sha256
    )
    with r15_pg_engine.begin() as connection:
        connection.execute(
            text("UPDATE sources SET visibility='tenant',tenant_id=:tenant WHERE source_id=:id"),
            dict(tenant="fixture-other", id=source["source_id"]),
        )
    with pytest.raises(CrossTenantAccessError):
        current.read_report(sub.subscription_id, report.report_id)
    with r15_pg_engine.begin() as connection:
        connection.execute(
            update(users).where(users.c.user_id == owner.user_id).values(role="viewer")
        )


def test_real_assessment_receipt_supported_then_asset_change_stales_history(
    r15_pg_engine, tmp_path
):
    seeded = seed(r15_pg_engine, tmp_path)
    publish(r15_pg_engine, seeded)
    imported = asset(r15_pg_engine, seeded)
    assessment_service = assessor(r15_pg_engine, seeded)
    receipt = assessment_service.commit(
        assessment_service.prepare(
            imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
        )
    )
    current = service(r15_pg_engine, seeded["asset_token"], seeded["store"])
    sub = current.create_subscription(SubscriptionSpec(asset_ids=(UUID(imported.asset_id),)))
    generation = current.generate(
        sub.subscription_id, expected_version=1, event_ids=(UUID(seeded["event_id"]),)
    )
    assert generation.content.batch.candidates[0].kind == "supported_risk"
    assert (
        generation.content.batch.candidates[0].assessments[0].assessment_id == receipt.assessment_id
    )
    report = current.create_report(sub.subscription_id, generation.generation_id, frequency="week")
    asset(r15_pg_engine, seeded, "2.0", asset_id=imported.asset_id)
    history = current.read_report(sub.subscription_id, report.report_id)
    assert history.current_status == "stale" and history.content_sha256 == report.content_sha256
    _, other_cookie = actor(r15_pg_engine, "fixture-other-" + uuid4().hex)
    with pytest.raises(CrossTenantAccessError):
        service(r15_pg_engine, other_cookie, seeded["store"]).create_subscription(
            SubscriptionSpec(asset_ids=(UUID(imported.asset_id),))
        )
    _, viewer_cookie = actor(r15_pg_engine, seeded["tenant"], Role.VIEWER)
    with pytest.raises(PermissionDeniedError):
        service(r15_pg_engine, viewer_cookie, seeded["store"]).create_subscription(
            SubscriptionSpec(asset_ids=(UUID(imported.asset_id),))
        )
    with r15_pg_engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == seeded["asset_actor"].user_id)
            .values(role="viewer")
        )
    with pytest.raises(PermissionDeniedError):
        current.read_report(sub.subscription_id, report.report_id)


@pytest.mark.parametrize("change", ["unsubscribe", "role", "withdraw", "epoch"])
def test_preparation_final_cas_rejects_actual_intervening_changes(r15_pg_engine, tmp_path, change):
    store = ContentStore(tmp_path)
    actor_scope, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    source = semantic_source(r15_pg_engine, store)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    prepared = current.prepare_generation(
        sub.subscription_id, expected_version=1, event_ids=(source["event_id"],)
    )
    if change == "unsubscribe":
        current.set_enabled(sub.subscription_id, expected_version=1, enabled=False)
    elif change == "role":
        with r15_pg_engine.begin() as connection:
            connection.execute(
                update(users).where(users.c.user_id == actor_scope.user_id).values(role="viewer")
            )
    elif change == "withdraw":
        add_withdrawal(r15_pg_engine, source)
    else:
        with r15_pg_engine.begin() as connection:
            connection.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended("knowledge-publication:public", 0)
                    )
                )
            )
            connection.execute(
                update(scope_epochs)
                .where(scope_epochs.c.scope_key == "public")
                .values(epoch=scope_epochs.c.epoch + 1)
            )
    with pytest.raises(RecommendationConflictError):
        current.commit_generation(prepared)
    with r15_pg_engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(r15_generations)
                .where(r15_generations.c.subscription_id == str(sub.subscription_id))
            )
            == 0
        )


def test_subscription_lock_waits_then_observes_unsubscribe(r15_pg_engine, tmp_path):
    store = ContentStore(tmp_path)
    _, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    source = semantic_source(r15_pg_engine, store)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    prepared = current.prepare_generation(
        sub.subscription_id, expected_version=1, event_ids=(source["event_id"],)
    )
    entered = Event()
    with r15_pg_engine.connect() as connection, connection.begin():
        connection.execute(
            select(r15_subscriptions)
            .where(r15_subscriptions.c.id == str(sub.subscription_id))
            .with_for_update()
        ).all()
        disabled = sub.spec.model_copy(update={"enabled": False})
        connection.execute(
            update(r15_subscriptions)
            .where(r15_subscriptions.c.id == str(sub.subscription_id))
            .values(
                enabled=False,
                version=2,
                spec_payload=disabled.model_dump(mode="json"),
                spec_sha256=content_sha256(disabled.model_dump(mode="json")),
                updated_at=datetime.now(UTC),
            )
        )

        def commit_waiter():
            entered.set()
            return current.commit_generation(prepared)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(commit_waiter)
            assert entered.wait(timeout=3)
            assert not future.done()
            connection.commit()
            with pytest.raises(RecommendationConflictError):
                future.result(timeout=8)


def test_pg_immutable_owner_fk_and_content_guards(r15_pg_engine, tmp_path):
    store = ContentStore(tmp_path)
    owner, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    source = semantic_source(r15_pg_engine, store)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    generation = current.generate(
        sub.subscription_id, expected_version=1, event_ids=(source["event_id"],)
    )
    report = current.create_report(sub.subscription_id, generation.generation_id, frequency="day")
    for table, row_id, column, value in (
        (r15_generations, generation.generation_id, "content_sha256", "f" * 64),
        (r15_recommendations, generation.recommendation_ids[0], "content_sha256", "f" * 64),
        (r15_reports, report.report_id, "current_reason", "cannot_update_append_only"),
    ):
        with pytest.raises(IntegrityError), r15_pg_engine.begin() as connection:
            connection.execute(
                update(table).where(table.c.id == str(row_id)).values(**{column: value})
            )
    with r15_pg_engine.begin() as connection:
        row = dict(
            connection.execute(
                select(r15_recommendations).where(
                    r15_recommendations.c.id == str(generation.recommendation_ids[0])
                )
            )
            .mappings()
            .one()
        )
    row.update(id=str(uuid4()), user_id="fixture-wrong-owner")
    with pytest.raises(IntegrityError), r15_pg_engine.begin() as connection:
        connection.execute(insert(r15_recommendations).values(**row))
    assert owner.user_id != row["user_id"]


def test_restart_replay_and_corrupt_original_fail_closed(r15_pg_engine, tmp_path):
    store = ContentStore(tmp_path)
    _, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    source = semantic_source(r15_pg_engine, store)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    prepared = current.prepare_generation(
        sub.subscription_id, expected_version=1, event_ids=(source["event_id"],)
    )
    first = current.commit_generation(prepared)
    r15_pg_engine.dispose()
    restarted = service(r15_pg_engine, cookie, store)
    replay = restarted.commit_generation(prepared)
    assert replay.reused and replay.generation_id == first.generation_id
    with r15_pg_engine.connect() as connection:
        digest = connection.scalar(
            select(document_revisions.c.content_hash).where(
                document_revisions.c.revision_id == source["revision_id"]
            )
        )
    store.object_path_for_hash(digest).write_bytes(b"corrupted synthetic object")
    with pytest.raises(ValueError, match="hash mismatch"):
        restarted.generate(sub.subscription_id, expected_version=1, event_ids=(source["event_id"],))


@pytest.mark.parametrize(
    "case,expected", [("unknown", "insufficient_evidence"), ("conflict", "conflicting_evidence")]
)
def test_actual_unknown_and_conflict_preserve_evidence_and_explicit_consequence_gap(
    r15_pg_engine, tmp_path, case, expected
):
    seeded = seed(r15_pg_engine, tmp_path)
    publish(r15_pg_engine, seeded)
    components = (
        [dict(ecosystem="PyPI", package_name="fixture", version=None)]
        if case == "unknown"
        else [
            dict(ecosystem="PyPI", package_name="fixture", version="1.4.1"),
            dict(ecosystem="PyPI", package_name="fixture", version="1.4.2"),
        ]
    )
    with Session(r15_pg_engine) as session, session.begin():
        imported = InventoryService(session, seeded["asset_actor"]).import_manifest(
            canonical_json_bytes(dict(format_version=1, components=components)),
            manifest_format="json_manifest_v1",
            display_name="Synthetic unresolved asset",
            source_version="fixture-1",
            observed_at=STAMP,
            idempotency_key=uuid4().hex,
        )
    assessment_service = assessor(r15_pg_engine, seeded)
    receipt = assessment_service.commit(
        assessment_service.prepare(
            imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
        )
    )
    assert receipt.status.value == expected
    current = service(r15_pg_engine, seeded["asset_token"], seeded["store"])
    sub = current.create_subscription(SubscriptionSpec(asset_ids=(UUID(imported.asset_id),)))
    generation = current.generate(
        sub.subscription_id, expected_version=1, event_ids=(UUID(seeded["event_id"]),)
    )
    candidate = generation.content.batch.candidates[0]
    assert candidate.kind == "prioritize_verification" and candidate.priority_bucket == 2
    assert candidate.assessments[0].status.value == expected and candidate.assessments[0].evidence
    assert candidate.assessments[0].conflicts == receipt.conflicts
    assert any(gap.code == "consequence_selector_unavailable" for gap in generation.content.gaps)


@pytest.mark.parametrize("state", ["stale", "withdrawn", "unsupported_value"])
def test_pg_quote_alone_never_supports_selector(r15_pg_engine, tmp_path, state):
    store = ContentStore(tmp_path)
    source = semantic_source(r15_pg_engine, store)
    _, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha", "PyPI:beta")))
    with r15_pg_engine.begin() as connection:
        values = (
            dict(freshness="stale")
            if state == "stale"
            else dict(claim_status="withdrawn")
            if state == "withdrawn"
            else dict(object_json={**source["value"], "package_key": "beta"})
        )
        connection.execute(
            update(claims).where(claims.c.claim_id == source["claim_id"]).values(**values)
        )
    generation = current.generate(
        sub.subscription_id, expected_version=1, event_ids=(source["event_id"],)
    )
    assert not generation.recommendation_ids and not generation.content.batch.candidates
    assert any(gap.code == "no_current_semantic_support" for gap in generation.content.gaps)


def test_security_empty_report_roster_and_asset_gaps_recheck_current_acl(r15_pg_engine, tmp_path):
    seeded = seed(r15_pg_engine, tmp_path)
    imported = asset(r15_pg_engine, seeded)
    current = service(r15_pg_engine, seeded["asset_token"], seeded["store"])
    sub = current.create_subscription(SubscriptionSpec(asset_ids=(UUID(imported.asset_id),)))
    generation = current.generate(
        sub.subscription_id, expected_version=1, event_ids=(UUID(seeded["event_id"]),)
    )
    assert not generation.content.batch.candidates and generation.content.gaps
    report = current.create_report(sub.subscription_id, generation.generation_id, frequency="day")
    assert report.content.event_ids and any(gap.asset_id is not None for gap in report.content.gaps)
    with r15_pg_engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == seeded["asset_actor"].user_id)
            .values(role="viewer")
        )
    with pytest.raises(PermissionDeniedError):
        current.read_report(sub.subscription_id, report.report_id)


def test_pg_budget_continuation_priority_cursor_and_complete_report(r15_pg_engine, tmp_path):
    store = ContentStore(tmp_path)
    sources = (semantic_source(r15_pg_engine, store), semantic_source(r15_pg_engine, store))
    roster = tuple(source["event_id"] for source in sources)
    _, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    current = service(r15_pg_engine, cookie, store)
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    first = current.generate(
        sub.subscription_id, expected_version=1, event_ids=roster, max_candidates=1
    )
    assert first.content.batch.partial and len(first.content.batch.continuation_keys) == 1
    second = current.generate(
        sub.subscription_id, expected_version=1, event_ids=roster, max_candidates=1
    )
    assert len(second.recommendation_ids) == 1 and not second.content.batch.partial
    assert set(first.recommendation_ids).isdisjoint(second.recommendation_ids)
    page = current.list_recommendations(sub.subscription_id, limit=1)
    assert page.next_cursor is not None
    final = current.list_recommendations(sub.subscription_id, limit=1, cursor=page.next_cursor)
    assert (
        final.next_cursor is None
        and final.items[0].recommendation_id != page.items[0].recommendation_id
    )
    with pytest.raises(ValueError, match="cursor_invalid"):
        current.list_recommendations(sub.subscription_id, cursor=uuid4())
    full = current.generate(sub.subscription_id, expected_version=1, event_ids=roster)
    assert not full.recommendation_ids and not full.content.report_batch.partial
    report = current.create_report(sub.subscription_id, full.generation_id, frequency="day")
    assert (
        len(report.content.report.intelligence_updates) == 2 and not report.content.report.partial
    )
    with pytest.raises(RecommendationConflictError, match="budget_changed"):
        current.create_report(sub.subscription_id, full.generation_id, frequency="day", max_items=1)


def test_pg_actual_2000_event_boundary_and_2001_rejection(r15_pg_engine, tmp_path):
    roster = tuple(uuid4() for _ in range(2000))
    with r15_pg_engine.begin() as connection:
        connection.execute(
            insert(events),
            [
                dict(
                    event_id=str(identifier),
                    event_type="vulnerability",
                    title="Synthetic missing support",
                    scope_key="public",
                    visibility="public",
                    tenant_id=None,
                    status="active",
                    first_seen_at=STAMP,
                    business_version=1,
                )
                for identifier in roster
            ],
        )
    _, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    current = service(r15_pg_engine, cookie, ContentStore(tmp_path))
    sub = current.create_subscription(SubscriptionSpec(product_keys=("PyPI:alpha",)))
    generation = current.generate(sub.subscription_id, expected_version=1, event_ids=roster)
    assert len(generation.content.event_ids) == 2000 and len(generation.content.gaps) == 2000
    assert generation.content.batch.stop_reason == "no_supported_subscription_match"
    with pytest.raises(ValueError, match="budget_or_identity_invalid"):
        current.generate(sub.subscription_id, expected_version=1, event_ids=(*roster, uuid4()))


def test_actual_atlas_topic_uses_both_mechanism_and_pinned_taxonomy_evidence(
    r15_pg_engine, tmp_path, monkeypatch
):
    import test_r10_evidence_graph_pg as graph_fixture

    raw_directory = tmp_path / "raw"
    monkeypatch.setattr(graph_fixture, "FIXTURE_RAW_DIRECTORY", raw_directory)
    alphabet = "23456789cfghjmpqrvwx"
    identity = "".join(alphabet[int(value, 16)] for value in uuid4().hex[:12])
    source_identifier = f"GHSA-{identity[:4]}-{identity[4:8]}-{identity[8:]}"
    monkeypatch.setattr(graph_fixture, "SOURCE_IDENTIFIER", source_identifier)
    mapping_value = {
        **graph_fixture.ATLAS,
        "mechanism": graph_fixture.ATLAS["mechanism"].replace(
            "GHSA-2345-6789-cfgh", source_identifier
        ),
    }
    with r15_pg_engine.connect() as connection:
        before = set(connection.scalars(select(document_revisions.c.revision_id)))
    event_id = uuid4()
    mapping = graph_fixture.publish_fact(r15_pg_engine, tmp_path / "claim", event_id, mapping_value)
    with Session(r15_pg_engine) as session, session.begin():
        created_ids = tuple(
            session.scalars(
                select(document_revisions.c.revision_id).where(
                    document_revisions.c.revision_id.not_in(before)
                )
            )
        )
        scope = VisibilityScope(visibility="public")
        EventRepository(session, graph_fixture.publisher_scope(scope)).publish_events(
            uuid4().hex,
            scope,
            (
                EventSubmission(
                    event_id=Identifier(value=str(event_id)),
                    event_type="vulnerability",
                    title="Synthetic unique Atlas event",
                    scope=scope,
                    external_ids=(EventIdentifier(id_type="ghsa", id_value=source_identifier),),
                    source_revision_ids=tuple(Identifier(value=value) for value in created_ids),
                ),
            ),
            STAMP,
        )
    with r15_pg_engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == mapping.record.claim_id.value)
            .values(freshness="current", observed_at=STAMP)
        )
        connection.execute(
            update(document_revisions)
            .where(
                document_revisions.c.revision_id.in_(
                    select(event_documents.c.revision_id).where(
                        event_documents.c.event_id == str(event_id)
                    )
                ),
            )
            .values(first_observed_at=STAMP)
        )
    _, cookie = actor(r15_pg_engine, "fixture-tenant-" + uuid4().hex)
    current = service(r15_pg_engine, cookie, ContentStore(raw_directory))
    sub = current.create_subscription(SubscriptionSpec(risk_topics=("AML.T0051",)))
    generation = current.generate(sub.subscription_id, expected_version=1, event_ids=(event_id,))
    assert len(generation.recommendation_ids) == 1
    reason = generation.content.batch.candidates[0].reasons[0]
    assert reason.code == "risk_topic_match" and reason.matched_key == "AML.T0051"
    assert len({citation.revision_id for citation in reason.citations}) == 2
    assert any("atlas-data" in str(citation.source_uri) for citation in reason.citations)
