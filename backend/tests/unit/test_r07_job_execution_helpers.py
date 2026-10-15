"""Offline checks cover workflow grouping and snapshot identity, without external calls."""

import pytest

from ai_intel.enrichment.job_contracts import EventEnrichmentRequest
from ai_intel.enrichment.job_types import logical_job_status, physical_steps


def test_default_dimensions_create_ten_physical_steps_and_one_publication():
    request = EventEnrichmentRequest(expected_event_version=1)
    steps = physical_steps(request)
    assert len(steps) == 10
    assert [step.step_key for step in steps][-2:] == ["exposure:hunter", "exposure:quake"]
    assert sum(step.output_token_budget for step in steps) == 4096


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], "queued"),
        (["succeeded", "blocked"], "partial"),
        (["failed", "failed"], "failed"),
        (["blocked", "blocked"], "blocked"),
        (["succeeded", "queued"], "running"),
        (["succeeded", "succeeded"], "succeeded"),
        (["cancelled", "cancelled"], "cancelled"),
    ],
)
def test_logical_dimension_uses_only_persisted_job_statuses(statuses, expected):
    assert logical_job_status(tuple(statuses)) == expected
