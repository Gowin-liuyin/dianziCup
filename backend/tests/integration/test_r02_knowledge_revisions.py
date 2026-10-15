"""R02版本与证据在隔离真实PostgreSQL中的事务/并发验证。"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.enums import ClaimStatus
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.ingestion.parsing.text_blocks import TextBlock
from ai_intel.knowledge.event_linking import (
    EventIdentifier,
    EventLinkingError,
    EventRepository,
    EventSubmission,
)
from ai_intel.knowledge.evidence import locate_evidence_span, render_revision_snippet
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    evidence,
    job_runs,
    outbox_events,
    scope_epochs,
)
from ai_intel.knowledge.persistence import (
    AliasSubmission,
    ClaimRelation,
    ClaimSubmission,
    EntitySubmission,
    EvidenceLink,
    KnowledgePublicationError,
    KnowledgeRepository,
)
from ai_intel.knowledge.persistence_models import (
    change_events,
    claim_assertions,
    claims,
    entities,
    event_documents,
    event_operations,
    events,
    publication_receipts,
)
from ai_intel.knowledge.revisions import (
    QuoteConsistencyError,
    add_text_block,
    attach_evidence_span,
    bump_scope_epoch,
    record_fetch_attempt,
    save_document_revision,
)

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, tzinfo=UTC)


def seed_document(connection, document_id: str, visibility: str, tenant_id: str | None) -> None:
    source_id = str(uuid4())
    content_hash = uuid4().hex + uuid4().hex
    connection.execute(
        content_objects.insert().values(
            content_hash=content_hash,
            size_bytes=0,
            created_at=NOW,
        )
    )
    connection.execute(
        text(
            "INSERT INTO sources(source_id,name,category,base_origin,"
            "visibility,tenant_id,created_at) "
            "VALUES (:id,:id,'vendor_advisory','https://example.invalid',:visibility,:tenant,:now)"
        ),
        {"id": source_id, "visibility": visibility, "tenant": tenant_id, "now": NOW},
    )
    connection.execute(
        documents.insert().values(
            document_id=document_id,
            source_id=source_id,
            kind="advisory",
            title="test advisory",
            published_at=None,
            retrieved_at=NOW,
            content_hash=content_hash,
            visibility=visibility,
            tenant_id=tenant_id,
            schema_version=1,
        )
    )


def test_nonzero_unicode_block_locate_attach_read_roundtrip(migrated_engine, tmp_path) -> None:
    document_id = str(uuid4())
    store = ContentStore(tmp_path / "objects")
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "public", None)
        saved = save_document_revision(connection, store, document_id, b"A", "public", None, NOW)
        text = "引用🙂与中文"
        block_id = add_text_block(connection, saved.revision_id, 1, 100, 106, text)
        block = TextBlock(block_id, 1, "paragraph", text, 100, 106)
        located = locate_evidence_span((block,), "🙂与中", block_id)
        evidence_id = attach_evidence_span(
            connection,
            saved.revision_id,
            located.start_offset,
            located.end_offset,
            "paragraph 1",
            "🙂与中",
            True,
            "public",
            None,
            NOW,
            block_id=block_id,
            verified_at=NOW,
        )
    with migrated_engine.connect() as connection:
        row = connection.execute(
            select(evidence).where(evidence.c.evidence_id == evidence_id)
        ).one()
        assert (row.start_offset, row.end_offset, row.quote) == (102, 105, "🙂与中")
        scope = AccessScope.for_authenticated_user("viewer", "tenant-a", Role.VIEWER)
        assert render_revision_snippet((block,), located, scope, "public", None) == "🙂与中"
    with Session(migrated_engine) as session:
        stored = KnowledgeRepository(session, scope).get_evidence(evidence_id)
        assert stored.record.quote == "🙂与中"
        assert stored.record.span.start_offset == 102
        assert stored.coordinate_version == "fulltext_unicode_v1"


def test_invalid_global_coordinate_and_invalid_block_length_rejected(migrated_engine, tmp_path):
    document_id = str(uuid4())
    store = ContentStore(tmp_path / "objects")
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "public", None)
        saved = save_document_revision(connection, store, document_id, b"A", "public", None, NOW)
        with pytest.raises(QuoteConsistencyError):
            add_text_block(connection, saved.revision_id, 1, 100, 102, "long")
        block_id = add_text_block(connection, saved.revision_id, 1, 100, 104, "long")
        with pytest.raises(QuoteConsistencyError):
            attach_evidence_span(
                connection,
                saved.revision_id,
                0,
                4,
                "paragraph",
                "long",
                True,
                "public",
                None,
                NOW,
                block_id=block_id,
            )
        with pytest.raises(QuoteConsistencyError):
            attach_evidence_span(
                connection,
                saved.revision_id,
                100,
                104,
                "paragraph",
                "long",
                True,
                "public",
                None,
                NOW,
            )


def test_two_connections_same_tip_publish_one_revision(migrated_engine, tmp_path) -> None:
    document_id = str(uuid4())
    store = ContentStore(tmp_path / "objects")
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "public", None)
    barrier = Barrier(2)

    def save_tip(_: int):
        barrier.wait(timeout=10)
        with Session(migrated_engine) as session, session.begin():
            return save_document_revision(session, store, document_id, b"same", "public", None, NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = list(pool.map(save_tip, range(2)))
    assert saved[0].revision_id == saved[1].revision_id
    assert sorted(result.reused for result in saved) == [False, True]
    with migrated_engine.connect() as connection:
        assert (
            len(
                connection.execute(
                    select(document_revisions).where(
                        document_revisions.c.document_id == document_id
                    )
                ).all()
            )
            == 1
        )


def test_two_connections_increment_scope_without_lost_update(migrated_engine) -> None:
    scope_key = "test-scope-" + str(uuid4())
    barrier = Barrier(2)

    def increment(_: int) -> int:
        barrier.wait(timeout=10)
        with Session(migrated_engine) as session, session.begin():
            return bump_scope_epoch(session, scope_key, NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        epochs = list(pool.map(increment, range(2)))
    assert sorted(epochs) == [1, 2]


def prepared_submission(
    engine,
    tmp_path,
    *,
    scope=None,
    claim_status="supported",
    claim_origin="source_explicit",
    value="affected",
    condition="true",
    predicate="affects",
    scoring_authority="",
):
    scope = scope or VisibilityScope(visibility="public")
    document_id = str(uuid4())
    store = ContentStore(tmp_path / "objects")
    with engine.begin() as connection:
        seed_document(connection, document_id, scope.visibility, scope.tenant_id)
        source_id = connection.execute(
            select(documents.c.source_id).where(
                documents.c.document_id == document_id,
            )
        ).scalar_one()
        saved = save_document_revision(
            connection, store, document_id, b"first body", scope.visibility, scope.tenant_id, NOW
        )
        block_id = add_text_block(connection, saved.revision_id, 1, 100, 115, "explicit source")
        evidence_id = attach_evidence_span(
            connection,
            saved.revision_id,
            100,
            115,
            "paragraph",
            "explicit source",
            True,
            scope.visibility,
            scope.tenant_id,
            NOW,
            block_id=block_id,
            verified_at=NOW,
        )
    record = ClaimRecord.model_validate(
        {
            "claim_id": {"value": str(uuid4())},
            "subject": "test-component-" + document_id,
            "predicate": predicate,
            "object_value": value,
            "claim_status": claim_status,
            "claim_origin": claim_origin,
            "condition_value": condition,
            "freshness": "unknown",
            "asserted_at": NOW,
            "scope": scope.model_dump(),
        }
    )
    return ClaimSubmission(
        record=record,
        source_id={"value": source_id},
        revision_id={"value": saved.revision_id},
        json_path="$.value",
        scoring_authority=scoring_authority,
        evidence_links=(
            EvidenceLink(
                evidence_id={"value": evidence_id},
                support_kind="supports",
                validation_status="validated",
            ),
        ),
    )


def publisher_scope(visibility):
    return AccessScope.for_authenticated_user(
        "test-publisher",
        visibility.tenant_id,
        Role.SYSTEM_ADMIN if visibility.visibility == "public" else Role.TENANT_ADMIN,
    )


def publish_submission(engine, submission, key=None, **kwargs):
    with Session(engine) as session, session.begin():
        return KnowledgeRepository(session, publisher_scope(submission.record.scope)).publish(
            key or str(uuid4()),
            submission.record.scope,
            (submission,),
            created_at=NOW,
            **kwargs,
        )


def test_publication_database_failure_rolls_back_every_business_row_and_key(
    migrated_engine, tmp_path
):
    first = prepared_submission(migrated_engine, tmp_path)
    second = first.model_copy(
        update={"record": first.record.model_copy(update={"object_value": "different"})}
    )
    key = str(uuid4())
    with Session(migrated_engine) as session, session.begin():
        repository = KnowledgeRepository(session, publisher_scope(first.record.scope))
        before_epoch = session.execute(
            select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public")
        ).scalar_one_or_none()
        with pytest.raises(IntegrityError):
            repository.publish(key, first.record.scope, (first, second), created_at=NOW)
        assert (
            session.execute(
                select(claims.c.claim_id).where(claims.c.claim_id == first.record.claim_id.value)
            ).all()
            == []
        )
        assert (
            session.execute(
                select(claim_assertions.c.assertion_id).where(
                    claim_assertions.c.claim_id == first.record.claim_id.value
                )
            ).all()
            == []
        )
        assert (
            session.execute(
                select(publication_receipts.c.receipt_id).where(
                    publication_receipts.c.publication_key == key
                )
            ).all()
            == []
        )
        assert (
            session.execute(
                select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public")
            ).scalar_one_or_none()
            == before_epoch
        )
        saved = repository.publish(key, first.record.scope, (first,), created_at=NOW)
    assert saved.claim_ids == (first.record.claim_id.value,)


def test_same_key_different_digest_rejected_without_second_message(migrated_engine, tmp_path):
    first = prepared_submission(migrated_engine, tmp_path)
    key = str(uuid4())
    receipt = publish_submission(migrated_engine, first, key)
    different = first.model_copy(update={"json_path": "$.changed"})
    with pytest.raises(IdempotencyConflictError):
        publish_submission(migrated_engine, different, key)
    with migrated_engine.connect() as connection:
        assert (
            len(
                connection.execute(
                    select(publication_receipts).where(
                        publication_receipts.c.publication_key == key
                    )
                ).all()
            )
            == 1
        )
        assert (
            len(
                connection.execute(
                    select(outbox_events).where(outbox_events.c.job_id == receipt.job_id)
                ).all()
            )
            == 1
        )
        assert (
            connection.execute(
                select(job_runs.c.payload_ref).where(job_runs.c.job_id == receipt.job_id)
            ).scalar_one()
            == "pg:change:" + receipt.change_id
        )


def test_two_processes_publish_one_receipt_and_restart_reads_same_fact(migrated_engine, tmp_path):
    submission = prepared_submission(migrated_engine, tmp_path)
    key = str(uuid4())
    helper = (
        Path(__file__).resolve().parents[3]
        / "reports/runs/recovery_r02_knowledge_20261015/process_probe.py"
    )
    payload = json.dumps({"submission": submission.model_dump(mode="json"), "key": key})

    def invoke(mode):
        completed = subprocess.run(
            [sys.executable, str(helper), mode],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=25,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return json.loads(completed.stdout)

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(invoke, ("publish", "publish")))
    assert receipts[0]["receipt_id"] == receipts[1]["receipt_id"]
    restarted = invoke("read")
    assert restarted["claim_id"] == submission.record.claim_id.value
    assert restarted["object_value"] == "affected"
    with migrated_engine.connect() as connection:
        assert (
            len(
                connection.execute(
                    select(publication_receipts).where(
                        publication_receipts.c.publication_key == key
                    )
                ).all()
            )
            == 1
        )


@pytest.mark.parametrize(
    "reader_role,reader_tenant",
    [(Role.ANALYST, "tenant-b"), (Role.VIEWER, "tenant-a"), (Role.SYSTEM_ADMIN, None)],
)
def test_tenant_claims_not_read_searched_or_exported_to_unauthorized_scope(
    migrated_engine, tmp_path, reader_role, reader_tenant
):
    submission = prepared_submission(
        migrated_engine,
        tmp_path,
        scope=VisibilityScope(visibility="tenant", tenant_id="tenant-a"),
        value="private-asset-value",
    )
    publish_submission(migrated_engine, submission)
    scope = AccessScope.for_authenticated_user("reader", reader_tenant, reader_role)
    with Session(migrated_engine) as session:
        repository = KnowledgeRepository(session, scope)
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            repository.get_claim(submission.record.claim_id.value)
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            repository.get_evidence(submission.evidence_links[0].evidence_id.value)
        assert (
            repository.list_current_claims(candidate_ids=(submission.record.claim_id.value,)) == ()
        )
        assert "private-asset-value" not in repository.export_current_claims(limit=1000)


def test_own_tenant_reader_gets_private_claim_but_public_derivation_rejected(
    migrated_engine, tmp_path
):
    submission = prepared_submission(
        migrated_engine, tmp_path, scope=VisibilityScope(visibility="tenant", tenant_id="tenant-a")
    )
    publish_submission(migrated_engine, submission)
    owner = AccessScope.for_authenticated_user("reader", "tenant-a", Role.ANALYST)
    with Session(migrated_engine) as session:
        assert (
            KnowledgeRepository(session, owner)
            .get_claim(submission.record.claim_id.value)
            .object_value
            == "affected"
        )
    widened = submission.model_copy(
        update={
            "record": submission.record.model_copy(
                update={"scope": VisibilityScope(visibility="public")}
            )
        }
    )
    with pytest.raises(CrossTenantAccessError):
        publish_submission(migrated_engine, widened)


def test_model_hypothesis_and_unverified_support_never_become_current_fact(
    migrated_engine, tmp_path
):
    hypothesis = prepared_submission(
        migrated_engine, tmp_path, claim_status="unverified", claim_origin="model_hypothesis"
    )
    receipt = publish_submission(migrated_engine, hypothesis)
    with Session(migrated_engine) as session:
        repo = KnowledgeRepository(session, publisher_scope(hypothesis.record.scope))
        assert repo.get_claim(receipt.claim_ids[0]).claim_status.value == "unverified"
        assert repo.list_current_claims(candidate_ids=receipt.claim_ids) == ()
    elevated = hypothesis.model_copy(
        update={
            "record": hypothesis.record.model_copy(update={"claim_status": ClaimStatus.SUPPORTED})
        }
    )
    with pytest.raises(KnowledgePublicationError, match="hypothesis"):
        publish_submission(migrated_engine, elevated)
    unsupported = prepared_submission(migrated_engine, tmp_path)
    unsupported = unsupported.model_copy(
        update={
            "evidence_links": (
                unsupported.evidence_links[0].model_copy(
                    update={"validation_status": "unverified"}
                ),
            )
        }
    )
    with pytest.raises(KnowledgePublicationError, match="support"):
        publish_submission(migrated_engine, unsupported)


def test_same_field_different_uuid_deduplicates_but_path_and_authority_remain(
    migrated_engine, tmp_path
):
    original = prepared_submission(migrated_engine, tmp_path)
    first = publish_submission(migrated_engine, original)
    duplicate = original.model_copy(
        update={
            "record": original.record.model_copy(
                update={"claim_id": Identifier(value=str(uuid4()))}
            )
        }
    )
    duplicate = ClaimSubmission.model_validate(duplicate.model_dump())
    second = publish_submission(migrated_engine, duplicate)
    assert first.claim_ids == second.claim_ids
    for field in ("json_path", "scoring_authority"):
        different = original.model_copy(
            update={
                field: "different",
                "record": original.record.model_copy(
                    update={"claim_id": Identifier(value=str(uuid4()))}
                ),
            }
        )
        different = ClaimSubmission.model_validate(different.model_dump())
        assert publish_submission(migrated_engine, different).claim_ids != first.claim_ids


def test_supersede_preserves_old_value_history_and_404_does_not_withdraw(migrated_engine, tmp_path):
    original = prepared_submission(migrated_engine, tmp_path)
    publish_submission(migrated_engine, original)
    with migrated_engine.begin() as connection:
        document_id = connection.execute(
            select(document_revisions.c.document_id).where(
                document_revisions.c.revision_id == original.revision_id.value
            )
        ).scalar_one()
        saved = save_document_revision(
            connection,
            ContentStore(tmp_path / "objects"),
            document_id,
            b"changed body",
            "public",
            None,
            NOW + timedelta(seconds=1),
        )
        block_id = add_text_block(connection, saved.revision_id, 1, 100, 107, "changed")
        evidence_id = attach_evidence_span(
            connection,
            saved.revision_id,
            100,
            107,
            "paragraph",
            "changed",
            True,
            "public",
            None,
            NOW + timedelta(seconds=1),
            block_id=block_id,
            verified_at=NOW + timedelta(seconds=1),
        )
    changed_record = original.record.model_copy(
        update={"claim_id": Identifier(value=str(uuid4())), "object_value": "fixed"}
    )
    changed = ClaimSubmission.model_validate(
        {
            **original.model_dump(),
            "record": changed_record.model_dump(),
            "revision_id": {"value": saved.revision_id},
            "evidence_links": [
                {
                    "evidence_id": {"value": evidence_id},
                    "support_kind": "supports",
                    "validation_status": "validated",
                }
            ],
        }
    )
    relation = ClaimRelation(
        left_claim_id=original.record.claim_id,
        right_claim_id=changed.record.claim_id,
        relation_type="supersedes",
        reason="explicit vendor revision",
    )
    with Session(migrated_engine) as session, session.begin():
        repo = KnowledgeRepository(session, publisher_scope(original.record.scope))
        repo.publish(
            str(uuid4()),
            changed.record.scope,
            (changed,),
            relations=(relation,),
            created_at=NOW + timedelta(seconds=2),
        )
        historical = repo.get_claim(
            original.record.claim_id.value, known_at=NOW + timedelta(seconds=1)
        )
        assert (
            historical.claim_status.value == "supported" and historical.object_value == "affected"
        )
        assert repo.get_claim(original.record.claim_id.value).claim_status.value == "superseded"
        assert repo.list_current_claims(candidate_ids=(original.record.claim_id.value,)) == ()
        record_fetch_attempt(
            session, original.source_id.value, NOW + timedelta(seconds=3), "failed", 404
        )
        assert repo.get_claim(changed.record.claim_id.value).claim_status.value == "supported"


def test_entity_ecosystem_and_verified_alias_are_persistent(migrated_engine, tmp_path):
    submission = prepared_submission(migrated_engine, tmp_path)
    alias = AliasSubmission(
        alias_value="test-alias-" + str(uuid4()),
        source_id=submission.source_id,
        revision_id=submission.revision_id,
        evidence_id=submission.evidence_links[0].evidence_id,
        status="validated",
    )
    first = EntitySubmission(
        entity_id={"value": str(uuid4())},
        entity_type="package",
        ecosystem="pypi",
        canonical_name="Demo-" + str(uuid4()),
        scope=submission.record.scope,
        aliases=(alias,),
    )
    second = first.model_copy(
        update={"entity_id": Identifier(value=str(uuid4())), "ecosystem": "npm", "aliases": ()}
    )
    second = EntitySubmission.model_validate(second.model_dump())
    publish_submission(migrated_engine, submission, entity_submissions=(first, second))
    with Session(migrated_engine) as session:
        repo = KnowledgeRepository(session, publisher_scope(submission.record.scope))
        assert repo.resolve_entity_alias(alias.alias_value, known_at=NOW) == (
            first.entity_id.value,
        )
        rows = session.execute(
            select(entities.c.ecosystem, entities.c.entity_id).where(
                entities.c.entity_id.in_((first.entity_id.value, second.entity_id.value))
            )
        ).all()
        assert {row[0] for row in rows} == {"pypi", "npm"}


def test_one_article_two_cves_keeps_two_persistent_events_and_merge_rejected(
    migrated_engine, tmp_path
):
    source = prepared_submission(migrated_engine, tmp_path)
    first = EventSubmission(
        event_id={"value": str(uuid4())},
        event_type="vulnerability",
        title="first event",
        scope=source.record.scope,
        external_ids=(
            EventIdentifier(id_type="cve", id_value=f"CVE-2026-{int(uuid4().hex[:8], 16):08d}"),
        ),
        source_revision_ids=(source.revision_id,),
    )
    second = EventSubmission(
        event_id={"value": str(uuid4())},
        event_type="vulnerability",
        title="second event",
        scope=source.record.scope,
        external_ids=(
            EventIdentifier(id_type="cve", id_value=f"CVE-2026-{int(uuid4().hex[:8], 16):08d}"),
        ),
        source_revision_ids=(source.revision_id,),
    )
    with Session(migrated_engine) as session, session.begin():
        repo = EventRepository(session, publisher_scope(source.record.scope))
        repo.publish_events(str(uuid4()), source.record.scope, (first, second), NOW)
        assert repo.get_source_revisions(first.event_id.value) == (source.revision_id.value,)
        assert repo.get_source_revisions(second.event_id.value) == (source.revision_id.value,)
        with pytest.raises(EventLinkingError, match="different CVEs"):
            repo.merge_events(
                str(uuid4()),
                first.event_id.value,
                second.event_id.value,
                "same article is insufficient",
                NOW,
            )
        assert (
            len(
                session.execute(
                    select(events).where(
                        events.c.event_id.in_((first.event_id.value, second.event_id.value))
                    )
                ).all()
            )
            == 2
        )


def prepared_event_pair(engine, tmp_path):
    first_source = prepared_submission(engine, tmp_path)
    second_source = prepared_submission(engine, tmp_path)
    first = EventSubmission(
        event_id={"value": str(uuid4())},
        event_type="research_risk",
        title="candidate first",
        scope=first_source.record.scope,
        source_revision_ids=(first_source.revision_id,),
    )
    second = EventSubmission(
        event_id={"value": str(uuid4())},
        event_type="research_risk",
        title="candidate second",
        scope=first_source.record.scope,
        source_revision_ids=(second_source.revision_id,),
    )
    with Session(engine) as session, session.begin():
        EventRepository(session, publisher_scope(first.scope)).publish_events(
            str(uuid4()), first.scope, (first, second), NOW
        )
    return first, second


def test_merge_undo_restores_exact_sources_keeps_history_and_outbox(migrated_engine, tmp_path):
    first, second = prepared_event_pair(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repo = EventRepository(session, publisher_scope(first.scope))
        merged = repo.merge_events(
            str(uuid4()),
            first.event_id.value,
            second.event_id.value,
            "explicit candidate association",
            NOW + timedelta(seconds=1),
        )
        assert set(repo.get_source_revisions(second.event_id.value)) == {
            first.source_revision_ids[0].value,
            second.source_revision_ids[0].value,
        }
        operation_id = session.execute(
            select(event_operations.c.operation_id).where(
                event_operations.c.source_event_id == first.event_id.value,
                event_operations.c.operation_type == "merge",
            )
        ).scalar_one()
        undo_key = str(uuid4())
        undone = repo.undo_merge(
            undo_key,
            operation_id,
            "association review found wrong link",
            NOW + timedelta(seconds=2),
        )
        repeated = repo.undo_merge(
            undo_key,
            operation_id,
            "association review found wrong link",
            NOW + timedelta(seconds=3),
        )
        assert undone.receipt_id == repeated.receipt_id
        assert repo.get_source_revisions(first.event_id.value) == (
            first.source_revision_ids[0].value,
        )
        assert repo.get_source_revisions(second.event_id.value) == (
            second.source_revision_ids[0].value,
        )
        assert (
            len(
                session.execute(
                    select(event_operations).where(
                        event_operations.c.source_event_id == first.event_id.value
                    )
                ).all()
            )
            == 2
        )
        assert (
            session.execute(
                select(outbox_events.c.event_id).where(outbox_events.c.job_id == merged.job_id)
            ).first()
            is not None
        )
        assert (
            session.execute(
                select(outbox_events.c.event_id).where(outbox_events.c.job_id == undone.job_id)
            ).first()
            is not None
        )
        inactive = session.execute(
            select(event_documents.c.active).where(
                event_documents.c.event_id == second.event_id.value,
                event_documents.c.revision_id == first.source_revision_ids[0].value,
            )
        ).scalar_one()
        assert inactive is False


def test_undo_after_new_association_rejects_without_erasing_new_sources(migrated_engine, tmp_path):
    first, second = prepared_event_pair(migrated_engine, tmp_path)
    with Session(migrated_engine) as session, session.begin():
        repo = EventRepository(session, publisher_scope(first.scope))
        repo.merge_events(
            str(uuid4()),
            first.event_id.value,
            second.event_id.value,
            "reviewed candidate",
            NOW + timedelta(seconds=1),
        )
        operation_id = session.execute(
            select(event_operations.c.operation_id).where(
                event_operations.c.source_event_id == first.event_id.value,
                event_operations.c.operation_type == "merge",
            )
        ).scalar_one()
        independently_confirmed = second.model_copy(
            update={"source_revision_ids": first.source_revision_ids}
        )
        repo.publish_events(
            str(uuid4()), second.scope, (independently_confirmed,), NOW + timedelta(seconds=2)
        )
        with pytest.raises(EventLinkingError, match="rebase"):
            repo.undo_merge(
                str(uuid4()), operation_id, "old undo request", NOW + timedelta(seconds=3)
            )
        assert first.source_revision_ids[0].value in repo.get_source_revisions(
            second.event_id.value
        )


@pytest.mark.parametrize(
    "predicate,value",
    [
        ("cvss_score", {"kind": "score", "score": 8.1, "authority": "CNA", "vector": None}),
        (
            "reference_link",
            {
                "kind": "link",
                "url": "https://example.invalid/advisory",
                "title": "static source link",
            },
        ),
        (
            "affected_versions",
            {
                "kind": "version_range",
                "ecosystem": "pypi",
                "expression": ">=1,<2",
                "branch": "stable",
            },
        ),
    ],
)
def test_structured_claim_values_roundtrip_in_existing_pg_claims(
    migrated_engine, tmp_path, predicate, value
):
    submission = prepared_submission(
        migrated_engine,
        tmp_path,
        predicate=predicate,
        value=value,
        scoring_authority="CNA" if predicate == "cvss_score" else "",
    )
    receipt = publish_submission(migrated_engine, submission)
    with Session(migrated_engine) as session:
        record = KnowledgeRepository(session, publisher_scope(submission.record.scope)).get_claim(
            receipt.claim_ids[0]
        )
        assert record.object_value.model_dump(mode="json") == value
        row = session.execute(
            select(claims.c.object_json, claims.c.value_kind).where(
                claims.c.claim_id == record.claim_id.value
            )
        ).one()
        assert row[0] == value and row[1] == value["kind"]


def test_outbox_sql_failure_rolls_back_facts_epoch_change_job_and_receipt(
    migrated_engine, tmp_path
):
    submission = prepared_submission(migrated_engine, tmp_path)
    key = str(uuid4())
    function_name = "test_r02_outbox_failure_" + uuid4().hex
    trigger_name = "test_r02_outbox_trigger_" + uuid4().hex
    with Session(migrated_engine) as session, session.begin():
        repo = KnowledgeRepository(session, publisher_scope(submission.record.scope))
        counts_before = [
            session.execute(select(func.count()).select_from(table)).scalar_one()
            for table in (claims, change_events, job_runs, outbox_events, publication_receipts)
        ]
        epoch_before = session.execute(
            select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public")
        ).scalar_one_or_none()
        session.execute(
            text(
                f"CREATE FUNCTION {function_name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'synthetic outbox write failure'; END $$"
            )
        )
        session.execute(
            text(
                f"CREATE TRIGGER {trigger_name} BEFORE INSERT ON outbox_events "
                f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
            )
        )
        try:
            with pytest.raises(DBAPIError, match="synthetic outbox write failure"):
                repo.publish(key, submission.record.scope, (submission,), created_at=NOW)
            counts_after = [
                session.execute(select(func.count()).select_from(table)).scalar_one()
                for table in (claims, change_events, job_runs, outbox_events, publication_receipts)
            ]
            assert counts_after == counts_before
            assert (
                session.execute(
                    select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public")
                ).scalar_one_or_none()
                == epoch_before
            )
        finally:
            session.execute(text(f"DROP TRIGGER {trigger_name} ON outbox_events"))
            session.execute(text(f"DROP FUNCTION {function_name}()"))
        assert repo.publish(
            key, submission.record.scope, (submission,), created_at=NOW
        ).claim_ids == (submission.record.claim_id.value,)


def conflict_pair(engine, tmp_path, *, different_authorities=False):
    first = prepared_submission(
        engine, tmp_path, value="affected", condition="true", scoring_authority="CNA"
    )
    second = prepared_submission(
        engine,
        tmp_path,
        value="unaffected",
        condition="false",
        scoring_authority="OTHER" if different_authorities else "CNA",
    )
    second = second.model_copy(
        update={"record": second.record.model_copy(update={"subject": first.record.subject})}
    )
    return first, second


def test_conflict_retains_both_claims_and_historical_supported_status(migrated_engine, tmp_path):
    first, second = conflict_pair(migrated_engine, tmp_path)
    publish_submission(migrated_engine, first)
    relation = ClaimRelation(
        left_claim_id=first.record.claim_id,
        right_claim_id=second.record.claim_id,
        relation_type="disputed",
        reason="same-scope opposite condition evidence",
    )
    with Session(migrated_engine) as session, session.begin():
        repo = KnowledgeRepository(session, publisher_scope(first.record.scope))
        repo.publish(
            str(uuid4()),
            second.record.scope,
            (second,),
            relations=(relation,),
            created_at=NOW + timedelta(seconds=2),
        )
        assert (
            repo.get_claim(
                first.record.claim_id.value, known_at=NOW + timedelta(seconds=1)
            ).claim_status.value
            == "supported"
        )
        both = repo.list_current_claims(
            candidate_ids=(first.record.claim_id.value, second.record.claim_id.value)
        )
        assert len(both) == 2 and {record.claim_status.value for record in both} == {"disputed"}
        assert {record.condition_value.value for record in both} == {"true", "false"}
        assert (
            repo.get_claim(
                second.record.claim_id.value, known_at=NOW + timedelta(seconds=2)
            ).claim_status.value
            == "disputed"
        )


def test_different_authorities_remain_parallel_and_dispute_batch_rolls_back(
    migrated_engine, tmp_path
):
    first, second = conflict_pair(migrated_engine, tmp_path, different_authorities=True)
    publish_submission(migrated_engine, first)
    relation = ClaimRelation(
        left_claim_id=first.record.claim_id,
        right_claim_id=second.record.claim_id,
        relation_type="disputed",
        reason="invalid institution conflict",
    )
    with Session(migrated_engine) as session, session.begin():
        repo = KnowledgeRepository(session, publisher_scope(first.record.scope))
        with pytest.raises(KnowledgePublicationError, match="authorities"):
            repo.publish(
                str(uuid4()),
                second.record.scope,
                (second,),
                relations=(relation,),
                created_at=NOW + timedelta(seconds=2),
            )
        assert repo.get_claim(first.record.claim_id.value).claim_status.value == "supported"
        with pytest.raises(CrossTenantAccessError):
            repo.get_claim(second.record.claim_id.value)
        repo.publish(
            str(uuid4()), second.record.scope, (second,), created_at=NOW + timedelta(seconds=3)
        )
        assert (
            len(
                repo.list_current_claims(
                    candidate_ids=(first.record.claim_id.value, second.record.claim_id.value)
                )
            )
            == 2
        )


def test_legacy_sql_values_survive_but_cannot_be_current_verified_results(migrated_engine):
    claim_id = str(uuid4())
    with Session(migrated_engine) as session, session.begin():
        session.execute(
            claims.insert().values(
                claim_id=claim_id,
                subject="legacy component",
                predicate="affects",
                object_value="legacy preserved value",
                claim_status="supported",
                claim_origin="source_explicit",
                condition_value="unknown",
                freshness="unknown",
                asserted_at=NOW,
                observed_at=None,
                visibility="public",
                tenant_id=None,
                created_at=NOW,
            )
        )
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("reader", "tenant-a", Role.VIEWER)
        )
        record = repo.get_claim(claim_id)
        assert (
            record.claim_status.value == "unverified"
            and record.object_value == "legacy preserved value"
        )
        assert repo.list_current_claims(candidate_ids=(claim_id,)) == ()
        row = session.execute(
            select(claims.c.claim_status, claims.c.condition_value).where(
                claims.c.claim_id == claim_id
            )
        ).one()
        assert row == ("supported", "unknown")
