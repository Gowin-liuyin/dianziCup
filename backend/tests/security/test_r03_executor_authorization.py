"""PG任务范围、固定handler与payload输入身份的实际拒绝回归。"""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import fetch_attempts, job_runs
from ai_intel.workers.executor import execute_job, record_source_fetch_failure
from ai_intel.workers.jobs import read_job_with_scope

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize("spoof_scope", [True, False])
def test_worker_denies_source_from_other_tenant_and_payload_self_authorization(
    migrated_engine,
    spoof_scope,
) -> None:
    now = datetime.now(UTC)
    source_id = str(uuid4())
    with Session(migrated_engine) as session, session.begin():
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES(:id,:name,'vendor_advisory','https://example.invalid','tenant','tenant-a',:at)"
            ),
            {"id": source_id, "name": "r03-security-" + source_id, "at": now},
        )
        payload = {"source_id": source_id, "observed_at": now.isoformat()}
        if spoof_scope:
            payload["tenant_id"] = "tenant-a"
        job_id = enqueue_job(
            session, "tenant-b", "record_source_fetch_failure", json.dumps(payload).encode(), now
        )
    assert (
        execute_job(
            migrated_engine,
            job_id,
            "trusted-worker",
            {"record_source_fetch_failure": record_source_fetch_failure},
        )
        == "blocked"
    )
    with Session(migrated_engine) as session:
        row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
        assert row["error_code"] == (
            "invalid_job_payload" if spoof_scope else "source_scope_denied"
        )
        assert (
            session.execute(
                select(func.count())
                .select_from(fetch_attempts)
                .where(fetch_attempts.c.source_id == source_id)
            ).scalar_one()
            == 0
        )
        outsider = AccessScope.for_authenticated_user("other-user", "tenant-a", Role.TENANT_ADMIN)
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            read_job_with_scope(session, job_id, outsider)


def test_topic_and_payload_reference_cannot_select_arbitrary_task_or_resource(
    migrated_engine,
) -> None:
    now = datetime.now(UTC)
    with Session(migrated_engine) as session, session.begin():
        job_id = enqueue_job(session, None, "fixture_supported", b"{}", now)
        session.execute(
            update(job_runs)
            .where(job_runs.c.job_id == job_id)
            .values(payload_ref="https://127.0.0.1/private")
        )
    reached_handler = []

    def forbidden_handler(session, context, payload):
        reached_handler.append(True)
        raise AssertionError("invalid reference was followed")

    assert (
        execute_job(
            migrated_engine, job_id, "trusted-worker", {"fixture_supported": forbidden_handler}
        )
        == "blocked"
    )
    assert reached_handler == []
