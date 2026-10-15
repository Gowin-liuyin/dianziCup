"""Real forward migration and independent reservations preserve the existing job authority."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r07_enrichment_inputs_pg import seeded_event

from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import job_runs, users

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, tzinfo=UTC)


def seed_workflow(engine, tmp_path):
    _, event_id = seeded_event(engine, tmp_path)
    actor, workflow = str(uuid4()), str(uuid4())
    with Session(engine) as session, session.begin():
        session.execute(
            insert(users).values(
                user_id=actor,
                username="synthetic-job-" + actor,
                password_hash="unusable synthetic hash",
                tenant_id=None,
                role="system_admin",
                created_at=NOW,
            )
        )
        parent = enqueue_job(session, None, "event_enrichment_dispatch", b"{}", NOW)
        session.execute(
            insert(enrichment_workflows).values(
                workflow_id=workflow,
                parent_job_id=parent,
                actor_user_id=actor,
                actor_session_hash=hashlib.sha256(b"synthetic-session").hexdigest(),
                actor_role="system_admin",
                event_id=str(event_id),
                visibility="public",
                request_payload={"expected_event_version": 1, "dimensions": ["versions"]},
                request_sha256="a" * 64,
                rule_version="r07-enrichment-workflow-1",
                created_at=NOW,
            )
        )
        child = enqueue_job(session, None, "event_enrichment_dimension", b"{}", NOW, max_attempts=1)
        session.execute(
            insert(enrichment_job_steps).values(
                job_id=child,
                workflow_id=workflow,
                step_key="versions",
                dimension="versions",
                output_token_budget=1024,
                created_at=NOW,
            )
        )
    return workflow, parent, child


def test_forward_migration_exposes_metadata_without_a_duplicate_job_status(catalog_engine):
    tables = set(inspect(catalog_engine).get_table_names())
    assert {"enrichment_workflows", "enrichment_job_steps", "job_runs"} <= tables
    for name in ("enrichment_workflows", "enrichment_job_steps"):
        assert "status" not in {row["name"] for row in inspect(catalog_engine).get_columns(name)}
    with catalog_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0017_enrichment_job_workflows"
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"input_context": {}},
        {"input_context": {}, "initialized_at": NOW},
        {"input_context": {}, "input_fingerprint": "b" * 64},
        {"input_fingerprint": "b" * 64},
        {"actor_session_hash": "raw-cookie-is-not-a-hash"},
        {"visibility": "tenant", "tenant_id": None},
        {"visibility": "public", "tenant_id": "other"},
        {"actor_permission_version": 0},
        {"execution_policy": []},
        {"execution_policy_sha256": "unknown"},
    ],
)
def test_workflow_incomplete_or_invalid_identity_is_rejected(catalog_engine, tmp_path, changes):
    workflow, _, _ = seed_workflow(catalog_engine, tmp_path)
    with pytest.raises(IntegrityError), catalog_engine.begin() as connection:
        connection.execute(
            update(enrichment_workflows)
            .where(enrichment_workflows.c.workflow_id == workflow)
            .values(**changes)
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"dimension": None, "step_key": "invalid"},
        {"dimension": None, "step_key": "exposure:hunter", "provider": "hunter"},
        {"dimension": "exposure", "step_key": "exposure:unknown", "provider": "unknown"},
        {"result_payload": {}, "result_recorded_at": NOW},
        {"result_payload": {}, "result_sha256": "a" * 64},
        {"model_call_completed_at": NOW},
        {"output_token_budget": 4096},
        {
            "dimension": "exposure",
            "step_key": "exposure",
            "output_token_budget": 0,
            "model_call_reserved_at": NOW,
        },
    ],
)
def test_step_invalid_nullable_combinations_do_not_bypass_pg_checks(
    catalog_engine, tmp_path, changes
):
    _, _, child = seed_workflow(catalog_engine, tmp_path)
    with pytest.raises(IntegrityError), catalog_engine.begin() as connection:
        connection.execute(
            update(enrichment_job_steps)
            .where(enrichment_job_steps.c.job_id == child)
            .values(**changes)
        )


def test_external_reservation_does_not_wait_for_the_handler_job_row(catalog_engine, tmp_path):
    _, _, child = seed_workflow(catalog_engine, tmp_path)

    def reserve():
        with catalog_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '1000ms'"))
            changed = connection.execute(
                update(enrichment_job_steps)
                .where(
                    enrichment_job_steps.c.job_id == child,
                    enrichment_job_steps.c.model_call_reserved_at.is_(None),
                )
                .values(model_call_reserved_at=NOW)
                .returning(enrichment_job_steps.c.job_id)
            ).scalar_one()
            return changed

    with Session(catalog_engine) as session, session.begin():
        session.execute(select(job_runs).where(job_runs.c.job_id == child).with_for_update()).one()
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(reserve).result(timeout=3) == child
    with catalog_engine.connect() as connection:
        assert (
            connection.scalar(
                select(enrichment_job_steps.c.model_call_reserved_at).where(
                    enrichment_job_steps.c.job_id == child
                )
            )
            == NOW
        )
