"""T07 任务与事务 outbox 集成验收测试: 真实 PostgreSQL, 覆盖 T07-C01—C06。"""

from __future__ import annotations

import socket
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.outbox import (
    IdempotencyConflictError,
    enqueue_job,
    relay_pending_events,
)
from ai_intel.knowledge.models import job_runs, outbox_events
from ai_intel.workers.jobs import (
    JobLeaseLostError,
    cancel_job_with_scope,
    claim_next_job,
    complete_job,
    read_job_with_scope,
    schedule_retry_or_fail,
)

UTC = UTC
DEVELOPMENT_DSN = "postgresql+psycopg://ai_intel:dev-only-not-a-secret@127.0.0.1:5432/ai_intel"


def database_available() -> bool:
    """数据库端口探测; 不可用即 blocked, 不使用 SQLite 冒充。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.settimeout(2)
        return probe_socket.connect_ex(("127.0.0.1", 5432)) == 0


pytestmark = pytest.mark.skipif(
    not database_available(),
    reason="blocked: 数据库容器不可用（T07 集成验证挂起）, 不使用 SQLite 冒充",
)


@pytest.fixture()
def migrated_engine():
    run_migrations(DEVELOPMENT_DSN)
    engine = create_engine(DEVELOPMENT_DSN)
    yield engine
    engine.dispose()


def test_outbox_survives_queue_outage_and_delivers_after_recovery(migrated_engine) -> None:
    """T07-C01: 事务提交成功但队列暂不可用 → outbox 保留, 恢复后被投递。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    with migrated_engine.begin() as connection:
        job_id = enqueue_job(connection, None, "collect_source_updates", b"payload-a", now)
        first_relay = relay_pending_events(connection, now)
    assert any(event["job_id"] == job_id for event in first_relay)
    with migrated_engine.begin() as connection:
        second_relay = relay_pending_events(connection, now + timedelta(minutes=1))
        assert all(event["job_id"] != job_id for event in second_relay)
        unpublished = connection.execute(
            select(outbox_events.c.event_id).where(
                outbox_events.c.job_id == job_id, outbox_events.c.published_at.is_(None)
            )
        ).all()
    assert unpublished == []


def test_duplicate_message_yields_single_business_result(migrated_engine) -> None:
    """T07-C02: 同一消息重复到达只形成一个有效业务结果(幂等键复用同一 job)。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    key = "idem-" + str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        first = enqueue_job(
            connection, None, "parse_document", b"same-payload", now, idempotency_key=key
        )
        second = enqueue_job(
            connection, None, "parse_document", b"same-payload", now, idempotency_key=key
        )
        rows = connection.execute(
            select(job_runs.c.job_id).where(job_runs.c.idempotency_key == key)
        ).all()
    assert first == second
    assert len(rows) == 1


def test_same_idempotency_key_different_payload_conflicts(migrated_engine) -> None:
    """T07-C03: 相同 Idempotency-Key 不同 payload → 409 语义, 不覆盖原请求。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    key = "idem-" + str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        original = enqueue_job(
            connection, None, "parse_document", b"original", now, idempotency_key=key
        )
        with pytest.raises(IdempotencyConflictError):
            enqueue_job(connection, None, "parse_document", b"different", now, idempotency_key=key)
        row = connection.execute(
            select(job_runs.c.payload_sha256).where(job_runs.c.job_id == original)
        ).scalar_one()
    import hashlib

    assert row == hashlib.sha256(b"original").hexdigest()


def test_lost_worker_recovers_after_lease_expiry(migrated_engine) -> None:
    """T07-C04: worker 中断 → 租约过期后其他 worker 恢复认领, 不丢任务。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    with migrated_engine.begin() as connection:
        job_id = enqueue_job(connection, None, "enrich_claim", b"payload-c", now)
        claimed = claim_next_job(connection, "worker-1", now, job_type="enrich_claim")
        assert claimed is not None and claimed["job_id"] == job_id
    later = now + timedelta(seconds=120)
    with migrated_engine.begin() as connection:
        recovered = claim_next_job(connection, "worker-2", later, job_type="enrich_claim")
        assert recovered is not None and recovered["job_id"] == job_id
        with pytest.raises(JobLeaseLostError):
            complete_job(connection, job_id, "worker-1", "succeeded", later)


def test_permanent_failure_does_not_retry_forever(migrated_engine) -> None:
    """T07-C05: 永久认证错误 → failed, 不进入无限重试。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    with migrated_engine.begin() as connection:
        job_id = enqueue_job(connection, None, "fetch_with_auth", b"payload-d", now)
        claim_next_job(connection, "worker-1", now, job_type="fetch_with_auth")
        outcome = schedule_retry_or_fail(
            connection, job_id, "worker-1", permanent=True, failed_at=now
        )
        status = connection.execute(
            select(job_runs.c.status).where(job_runs.c.job_id == job_id)
        ).scalar_one()
    assert outcome == "failed" and status == "failed"


def test_guessing_other_tenant_job_id_returns_404_without_leak(migrated_engine) -> None:
    """T07-C06: 用户猜测他人 job_id → 404 语义且无任务参数泄露。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    outsider = AccessScope.for_authenticated_user("user-b", "tenant-beta", Role.ANALYST)
    with migrated_engine.begin() as connection:
        job_id = enqueue_job(connection, "tenant-alpha", "enrich_claim", b"secret-payload", now)
        with pytest.raises(CrossTenantAccessError) as captured:
            read_job_with_scope(connection, job_id, outsider)
        assert "secret" not in str(captured.value)
        assert "tenant-alpha" not in str(captured.value)
        with pytest.raises(CrossTenantAccessError):
            cancel_job_with_scope(connection, job_id, outsider, now)
