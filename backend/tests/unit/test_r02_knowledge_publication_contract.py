"""显式isolated fixture验证发布边界/类型与SQL授权, 不计PG或live。"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.knowledge.event_linking import (
    EventIdentifier,
    EventLinkingError,
    EventRepository,
    EventSubmission,
)
from ai_intel.knowledge.persistence import (
    ClaimSubmission,
    EvidenceLink,
    KnowledgePublicationError,
    KnowledgeRepository,
    _claim_from_row,
    _receipt_from_row,
    find_prior_publication,
    knowledge_scope_key,
    publication_payload_digest,
)

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def fixture_submission(scope=None, **changes):
    scope = scope or VisibilityScope(visibility="public")
    record = {
        "claim_id": {"value": str(uuid4())},
        "subject": "test component",
        "predicate": "affects",
        "object_value": "synthetic affected",
        "claim_status": "supported",
        "claim_origin": "source_explicit",
        "condition_value": "unknown",
        "freshness": "unknown",
        "asserted_at": NOW,
        "scope": scope.model_dump(),
        **changes,
    }
    return ClaimSubmission(
        record=ClaimRecord.model_validate(record),
        source_id=Identifier(value=str(uuid4())),
        revision_id=Identifier(value=str(uuid4())),
        json_path="$.affected",
        evidence_links=(
            EvidenceLink(
                evidence_id=Identifier(value=str(uuid4())),
                support_kind="supports",
                validation_status="validated",
            ),
        ),
    )


def fixture_evidence(submission, **changes):
    return {
        "evidence_id": submission.evidence_links[0].evidence_id.value,
        "revision_id": submission.revision_id.value,
        "visibility": submission.record.scope.visibility,
        "tenant_id": submission.record.scope.tenant_id,
        "coordinate_version": "fulltext_unicode_v1",
        "verified_at": NOW,
        "supports_claim": True,
        "block_id": str(uuid4()),
        "start_offset": 100,
        "end_offset": 110,
        "quote_sha256": None,
        **changes,
    }


def fixture_row(submission, **changes):
    return {
        "claim_id": submission.record.claim_id.value,
        "subject": "test component",
        "predicate": "affects",
        "object_value": "synthetic affected",
        "object_json": None,
        "schema_version": 2,
        "provenance_status": "source_verified",
        "claim_status": "supported",
        "claim_origin": "source_explicit",
        "condition_value": "unknown",
        "freshness": "unknown",
        "asserted_at": NOW,
        "observed_at": None,
        "visibility": submission.record.scope.visibility,
        "tenant_id": submission.record.scope.tenant_id,
        **changes,
    }


def test_scope_key_and_digest_are_stable_without_mutating_inputs():
    assert knowledge_scope_key(VisibilityScope(visibility="public")) == "public"
    assert (
        knowledge_scope_key(VisibilityScope(visibility="tenant", tenant_id="test-a"))
        == "tenant:test-a"
    )
    assert publication_payload_digest({"x": 1, "y": 2}) == publication_payload_digest(
        {"y": 2, "x": 1}
    )
    assert publication_payload_digest({"x": 1}) != publication_payload_digest({"x": 2})


def test_typed_score_and_legacy_unknown_roundtrip_preserve_meaning():
    submission = fixture_submission()
    typed = _claim_from_row(
        fixture_row(
            submission,
            predicate="cvss_score",
            object_json={"kind": "score", "score": 8.1, "authority": "CNA", "vector": None},
        )
    )
    assert typed.object_value.score == 8.1 and typed.object_value.authority == "CNA"
    legacy = _claim_from_row(fixture_row(submission, schema_version=1, claim_status="unverified"))
    assert legacy.schema_version == 1 and legacy.condition_value.value == "unknown"
    assert legacy.object_value == "synthetic affected"


def test_receipt_reconstruction_preserves_all_replay_identifiers():
    identifiers = [str(uuid4()) for _ in range(5)]
    row = {
        "receipt_id": identifiers[0],
        "scope_key": "public",
        "publication_key": "synthetic input",
        "payload_sha256": "synthetic digest",
        "claim_ids": [identifiers[1]],
        "epoch": 2,
        "job_id": identifiers[2],
        "outbox_id": identifiers[3],
        "change_id": identifiers[4],
        "created_at": NOW,
    }
    receipt = _receipt_from_row(row)
    assert receipt.claim_ids == (identifiers[1],)
    assert receipt.job_id == identifiers[2] and receipt.outbox_id == identifiers[3]
    assert receipt.change_id == identifiers[4] and receipt.epoch == 2


@pytest.mark.parametrize(
    "role,tenant,target_scope,error",
    [
        (Role.VIEWER, "a", VisibilityScope(visibility="public"), PermissionDeniedError),
        (
            Role.VIEWER,
            "a",
            VisibilityScope(visibility="tenant", tenant_id="a"),
            PermissionDeniedError,
        ),
        (
            Role.TENANT_ADMIN,
            "a",
            VisibilityScope(visibility="tenant", tenant_id="b"),
            CrossTenantAccessError,
        ),
    ],
)
def test_write_access_fails_before_database_query(role, tenant, target_scope, error):
    with Session() as session, patch.object(session, "execute") as execute:
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", tenant, role)
        )
        with pytest.raises(error):
            repo.publish("key", target_scope, (fixture_submission(target_scope),), created_at=NOW)
        execute.assert_not_called()


def test_sql_visibility_excludes_tenant_for_viewer_and_admin_without_tenant():
    for role, tenant in ((Role.VIEWER, "a"), (Role.SYSTEM_ADMIN, None)):
        with Session() as session:
            repo = KnowledgeRepository(
                session, AccessScope.for_authenticated_user("test", tenant, role)
            )
            predicate = str(
                repo._visible_claims().compile(
                    dialect=dialect(), compile_kwargs={"literal_binds": True}
                )
            )
            assert "tenant_id IS NULL" in predicate and " OR " not in predicate
    with Session() as session:
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", "a", Role.ANALYST)
        )
        predicate = str(
            repo._visible_claims().compile(
                dialect=dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert " OR " in predicate and "tenant_id = 'a'" in predicate


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"claim_origin": "model_hypothesis"}, "hypothesis"),
        ({"schema_version": 1}, "legacy"),
        ({"claim_status": "withdrawn"}, "initial status"),
    ],
)
def test_candidate_states_cannot_skip_publication_validation(changes, reason):
    submission = fixture_submission(**changes)
    with Session() as session, patch.object(session, "execute") as execute:
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        with pytest.raises(KnowledgePublicationError, match=reason):
            repo._validate_submission(submission, submission.record.scope)
        execute.assert_not_called()


@pytest.mark.parametrize(
    "evidence_changes,reason",
    [
        ({"coordinate_version": "legacy_unverified"}, "legacy"),
        ({"verified_at": None}, "unverified"),
        ({"supports_claim": False}, "support"),
    ],
)
def test_valid_quote_alone_does_not_make_supported_claim(evidence_changes, reason):
    submission = fixture_submission()
    result = MagicMock()
    result.first.return_value = ("public", None)
    result.mappings.return_value.first.return_value = fixture_evidence(
        submission, **evidence_changes
    )
    with Session() as session, patch.object(session, "execute", return_value=result):
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        with pytest.raises(KnowledgePublicationError, match=reason):
            repo._validate_submission(submission, submission.record.scope)


def test_missing_source_or_evidence_never_falls_back_to_supported():
    submission = fixture_submission()
    result = MagicMock()
    with Session() as session, patch.object(session, "execute", return_value=result):
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        result.first.return_value = None
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            repo._validate_submission(submission, submission.record.scope)
        result.first.return_value = ("public", None)
        result.mappings.return_value.first.return_value = None
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            repo._validate_submission(submission, submission.record.scope)


def test_current_read_and_export_use_permission_predicate_with_bounded_limit():
    submission = fixture_submission()
    result = MagicMock()
    result.mappings.return_value.all.return_value = [fixture_row(submission)]
    with Session() as session, patch.object(session, "execute", return_value=result) as execute:
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", "a", Role.ANALYST)
        )
        current = repo.list_current_claims(candidate_ids=(submission.record.claim_id.value,))
        assert current[0].object_value == "synthetic affected"
        sql = str(
            execute.call_args.args[0].compile(
                dialect=dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "tenant_id = 'a'" in sql and "is_current IS true" in sql
        assert "stale" in sql and "supported" in sql
        assert "synthetic affected" in repo.export_current_claims()
        with pytest.raises(KnowledgePublicationError, match="limit"):
            repo.list_current_claims(limit=1001)


def test_known_at_selects_history_state_and_missing_object_is_uniform():
    submission = fixture_submission()
    result = MagicMock()
    result.mappings.return_value.first.return_value = fixture_row(
        submission, claim_status="superseded"
    )
    result.scalar_one_or_none.return_value = "supported"
    with Session() as session, patch.object(session, "execute", return_value=result):
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        assert (
            repo.get_claim(submission.record.claim_id.value, known_at=NOW).claim_status.value
            == "supported"
        )
        with pytest.raises(KnowledgePublicationError, match="aware"):
            repo.get_claim(submission.record.claim_id.value, known_at=NOW.replace(tzinfo=None))
        result.mappings.return_value.first.return_value = None
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            repo.get_claim(submission.record.claim_id.value)


@pytest.mark.parametrize("coordinate_version", ["fulltext_unicode_v1", "legacy_unverified"])
def test_evidence_read_preserves_unicode_offsets_and_legacy_verification_boundary(
    coordinate_version,
):
    submission = fixture_submission()
    row = fixture_evidence(submission, coordinate_version=coordinate_version)
    row.update(
        document_id=str(uuid4()), locator="paragraph", quote="explicit source", supports_claim=True
    )
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    with Session() as session, patch.object(session, "execute", return_value=result):
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", "a", Role.ANALYST)
        )
        stored = repo.get_evidence(row["evidence_id"])
        assert stored.record.span.start_offset == 100
        assert stored.revision_id.value == submission.revision_id.value
        assert stored.verified_at == (NOW if coordinate_version == "fulltext_unicode_v1" else None)
        result.mappings.return_value.first.return_value = None
        with pytest.raises(CrossTenantAccessError):
            repo.get_evidence(row["evidence_id"])


def test_publication_replay_returns_same_identifiers_and_conflict_does_not_overwrite():
    from ai_intel.infrastructure.outbox import IdempotencyConflictError

    result = MagicMock()
    with Session() as session, patch.object(session, "execute", return_value=result):
        result.mappings.return_value.first.return_value = None
        assert find_prior_publication(session, "public", "key", "digest") is None
        row = {
            "receipt_id": str(uuid4()),
            "scope_key": "public",
            "publication_key": "key",
            "payload_sha256": "digest",
            "claim_ids": [str(uuid4())],
            "epoch": 1,
            "job_id": str(uuid4()),
            "outbox_id": str(uuid4()),
            "change_id": str(uuid4()),
            "created_at": NOW,
        }
        result.mappings.return_value.first.return_value = row
        assert (
            find_prior_publication(session, "public", "key", "digest").receipt_id
            == row["receipt_id"]
        )
        with pytest.raises(IdempotencyConflictError):
            find_prior_publication(session, "public", "key", "different")


def test_multi_cve_event_is_rejected_before_persistence():
    with pytest.raises(ValueError, match="distinct events"):
        EventSubmission(
            event_id=Identifier(value=str(uuid4())),
            event_type="vulnerability",
            title="synthetic article",
            scope=VisibilityScope(visibility="public"),
            source_revision_ids=(Identifier(value=str(uuid4())),),
            external_ids=(
                EventIdentifier(id_type="cve", id_value="CVE-2026-0001"),
                EventIdentifier(id_type="cve", id_value="CVE-2026-0002"),
            ),
        )


def test_event_read_sql_does_not_give_viewer_private_access():
    row = {
        "event_id": str(uuid4()),
        "scope_key": "public",
        "visibility": "public",
        "tenant_id": None,
        "status": "active",
        "event_type": "research_risk",
        "business_version": 1,
    }
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    with Session() as session, patch.object(session, "execute", return_value=result) as execute:
        repo = EventRepository(
            session, AccessScope.for_authenticated_user("test", "a", Role.VIEWER)
        )
        assert repo._visible_event(row["event_id"])["event_id"] == row["event_id"]
        sql = str(
            execute.call_args.args[0].compile(
                dialect=dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "tenant_id IS NULL" in sql and " OR " not in sql
        result.mappings.return_value.first.return_value = None
        with pytest.raises(CrossTenantAccessError):
            repo._visible_event(row["event_id"])


def test_event_scope_permission_and_invalid_empty_publication_fail_without_io():
    with Session() as session, patch.object(session, "execute") as execute:
        viewer = EventRepository(
            session, AccessScope.for_authenticated_user("test", "a", Role.VIEWER)
        )
        with pytest.raises(PermissionDeniedError):
            viewer.publish_events("key", VisibilityScope(visibility="public"), (), NOW)
        with pytest.raises(PermissionDeniedError):
            viewer.publish_events(
                "key", VisibilityScope(visibility="tenant", tenant_id="a"), (), NOW
            )
        admin = EventRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        with pytest.raises(EventLinkingError, match="publication requires"):
            admin.publish_events("", VisibilityScope(visibility="public"), (), NOW)
        execute.assert_not_called()


@pytest.mark.parametrize("invalid_input", ["multiple_cves", "missing_sources", "long_key"])
def test_event_publication_revalidates_copied_dto_and_bounded_key_before_io(invalid_input):
    submission = EventSubmission(
        event_id=Identifier(value=str(uuid4())),
        event_type="vulnerability",
        title="synthetic boundary case",
        scope=VisibilityScope(visibility="public"),
        source_revision_ids=(Identifier(value=str(uuid4())),),
    )
    key = "event-boundary"
    if invalid_input == "multiple_cves":
        submission = submission.model_copy(
            update={
                "external_ids": (
                    EventIdentifier(id_type="cve", id_value="CVE-2026-0001"),
                    EventIdentifier(id_type="cve", id_value="CVE-2026-0002"),
                )
            }
        )
    elif invalid_input == "missing_sources":
        submission = submission.model_copy(update={"source_revision_ids": ()})
    else:
        key = "k" * 501
    with Session() as session, patch.object(session, "execute") as execute:
        repository = EventRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        with pytest.raises(ValueError if invalid_input != "long_key" else EventLinkingError):
            repository.publish_events(key, submission.scope, (submission,), NOW)
        execute.assert_not_called()


def test_same_event_merge_is_rejected_before_modification():
    row = {
        "event_id": str(uuid4()),
        "scope_key": "public",
        "visibility": "public",
        "tenant_id": None,
        "status": "active",
        "event_type": "research_risk",
        "business_version": 1,
    }
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    with Session() as session, patch.object(session, "execute", return_value=result) as execute:
        repo = EventRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        with pytest.raises(EventLinkingError, match="distinct"):
            repo.merge_events("key", row["event_id"], row["event_id"], "reason", NOW)
        assert len(execute.call_args_list) == 2


def test_score_authority_mismatch_cannot_enter_database():
    submission = fixture_submission(
        predicate="cvss_score", object_value={"kind": "score", "score": 8.1, "authority": "CNA"}
    )
    with Session() as session, patch.object(session, "execute") as execute:
        repo = KnowledgeRepository(
            session, AccessScope.for_authenticated_user("test", None, Role.SYSTEM_ADMIN)
        )
        with pytest.raises(KnowledgePublicationError, match="authority"):
            repo._validate_submission(submission, submission.record.scope)
        execute.assert_not_called()


def test_legacy_supported_sql_status_is_not_exposed_as_verified_fact():
    submission = fixture_submission()
    row = fixture_row(
        submission,
        schema_version=1,
        claim_status="supported",
        provenance_status="legacy_unverified",
    )
    record = _claim_from_row(row)
    assert record.claim_status.value == "unverified"
    assert row["claim_status"] == "supported"
