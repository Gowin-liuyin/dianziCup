"""独立审查发现的关系/事件边界回归；只访问有标识的真实测试PG。"""

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from test_r02_knowledge_revisions import (
    NOW,
    prepared_submission,
    publish_submission,
    publisher_scope,
)

from ai_intel.domain.records import ScoreValue, VersionRangeValue
from ai_intel.domain.values import Identifier
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.event_linking import (
    EventIdentifier,
    EventLinkingError,
    EventRepository,
    EventSubmission,
)
from ai_intel.knowledge.models import document_revisions
from ai_intel.knowledge.persistence import ClaimRelation, ClaimSubmission, KnowledgePublicationError
from ai_intel.knowledge.persistence import KnowledgeRepository as Repository
from ai_intel.knowledge.persistence_models import event_external_ids
from ai_intel.knowledge.revisions import (
    add_text_block,
    attach_evidence_span,
    save_document_revision,
)

pytestmark = pytest.mark.real_pg


def test_existing_event_rejects_second_cve_without_changing_original(
    migrated_engine: Engine, tmp_path: Path
) -> None:
    source = prepared_submission(migrated_engine, tmp_path)
    original_id = "CVE-2026-" + str(int(uuid4().hex[:8], 16))
    other_id = "CVE-2026-" + str(int(uuid4().hex[:8], 16))
    first = EventSubmission(
        event_id=Identifier(value=str(uuid4())),
        event_type="vulnerability",
        title="identity regression",
        scope=source.record.scope,
        external_ids=(EventIdentifier(id_type="cve", id_value=original_id),),
        source_revision_ids=(source.revision_id,),
    )
    changed = first.model_copy(
        update={"external_ids": (EventIdentifier(id_type="cve", id_value=other_id),)}
    )
    with Session(migrated_engine) as session, session.begin():
        repository = EventRepository(session, publisher_scope(first.scope))
        repository.publish_events(str(uuid4()), first.scope, (first,), NOW)
        with pytest.raises(EventLinkingError):
            repository.publish_events(str(uuid4()), first.scope, (changed,), NOW)
        identifiers = (
            session.execute(
                select(event_external_ids.c.id_value).where(
                    event_external_ids.c.event_id == first.event_id.value
                )
            )
            .scalars()
            .all()
        )
        assert identifiers == [original_id]


@pytest.mark.parametrize("boundary", ["branch", "authority", "ecosystem"])
def test_supersede_keeps_independent_assertions(
    migrated_engine: Engine, tmp_path: Path, boundary: str
) -> None:
    if boundary == "authority":
        original_value = ScoreValue(score=5, authority="vendor-A")
        replacement_value = ScoreValue(score=9, authority="vendor-B")
        predicate = "cvss_score"
        original_authority, replacement_authority = "vendor-A", "vendor-B"
    else:
        original_value = VersionRangeValue(ecosystem="pypi", expression="<1.5", branch="1.x")
        replacement_value = VersionRangeValue(
            ecosystem="npm" if boundary == "ecosystem" else "pypi",
            expression="<2.5",
            branch="1.x" if boundary == "ecosystem" else "2.x",
        )
        predicate = "affected_versions"
        original_authority = replacement_authority = ""
    first = prepared_submission(
        migrated_engine,
        tmp_path,
        value=original_value,
        predicate=predicate,
        scoring_authority=original_authority,
    )
    publish_submission(migrated_engine, first)
    at = NOW + timedelta(seconds=1)
    with migrated_engine.begin() as connection:
        document_id = connection.execute(
            select(document_revisions.c.document_id).where(
                document_revisions.c.revision_id == first.revision_id.value
            )
        ).scalar_one()
        revision = save_document_revision(
            connection,
            ContentStore(tmp_path / "objects"),
            document_id,
            b"later independent field",
            "public",
            None,
            at,
        )
        block_id = add_text_block(connection, revision.revision_id, 1, 100, 107, "changed")
        evidence_id = attach_evidence_span(
            connection,
            revision.revision_id,
            100,
            107,
            "paragraph",
            "changed",
            True,
            "public",
            None,
            at,
            block_id=block_id,
            verified_at=at,
        )
    replacement = ClaimSubmission.model_validate(
        {
            **first.model_dump(),
            "record": first.record.model_copy(
                update={
                    "claim_id": Identifier(value=str(uuid4())),
                    "object_value": replacement_value,
                }
            ).model_dump(),
            "scoring_authority": replacement_authority,
            "revision_id": {"value": revision.revision_id},
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
        left_claim_id=first.record.claim_id,
        right_claim_id=replacement.record.claim_id,
        relation_type="supersedes",
        reason="independent field must remain parallel",
    )
    with Session(migrated_engine) as session, session.begin():
        repository = Repository(session, publisher_scope(first.record.scope))
        with pytest.raises(KnowledgePublicationError):
            repository.publish(
                str(uuid4()),
                first.record.scope,
                (replacement,),
                relations=(relation,),
                created_at=NOW + timedelta(seconds=2),
            )
        assert repository.get_claim(first.record.claim_id.value).claim_status.value == "supported"
        assert [
            item.claim_id.value
            for item in repository.list_current_claims(
                candidate_ids=(first.record.claim_id.value, replacement.record.claim_id.value)
            )
        ] == [first.record.claim_id.value]


def test_dispute_cannot_promote_model_hypothesis(migrated_engine: Engine, tmp_path: Path) -> None:
    model_claim = prepared_submission(
        migrated_engine,
        tmp_path,
        claim_origin="model_hypothesis",
        claim_status="unverified",
        condition="true",
    )
    factual_claim = prepared_submission(migrated_engine, tmp_path, condition="false")
    factual_claim = ClaimSubmission.model_validate(
        {
            **factual_claim.model_dump(),
            "record": factual_claim.record.model_copy(
                update={"subject": model_claim.record.subject}
            ).model_dump(),
        }
    )
    relation = ClaimRelation(
        left_claim_id=model_claim.record.claim_id,
        right_claim_id=factual_claim.record.claim_id,
        relation_type="disputed",
        reason="model output is not a verified fact",
    )
    with Session(migrated_engine) as session, session.begin():
        repository = Repository(session, publisher_scope(model_claim.record.scope))
        with pytest.raises(KnowledgePublicationError):
            repository.publish(
                str(uuid4()),
                model_claim.record.scope,
                (model_claim, factual_claim),
                relations=(relation,),
                created_at=NOW,
            )
        assert (
            repository.list_current_claims(candidate_ids=(model_claim.record.claim_id.value,)) == ()
        )
