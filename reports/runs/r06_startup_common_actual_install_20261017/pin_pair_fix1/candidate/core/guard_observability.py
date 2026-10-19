"""Keep one bounded guard read-chain profile in memory until owned producers have stopped."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Literal

from runtime_controls import MAX_SNAPSHOT_AGE_SECONDS

STAGES = (
    "job_usage",
    "connect",
    "context_enter",
    "set_read_only",
    "timestamp_query",
    "count_query",
    "running_query",
    "row_mapping",
    "row_materialization",
    "context_exit",
    "lease_projection",
    "component_log",
    "journal_exists",
    "journal_stat",
    "host_utc_evaluation",
    "resource_and_lease_decision",
)
MAX_DIAGNOSTIC_BYTES = 8192
StageStatus = Literal["not_reached", "in_progress", "completed", "failed"]


@dataclass
class StageTiming:
    started: float | None = None
    ended: float | None = None
    status: StageStatus = "not_reached"

    def as_dict(self) -> dict[str, str | float]:
        duration = None
        if self.started is not None and self.ended is not None and self.ended >= self.started:
            duration = self.ended - self.started
        return {
            "started_monotonic_seconds": self.started if self.started is not None else "unknown",
            "ended_monotonic_seconds": self.ended if self.ended is not None else "unknown",
            "duration_seconds": duration if duration is not None else "unknown",
            "status": self.status,
        }


def monotonic_sample() -> float | None:
    sample = time.monotonic()
    return sample if isfinite(sample) else None


def aware_utc_timestamp(value: object) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return "unknown"
    return value.astimezone(UTC).isoformat()


@dataclass
class GuardObservation:
    """Timing is observational; the existing PG age and resource decisions remain authoritative."""

    round_number: int
    started: float | None = field(default_factory=monotonic_sample)
    ended: float | None = None
    timings: dict[str, StageTiming] = field(
        default_factory=lambda: {stage: StageTiming() for stage in STAGES}
    )
    active_stage: str | None = None
    pg_transaction_timestamp_utc: str = "unknown"
    host_utc_evaluated_at: str = "unknown"
    signed_age_seconds: float | None = None
    age_branch: str = "invalid_or_unavailable"
    outcome: str = "in_progress"

    def begin(self, stage: str) -> None:
        if stage not in self.timings or self.active_stage is not None:
            raise ValueError("fixed non-overlapping guard stage required")
        timing = self.timings[stage]
        timing.started = monotonic_sample()
        timing.status = "in_progress"
        self.active_stage = stage

    def end(self, status: Literal["completed", "failed"] = "completed") -> None:
        if self.active_stage is not None:
            timing = self.timings[self.active_stage]
            timing.ended = monotonic_sample()
            timing.status = status
            self.active_stage = None

    def record_age(self, host_utc: datetime, signed_age_seconds: float) -> None:
        self.host_utc_evaluated_at = aware_utc_timestamp(host_utc)
        if isinstance(signed_age_seconds, bool) or not isfinite(signed_age_seconds):
            return
        self.signed_age_seconds = signed_age_seconds
        if signed_age_seconds < 0:
            self.age_branch = "negative"
        elif signed_age_seconds > MAX_SNAPSHOT_AGE_SECONDS:
            self.age_branch = "greater_than_limit"
        else:
            self.age_branch = "within_range"

    def finish(self, failed: bool = False) -> None:
        if self.ended is not None:
            return
        self.end("failed" if failed else "completed")
        self.ended = monotonic_sample()
        self.outcome = "read_chain_exception" if failed else "decision_completed"

    def as_dict(self) -> dict[str, object]:
        total_status: StageStatus = "in_progress"
        if self.outcome == "read_chain_exception":
            total_status = "failed"
        elif self.ended is not None:
            total_status = "completed"
        total = StageTiming(self.started, self.ended, total_status).as_dict()
        value: dict[str, object] = {
            "schema": "r06_guard_observation_v1",
            "guard_rounds_attempted": self.round_number,
            "outcome": self.outcome,
            "pg_transaction_timestamp_utc": self.pg_transaction_timestamp_utc,
            "host_utc_evaluated_at": self.host_utc_evaluated_at,
            "signed_age_seconds": (
                self.signed_age_seconds if self.signed_age_seconds is not None else "unknown"
            ),
            "age_branch": self.age_branch,
            "clock_offset_seconds": "unknown",
            "clock_offset_status": "pg_current_clock_not_observed",
            "read_chain": total,
            "stages": {stage: timing.as_dict() for stage, timing in self.timings.items()},
        }
        if len(json.dumps(value, allow_nan=False).encode("utf-8")) > MAX_DIAGNOSTIC_BYTES:
            raise ValueError("guard diagnostic exceeds fixed byte bound")
        return value
