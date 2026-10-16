"""Synthetic job observations test completion without calling a database or model."""

import pytest

from ai_intel.revalidation.fan_in import summarize_dependency_statuses
from ai_intel.workers.executor import JobExecutionError


def test_completed_work_is_not_a_negative_risk_conclusion():
    result = summarize_dependency_statuses(("succeeded", "succeeded"), 1, 10, ())
    assert result.outcome == "succeeded"
    assert result.result_ref is None
    assert result.error_code is None
    assert not hasattr(result, "assessment_status")


@pytest.mark.parametrize("status", ["queued", "running", "retry_wait"])
def test_pending_work_uses_existing_durable_retry_boundary(status):
    with pytest.raises(JobExecutionError) as retry:
        summarize_dependency_statuses(("succeeded", status), 2, 10, ())
    assert retry.value.error_code == "revalidation_completion_pending"
    assert retry.value.retry_after_seconds == 5.0
    assert not retry.value.blocked and not retry.value.permanent


@pytest.mark.parametrize("status", ["queued", "running", "retry_wait"])
def test_last_check_preserves_explicit_partial_instead_of_a_false_failure(status):
    result = summarize_dependency_statuses((status,), 10, 10, ())
    assert result.outcome == "partial"
    assert result.error_code == "revalidation_completion_budget_exhausted"


@pytest.mark.parametrize(
    "statuses,outcome,reason",
    [
        ((None,), "partial", "revalidation_dependency_unavailable"),
        (("failed",), "partial", "revalidation_dependency_failed"),
        (("cancelled",), "partial", "revalidation_dependency_failed"),
        (("partial",), "partial", "revalidation_dependency_incomplete"),
        (("waiting_approval",), "partial", "revalidation_dependency_incomplete"),
        (("succeeded", "blocked"), "blocked", "revalidation_dependency_blocked"),
        (("invented_status",), "blocked", "revalidation_dependency_status_invalid"),
    ],
)
def test_missing_and_unsuccessful_dependencies_remain_observable(statuses, outcome, reason):
    result = summarize_dependency_statuses(statuses, 1, 10, ())
    assert (result.outcome, result.error_code) == (outcome, reason)


def test_empty_rule_watch_gap_cannot_be_declared_complete():
    result = summarize_dependency_statuses((), 1, 10, ("no_visible_rules_requires_scope_watch",))
    assert result.outcome == "partial"
    assert result.error_code == "no_visible_rules_requires_scope_watch"


def test_completion_replay_is_deterministic_and_leaves_original_observations_unchanged():
    statuses = ("succeeded", "partial")
    expected = ("partial", "revalidation_dependency_incomplete")
    for _ in range(2):
        result = summarize_dependency_statuses(statuses, 1, 10, ())
        assert (result.outcome, result.error_code) == expected
    assert statuses == ("succeeded", "partial")
