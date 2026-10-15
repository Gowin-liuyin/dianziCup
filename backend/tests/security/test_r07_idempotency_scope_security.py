"""Unknown or tampered history fails closed and request bodies cannot grant event access."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from tests.r07_idempotency_scope_helpers import (
    NOW,
    create_actor,
    queue,
    queue_legacy,
    setup_scope,
)
from tests.r07_idempotency_scope_helpers import (
    scope_engine as scope_engine,
)

from ai_intel.domain.access import CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.enrichment.job_contracts import EventEnrichmentRequest
from ai_intel.enrichment.job_models import enrichment_workflows
from ai_intel.enrichment.job_service import ENRICHMENT_PARENT_JOB_TYPE
from ai_intel.infrastructure.outbox import IdempotencyConflictError, enqueue_job
from ai_intel.knowledge.models import job_payloads, job_runs
from ai_intel.knowledge.persistence_models import events

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize(
    "tamper", ["request", "policy", "binding_actor", "workflow_uuid", "payload", "orphan"]
)
def test_expected_legacy_parent_corruption_cannot_create_or_reuse_an_operation(
    scope_engine, tmp_path, tamper
):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    if tamper == "orphan":
        with Session(scope_engine) as session, session.begin():
            enqueue_job(
                session,
                None,
                ENRICHMENT_PARENT_JOB_TYPE,
                b"{}",
                NOW,
                idempotency_key="synthetic-shared-key",
            )
    else:
        _, parent_id = queue_legacy(service, scope, session_hash, event_id, request)
        with scope_engine.begin() as connection:
            if tamper == "request":
                connection.execute(
                    update(enrichment_workflows).values(
                        request_payload={"expected_event_version": 1, "dimensions": ["cvss"]}
                    )
                )
            elif tamper == "policy":
                connection.execute(
                    update(enrichment_workflows).values(execution_policy={"data_mode": "live"})
                )
            elif tamper == "binding_actor":
                other, _ = create_actor(scope_engine)
                connection.execute(update(enrichment_workflows).values(actor_user_id=other.user_id))
            elif tamper == "workflow_uuid":
                connection.execute(update(enrichment_workflows).values(workflow_id=str(uuid4())))
            else:
                connection.execute(
                    update(job_payloads)
                    .where(job_payloads.c.job_id == str(parent_id))
                    .values(payload=b"{}")
                )
    with pytest.raises(IdempotencyConflictError):
        queue(service, scope, session_hash, event_id, request)
    with Session(scope_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(job_runs)
                .where(job_runs.c.job_type == ENRICHMENT_PARENT_JOB_TYPE)
            )
            == 1
        )


def test_tampered_v2_record_with_internal_prefix_is_not_accepted_as_an_alias(
    scope_engine, tmp_path
):
    service, scope, session_hash, event_id, request = setup_scope(scope_engine, tmp_path)
    first = queue(service, scope, session_hash, event_id, request)
    with Session(scope_engine) as session:
        key = session.scalar(
            select(job_runs.c.idempotency_key).where(job_runs.c.job_id == str(first.parent_job_id))
        )
    with scope_engine.begin() as connection:
        connection.execute(update(enrichment_workflows).values(request_sha256="a" * 64))
    with pytest.raises(IdempotencyConflictError):
        queue(service, scope, session_hash, event_id, request, key)


def test_private_event_cross_tenant_and_public_write_roles_are_not_granted_by_key(
    scope_engine, tmp_path
):
    service, admin, admin_session, event_id, request = setup_scope(scope_engine, tmp_path)
    tenant_admin, tenant_session = create_actor(
        scope_engine, tenant_id="synthetic-tenant", role=Role.TENANT_ADMIN
    )
    with pytest.raises(PermissionDeniedError):
        queue(service, tenant_admin, tenant_session, event_id, request)
    with scope_engine.begin() as connection:
        connection.execute(update(events).values(visibility="tenant", tenant_id="synthetic-tenant"))
    with pytest.raises(CrossTenantAccessError):
        queue(service, admin, admin_session, event_id, request)
    private = queue(service, tenant_admin, tenant_session, event_id, request)
    with Session(scope_engine) as session:
        assert (
            session.scalar(
                select(job_runs.c.tenant_id).where(job_runs.c.job_id == str(private.parent_job_id))
            )
            == "synthetic-tenant"
        )
    with pytest.raises(ValidationError):
        EventEnrichmentRequest.model_validate(
            {"expected_event_version": 1, "tenant_id": "synthetic-tenant", "role": "system_admin"}
        )
