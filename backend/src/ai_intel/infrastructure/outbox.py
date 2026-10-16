"""事务内保存可恢复任务输入，实际broker发布成功后确认outbox。"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.orm import Session

from ai_intel.knowledge.models import job_payloads, job_runs, outbox_events

MAX_JOB_PAYLOAD_BYTES = 1048576
EventPublisher = Callable[[dict[str, str]], None]


class IdempotencyConflictError(ValueError):
    """同scope/type/key输入不同，保留原请求并返回409语义。"""


def enqueue_job(
    session: Session,
    tenant_id: str | None,
    job_type: str,
    payload: bytes,
    created_at: datetime,
    idempotency_key: str | None = None,
    max_attempts: int = 5,
) -> str:
    """同事务保存job/payload/outbox；PG事务锁协调并发幂等与回滚。"""
    if tenant_id is not None and (not tenant_id.strip() or len(tenant_id) > 200):
        raise ValueError("invalid tenant scope")
    if not job_type.strip() or len(job_type) > 120:
        raise ValueError("invalid job type")
    if not isinstance(payload, bytes) or len(payload) > MAX_JOB_PAYLOAD_BYTES:
        raise ValueError("job payload must be bytes with maximum size 1 MiB")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("job timestamps require timezone")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
        raise ValueError("max_attempts must be between 1 and 10")
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    if idempotency_key is not None:
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ValueError("invalid idempotency key")
        scope_identity = repr((tenant_id, job_type, idempotency_key)).encode("utf-8")
        lock_id = int.from_bytes(hashlib.sha256(scope_identity).digest()[:8], "big", signed=True)
        session.execute(select(func.pg_advisory_xact_lock(lock_id)))
        scope_clause = (
            job_runs.c.tenant_id.is_(None)
            if tenant_id is None
            else (job_runs.c.tenant_id == tenant_id)
        )
        existing = (
            session.execute(
                select(job_runs).where(
                    scope_clause,
                    job_runs.c.job_type == job_type,
                    job_runs.c.idempotency_key == idempotency_key,
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            if existing["payload_sha256"] != payload_sha256:
                raise IdempotencyConflictError("idempotency key reused with different payload")
            return str(existing["job_id"])
    job_id = str(uuid4())
    payload_ref = "pg:job:" + job_id
    session.execute(
        insert(job_runs).values(
            job_id=job_id,
            tenant_id=tenant_id,
            job_type=job_type,
            status="queued",
            idempotency_key=idempotency_key,
            payload_sha256=payload_sha256,
            payload_ref=payload_ref,
            attempt_count=0,
            max_attempts=max_attempts,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.execute(
        insert(job_payloads).values(
            job_id=job_id,
            payload=payload,
            created_at=created_at,
        )
    )
    session.execute(
        insert(outbox_events).values(
            event_id=str(uuid4()),
            job_id=job_id,
            topic="job." + job_type,
            payload_ref=payload_ref,
            created_at=created_at,
        )
    )
    return job_id


def relay_pending_events(
    session: Session,
    published_at: datetime,
    *,
    publisher: EventPublisher,
    limit: int = 100,
) -> list[dict[str, str]]:
    """仅发布权威job仍可投递且引用一致的事件，同行锁隔离取消与双发。"""
    if not 1 <= limit <= 1000:
        raise ValueError("outbox limit must be between 1 and 1000")
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ValueError("outbox timestamps require timezone")
    pending = (
        session.execute(
            select(outbox_events)
            .join(job_runs, job_runs.c.job_id == outbox_events.c.job_id)
            .where(
                job_runs.c.status.in_(("queued", "retry_wait", "running")),
                outbox_events.c.payload_ref == job_runs.c.payload_ref,
                outbox_events.c.published_at.is_(None),
                or_(
                    outbox_events.c.next_delivery_at.is_(None),
                    outbox_events.c.next_delivery_at <= published_at,
                ),
            )
            .order_by(outbox_events.c.created_at, outbox_events.c.event_id)
            .limit(limit)
            .with_for_update(of=(job_runs, outbox_events), skip_locked=True)
        )
        .mappings()
        .all()
    )
    released: list[dict[str, str]] = []
    for row in pending:
        event = {key: str(row[key]) for key in ("event_id", "job_id", "topic", "payload_ref")}
        attempts = int(row["delivery_attempts"]) + 1
        try:
            publisher(event)
        except Exception:
            session.execute(
                update(outbox_events)
                .where(
                    outbox_events.c.event_id == row["event_id"],
                )
                .values(
                    delivery_attempts=attempts,
                    last_error_code="broker_publish_failed",
                    next_delivery_at=published_at
                    + timedelta(seconds=min(300, 5 * 2 ** min(attempts - 1, 6))),
                )
            )
            continue
        session.execute(
            update(outbox_events)
            .where(
                outbox_events.c.event_id == row["event_id"],
            )
            .values(
                published_at=published_at,
                delivery_attempts=attempts,
                next_delivery_at=None,
                last_error_code=None,
            )
        )
        released.append(event)
    return released
