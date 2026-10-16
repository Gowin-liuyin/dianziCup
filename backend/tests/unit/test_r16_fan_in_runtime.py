"""Explicit fixture sessions test exact cohorts and controlled change interleavings offline."""

import hashlib
from datetime import timedelta
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from tests.unit.test_r16_assessment_candidates import receipt
from tests.unit.test_r16_revalidation_runtime import KEY, NOW, reference

from ai_intel.api.actor_references import ActorJobOwner, actor_reference_payload
from ai_intel.domain.access import PermissionDeniedError
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.revalidation import fan_in, runtime_policy
from ai_intel.revalidation.execution_contracts import (
    ReassessmentRequest,
    ReassessmentTarget,
    RevalidationChangeRequest,
    RevalidationFanInManifest,
    RevalidationPlan,
)
from ai_intel.revalidation.fan_in import OwnedDependency
from ai_intel.revalidation.verified_content import VerificationBudgetExceeded, VerifiedFanInResult
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError, JobExecutionResult

PARENT, CHILD, NEXT_PAGE, COMPLETION, NEXT_COMPLETION, ASSESSMENT = (
    str(UUID(int=index)) for index in range(1, 7)
)
EPOCHS = {"public": 2, "tenant:synthetic-tenant-a": None}
CONTEXT = JobExecutionContext(COMPLETION, "fixture-worker", 1, "synthetic-tenant-a")


def change_request(**updates):
    return RevalidationChangeRequest(
        **{
            "change_id": "fixture-change",
            "target_epoch": 2,
            "assessment_created_before": NOW,
            "frozen_scope_epoch_map": EPOCHS,
            "frozen_rule_scope_fingerprint": "a" * 64,
            **updates,
        }
    )


def completion_request(**updates):
    return change_request(
        fan_in=RevalidationFanInManifest(
            parent_job_id=PARENT, effective_epoch=2, child_job_ids=(CHILD,), **updates
        )
    )


def child_request(**updates):
    return ReassessmentRequest(
        **{
            "change_id": "fixture-change",
            "target_epoch": 2,
            "asset_id": "fixture-asset",
            "asset_snapshot_id": "fixture-snapshot",
            "rule_id": "fixture-rule",
            "rule_version": 1,
            **updates,
        }
    )


def child_job(**updates):
    return OwnedDependency(
        CHILD, "succeeded", "pg:assessment:" + ASSESSMENT, child_request(**updates)
    )


def current_receipt(**updates):
    original, _watch = receipt()
    return original.model_copy(
        update={
            "assessment_id": ASSESSMENT,
            "tenant_id": "synthetic-tenant-a",
            "asset_id": "fixture-asset",
            "rule_id": "fixture-rule",
            "freshness": FreshnessStatus.CURRENT,
            "scope_epoch_map": EPOCHS,
            **updates,
        }
    )


def stub_owned_jobs(monkeypatch, jobs):
    inspected = []

    def read_owned(session, actor, job_id):
        inspected.append(job_id)
        return jobs.get(job_id)

    monkeypatch.setattr(fan_in, "read_owned_dependency", read_owned)
    return inspected


def test_parent_partial_history_remains_distinct_from_completed_children(monkeypatch):
    parent = OwnedDependency(PARENT, "partial", "pg:job:" + COMPLETION, change_request())
    inspected = stub_owned_jobs(monkeypatch, {PARENT: parent, CHILD: child_job()})
    children, statuses = fan_in.read_fan_in_dependencies(
        MagicMock(), reference(), completion_request(), CONTEXT
    )
    assert inspected == [PARENT, CHILD]
    assert statuses == ("succeeded", "succeeded")
    assert children == (child_job(),)
    assert parent.status == "partial" and parent.result_ref == "pg:job:" + COMPLETION


def test_check_delivered_before_parent_commit_waits_without_claiming_its_lease(monkeypatch):
    parent = OwnedDependency(PARENT, "running", None, change_request())
    inspected = stub_owned_jobs(monkeypatch, {PARENT: parent})
    children, statuses = fan_in.read_fan_in_dependencies(
        MagicMock(), reference(), completion_request(), CONTEXT
    )
    assert inspected == [PARENT]
    assert children == () and statuses == ("running",)
    assert parent.status == "running"


def test_missing_exact_child_remains_unknown(monkeypatch):
    parent = OwnedDependency(PARENT, "partial", "pg:job:" + COMPLETION, change_request())
    stub_owned_jobs(monkeypatch, {PARENT: parent})
    children, statuses = fan_in.read_fan_in_dependencies(
        MagicMock(), reference(), completion_request(), CONTEXT
    )
    assert children == () and statuses == (None, "succeeded")


def test_an_unrelated_completion_cannot_claim_parent_cohort(monkeypatch):
    parent = OwnedDependency(PARENT, "partial", "pg:job:" + NEXT_COMPLETION, change_request())
    inspected = stub_owned_jobs(monkeypatch, {PARENT: parent})
    with pytest.raises(JobExecutionError, match="completion_parent_invalid"):
        fan_in.read_fan_in_dependencies(MagicMock(), reference(), completion_request(), CONTEXT)
    assert inspected == [PARENT]


@pytest.mark.parametrize("updates", [{"change_id": "other-change"}, {"target_epoch": 1}])
def test_wrong_child_change_or_effective_epoch_is_rejected(updates):
    with pytest.raises(JobExecutionError, match="dependency_input_mismatch"):
        fan_in.require_same_change(child_job(**updates), completion_request())


def test_original_requested_epoch_can_coalesce_without_changing_frozen_history_cutoff():
    original = OwnedDependency(
        PARENT, "partial", "pg:job:" + COMPLETION, change_request(target_epoch=1)
    )
    fan_in.require_same_change(original, completion_request(), allow_requested_epoch=True)
    different_cutoff = OwnedDependency(
        PARENT,
        "partial",
        "pg:job:" + COMPLETION,
        change_request(assessment_created_before=NOW + timedelta(seconds=1)),
    )
    with pytest.raises(JobExecutionError, match="dependency_input_mismatch"):
        fan_in.require_same_change(
            different_cutoff, completion_request(), allow_requested_epoch=True
        )


@pytest.mark.parametrize("freshness", [FreshnessStatus.STALE, FreshnessStatus.UNKNOWN])
def test_succeeded_job_does_not_make_an_old_or_unknown_receipt_current(freshness):
    with pytest.raises(JobExecutionError, match="assessment_stale"):
        fan_in.require_current_child_receipt(
            child_job(), current_receipt(freshness=freshness), completion_request()
        )


def test_changed_scope_and_mismatched_receipt_identity_are_separate_failures():
    with pytest.raises(JobExecutionError, match="assessment_stale"):
        fan_in.require_current_child_receipt(
            child_job(),
            current_receipt(scope_epoch_map={**EPOCHS, "public": 3}),
            completion_request(),
        )
    with pytest.raises(JobExecutionError, match="assessment_identity_changed"):
        fan_in.require_current_child_receipt(
            child_job(), current_receipt(asset_id="other-asset"), completion_request()
        )


def test_latest_child_snapshot_is_accepted_only_with_a_current_authoritative_receipt():
    fan_in.require_current_child_receipt(
        child_job(),
        current_receipt(asset_snapshot_id="fixture-new-snapshot", rule_version=2),
        completion_request(),
    )


@pytest.mark.parametrize("reference_value", [None, "https://untrusted.invalid", "pg:job:" + CHILD])
def test_child_result_cannot_select_an_arbitrary_resource(reference_value):
    child = OwnedDependency(CHILD, "succeeded", reference_value, child_request())
    with pytest.raises(JobExecutionError, match="assessment_reference_invalid"):
        fan_in.assessment_id_for_child(child)


def test_cross_tenant_dependency_fails_before_payload_or_actor_lookup(monkeypatch):
    session = MagicMock()
    session.execute.return_value.mappings.return_value.first.return_value = {"tenant_id": "other"}
    lookup = MagicMock()
    monkeypatch.setattr(fan_in, "lock_actor_reference_scope", lookup)
    with pytest.raises(PermissionDeniedError):
        fan_in.read_owned_dependency(session, reference(), CHILD)
    lookup.assert_not_called()


def test_revoked_owner_is_not_replaced_by_payload_identity(monkeypatch):
    session = MagicMock()
    session.execute.return_value.mappings.return_value.first.return_value = {"tenant_id": "t"}
    actor = reference()
    session.execute.return_value.mappings.return_value.first.return_value = {
        "tenant_id": actor.tenant_id
    }
    monkeypatch.setattr(
        fan_in, "lock_actor_reference_scope", MagicMock(side_effect=PermissionDeniedError)
    )
    payload_read = MagicMock()
    monkeypatch.setattr(fan_in, "read_job_payload", payload_read)
    with pytest.raises(PermissionDeniedError):
        fan_in.read_owned_dependency(session, actor, CHILD)
    payload_read.assert_not_called()


def test_status_is_reread_after_current_authority_proof_without_locking_dependency_job(monkeypatch):
    actor = reference()
    payload = child_request().model_dump_json().encode()
    digest = hashlib.sha256(payload).hexdigest()
    older = {
        "tenant_id": actor.tenant_id,
        "job_type": "revalidate_assessment",
        "status": "running",
        "result_ref": None,
        "payload_ref": "pg:job:" + CHILD,
        "payload_sha256": digest,
    }
    completed = {**older, "status": "succeeded", "result_ref": "pg:assessment:" + ASSESSMENT}
    first, latest = MagicMock(), MagicMock()
    first.mappings.return_value.first.return_value = older
    latest.mappings.return_value.first.return_value = completed
    session = MagicMock()
    session.execute.side_effect = [first, latest]
    session.scalar.return_value = digest
    scope = MagicMock()
    monkeypatch.setattr(fan_in, "lock_actor_reference_scope", lambda *args: scope)
    owner = ActorJobOwner(
        actor.user_id, actor.tenant_id, actor.role, actor_reference_payload(actor)
    )
    owner_read = MagicMock(return_value=owner)
    monkeypatch.setattr(runtime_policy.RevalidationJobOwner, "read_actor_job_owner", owner_read)
    exclusive_owner_lock = MagicMock(
        side_effect=AssertionError("dependency job must not be locked")
    )
    monkeypatch.setattr(
        runtime_policy.RevalidationJobOwner, "lock_actor_job_owner", exclusive_owner_lock
    )
    monkeypatch.setattr(fan_in, "read_job_payload", lambda *args: payload)
    observed = fan_in.read_owned_dependency(session, actor, CHILD)
    assert observed.status == "succeeded" and observed.result_ref == "pg:assessment:" + ASSESSMENT
    assert older["status"] == "running"
    owner_read.assert_called_once()
    exclusive_owner_lock.assert_not_called()
    session.scalar.return_value = "f" * 64
    session.execute.side_effect = [first, latest]
    with pytest.raises(JobExecutionError, match="dependency_payload_changed"):
        fan_in.read_owned_dependency(session, actor, CHILD)


def test_continuation_reads_only_its_fixed_completion_and_preserves_page_history(monkeypatch):
    page = OwnedDependency(NEXT_PAGE, "partial", "pg:job:" + NEXT_COMPLETION, change_request())
    next_check = OwnedDependency(
        NEXT_COMPLETION,
        "succeeded",
        "pg:change:fixture-change",
        change_request(
            fan_in=RevalidationFanInManifest(
                parent_job_id=NEXT_PAGE, effective_epoch=2, child_job_ids=()
            )
        ),
    )
    inspected = stub_owned_jobs(monkeypatch, {NEXT_PAGE: page, NEXT_COMPLETION: next_check})
    status = fan_in.read_continuation_status(
        MagicMock(), reference(), completion_request(next_page_job_id=NEXT_PAGE), COMPLETION
    )
    assert status == "succeeded" and inspected == [NEXT_PAGE, NEXT_COMPLETION]
    assert page.status == "partial"


def test_continuation_reference_cycle_cannot_trigger_a_second_lookup(monkeypatch):
    page = OwnedDependency(NEXT_PAGE, "partial", "pg:job:" + COMPLETION, change_request())
    inspected = stub_owned_jobs(monkeypatch, {NEXT_PAGE: page})
    with pytest.raises(JobExecutionError, match="reference_cycle"):
        fan_in.read_continuation_status(
            MagicMock(), reference(), completion_request(next_page_job_id=NEXT_PAGE), COMPLETION
        )
    assert inspected == [NEXT_PAGE]


def test_coalesced_continuation_keeps_signed_cursor_requested_epoch_and_effective_cohort(
    monkeypatch,
):
    request = change_request(
        target_epoch=1,
        fan_in=RevalidationFanInManifest(
            parent_job_id=PARENT,
            effective_epoch=2,
            child_job_ids=(CHILD,),
            next_page_job_id=NEXT_PAGE,
        ),
    )
    page_request = change_request(target_epoch=1, continuation="signed-original-requested-epoch")
    page = OwnedDependency(NEXT_PAGE, "partial", "pg:job:" + NEXT_COMPLETION, page_request)
    next_request = change_request(
        target_epoch=1,
        fan_in=RevalidationFanInManifest(
            parent_job_id=NEXT_PAGE, effective_epoch=2, child_job_ids=()
        ),
    )
    check = OwnedDependency(NEXT_COMPLETION, "succeeded", "pg:change:fixture-change", next_request)
    inspected = stub_owned_jobs(monkeypatch, {NEXT_PAGE: page, NEXT_COMPLETION: check})
    assert (
        fan_in.read_continuation_status(MagicMock(), reference(), request, COMPLETION)
        == "succeeded"
    )
    assert inspected == [NEXT_PAGE, NEXT_COMPLETION]
    assert (
        page.request.target_epoch == 1
        and page.request.continuation == "signed-original-requested-epoch"
    )
    fan_in.require_same_change(child_job(), request)


def test_a_continuation_from_a_later_effective_cohort_cannot_be_counted_as_this_completion(
    monkeypatch,
):
    page = OwnedDependency(NEXT_PAGE, "partial", "pg:job:" + NEXT_COMPLETION, change_request())
    check = OwnedDependency(
        NEXT_COMPLETION,
        "succeeded",
        "pg:change:fixture-change",
        change_request(
            fan_in=RevalidationFanInManifest(
                parent_job_id=NEXT_PAGE, effective_epoch=3, child_job_ids=()
            )
        ),
    )
    stub_owned_jobs(monkeypatch, {NEXT_PAGE: page, NEXT_COMPLETION: check})
    with pytest.raises(JobExecutionError, match="dependency_input_mismatch"):
        fan_in.read_continuation_status(
            MagicMock(), reference(), completion_request(next_page_job_id=NEXT_PAGE), COMPLETION
        )


def test_completion_enqueue_reuses_existing_attempt_budget_and_atomic_owned_job_port(monkeypatch):
    session = MagicMock()
    actor = reference()
    scope = MagicMock()
    scope.tenant_id = actor.tenant_id
    monkeypatch.setattr(runtime_policy, "lock_actor_reference_scope", lambda *args: scope)
    monkeypatch.setattr(
        runtime_policy.CandidateDiscoveryService, "_authorize_change", lambda *args: None
    )
    session.execute.return_value.mappings.return_value.first.return_value = {
        "scope_key": "public",
        "epoch": 1,
    }
    session.scalar.return_value = 2
    enqueue = MagicMock(return_value=COMPLETION)
    monkeypatch.setattr(runtime_policy, "_enqueue_owned_job", enqueue)
    request = completion_request(remaining_checks=7)
    assert runtime_policy.enqueue_revalidation_change(session, actor, request, NOW) == COMPLETION
    assert enqueue.call_args.kwargs["max_attempts"] == 7
    stored = RevalidationChangeRequest.model_validate_json(enqueue.call_args.args[3])
    assert stored.fan_in == request.fan_in
    session.scalar.return_value = 3
    with pytest.raises(runtime_policy.RevalidationError, match="not_authoritative"):
        runtime_policy.enqueue_revalidation_change(session, actor, request, NOW)
    assert enqueue.call_count == 1


def test_final_guard_rejects_change_between_public_read_and_terminal_commit(monkeypatch):
    session = MagicMock()
    child = child_job()
    session.execute.return_value.mappings.return_value.first.return_value = {
        "result_payload": current_receipt().model_dump(mode="json")
    }
    monkeypatch.setattr(fan_in, "check_fan_in", lambda *args: (JobExecutionResult(), (child,)))
    lock_inputs = MagicMock()
    monkeypatch.setattr(fan_in, "lock_completion_inputs", lock_inputs)
    monkeypatch.setattr(
        fan_in,
        "require_current_scope",
        MagicMock(
            side_effect=JobExecutionError("revalidation_completion_inputs_changed", blocked=True)
        ),
    )
    with pytest.raises(JobExecutionError, match="completion_inputs_changed"):
        fan_in.guard_completed_fan_in(
            session, MagicMock(), reference(), MagicMock(), completion_request(), CONTEXT
        )
    lock_inputs.assert_called_once()


def test_planner_pins_the_actual_child_ids_to_a_new_completion_without_finalizing_parent(
    monkeypatch,
):
    actor = reference()
    target = ReassessmentTarget(
        asset_id="fixture-asset",
        asset_snapshot_id="fixture-snapshot",
        rule_id="fixture-rule",
        rule_version=1,
    )
    plan = RevalidationPlan(
        change_id="fixture-change",
        actor_user_id=actor.user_id,
        tenant_id=actor.tenant_id,
        permission_version=actor.permission_version,
        permissions_digest=actor.permissions_digest,
        requested_epoch=1,
        target_epoch=2,
        scope_epoch_map=EPOCHS,
        rule_scope_fingerprint="a" * 64,
        assessment_created_before=NOW,
        targets=(target,),
        candidate_count=1,
        planning_status="complete",
        incomplete_reasons=(),
    )
    session = MagicMock()
    session.__enter__.return_value = session
    monkeypatch.setattr(runtime_policy, "Session", lambda *args: session)
    monkeypatch.setattr(runtime_policy, "_lock_bound_actor", lambda *args: actor)
    service = MagicMock()
    service.plan_change.return_value = plan
    monkeypatch.setattr(runtime_policy, "RevalidationService", lambda *args: service)
    enqueue_children = MagicMock(return_value=(CHILD,))
    enqueue_check = MagicMock(return_value=COMPLETION)
    monkeypatch.setattr(runtime_policy, "enqueue_reassessment_plan", enqueue_children)
    monkeypatch.setattr(runtime_policy, "enqueue_revalidation_change", enqueue_check)
    handler = runtime_policy.make_revalidation_change_handler(MagicMock(), MagicMock(), KEY)
    planning_context = JobExecutionContext(PARENT, "fixture-worker", 1, actor.tenant_id)
    result = handler.handler(
        planning_context, change_request(target_epoch=1).model_dump_json().encode()
    )
    assert result.outcome == "partial" and result.result_ref == "pg:job:" + COMPLETION
    completion = enqueue_check.call_args.args[2]
    assert completion.target_epoch == 1 and completion.fan_in.parent_job_id == PARENT
    assert completion.fan_in.effective_epoch == 2
    assert completion.fan_in.child_job_ids == (CHILD,)
    assert completion.frozen_scope_epoch_map == EPOCHS
    enqueue_children.assert_called_once()
    session.execute.assert_not_called()


def test_completion_guard_rechecks_authority_for_partial_without_rewriting_history(monkeypatch):
    actor = reference()
    bound = MagicMock(return_value=actor)
    current_scope = MagicMock()
    final_validation = MagicMock()
    monkeypatch.setattr(runtime_policy, "_lock_bound_actor", bound)
    monkeypatch.setattr(runtime_policy, "require_current_scope", current_scope)
    monkeypatch.setattr(runtime_policy, "guard_completed_fan_in", final_validation)
    handler = runtime_policy.make_revalidation_change_handler(MagicMock(), MagicMock(), KEY)
    assert handler.completion_guard is not None
    session = MagicMock()
    result = JobExecutionResult(
        "partial", "pg:change:fixture-change", "revalidation_dependency_incomplete"
    )
    payload = completion_request().model_dump_json().encode()
    handler.completion_guard(session, CONTEXT, payload, result)
    bound.assert_called_once_with(session, CONTEXT, payload)
    current_scope.assert_called_once()
    final_validation.assert_not_called()
    session.execute.assert_not_called()


def test_planning_payload_keeps_the_original_none_guard_behavior(monkeypatch):
    bound = MagicMock()
    monkeypatch.setattr(runtime_policy, "_lock_bound_actor", bound)
    handler = runtime_policy.make_revalidation_change_handler(MagicMock(), MagicMock(), KEY)
    assert handler.completion_guard is not None
    handler.completion_guard(
        MagicMock(),
        CONTEXT,
        change_request().model_dump_json().encode(),
        JobExecutionResult("partial"),
    )
    bound.assert_not_called()


@pytest.mark.parametrize("over_budget", [False, True])
def test_only_real_verification_result_can_produce_success_proof_and_budget_stays_partial(
    monkeypatch, over_budget
):
    actor = reference()
    session = MagicMock()
    session.__enter__.return_value = session
    monkeypatch.setattr(runtime_policy, "Session", lambda *args: session)
    monkeypatch.setattr(runtime_policy, "_lock_bound_actor", lambda *args: actor)
    monkeypatch.setattr(
        runtime_policy, "check_fan_in", lambda *args: (JobExecutionResult(), (child_job(),))
    )
    verification = MagicMock(return_value={})
    if over_budget:
        verification.side_effect = VerificationBudgetExceeded(
            "revalidation_verification_budget_exhausted"
        )
    monkeypatch.setattr(runtime_policy, "read_completed_assessments", verification)
    planner = MagicMock(
        side_effect=AssertionError("completion must not rediscover or enqueue children")
    )
    monkeypatch.setattr(runtime_policy, "RevalidationService", planner)
    handler = runtime_policy.make_revalidation_change_handler(MagicMock(), MagicMock(), KEY)
    payload = completion_request().model_dump_json().encode()
    result = handler.handler(CONTEXT, payload)
    verification.assert_called_once()
    if over_budget:
        assert result.outcome == "partial"
        assert result.error_code == "revalidation_verification_budget_exhausted"
        assert not isinstance(result, VerifiedFanInResult)
    else:
        assert isinstance(result, VerifiedFanInResult) and result.outcome == "succeeded"
        assert result.proof.actor == actor and result.proof.job_id == CONTEXT.job_id
        assert result.proof.request_sha256 == hashlib.sha256(payload).hexdigest()
    planner.assert_not_called()
    session.execute.assert_not_called()
