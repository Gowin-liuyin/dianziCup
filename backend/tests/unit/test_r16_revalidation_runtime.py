"""Isolated fixtures check runtime contracts without pretending to exercise PostgreSQL."""

import base64
import hmac
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.engine import Engine
from tests.unit.test_r16_assessment_candidates import cursor
from tests.unit.test_r18_actor_references import NOW, TOKEN, connection_for, session_row

from ai_intel.api.actor_references import (
    actor_reference_from_payload,
    actor_reference_payload,
    create_actor_reference,
)
from ai_intel.api.credentials import SessionCredential
from ai_intel.domain.access import PermissionDeniedError
from ai_intel.revalidation.candidate_contracts import AssessmentChangeCandidate
from ai_intel.revalidation.candidates import (
    CandidateDiscoveryError,
    CandidateDiscoveryService,
    _decode_cursor,
    _encode_cursor,
)
from ai_intel.revalidation.execution_contracts import (
    ReassessmentRequest,
    RevalidationChangeRequest,
    RevalidationPlan,
)
from ai_intel.revalidation.persistence_models import revalidation_job_bindings
from ai_intel.revalidation.runtime_policy import make_revalidation_job_handlers
from ai_intel.revalidation.service import (
    RevalidationError,
    RevalidationService,
    _require_remaining,
    unique_current_assets,
)
from ai_intel.workers.executor import DetachedJobHandler, JobExecutionContext

KEY = SecretStr("01" * 32)


def reference():
    return create_actor_reference(connection_for(session_row()), SessionCredential(TOKEN), NOW)


def plan_payload():
    return dict(
        change_id="fixture-change",
        actor_user_id="fixture-user",
        tenant_id="fixture-tenant",
        permission_version=1,
        permissions_digest="a" * 64,
        requested_epoch=1,
        target_epoch=2,
        scope_epoch_map={"public": 2, "tenant:fixture-tenant": None},
        assessment_created_before=NOW,
        targets=(),
        candidate_count=0,
        planning_status="complete",
        incomplete_reasons=(),
    )


def child_payload():
    return dict(
        change_id="fixture-change",
        target_epoch=2,
        asset_id="fixture-asset",
        asset_snapshot_id="fixture-snapshot",
        rule_id="fixture-rule",
        rule_version=1,
    )


def test_history_rows_collapse_to_one_current_asset_without_losing_other_assets():
    candidates = tuple(
        AssessmentChangeCandidate(
            asset_id=asset,
            asset_snapshot_id=snapshot,
            assessment_id=assessment,
            reasons=("old_dependency",),
        )
        for asset, snapshot, assessment in (
            ("b", "snapshot-b", None),
            ("a", "snapshot-a", "old-1"),
            ("a", "snapshot-a", "old-2"),
        )
    )
    assert unique_current_assets(candidates) == (("a", "snapshot-a"), ("b", "snapshot-b"))


def test_conflicting_current_snapshots_cannot_be_silently_chosen():
    candidates = tuple(
        AssessmentChangeCandidate(
            asset_id="fixture-asset", asset_snapshot_id=snapshot, reasons=("scope_watch",)
        )
        for snapshot in ("older", "newer")
    )
    with pytest.raises(RevalidationError, match="candidate_snapshot_changed"):
        unique_current_assets(candidates)


@pytest.mark.parametrize(
    "updates",
    [
        dict(planning_status="complete", incomplete_reasons=("pending",)),
        dict(planning_status="partial"),
        dict(target_epoch=0),
        dict(scope_epoch_map={}),
        dict(scope_epoch_map={"public": 2, "tenant:other": None}),
        dict(scope_epoch_map={"public": -1, "tenant:fixture-tenant": None}),
        dict(permission_version=True),
        dict(actor_role="system_admin"),
        dict(status="reassessed"),
    ],
)
def test_invalid_plan_never_claims_complete_or_changes_authenticated_scope(updates):
    with pytest.raises(ValidationError):
        RevalidationPlan.model_validate({**plan_payload(), **updates})


def test_partial_plan_exposes_a_remaining_candidate_cursor():
    plan = RevalidationPlan.model_validate(
        {
            **plan_payload(),
            "planning_status": "partial",
            "incomplete_reasons": ("candidate_pages_remaining",),
            "continuation": "signed-fixture-cursor",
        }
    )
    assert plan.continuation and not plan.targets
    assert not hasattr(plan, "assessment_status")


@pytest.mark.parametrize(
    "updates",
    [
        dict(tenant_id="other"),
        dict(user_id="spoofed"),
        dict(actor_reference={}),
        dict(job_type="shell"),
        dict(rule_version=0),
        dict(target_epoch=True),
    ],
)
def test_child_identity_and_tool_spoofing_fail_at_payload_boundary(updates):
    with pytest.raises(ValidationError):
        ReassessmentRequest.model_validate({**child_payload(), **updates})


@pytest.mark.parametrize("pages,children", [(0, 1), (101, 1), (1, 0), (1, 1001), (True, 1)])
def test_parent_has_fixed_positive_page_and_child_budgets(pages, children):
    with pytest.raises(ValidationError):
        RevalidationChangeRequest(
            change_id="fixture-change",
            target_epoch=1,
            assessment_created_before=NOW,
            remaining_pages=pages,
            remaining_children=children,
        )


def test_frozen_history_time_survives_signed_cursor_round_trip():
    frozen = cursor().model_copy(update={"assessment_created_before": NOW})
    key = bytes.fromhex(KEY.get_secret_value())
    restored = _decode_cursor(_encode_cursor(frozen, key), key)
    assert restored.assessment_created_before == NOW
    assert cursor().assessment_created_before is None


def test_pre_cutoff_signed_cursor_bytes_still_decode_with_default_none():
    old = cursor().model_dump(mode="json")
    old.pop("assessment_created_before")
    payload = json.dumps(old, separators=(",", ":")).encode()
    key = bytes.fromhex(KEY.get_secret_value())
    encoded = base64.urlsafe_b64encode(hmac.digest(key, payload, "sha256") + payload).decode()
    restored = _decode_cursor(encoded, key)
    assert restored.assessment_created_before is None
    assert restored.after_asset_id == "fixture-asset"


def test_boolean_scope_epoch_is_not_silently_coerced_to_an_integer():
    with pytest.raises(ValidationError):
        RevalidationPlan.model_validate(
            {**plan_payload(), "scope_epoch_map": {"public": True, "tenant:fixture-tenant": None}}
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"frozen_scope_epoch_map": {"public": 2}},
        {"frozen_rule_scope_fingerprint": "a" * 64},
        {"frozen_scope_epoch_map": {}, "frozen_rule_scope_fingerprint": "a" * 64},
        {
            "frozen_scope_epoch_map": {"public": True},
            "frozen_rule_scope_fingerprint": "a" * 64,
        },
        {
            "frozen_scope_epoch_map": {"public": 2},
            "frozen_rule_scope_fingerprint": "not-a-digest",
        },
    ],
)
def test_rule_continuation_requires_paired_strict_frozen_context(updates):
    with pytest.raises(ValidationError):
        RevalidationChangeRequest.model_validate(
            {
                "change_id": "fixture-change",
                "target_epoch": 2,
                "assessment_created_before": NOW,
                "rule_after_id": "fixture-rule",
                **updates,
            }
        )


def test_legacy_parent_payload_still_decodes_without_new_frozen_fields():
    request = RevalidationChangeRequest.model_validate(
        {
            "change_id": "fixture-change",
            "target_epoch": 2,
            "assessment_created_before": NOW,
            "rule_after_id": "fixture-rule",
        }
    )
    assert request.frozen_scope_epoch_map is None
    assert request.frozen_rule_scope_fingerprint is None
    assert request.remaining_pages == 100 and request.remaining_children == 1000


@pytest.mark.parametrize(
    "cutoff", [NOW.replace(tzinfo=None), datetime.now(UTC) + timedelta(days=1)]
)
def test_invalid_cutoff_fails_before_database_access(cutoff):
    engine = MagicMock(spec=Engine)
    service = CandidateDiscoveryService(engine, "isolated-cookie", KEY)
    with pytest.raises(CandidateDiscoveryError, match="history_cutoff_invalid"):
        service.discover("fixture-change", 1, assessment_created_before=cutoff)
    engine.connect.assert_not_called()


def test_runtime_accepts_only_server_constructed_references():
    with pytest.raises(TypeError, match="internal actor"):
        RevalidationService(MagicMock(spec=Engine), "cookie", MagicMock(), KEY)


def test_readonly_api_key_cannot_create_revalidation_effects():
    payload = actor_reference_payload(reference())
    payload.update(
        credential_kind="api_key", session_hash=None, key_id="fixture-key", credential_version=1
    )
    api_reference = actor_reference_from_payload(payload)
    with pytest.raises(PermissionDeniedError, match="tenant session"):
        RevalidationService(MagicMock(spec=Engine), api_reference, MagicMock(), KEY)


def test_binding_has_only_identity_and_digest_and_no_parallel_task_status():
    assert tuple(revalidation_job_bindings.c.keys()) == (
        "job_id",
        "actor_user_id",
        "tenant_id",
        "authorized_role",
        "actor_reference",
        "payload_sha256",
        "created_at",
    )
    assert revalidation_job_bindings.c.job_id.primary_key
    assert revalidation_job_bindings.c.actor_reference.nullable is False


def test_fixed_factories_expose_only_two_trusted_detached_job_types():
    handlers = make_revalidation_job_handlers(MagicMock(spec=Engine), MagicMock(), KEY)
    assert set(handlers) == {"revalidate_change", "revalidate_assessment"}
    assert all(isinstance(handler, DetachedJobHandler) for handler in handlers.values())
    context = JobExecutionContext("fixture-job", "fixture-worker", 1, "fixture-tenant")
    with pytest.raises(ValidationError):
        handlers["revalidate_assessment"].handler(context, b'{"tenant_id":"spoofed"}')


def test_expired_runtime_deadline_is_not_reported_as_success():
    with pytest.raises(RevalidationError, match="deadline_exceeded"):
        _require_remaining(0)
