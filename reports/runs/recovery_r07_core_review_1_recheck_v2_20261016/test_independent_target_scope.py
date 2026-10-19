"""Exercise embedded target ACLs, exact identities, saved rollback keys and replay in own PG."""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import NOW, prepared_submission, publish_submission, publisher_scope
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r07_signal_claim_values_pg import signal_submission
from tests.unit.test_r07_enrichment_contracts import SIGNALS

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.models import document_revisions, evidence, job_runs, outbox_events, scope_epochs
from ai_intel.knowledge.persistence import KnowledgePublicationError, KnowledgeRepository
from ai_intel.knowledge.persistence_models import change_events, claim_assertions, claim_evidence, claims, publication_receipts

pytestmark = pytest.mark.real_pg
RUN = Path(__file__).resolve().parent
PUBLIC = VisibilityScope(visibility="public")
OWNER = VisibilityScope(visibility="tenant", tenant_id="independent-private-tenant")
OTHER = VisibilityScope(visibility="tenant", tenant_id="independent-other-tenant")
OBSERVATIONS = []


def snapshot(engine):
    with Session(engine) as session:
        counts = {table.name: session.scalar(select(func.count()).select_from(table)) for table in (claims, claim_assertions, claim_evidence, evidence, publication_receipts, change_events, job_runs, outbox_events)}
        epochs = [{"scope_key": row.scope_key, "epoch": row.epoch, "updated_at": row.updated_at.isoformat()} for row in session.execute(select(scope_epochs).order_by(scope_epochs.c.scope_key))]
    return {"counts": counts, "epochs": epochs}


def target(engine, path, scope):
    template = prepared_submission(engine, path, scope=scope)
    with Session(engine) as session:
        document_id = session.scalar(select(document_revisions.c.document_id).where(document_revisions.c.revision_id == template.revision_id.value))
    return document_id, template.revision_id.value, template.evidence_links[0].evidence_id.value


def log_observation(label, submission, before, after, **extra):
    OBSERVATIONS.append({"label": label, "input": submission.model_dump(mode="json"), "before": before, "after": after, **extra})
    (RUN / "independent_pg_observations.json").write_text(json.dumps({"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "database": "test_dianzi_r06_catalog_r07_core_recheck_v2_20261016", "cases": OBSERVATIONS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


@pytest.mark.parametrize("scenario", ["original_public_private", "public_accessible_private", "cross_tenant", "missing_document", "missing_revision", "real_mismatched_pair"])
def test_rejected_target_has_no_business_side_effect_and_hides_identity(catalog_engine, tmp_path, scenario):
    claim_scope = OWNER if scenario == "cross_tenant" else PUBLIC
    target_scope = OTHER if scenario == "cross_tenant" else OWNER if "private" in scenario else PUBLIC
    document_id, revision_id, evidence_id = target(catalog_engine, tmp_path / "target", target_scope)
    if scenario == "missing_document":
        document_id = str(uuid4())
    elif scenario == "missing_revision":
        revision_id = str(uuid4())
    elif scenario == "real_mismatched_pair":
        document_id, _, _ = target(catalog_engine, tmp_path / "other_target", PUBLIC)
    submission = signal_submission(catalog_engine, tmp_path / "claim", {**SIGNALS[6], "target_document_id": document_id, "target_revision_id": revision_id}, scope=claim_scope)
    actor = publisher_scope(claim_scope)
    expected_error = CrossTenantAccessError
    if scenario == "public_accessible_private":
        actor = AccessScope.for_authenticated_user("independent-owner-system-admin", OWNER.tenant_id, Role.SYSTEM_ADMIN)
        assert actor.can_access(target_scope.visibility, target_scope.tenant_id)
        expected_error = KnowledgePublicationError
    before = snapshot(catalog_engine)
    caught = None
    with Session(catalog_engine) as session, session.begin():
        try:
            KnowledgeRepository(session, actor).publish("independent-denied-" + uuid4().hex, claim_scope, (submission,), created_at=NOW)
        except (CrossTenantAccessError, KnowledgePublicationError) as error:
            caught = error
    after = snapshot(catalog_engine)
    log_observation(scenario, submission, before, after, exception_type=type(caught).__name__, exception_message=str(caught))
    assert isinstance(caught, expected_error)
    assert after == before
    viewer = AccessScope.for_authenticated_user("independent-other-viewer", "other-tenant", Role.VIEWER)
    with Session(catalog_engine) as session:
        repository = KnowledgeRepository(session, viewer)
        with pytest.raises(CrossTenantAccessError):
            repository.get_claim(submission.record.claim_id.value)
        if target_scope.visibility == "tenant":
            with pytest.raises(CrossTenantAccessError):
                repository.get_evidence(evidence_id)


@pytest.mark.parametrize("scenario", ["public_public", "same_tenant", "tenant_public", "external_omitted", "external_explicit_null"])
def test_visible_or_external_targets_preserve_full_value_and_replay(catalog_engine, tmp_path, scenario):
    claim_scope = OWNER if scenario in {"same_tenant", "tenant_public"} else PUBLIC
    value = dict(SIGNALS[6])
    if scenario in {"public_public", "same_tenant", "tenant_public"}:
        target_scope = OWNER if scenario == "same_tenant" else PUBLIC
        document_id, revision_id, _ = target(catalog_engine, tmp_path / "target", target_scope)
        value.update(target_document_id=document_id, target_revision_id=revision_id)
    elif scenario == "external_explicit_null":
        value.update(target_document_id=None, target_revision_id=None)
    submission = signal_submission(catalog_engine, tmp_path / "claim", value, scope=claim_scope)
    key = "independent-allowed-" + uuid4().hex
    before = snapshot(catalog_engine)
    first = publish_submission(catalog_engine, submission, key)
    after_first = snapshot(catalog_engine)
    repeated = publish_submission(catalog_engine, submission, key)
    after_replay = snapshot(catalog_engine)
    with Session(catalog_engine) as session:
        stored = KnowledgeRepository(session, publisher_scope(claim_scope)).get_claim(submission.record.claim_id.value)
    log_observation(scenario, submission, before, after_first, after_replay=after_replay, preserved_full_record=stored == submission.record)
    assert first == repeated and after_first == after_replay
    assert stored == submission.record
    assert stored.claim_status.value == "unverified" and stored.condition_value.value == "unknown"
    assert after_first["counts"]["claims"] - before["counts"]["claims"] == 1
    assert after_first["counts"]["claim_evidence"] - before["counts"]["claim_evidence"] == 1


def test_failed_batch_does_not_reserve_key_and_corrected_batch_replays_once(catalog_engine, tmp_path):
    public_doc, public_rev, _ = target(catalog_engine, tmp_path / "public_target", PUBLIC)
    private_doc, private_rev, _ = target(catalog_engine, tmp_path / "private_target", OWNER)
    valid = signal_submission(catalog_engine, tmp_path / "valid", {**SIGNALS[6], "target_document_id": public_doc, "target_revision_id": public_rev})
    invalid = signal_submission(catalog_engine, tmp_path / "invalid", {**SIGNALS[6], "target_document_id": private_doc, "target_revision_id": private_rev})
    corrected = invalid.model_copy(update={"record": invalid.record.model_copy(update={"object_value": valid.record.object_value})})
    key = "independent-retry-key-" + uuid4().hex
    before = snapshot(catalog_engine)
    with Session(catalog_engine) as session, session.begin():
        repository = KnowledgeRepository(session, publisher_scope(PUBLIC))
        with pytest.raises(CrossTenantAccessError):
            repository.publish(key, PUBLIC, (valid, invalid), created_at=NOW)
        assert snapshot(catalog_engine) == before
        first = repository.publish(key, PUBLIC, (valid, corrected), created_at=NOW)
    after_first = snapshot(catalog_engine)
    with Session(catalog_engine) as session, session.begin():
        repeated = KnowledgeRepository(session, publisher_scope(PUBLIC)).publish(key, PUBLIC, (valid, corrected), created_at=NOW)
    after_replay = snapshot(catalog_engine)
    log_observation("batch_rollback_corrected_key", invalid, before, after_first, after_replay=after_replay)
    assert first == repeated and after_first == after_replay
    assert after_first["counts"]["claims"] - before["counts"]["claims"] == 2
    assert after_first["counts"]["publication_receipts"] - before["counts"]["publication_receipts"] == 1


def test_changed_target_is_not_accepted_as_same_idempotent_payload(catalog_engine, tmp_path):
    first_doc, first_rev, _ = target(catalog_engine, tmp_path / "first", PUBLIC)
    second_doc, second_rev, _ = target(catalog_engine, tmp_path / "second", PUBLIC)
    submission = signal_submission(catalog_engine, tmp_path / "claim", {**SIGNALS[6], "target_document_id": first_doc, "target_revision_id": first_rev})
    different_value = submission.record.object_value.model_copy(update={"target_document_id": second_doc, "target_revision_id": second_rev})
    changed = submission.model_copy(update={"record": submission.record.model_copy(update={"object_value": different_value})})
    key = "independent-conflict-" + uuid4().hex
    publish_submission(catalog_engine, submission, key)
    before = snapshot(catalog_engine)
    with pytest.raises(IdempotencyConflictError):
        publish_submission(catalog_engine, changed, key)
    after = snapshot(catalog_engine)
    log_observation("same_key_changed_target", changed, before, after)
    assert after == before


def test_model_hypothesis_and_invalid_pair_are_revalidated_on_publication(catalog_engine, tmp_path):
    submission = signal_submission(catalog_engine, tmp_path, SIGNALS[6])
    before = snapshot(catalog_engine)
    promoted = submission.model_copy(update={"record": submission.record.model_copy(update={"claim_status": "supported"})})
    with pytest.raises(KnowledgePublicationError, match="model hypothesis"):
        publish_submission(catalog_engine, promoted)
    malformed_value = submission.record.object_value.model_copy(update={"target_document_id": uuid4()})
    malformed = submission.model_copy(update={"record": submission.record.model_copy(update={"object_value": malformed_value})})
    with pytest.raises(ValidationError):
        publish_submission(catalog_engine, malformed)
    after = snapshot(catalog_engine)
    log_observation("publication_revalidation", submission, before, after)
    assert after == before
