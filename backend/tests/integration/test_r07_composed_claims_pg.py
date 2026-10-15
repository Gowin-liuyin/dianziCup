"""Multiple fixed source assertions preserve scoped evidence and publication replay."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import publish_submission
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r07_signal_claim_values_pg import signal_submission
from tests.unit.test_r07_enrichment_contracts import SIGNALS

from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.domain.values import VisibilityScope
from ai_intel.knowledge.persistence import (
    ClaimSubmission,
    KnowledgePublicationError,
    SupportingSource,
)
from ai_intel.knowledge.persistence_models import claim_assertions, claim_evidence, claims

pytestmark = pytest.mark.real_pg


def composition(engine, tmp_path, *, target_scope=None):
    first = signal_submission(engine, tmp_path / "primary", SIGNALS[3])
    second = signal_submission(engine, tmp_path / "secondary", SIGNALS[3], scope=target_scope)
    additional = SupportingSource(
        source_id=second.source_id,
        revision_id=second.revision_id,
        json_path=second.json_path,
    )
    return first.model_copy(
        update={
            "additional_sources": (additional,),
            "evidence_links": first.evidence_links + second.evidence_links,
        }
    )


def test_composed_claim_keeps_both_revision_assertions_and_evidence_on_replay(
    catalog_engine, tmp_path
):
    submission = composition(catalog_engine, tmp_path)
    key = "composed-fixture-" + uuid4().hex
    first = publish_submission(catalog_engine, submission, key)
    assert publish_submission(catalog_engine, submission, key) == first
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(claims)) == 1
        assert set(session.scalars(select(claim_assertions.c.revision_id))) == {
            submission.revision_id.value,
            submission.additional_sources[0].revision_id.value,
        }
        assert session.scalar(select(func.count()).select_from(claim_evidence)) == 2


def test_undeclared_secondary_evidence_cannot_be_published(catalog_engine, tmp_path):
    submission = composition(catalog_engine, tmp_path).model_copy(update={"additional_sources": ()})
    with pytest.raises(CrossTenantAccessError):
        publish_submission(catalog_engine, submission)
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(claims)) == 0


def test_private_secondary_cannot_widen_public_composed_visibility(catalog_engine, tmp_path):
    submission = composition(
        catalog_engine,
        tmp_path,
        target_scope=VisibilityScope(visibility="tenant", tenant_id="fixture-owner"),
    )
    with pytest.raises((CrossTenantAccessError, KnowledgePublicationError)):
        publish_submission(catalog_engine, submission)
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(claim_assertions)) == 0


def test_declared_but_unused_secondary_source_is_rejected(catalog_engine, tmp_path):
    submission = composition(catalog_engine, tmp_path)
    submission = submission.model_copy(update={"evidence_links": submission.evidence_links[:1]})
    with pytest.raises(KnowledgePublicationError, match="every declared source"):
        publish_submission(catalog_engine, submission)


def test_repeated_or_legacy_additional_revision_is_revalidated(catalog_engine, tmp_path):
    submission = composition(catalog_engine, tmp_path)
    repeated = submission.additional_sources[0].model_copy(
        update={"revision_id": submission.revision_id}
    )
    with pytest.raises(ValidationError):
        ClaimSubmission.model_validate(
            submission.model_copy(update={"additional_sources": (repeated,)}).model_dump()
        )
    legacy = submission.record.model_copy(
        update={"schema_version": 2, "predicate": "affected_by", "object_value": "fixture"}
    )
    with pytest.raises(ValidationError):
        ClaimSubmission.model_validate(
            submission.model_copy(update={"record": legacy}).model_dump()
        )


def test_empty_additional_sources_preserve_old_serialized_payload(catalog_engine, tmp_path):
    submission = signal_submission(catalog_engine, tmp_path, SIGNALS[3])
    assert "additional_sources" not in submission.model_dump(mode="json")
    explicit = ClaimSubmission.model_validate({**submission.model_dump(), "additional_sources": ()})
    assert explicit.model_dump(mode="json") == submission.model_dump(mode="json")
