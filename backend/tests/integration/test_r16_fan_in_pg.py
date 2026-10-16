"""Synthetic cohorts for a separately authorized real PostgreSQL run; no resource skips."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.test_r11_pg_assessments import asset, publish, seed
from tests.integration.test_r16_assessment_candidates_pg import synthetic_change
from tests.integration.test_r16_revalidation_runtime_pg import (
    actor_reference,
    execute,
    latest_change,
    queue_change,
    row,
)

from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.revalidation.execution_contracts import RevalidationChangeRequest
from ai_intel.workers.jobs import read_job_payload

pytestmark = pytest.mark.real_pg


def stored_request(engine, job_id, tenant):
    with Session(engine) as session, session.begin():
        return RevalidationChangeRequest.model_validate_json(
            read_job_payload(session, job_id, tenant)
        )


def test_completion_preserves_parent_terminal_history_and_real_assessment(
    migrated_engine, tmp_path
):
    seeded = seed(migrated_engine, tmp_path)
    publish(migrated_engine, seeded)
    imported = asset(migrated_engine, seeded)
    parent_id = queue_change(migrated_engine, seeded)
    assert execute(migrated_engine, seeded, parent_id) == "partial"
    original_parent = dict(row(migrated_engine, parent_id))
    completion_id = original_parent["result_ref"].removeprefix("pg:job:")
    completion = stored_request(migrated_engine, completion_id, seeded["tenant"])
    assert completion.fan_in.parent_job_id == parent_id
    assert completion.fan_in.child_job_ids
    for child_id in completion.fan_in.child_job_ids:
        assert execute(migrated_engine, seeded, child_id) == "succeeded"
    with migrated_engine.connect() as connection:
        immutable_receipts = tuple(connection.execute(select(assessment_results)).mappings())
    assert execute(migrated_engine, seeded, completion_id) == "succeeded"
    assert dict(row(migrated_engine, parent_id)) == original_parent
    with migrated_engine.connect() as connection:
        assert (
            tuple(connection.execute(select(assessment_results)).mappings()) == immutable_receipts
        )
    assert any(
        receipt["asset_snapshot_id"] == imported.snapshot.snapshot_id
        for receipt in immutable_receipts
    )


def test_pending_check_reuses_owned_completion_and_preserves_parent(migrated_engine, tmp_path):
    from ai_intel.revalidation.runtime_policy import _enqueue_owned_job

    seeded = seed(migrated_engine, tmp_path)
    publish(migrated_engine, seeded)
    asset(migrated_engine, seeded)
    parent_id = queue_change(migrated_engine, seeded)
    assert execute(migrated_engine, seeded, parent_id) == "partial"
    original_parent = dict(row(migrated_engine, parent_id))
    completion_id = original_parent["result_ref"].removeprefix("pg:job:")
    completion = stored_request(migrated_engine, completion_id, seeded["tenant"])
    assert execute(migrated_engine, seeded, completion_id) == "retry_wait"
    assert row(migrated_engine, completion_id)["attempt_count"] == 1
    assert row(migrated_engine, completion_id)["error_code"] == "revalidation_completion_pending"
    assert dict(row(migrated_engine, parent_id)) == original_parent
    assert completion.fan_in.remaining_checks == row(migrated_engine, completion_id)["max_attempts"]
    with Session(migrated_engine) as session, session.begin():
        actor = actor_reference(migrated_engine, seeded)
        repeated = _enqueue_owned_job(
            session,
            actor,
            "revalidate_change",
            completion.model_dump_json().encode(),
            datetime.now(UTC),
            max_attempts=completion.fan_in.remaining_checks,
        )
    assert repeated == completion_id


def test_page_budget_remains_blocked_at_manifest_continuation(migrated_engine, tmp_path):
    seeded = seed(migrated_engine, tmp_path)
    publish(migrated_engine, seeded)
    asset(migrated_engine, seeded)
    asset(migrated_engine, seeded)
    synthetic_change(migrated_engine, seeded)
    parent_id = queue_change(migrated_engine, seeded, remaining_pages=1)
    assert execute(migrated_engine, seeded, parent_id) == "partial"
    original_parent = dict(row(migrated_engine, parent_id))
    completion_id = original_parent["result_ref"].removeprefix("pg:job:")
    completion = stored_request(migrated_engine, completion_id, seeded["tenant"])
    assert completion.fan_in.next_page_job_id is not None
    next_page = row(migrated_engine, completion.fan_in.next_page_job_id)
    assert next_page["status"] == "blocked"
    assert next_page["error_code"] == "revalidation_page_budget_exhausted"
    assert completion.fan_in.effective_epoch == latest_change(migrated_engine, seeded)["epoch"]
    for child_id in completion.fan_in.child_job_ids:
        assert execute(migrated_engine, seeded, child_id) == "succeeded"
    assert execute(migrated_engine, seeded, completion_id) == "blocked"
    assert dict(row(migrated_engine, parent_id)) == original_parent
