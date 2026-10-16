"""PostgreSQL任务认领、持久重试和单调attempt租约隔离。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, case, func, insert, or_, select, update
from sqlalchemy.orm import Session

from ai_intel.domain.access import WRITE_ASSET, AccessScope, CrossTenantAccessError
from ai_intel.knowledge.models import job_payloads, job_runs, job_transitions, outbox_events
from ai_intel.knowledge.persistence_models import change_events

LEASE_SECONDS = 60
DELIVERY_RECOVERY_GRACE_SECONDS = 60
DELIVERY_ATTEMPTS_PER_JOB_ATTEMPT = 3
DELIVERY_STOPPED_AT = datetime(9999, 12, 31, tzinfo=UTC)
TERMINAL_JOB_STATUSES = (
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "blocked",
    "waiting_approval",
)


class JobLeaseLostError(RuntimeError):
    """持有者、attempt或未过期租约不成立，业务事务不得提交。"""


class JobPayloadUnavailableError(ValueError):
    """引用无法恢复或digest不一致；不编造旧任务输入。"""


def require_aware_time(at: datetime) -> None:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("job timestamps require timezone")


def validate_job_result_fields(result_ref: str | None, error_code: str | None) -> None:
    """持久化结果只接受内部引用和固定码，不保存上游异常或任意URL。"""
    if error_code is not None and not re.fullmatch("[a-z][a-z0-9_]{0,99}", error_code):
        raise ValueError("invalid handler error code")
    if result_ref is not None and not re.fullmatch(
        r"pg:[a-z][a-z0-9_]{0,49}:[a-zA-Z0-9_-]{1,200}",
        result_ref,
    ):
        raise ValueError("invalid handler result reference")


def retry_delay_seconds(attempt_count: int, retry_after_seconds: float | None = None) -> float:
    if attempt_count < 1 or attempt_count > 10:
        raise ValueError("attempt_count must be between 1 and 10")
    if retry_after_seconds is not None:
        if not 0 <= retry_after_seconds <= 300:
            raise ValueError("Retry-After must be between 0 and 300 seconds")
        return max(5.0, retry_after_seconds)
    return float(min(300, 5 * 2 ** (attempt_count - 1)))


def record_job_transition(
    session: Session, row: dict[str, object], to_status: str, reason: str, at: datetime
) -> None:
    session.execute(
        insert(job_transitions).values(
            job_id=row["job_id"],
            attempt_count=row["attempt_count"],
            from_status=row["status"],
            to_status=to_status,
            reason=reason,
            changed_at=at,
        )
    )


def _claim_job(
    session: Session,
    worker_id: str,
    claimed_at: datetime,
    job_type: str | None = None,
    job_id: str | None = None,
) -> dict[str, object] | None:
    require_aware_time(claimed_at)
    if not worker_id.strip() or len(worker_id) > 200:
        raise ValueError("worker_id must contain 1 to 200 characters")
    query = select(job_runs).where(
        or_(
            job_runs.c.status == "queued",
            and_(
                job_runs.c.status == "retry_wait",
                or_(
                    job_runs.c.next_retry_at.is_(None),
                    job_runs.c.next_retry_at <= claimed_at,
                ),
            ),
            and_(job_runs.c.status == "running", job_runs.c.lease_expires_at <= claimed_at),
        )
    )
    if job_type is not None:
        query = query.where(job_runs.c.job_type == job_type)
    if job_id is not None:
        query = query.where(job_runs.c.job_id == job_id)
    while True:
        candidate = (
            session.execute(
                query.order_by(job_runs.c.created_at, job_runs.c.job_id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            .mappings()
            .first()
        )
        if candidate is None:
            return None
        row = dict(candidate)
        if int(candidate["attempt_count"]) >= int(candidate["max_attempts"]):
            session.execute(
                update(job_runs)
                .where(job_runs.c.job_id == candidate["job_id"])
                .values(
                    status="failed",
                    error_code="attempts_exhausted",
                    finished_at=claimed_at,
                    lease_owner=None,
                    lease_expires_at=None,
                    next_retry_at=None,
                    updated_at=claimed_at,
                )
            )
            record_job_transition(session, row, "failed", "attempts_exhausted", claimed_at)
            continue
        claimed = (
            session.execute(
                update(job_runs)
                .where(job_runs.c.job_id == candidate["job_id"])
                .values(
                    status="running",
                    lease_owner=worker_id,
                    lease_expires_at=claimed_at + timedelta(seconds=LEASE_SECONDS),
                    attempt_count=int(candidate["attempt_count"]) + 1,
                    started_at=claimed_at,
                    finished_at=None,
                    next_retry_at=None,
                    error_code=None,
                    updated_at=claimed_at,
                )
                .returning(job_runs)
            )
            .mappings()
            .one()
        )
        transition = dict(row, attempt_count=claimed["attempt_count"])
        record_job_transition(session, transition, "running", "claimed", claimed_at)
        return dict(claimed)


def claim_next_job(
    session: Session,
    worker_id: str,
    claimed_at: datetime,
    job_type: str | None = None,
) -> dict[str, object] | None:
    """锁定已到期任务，跳过其他事务锁并返回更新后的attempt。"""
    return _claim_job(session, worker_id, claimed_at, job_type=job_type)


def claim_job(
    session: Session,
    job_id: str,
    worker_id: str,
    claimed_at: datetime,
) -> dict[str, object] | None:
    """固定Celery任务按job_id认领，重复消息不能重新认领有效租约。"""
    return _claim_job(session, worker_id, claimed_at, job_id=job_id)


def require_job_lease(
    session: Session,
    job_id: str,
    worker_id: str,
    at: datetime,
    *,
    expected_attempt: int,
) -> dict[str, object]:
    require_aware_time(at)
    row = (
        session.execute(
            select(job_runs)
            .where(
                job_runs.c.job_id == job_id,
                job_runs.c.status == "running",
                job_runs.c.lease_owner == worker_id,
                job_runs.c.attempt_count == expected_attempt,
                job_runs.c.lease_expires_at > at,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if row is None:
        raise JobLeaseLostError("job lease unavailable")
    return dict(row)


def renew_lease(
    session: Session,
    job_id: str,
    worker_id: str,
    renewed_at: datetime,
    *,
    expected_attempt: int,
) -> None:
    require_job_lease(session, job_id, worker_id, renewed_at, expected_attempt=expected_attempt)
    session.execute(
        update(job_runs)
        .where(job_runs.c.job_id == job_id)
        .values(
            lease_expires_at=renewed_at + timedelta(seconds=LEASE_SECONDS),
            updated_at=renewed_at,
        )
    )


def complete_job(
    session: Session,
    job_id: str,
    worker_id: str,
    outcome: str,
    completed_at: datetime,
    *,
    expected_attempt: int,
    result_ref: str | None = None,
    error_code: str | None = None,
) -> None:
    """完成状态与同Session业务效果原子提交；到期未被接管也拒绝旧提交。"""
    if outcome not in {"succeeded", "partial", "failed", "blocked"}:
        raise ValueError("unsupported job outcome")
    validate_job_result_fields(result_ref, error_code)
    row = require_job_lease(
        session, job_id, worker_id, completed_at, expected_attempt=expected_attempt
    )
    session.execute(
        update(job_runs)
        .where(job_runs.c.job_id == job_id)
        .values(
            status=outcome,
            lease_owner=None,
            lease_expires_at=None,
            next_retry_at=None,
            updated_at=completed_at,
            finished_at=completed_at,
            result_ref=result_ref,
            error_code=error_code,
        )
    )
    record_job_transition(session, row, outcome, error_code or "completed", completed_at)


def schedule_retry_or_fail(
    session: Session,
    job_id: str,
    worker_id: str,
    permanent: bool,
    failed_at: datetime,
    *,
    expected_attempt: int,
    error_code: str = "job_execution_failed",
    blocked: bool = False,
    retry_after_seconds: float | None = None,
) -> str:
    """PG唯一重试层保存到期时间和可重投outbox；永久认证错误可标blocked。"""
    validate_job_result_fields(None, error_code)
    row = require_job_lease(
        session, job_id, worker_id, failed_at, expected_attempt=expected_attempt
    )
    attempt_count = row["attempt_count"]
    max_attempts = row["max_attempts"]
    if not isinstance(attempt_count, int) or not isinstance(max_attempts, int):
        raise RuntimeError("job row violates attempt contract")
    if permanent or blocked or attempt_count >= max_attempts:
        outcome = "blocked" if blocked else "failed"
        complete_job(
            session,
            job_id,
            worker_id,
            outcome,
            failed_at,
            expected_attempt=expected_attempt,
            error_code=error_code,
        )
        return outcome
    retry_at = failed_at + timedelta(
        seconds=retry_delay_seconds(attempt_count, retry_after_seconds)
    )
    session.execute(
        update(job_runs)
        .where(job_runs.c.job_id == job_id)
        .values(
            status="retry_wait",
            lease_owner=None,
            lease_expires_at=None,
            next_retry_at=retry_at,
            error_code=error_code,
            updated_at=failed_at,
        )
    )
    session.execute(
        insert(outbox_events).values(
            event_id=str(uuid4()),
            job_id=job_id,
            topic="job." + str(row["job_type"]),
            payload_ref=row["payload_ref"],
            created_at=failed_at,
            next_delivery_at=retry_at,
        )
    )
    record_job_transition(session, row, "retry_wait", error_code, failed_at)
    return "retry_wait"


def read_job_payload(session: Session, job_id: str, scope_tenant_id: str | None) -> bytes:
    """仅解析同范围PG引用并核对digest，不允许任意URI或旧hash猜测。"""
    row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().first()
    if row is None or row["tenant_id"] != scope_tenant_id:
        raise JobPayloadUnavailableError("job_payload_scope_denied")
    reference = str(row["payload_ref"])
    if reference.startswith("pg:job:"):
        if reference != "pg:job:" + job_id:
            raise JobPayloadUnavailableError("job_payload_reference_invalid")
        payload = session.execute(
            select(job_payloads.c.payload).where(job_payloads.c.job_id == job_id)
        ).scalar_one_or_none()
        if payload is None:
            raise JobPayloadUnavailableError("job_payload_unavailable")
        encoded = bytes(payload)
    elif reference.startswith("pg:change:"):
        change_id = reference.removeprefix("pg:change:")
        try:
            UUID(change_id)
        except ValueError:
            raise JobPayloadUnavailableError("job_payload_reference_invalid") from None
        scope_key = "public" if scope_tenant_id is None else "tenant:" + scope_tenant_id
        change = session.execute(
            select(change_events.c.payload).where(
                change_events.c.change_id == change_id,
                change_events.c.scope_key == scope_key,
            )
        ).scalar_one_or_none()
        if change is None:
            raise JobPayloadUnavailableError("job_payload_scope_denied")
        encoded = json.dumps(
            change, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    else:
        raise JobPayloadUnavailableError("legacy_job_payload_unavailable")
    if len(encoded) > 1048576 or hashlib.sha256(encoded).hexdigest() != row["payload_sha256"]:
        raise JobPayloadUnavailableError("job_payload_digest_mismatch")
    return encoded


def recover_expired_job_deliveries(session: Session, at: datetime, *, limit: int = 100) -> int:
    """PG补偿过期租约或已发布但未认领的投递，不增加job/attempt/预算。

    每job既有broker尝试之和最多max_attempts×3。停止消息保留未发布事实，
    以固定远期时间隔离；不会把认领前PG失败变成不可见的永久queued。
    """
    require_aware_time(at)
    if not 1 <= limit <= 1000:
        raise ValueError("recovery limit must be between 1 and 1000")
    stopped: list[str] = list(
        session.execute(
            select(outbox_events.c.event_id)
            .join(job_runs, job_runs.c.job_id == outbox_events.c.job_id)
            .where(
                outbox_events.c.published_at.is_(None),
                or_(
                    outbox_events.c.next_delivery_at.is_(None),
                    outbox_events.c.next_delivery_at < DELIVERY_STOPPED_AT,
                ),
                job_runs.c.status.in_(TERMINAL_JOB_STATUSES),
            )
            .limit(limit)
            .with_for_update(of=outbox_events, skip_locked=True)
        )
        .scalars()
        .all()
    )
    if stopped:
        session.execute(
            update(outbox_events)
            .where(outbox_events.c.event_id.in_(stopped))
            .values(next_delivery_at=DELIVERY_STOPPED_AT, last_error_code="job_delivery_stopped")
        )
    delivery_statistics = (
        select(
            outbox_events.c.job_id,
            func.sum(outbox_events.c.delivery_attempts).label("delivery_attempts"),
            func.max(outbox_events.c.published_at).label("latest_published_at"),
            func.sum(
                case(
                    (
                        and_(
                            outbox_events.c.published_at.is_(None),
                            or_(
                                outbox_events.c.next_delivery_at.is_(None),
                                outbox_events.c.next_delivery_at < DELIVERY_STOPPED_AT,
                            ),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("pending_count"),
        )
        .group_by(outbox_events.c.job_id)
        .subquery()
    )
    delivery_count = func.coalesce(delivery_statistics.c.delivery_attempts, 0)
    latest_reference = func.coalesce(
        delivery_statistics.c.latest_published_at, job_runs.c.created_at
    )
    effective_pending = func.coalesce(delivery_statistics.c.pending_count, 0) > 0
    lease_expired = and_(job_runs.c.status == "running", job_runs.c.lease_expires_at <= at)
    awaiting_claim = or_(
        job_runs.c.status == "queued",
        and_(
            job_runs.c.status == "retry_wait",
            or_(job_runs.c.next_retry_at.is_(None), job_runs.c.next_retry_at <= at),
        ),
    )
    rows = (
        session.execute(
            select(job_runs, delivery_count.label("broker_delivery_attempts"))
            .outerjoin(delivery_statistics, delivery_statistics.c.job_id == job_runs.c.job_id)
            .where(
                or_(awaiting_claim, lease_expired),
                or_(
                    delivery_count >= job_runs.c.max_attempts * DELIVERY_ATTEMPTS_PER_JOB_ATTEMPT,
                    lease_expired,
                    and_(
                        latest_reference <= at - timedelta(seconds=DELIVERY_RECOVERY_GRACE_SECONDS),
                        ~effective_pending,
                    ),
                ),
            )
            .order_by(job_runs.c.updated_at, job_runs.c.job_id)
            .limit(limit)
            .with_for_update(of=job_runs, skip_locked=True)
        )
        .mappings()
        .all()
    )
    recovered = 0
    for row in rows:
        reason = None
        if int(row["attempt_count"]) >= int(row["max_attempts"]):
            reason = "attempts_exhausted"
        elif int(row["broker_delivery_attempts"]) >= (
            int(row["max_attempts"]) * DELIVERY_ATTEMPTS_PER_JOB_ATTEMPT
        ):
            reason = "delivery_attempts_exhausted"
        if reason is not None:
            session.execute(
                update(job_runs)
                .where(job_runs.c.job_id == row["job_id"])
                .values(
                    status="failed",
                    error_code=reason,
                    finished_at=at,
                    lease_owner=None,
                    lease_expires_at=None,
                    updated_at=at,
                )
            )
            record_job_transition(session, dict(row), "failed", reason, at)
            session.execute(
                update(outbox_events)
                .where(
                    outbox_events.c.job_id == row["job_id"], outbox_events.c.published_at.is_(None)
                )
                .values(next_delivery_at=DELIVERY_STOPPED_AT, last_error_code=reason)
            )
            continue
        pending = session.execute(
            select(outbox_events.c.event_id)
            .where(
                outbox_events.c.job_id == row["job_id"],
                outbox_events.c.published_at.is_(None),
                or_(
                    outbox_events.c.next_delivery_at.is_(None),
                    outbox_events.c.next_delivery_at < DELIVERY_STOPPED_AT,
                ),
            )
            .limit(1)
        ).scalar_one_or_none()
        if pending is None:
            session.execute(
                insert(outbox_events).values(
                    event_id=str(uuid4()),
                    job_id=row["job_id"],
                    topic="job." + row["job_type"],
                    payload_ref=row["payload_ref"],
                    created_at=at,
                )
            )
            recovered += 1
    return recovered


def cancel_job_with_scope(
    session: Session,
    job_id: str,
    scope: AccessScope,
    cancelled_at: datetime,
) -> None:
    require_aware_time(cancelled_at)
    session.execute(select(job_runs.c.job_id).where(job_runs.c.job_id == job_id).with_for_update())
    row = read_job_with_scope(session, job_id, scope)
    scope.requires(WRITE_ASSET)
    if row["status"] in {"succeeded", "partial", "failed", "cancelled", "blocked"}:
        raise ValueError("job already finished")
    session.execute(
        update(job_runs)
        .where(job_runs.c.job_id == job_id)
        .values(
            status="cancelled",
            lease_owner=None,
            lease_expires_at=None,
            next_retry_at=None,
            finished_at=cancelled_at,
            updated_at=cancelled_at,
        )
    )
    record_job_transition(session, row, "cancelled", "cancelled", cancelled_at)


def read_job_with_scope(session: Session, job_id: str, scope: AccessScope) -> dict[str, object]:
    row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().first()
    if row is None or not scope.can_access(
        "tenant" if row["tenant_id"] is not None else "public",
        row["tenant_id"],
    ):
        raise CrossTenantAccessError("resource not found")
    return dict(row)
