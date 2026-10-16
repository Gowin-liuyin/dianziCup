"""Isolated completion inputs preserve old change jobs and reject fabricated cohorts."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from ai_intel.revalidation.execution_contracts import (
    RevalidationChangeRequest,
    RevalidationFanInManifest,
)

PARENT = str(UUID(int=1))
CHILD = str(UUID(int=2))
NEXT_PAGE = str(UUID(int=3))
NOW = datetime(2026, 10, 16, tzinfo=UTC)


def manifest_payload():
    return dict(
        parent_job_id=PARENT, effective_epoch=2, child_job_ids=(CHILD,), remaining_checks=10
    )


def change_payload():
    return dict(change_id="fixture-change", target_epoch=2, assessment_created_before=NOW)


def test_old_planning_job_keeps_no_completion_manifest():
    request = RevalidationChangeRequest(**change_payload())
    assert request.fan_in is None
    assert "fan_in" not in request.model_dump(mode="json")
    assert RevalidationChangeRequest.model_validate_json(request.model_dump_json()) == request


def test_completion_preserves_exact_child_and_continuation_references():
    manifest = RevalidationFanInManifest(
        **manifest_payload(), next_page_job_id=NEXT_PAGE, plan_incomplete_reasons=()
    )
    request = RevalidationChangeRequest(
        **change_payload(),
        fan_in=manifest,
        frozen_scope_epoch_map={"public": 2, "tenant:fixture-tenant": None},
        frozen_rule_scope_fingerprint="a" * 64,
    )
    assert request.fan_in.child_job_ids == (CHILD,)
    assert request.fan_in.next_page_job_id == NEXT_PAGE
    assert RevalidationChangeRequest.model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize("budget", [0, 11, True, "3"])
def test_completion_budget_is_strict_and_matches_existing_job_attempt_limit(budget):
    with pytest.raises(ValidationError):
        RevalidationFanInManifest.model_validate({**manifest_payload(), "remaining_checks": budget})


@pytest.mark.parametrize(
    "updates",
    [
        {"child_job_ids": (CHILD, CHILD)},
        {"child_job_ids": tuple(str(UUID(int=index + 10)) for index in range(101))},
        {"child_job_ids": (PARENT,)},
        {"next_page_job_id": PARENT},
        {"next_page_job_id": CHILD},
        {"parent_job_id": "https://untrusted.invalid/job"},
        {"tenant_id": "spoofed"},
        {"plan_incomplete_reasons": ("candidate_pages_remaining",)},
        {"plan_incomplete_reasons": ("visible_rule_roster_budget_exceeded",)},
        {"plan_incomplete_reasons": ("arbitrary exception text",)},
        {"effective_epoch": True},
        {"effective_epoch": -1},
    ],
)
def test_invalid_cohorts_and_untrusted_identity_fail_before_storage(updates):
    with pytest.raises(ValidationError):
        RevalidationFanInManifest.model_validate({**manifest_payload(), **updates})


@pytest.mark.parametrize(
    "updates",
    [{}, {"continuation": "signed-cursor"}, {"rule_after_id": "fixture-rule"}],
)
def test_completion_cannot_restart_discovery_or_omit_frozen_context(updates):
    values = {**change_payload(), "fan_in": manifest_payload(), **updates}
    if updates:
        values.update(frozen_scope_epoch_map={"public": 2}, frozen_rule_scope_fingerprint="a" * 64)
    with pytest.raises(ValidationError):
        RevalidationChangeRequest.model_validate(values)


def test_a_real_empty_page_remains_empty_without_inventing_a_safe_result():
    manifest = RevalidationFanInManifest(
        parent_job_id=PARENT,
        effective_epoch=2,
        child_job_ids=(),
        plan_incomplete_reasons=("no_visible_rules_requires_scope_watch",),
        remaining_checks=1,
    )
    assert manifest.child_job_ids == ()
    assert manifest.plan_incomplete_reasons == ("no_visible_rules_requires_scope_watch",)


def test_effective_epoch_can_coalesce_but_cannot_precede_the_original_request():
    manifest = RevalidationFanInManifest(**manifest_payload())
    request = RevalidationChangeRequest(
        **{**change_payload(), "target_epoch": 1},
        fan_in=manifest,
        frozen_scope_epoch_map={"public": 2},
        frozen_rule_scope_fingerprint="a" * 64,
    )
    assert request.target_epoch == 1 and request.fan_in.effective_epoch == 2
    with pytest.raises(ValidationError):
        RevalidationChangeRequest(
            **{**change_payload(), "target_epoch": 3},
            fan_in=manifest,
            frozen_scope_epoch_map={"public": 2},
            frozen_rule_scope_fingerprint="a" * 64,
        )
