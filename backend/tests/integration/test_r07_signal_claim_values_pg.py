"""Typed v3 hypotheses roundtrip in real UUID-isolated PG without becoming supported facts."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import prepared_submission, publish_submission, publisher_scope
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from tests.unit.test_r07_enrichment_contracts import SIGNALS

from ai_intel.api.knowledge_contracts import ClaimSummary
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import VisibilityScope
from ai_intel.knowledge.persistence import KnowledgePublicationError, KnowledgeRepository
from ai_intel.knowledge.persistence_models import claims

pytestmark = pytest.mark.real_pg


def signal_submission(engine, tmp_path, value, *, scope=None):
    template = prepared_submission(
        engine,
        tmp_path,
        scope=scope,
        predicate=value["kind"],
        value="Synthetic candidate only",
        claim_status="unverified",
        claim_origin="model_hypothesis",
        condition="unknown",
        scoring_authority=value.get("authority", ""),
    )
    record = ClaimRecord.model_validate(
        {
            **template.record.model_dump(),
            "schema_version": 3,
            "object_value": value,
        }
    )
    return template.model_copy(
        update={
            "record": record,
            "evidence_links": tuple(
                link.model_copy(
                    update={
                        "support_kind": "context",
                        "validation_status": "unverified",
                    }
                )
                for link in template.evidence_links
            ),
        }
    )


@pytest.mark.parametrize("value", SIGNALS)
def test_typed_hypothesis_survives_new_session_and_replay_without_claim_promotion(
    catalog_engine, tmp_path, value
):
    submission = signal_submission(catalog_engine, tmp_path, value)
    key = "r07-signal-fixture-" + uuid4().hex
    first = publish_submission(catalog_engine, submission, key)
    second = publish_submission(catalog_engine, submission, key)
    assert second == first
    with Session(catalog_engine) as session:
        stored = KnowledgeRepository(session, publisher_scope(submission.record.scope)).get_claim(
            submission.record.claim_id.value
        )
        assert stored == submission.record and stored.schema_version == 3
        assert stored.claim_status.value == "unverified"
        assert stored.claim_origin.value == "model_hypothesis"
        assert stored.condition_value.value == "unknown"
        assert session.scalar(select(func.count()).select_from(claims)) == 1
        row = session.execute(select(claims.c.value_kind, claims.c.object_json)).one()
        assert row.value_kind == value["kind"]
        assert row.object_json["kind"] == value["kind"]


def test_large_typed_value_has_explicit_bounded_display_without_losing_full_structure(
    catalog_engine, tmp_path
):
    value = {**SIGNALS[5], "limitations": ["边界" * 700] * 4}
    submission = signal_submission(catalog_engine, tmp_path, value)
    assert len(submission.record.object_value.model_dump_json()) > 4000
    publish_submission(catalog_engine, submission)
    with Session(catalog_engine) as session:
        row = session.execute(select(claims)).mappings().one()
        summary = ClaimSummary(
            claim_id=row["claim_id"],
            predicate=row["predicate"],
            display_value=row["object_value"],
            origin=row["claim_origin"],
            status=row["claim_status"],
            source_revision_id=row["source_revision_id"],
            evidence_ids=(),
        )
        assert len(summary.display_value) == 4000
        assert summary.display_value.endswith("完整结构已保存，请查看原文证据）")
        restored = KnowledgeRepository(session, publisher_scope(submission.record.scope)).get_claim(
            submission.record.claim_id.value
        )
        assert restored.object_value == submission.record.object_value
        assert restored.object_value.limitations == tuple(value["limitations"])


def test_cvss_signal_authority_mismatch_cannot_write_even_an_unverified_claim(
    catalog_engine, tmp_path
):
    submission = signal_submission(catalog_engine, tmp_path, SIGNALS[0])
    with pytest.raises(KnowledgePublicationError, match="authority"):
        publish_submission(
            catalog_engine, submission.model_copy(update={"scoring_authority": "other"})
        )
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(claims)) == 0


def test_viewer_cannot_publish_typed_public_signal(catalog_engine, tmp_path):
    submission = signal_submission(catalog_engine, tmp_path, SIGNALS[1])
    viewer = AccessScope.for_authenticated_user("fixture-viewer", "fixture-tenant", Role.VIEWER)
    with (
        Session(catalog_engine) as session,
        session.begin(),
        pytest.raises(PermissionDeniedError),
    ):
        KnowledgeRepository(session, viewer).publish(
            "denied-r07",
            submission.record.scope,
            (submission,),
            created_at=submission.record.asserted_at,
        )


def test_other_tenant_cannot_read_typed_signal_or_source_reference(catalog_engine, tmp_path):
    submission = signal_submission(
        catalog_engine,
        tmp_path,
        SIGNALS[1],
        scope=VisibilityScope(visibility="tenant", tenant_id="fixture-owner"),
    )
    publish_submission(catalog_engine, submission)
    other = AccessScope.for_authenticated_user("fixture-other", "fixture-other", Role.TENANT_ADMIN)
    with Session(catalog_engine) as session:
        repository = KnowledgeRepository(session, other)
        with pytest.raises(CrossTenantAccessError):
            repository.get_claim(submission.record.claim_id.value)
        with pytest.raises(CrossTenantAccessError):
            repository.get_evidence(submission.evidence_links[0].evidence_id.value)
