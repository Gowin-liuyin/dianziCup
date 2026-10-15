"""T07 重试等待合同验收测试: 真实 PostgreSQL, 失败进 retry_wait, 恢复后仅重试一次。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from ai_intel.domain.enums import JobStatus
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import job_runs
from ai_intel.workers.jobs import claim_next_job, complete_job, schedule_retry_or_fail

pytestmark = pytest.mark.real_pg


def test_transient_failure_parks_in_retry_wait_then_retries_exactly_once(migrated_engine) -> None:
    """T07 结转: 瞬时失败 → retry_wait 挂起不立即重试, 恢复后观察重试次数 == 1。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    job_type = "t07-retry-wait-" + str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        job_id = enqueue_job(connection, None, job_type, b"payload-retry", now)
        first_claim = claim_next_job(connection, "worker-1", now, job_type=job_type)
        assert first_claim is not None and first_claim["job_id"] == job_id
        outcome = schedule_retry_or_fail(
            connection, job_id, "worker-1", permanent=False, failed_at=now, expected_attempt=1
        )
        parked = connection.execute(
            select(job_runs.c.status, job_runs.c.attempt_count, job_runs.c.lease_owner).where(
                job_runs.c.job_id == job_id
            )
        ).one()
    assert outcome == JobStatus.RETRY_WAIT.value == "retry_wait"
    assert parked.status == JobStatus.RETRY_WAIT.value
    assert parked.lease_owner is None
    assert int(parked.attempt_count) == 1
    recovery_at = now + timedelta(minutes=1)
    with migrated_engine.begin() as connection:
        recovered = claim_next_job(connection, "worker-2", recovery_at, job_type=job_type)
        assert recovered is not None and recovered["job_id"] == job_id
        observed = connection.execute(
            select(job_runs.c.attempt_count).where(job_runs.c.job_id == job_id)
        ).scalar_one()
        observed_retry_count = int(observed) - 1
        complete_job(connection, job_id, "worker-2", "succeeded", recovery_at, expected_attempt=2)
        further_retry = claim_next_job(
            connection, "worker-3", recovery_at + timedelta(minutes=1), job_type=job_type
        )
        final_status = connection.execute(
            select(job_runs.c.status).where(job_runs.c.job_id == job_id)
        ).scalar_one()
    assert observed_retry_count == 1
    assert further_retry is None
    assert final_status == "succeeded"
