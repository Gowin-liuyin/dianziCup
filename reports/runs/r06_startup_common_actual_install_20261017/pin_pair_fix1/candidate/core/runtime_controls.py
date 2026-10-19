"""Pure lease and finite resource decisions for the root-owned R06 supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil, isfinite
from typing import Literal

LEASE_SECONDS = 60
LEASE_GRACE_SECONDS = 5
SOURCE_JOB_CAP = 450
ENQUEUE_HEADROOM = 40
SOURCE_JOB_PRESTOP = SOURCE_JOB_CAP - ENQUEUE_HEADROOM
SOURCE_ATTEMPTS_PER_JOB = 3
SOURCE_FETCHES_PER_ATTEMPT = 2
DOH_QUERIES_PER_FETCH = 2
DOH_HOPS_PER_QUERY = 6
HTTPS_PER_JOB_UPPER_BOUND = (
    SOURCE_ATTEMPTS_PER_JOB
    * SOURCE_FETCHES_PER_ATTEMPT
    * (1 + DOH_QUERIES_PER_FETCH * DOH_HOPS_PER_QUERY)
)
MAXIMUM_SECONDS = 21600
CPU_SECONDS_CAP = 1200
SNAPSHOT_CAP_BYTES = 1024 * 1024
JOURNAL_CAP_BYTES = 16 * 1024**2
COMPONENT_LOG_CAP_BYTES = 8 * 1024**2
MAX_SNAPSHOT_AGE_SECONDS = 3
STOP_ACK_SECONDS = 1


@dataclass(frozen=True)
class RunningSourceLease:
    """Only a source job claimed during this new segment is an owned running task."""

    job_id: str
    started_at: datetime
    lease_expires_at: datetime | None


@dataclass(frozen=True)
class StopObservation:
    """Actual PID/kernel creation identity is checked separately from launcher exit."""

    ack_present: bool
    ownership_matches: bool
    actual_pid_exited: bool
    seconds_since_request: float


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware guard time required")


def running_lease_guard_reason(
    running_jobs: tuple[RunningSourceLease, ...],
    segment_started_at: datetime,
    observed_at: datetime,
) -> str | None:
    """An expired current lease gets five seconds; old interrupted jobs remain visible."""
    _aware(segment_started_at)
    _aware(observed_at)
    if observed_at < segment_started_at:
        raise ValueError("guard observation precedes segment")
    current = []
    for job in running_jobs:
        _aware(job.started_at)
        if job.started_at < segment_started_at:
            continue
        if job.started_at > observed_at:
            return "source_running_time_invalid"
        if job.lease_expires_at is None:
            return "source_running_lease_missing"
        _aware(job.lease_expires_at)
        lease_length = (job.lease_expires_at - job.started_at).total_seconds()
        if not 0 < lease_length <= LEASE_SECONDS:
            return "source_running_lease_invalid"
        current.append(job)
    if len(current) > 1:
        return "source_worker_concurrency_invalid"
    if any(
        observed_at >= job.lease_expires_at + timedelta(seconds=LEASE_GRACE_SECONDS)
        for job in current
        if job.lease_expires_at is not None
    ):
        return "source_running_lease_expired"
    return None


def resource_guard_reason(
    source_jobs: int,
    cpu_seconds: float,
    component_log_bytes: int,
    journal_bytes: int,
    snapshot_age_seconds: float,
) -> str | None:
    """Unknown or exhausted counters stop collection; response counts never imply wire counts."""
    if type(source_jobs) is not int or source_jobs < 0:
        return "source_job_count_invalid"
    if source_jobs > SOURCE_JOB_CAP:
        return "source_job_cap_violated"
    if source_jobs >= SOURCE_JOB_PRESTOP:
        return "source_job_headroom_stop"
    if (
        isinstance(cpu_seconds, bool)
        or not isfinite(cpu_seconds)
        or isinstance(snapshot_age_seconds, bool)
        or not isfinite(snapshot_age_seconds)
        or type(component_log_bytes) is not int
        or component_log_bytes < 0
        or type(journal_bytes) is not int
        or journal_bytes < 0
    ):
        return "resource_counter_invalid"
    if cpu_seconds < 0 or cpu_seconds >= CPU_SECONDS_CAP:
        return "cpu_budget"
    if component_log_bytes >= COMPONENT_LOG_CAP_BYTES:
        return "component_log_budget"
    if journal_bytes >= JOURNAL_CAP_BYTES:
        return "observation_log_budget"
    if snapshot_age_seconds < 0 or snapshot_age_seconds > MAX_SNAPSHOT_AGE_SECONDS:
        return "guard_snapshot_stale"
    return None


def pending_slot_budget(total_jobs: int, pending_jobs: int) -> dict[str, int]:
    """Existing queued/retry/running jobs use their original three-attempt allowance."""
    if not 0 <= pending_jobs <= total_jobs <= SOURCE_JOB_CAP:
        raise ValueError("invalid existing source inventory")
    return {
        "existing_jobs": total_jobs,
        "existing_pending_jobs": pending_jobs,
        "remaining_new_job_slots": SOURCE_JOB_CAP - total_jobs,
        "prestop_new_job_slots": SOURCE_JOB_PRESTOP - total_jobs,
        "total_https_upper_bound": SOURCE_JOB_CAP * HTTPS_PER_JOB_UPPER_BOUND,
        "pending_https_upper_bound": pending_jobs * HTTPS_PER_JOB_UPPER_BOUND,
    }


def enqueue_race_bound(
    snapshot_delay_seconds: float,
    beat_stop_seconds: float,
    worker_ack_seconds: float,
    poll_boundary_batches: int,
) -> int:
    """A solo worker leaves at most one current page after a warm-stop acknowledgement."""
    delay = snapshot_delay_seconds + beat_stop_seconds + worker_ack_seconds
    if not 0 <= delay <= 5 or not 0 <= poll_boundary_batches <= 2:
        raise ValueError("race assumptions require immediate fail-closed owned termination")
    page_jobs = 9 * (1 + ceil(delay / 7))
    root_jobs = poll_boundary_batches * 9
    return page_jobs + root_jobs + 1


def stop_action(
    role: Literal["beat", "worker"],
    observation: StopObservation,
    observed_at: datetime,
    current_lease_expires_at: datetime | None,
    hard_guard: bool = False,
) -> str:
    """A missing acknowledgement never becomes success; invalid ownership prohibits PID signals."""
    _aware(observed_at)
    if role not in ("beat", "worker"):
        raise ValueError("invalid controlled actor")
    if not observation.ownership_matches:
        return "refuse_pid_signal_close_owned_supervisor_job"
    if observation.actual_pid_exited:
        return "ended_with_ack" if observation.ack_present else "ended_without_ack_failure"
    if hard_guard:
        return "kill_owned_tree"
    if not isfinite(observation.seconds_since_request) or observation.seconds_since_request < 0:
        return "kill_owned_tree"
    if not observation.ack_present:
        return (
            "kill_owned_tree"
            if observation.seconds_since_request >= STOP_ACK_SECONDS
            else "wait_ack"
        )
    if role == "beat":
        return (
            "kill_owned_tree"
            if observation.seconds_since_request >= STOP_ACK_SECONDS
            else "wait_actual_exit"
        )
    if current_lease_expires_at is None:
        return "kill_owned_tree"
    _aware(current_lease_expires_at)
    if observed_at >= current_lease_expires_at + timedelta(seconds=LEASE_GRACE_SECONDS):
        return "kill_owned_tree"
    return "wait_current_task"
