"""幂等工作进程: 唯一键认领、租约续期、有限重试与丢失 worker 恢复。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ai_intel.domain.access import (
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
)
from ai_intel.knowledge.models import job_runs

LEASE_SECONDS = 60


class JobLeaseLostError(RuntimeError):
    """租约过期或被回收: 提交被拒, 任务留给恢复流程, 不重复业务写入。"""


def claim_next_job(
    session: Session,
    worker_id: str,
    claimed_at: datetime,
    job_type: str | None = None,
) -> dict[str, object] | None:
    """以唯一键认领到期任务(queued/retry_wait/租约过期), 成功者独占租约。"""
    candidate_query = select(job_runs).where(
        (job_runs.c.status.in_(("queued", "retry_wait")))
        | ((job_runs.c.status == "running") & (job_runs.c.lease_expires_at < claimed_at))
    )
    if job_type is not None:
        candidate_query = candidate_query.where(job_runs.c.job_type == job_type)
    candidates = (
        session.execute(candidate_query.order_by(job_runs.c.created_at).limit(1)).mappings().all()
    )
    if not candidates:
        return None
    candidate = candidates[0]
    claimed_rows = session.execute(
        update(job_runs)
        .where(
            job_runs.c.job_id == candidate["job_id"],
            job_runs.c.lease_expires_at.is_(None) | (job_runs.c.lease_expires_at < claimed_at),
        )
        .values(
            status="running",
            lease_owner=worker_id,
            lease_expires_at=claimed_at + timedelta(seconds=LEASE_SECONDS),
            attempt_count=int(candidate["attempt_count"]) + 1,
            updated_at=claimed_at,
        )
        .returning(job_runs.c.job_id)
    ).all()
    if not claimed_rows:
        return None
    return dict(candidate)


def renew_lease(session: Session, job_id: str, worker_id: str, renewed_at: datetime) -> None:
    """租约续期: 非持有者或已过期回收则拒绝。"""
    renewed_rows = session.execute(
        update(job_runs)
        .where(
            job_runs.c.job_id == job_id,
            job_runs.c.lease_owner == worker_id,
            job_runs.c.lease_expires_at > renewed_at,
        )
        .values(
            lease_expires_at=renewed_at + timedelta(seconds=LEASE_SECONDS),
            updated_at=renewed_at,
        )
        .returning(job_runs.c.job_id)
    ).all()
    if not renewed_rows:
        raise JobLeaseLostError(job_id)


def complete_job(
    session: Session, job_id: str, worker_id: str, outcome: str, completed_at: datetime
) -> None:
    """成功/部分完成/失败收尾: 校验租约持有者。"""
    if outcome not in {"succeeded", "partial", "failed", "blocked"}:
        raise ValueError(f"unsupported outcome: {outcome}")
    finished_rows = session.execute(
        update(job_runs)
        .where(job_runs.c.job_id == job_id, job_runs.c.lease_owner == worker_id)
        .values(
            status=outcome,
            lease_owner=None,
            lease_expires_at=None,
            updated_at=completed_at,
        )
        .returning(job_runs.c.job_id)
    ).all()
    if not finished_rows:
        raise JobLeaseLostError(job_id)


def schedule_retry_or_fail(
    session: Session, job_id: str, worker_id: str, permanent: bool, failed_at: datetime
) -> str:
    """重试分类: 永久错误直接 failed; 否则有限重试进入 retry_wait。"""
    row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().first()
    if row is None:
        raise LookupError(job_id)
    if permanent or int(row["attempt_count"]) >= int(row["max_attempts"]):
        complete_job(session, job_id, worker_id, "failed", failed_at)
        return "failed"
    retried_rows = session.execute(
        update(job_runs)
        .where(job_runs.c.job_id == job_id, job_runs.c.lease_owner == worker_id)
        .values(
            status="retry_wait",
            lease_owner=None,
            lease_expires_at=None,
            updated_at=failed_at,
        )
        .returning(job_runs.c.job_id)
    ).all()
    if not retried_rows:
        raise JobLeaseLostError(job_id)
    return "retry_wait"


def cancel_job_with_scope(
    session: Session, job_id: str, scope: AccessScope, cancelled_at: datetime
) -> None:
    """取消任务: 先查范围; 他人任务统一 404 语义, 不泄露任务参数。"""
    row = session.execute(
        select(job_runs.c.tenant_id, job_runs.c.status).where(job_runs.c.job_id == job_id)
    ).first()
    if row is None:
        raise CrossTenantAccessError("resource not found")
    job_tenant = row[0]
    job_tenant_id = str(job_tenant) if job_tenant is not None else None
    if not scope.can_access("tenant" if job_tenant_id is not None else "public", job_tenant_id):
        raise CrossTenantAccessError("resource not found")
    scope.requires(WRITE_ASSET)
    if str(row[1]) in {"succeeded", "failed", "cancelled"}:
        raise ValueError(f"job already finished: {row[1]}")
    session.execute(
        update(job_runs)
        .where(job_runs.c.job_id == job_id)
        .values(
            status="cancelled",
            lease_owner=None,
            lease_expires_at=None,
            updated_at=cancelled_at,
        ),
    )


def read_job_with_scope(session: Session, job_id: str, scope: AccessScope) -> dict[str, object]:
    """读取任务: 跨租户猜测他人 job_id 返回 404 语义且无参数泄露。"""
    row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().first()
    if row is None:
        raise CrossTenantAccessError("resource not found")
    raw_tenant = row["tenant_id"]
    job_tenant_id = str(raw_tenant) if raw_tenant is not None else None
    if not scope.can_access("tenant" if job_tenant_id is not None else "public", job_tenant_id):
        raise CrossTenantAccessError("resource not found")
    return dict(row)
