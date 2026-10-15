"""Embedded document references obey the same visibility boundary as evidence."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import prepared_submission, publish_submission
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r07_signal_claim_values_pg import signal_submission
from tests.unit.test_r07_enrichment_contracts import SIGNALS

from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.domain.values import VisibilityScope
from ai_intel.knowledge.models import (
    document_revisions,
    evidence,
    job_runs,
    outbox_events,
    scope_epochs,
)
from ai_intel.knowledge.persistence_models import (
    change_events,
    claim_assertions,
    claims,
    publication_receipts,
)

pytestmark = pytest.mark.real_pg
PUBLIC = VisibilityScope(visibility="public")
OWNER = VisibilityScope(visibility="tenant", tenant_id="fixture-owner")
OTHER = VisibilityScope(visibility="tenant", tenant_id="fixture-other")


def target_identity(engine, tmp_path, scope):
    target = prepared_submission(engine, tmp_path, scope=scope)
    with Session(engine) as session:
        document_id = session.scalar(
            select(document_revisions.c.document_id).where(
                document_revisions.c.revision_id == target.revision_id.value
            )
        )
    return document_id, target.revision_id.value


def snapshot(engine):
    with Session(engine) as session:
        counts = tuple(
            session.scalar(select(func.count()).select_from(table))
            for table in (
                claims,
                claim_assertions,
                evidence,
                publication_receipts,
                change_events,
                job_runs,
                outbox_events,
            )
        )
        epochs = tuple(session.execute(select(scope_epochs).order_by(scope_epochs.c.scope_key)))
        return counts, epochs


@pytest.mark.parametrize("claim_scope,target_scope", [(PUBLIC, OWNER), (OWNER, OTHER)])
def test_hidden_reference_target_is_rejected_without_any_publication_effect(
    catalog_engine, tmp_path, claim_scope, target_scope
):
    document_id, revision_id = target_identity(catalog_engine, tmp_path / "target", target_scope)
    submission = signal_submission(
        catalog_engine,
        tmp_path / "claim",
        {**SIGNALS[6], "target_document_id": document_id, "target_revision_id": revision_id},
        scope=claim_scope,
    )
    before = snapshot(catalog_engine)
    with pytest.raises(CrossTenantAccessError):
        publish_submission(catalog_engine, submission)
    assert snapshot(catalog_engine) == before


@pytest.mark.parametrize("wrong_identity", ["document", "revision"])
def test_reference_identity_must_resolve_to_the_exact_document_revision_pair(
    catalog_engine, tmp_path, wrong_identity
):
    document_id, revision_id = target_identity(catalog_engine, tmp_path / "target", PUBLIC)
    submission = signal_submission(
        catalog_engine,
        tmp_path / "claim",
        {
            **SIGNALS[6],
            "target_document_id": str(uuid4()) if wrong_identity == "document" else document_id,
            "target_revision_id": str(uuid4()) if wrong_identity == "revision" else revision_id,
        },
    )
    before = snapshot(catalog_engine)
    with pytest.raises(CrossTenantAccessError):
        publish_submission(catalog_engine, submission)
    assert snapshot(catalog_engine) == before


@pytest.mark.parametrize(
    "claim_scope,target_scope", [(PUBLIC, PUBLIC), (OWNER, OWNER), (OWNER, PUBLIC)]
)
def test_visible_targets_remain_publishable_with_fixed_identity_and_safe_replay(
    catalog_engine, tmp_path, claim_scope, target_scope
):
    document_id, revision_id = target_identity(catalog_engine, tmp_path / "target", target_scope)
    submission = signal_submission(
        catalog_engine,
        tmp_path / "claim",
        {**SIGNALS[6], "target_document_id": document_id, "target_revision_id": revision_id},
        scope=claim_scope,
    )
    key = "r07-visible-target-" + uuid4().hex
    assert publish_submission(catalog_engine, submission, key) == publish_submission(
        catalog_engine, submission, key
    )
