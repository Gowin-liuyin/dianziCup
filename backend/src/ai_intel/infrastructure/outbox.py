"""事务 outbox: 业务记录与事件同事务提交, relay 只发布引用与最小元数据。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from ai_intel.knowledge.models import job_runs, outbox_events


class IdempotencyConflictError(ValueError):
    """相同幂等键不同 payload: 409 语义, 不覆盖原请求。"""


def enqueue_job(
    session: Session,
    tenant_id: str | None,
    job_type: str,
    payload: bytes,
    created_at: datetime,
    idempotency_key: str | None = None,
    max_attempts: int = 5,
) -> str:
    """把业务任务与 outbox 事件同事务提交; 幂等键重复按 payload 判定复用或 409。"""
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    if idempotency_key is not None:
        existing = (
            session.execute(select(job_runs).where(job_runs.c.idempotency_key == idempotency_key))
            .mappings()
            .first()
        )
        if existing is not None:
            if existing["payload_sha256"] != payload_sha256:
                raise IdempotencyConflictError("idempotency key reused with different payload")
            return str(existing["job_id"])
    job_id = str(uuid.uuid4())
    session.execute(
        insert(job_runs).values(
            job_id=job_id,
            tenant_id=tenant_id,
            job_type=job_type,
            status="queued",
            idempotency_key=idempotency_key,
            payload_sha256=payload_sha256,
            payload_ref=payload_sha256,
            attempt_count=0,
            max_attempts=max_attempts,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.execute(
        insert(outbox_events).values(
            event_id=str(uuid.uuid4()),
            job_id=job_id,
            topic=f"job.{job_type}",
            payload_ref=payload_sha256,
            created_at=created_at,
        )
    )
    return job_id


def relay_pending_events(session: Session, published_at: datetime) -> list[dict[str, str]]:
    """relay: 只发布引用与最小元数据; 重复 relay 幂等(只取未发布)。"""
    pending = (
        session.execute(
            select(outbox_events)
            .where(outbox_events.c.published_at.is_(None))
            .order_by(outbox_events.c.created_at)
        )
        .mappings()
        .all()
    )
    released: list[dict[str, str]] = []
    for event in pending:
        session.execute(
            update(outbox_events)
            .where(outbox_events.c.event_id == event["event_id"])
            .values(published_at=published_at),
        )
        released.append(
            {
                "event_id": str(event["event_id"]),
                "job_id": str(event["job_id"]),
                "topic": str(event["topic"]),
                "payload_ref": str(event["payload_ref"]),
            }
        )
    return released
