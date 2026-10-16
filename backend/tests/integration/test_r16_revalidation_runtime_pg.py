"""Synthetic business inputs exercise real forward-migrated PG and trusted durable jobs."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from tests.integration import test_r16_assessment_candidates_pg as original_candidates
from tests.integration.test_r11_pg_assessments import assessor, asset, publish, seed

from ai_intel.api.actor_references import create_actor_reference
from ai_intel.api.credentials import SessionCredential
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.rule_service import RuleService
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import job_payloads, job_runs, users
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.revalidation.candidates import CandidateDiscoveryError
from ai_intel.revalidation.execution_contracts import ReassessmentRequest, RevalidationChangeRequest
from ai_intel.revalidation.runtime_policy import (
    enqueue_reassessment_plan,
    enqueue_revalidation_change,
    make_revalidation_job_handlers,
)
from ai_intel.revalidation.service import RevalidationError, RevalidationService
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg
RUN_ID = "r16_runtime_20261016"
KEY = SecretStr("01" * 32)


@pytest.fixture(scope="module")
def pg_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_" + RUN_ID
    assert url.host == "127.0.0.1" and url.port == 25432
    assert url.username and url.username.startswith("test_")
    assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID
    schema = "test_r16_runtime_" + uuid4().hex
    base = create_engine(url, hide_parameters=True, poolclass=NullPool)
    with base.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    base.dispose()
    migration_url = url.update_query_dict({"options": f"-c search_path={schema}"})
    run_migrations(migration_url.render_as_string(hide_password=False), "head")
    engine = create_engine(
        url.update_query_dict(
            {
                "options": f"-c search_path={schema},public "
                "-c statement_timeout=8000 -c lock_timeout=4000"
            }
        ),
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5, "application_name": RUN_ID},
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0030_revalidation_actor_bindings"
        )
    run = Path(os.environ["R16_RUNTIME_EVIDENCE_DIR"])
    (run / "schema_receipt.json").write_text(
        json.dumps(
            dict(
                schema=schema,
                database=url.database,
                revision="0030_revalidation_actor_bindings",
                synthetic=True,
                forward_only=True,
                retained=True,
                metadata_create_all=False,
                created_at=datetime.now(UTC).isoformat(),
                timestamp_timezone="UTC",
            ),
            indent=2,
        )
        + "\n"
    )
    yield engine
    engine.dispose()
    with base.connect() as connection:
        remaining = connection.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                "AND application_name=:run AND pid<>pg_backend_pid()"
            ),
            {"run": RUN_ID},
        )
    base.dispose()
    (run / "connection_audit.json").write_text(
        json.dumps(
            dict(
                remaining_owned_connections=remaining,
                schema_retained=schema,
                audited_at=datetime.now(UTC).isoformat(),
                timestamp_timezone="UTC",
            ),
            indent=2,
        )
        + "\n"
    )
    assert remaining == 0


@pytest.fixture(autouse=True)
def redact_owned_credentials(register_sensitive_failure_value):
    value = os.environ["TEST_DATABASE_URL"]
    register_sensitive_failure_value(SecretStr(value))
    password = make_url(value).password
    if password:
        register_sensitive_failure_value(SecretStr(password))


def actor_reference(engine, seeded):
    with engine.begin() as connection:
        return create_actor_reference(
            connection, SessionCredential(SecretStr(seeded["asset_token"])), datetime.now(UTC)
        )


def latest_change(engine, seeded):
    with engine.connect() as connection:
        return (
            connection.execute(
                select(change_events)
                .where(change_events.c.scope_key == "tenant:" + seeded["tenant"])
                .order_by(change_events.c.epoch.desc())
                .limit(1)
            )
            .mappings()
            .one()
        )


def service(engine, seeded):
    return RevalidationService(engine, actor_reference(engine, seeded), seeded["store"], KEY)


def queue_change(engine, seeded, **budgets):
    change = latest_change(engine, seeded)
    request = RevalidationChangeRequest(
        change_id=change["change_id"],
        target_epoch=change["epoch"],
        assessment_created_before=datetime.now(UTC),
        **budgets,
    )
    with Session(engine) as session, session.begin():
        actor = create_actor_reference(
            session.connection(),
            SessionCredential(SecretStr(seeded["asset_token"])),
            datetime.now(UTC),
        )
        job_id = enqueue_revalidation_change(session, actor, request, datetime.now(UTC))
    return job_id


def queue_child(engine, seeded):
    change = latest_change(engine, seeded)
    active_service = service(engine, seeded)
    plan = active_service.plan_change(change["change_id"], change["epoch"])
    with Session(engine) as session, session.begin():
        jobs = enqueue_reassessment_plan(session, active_service.actor, plan, datetime.now(UTC))
    assert len(jobs) == 1
    return jobs[0]


def row(engine, job_id):
    with engine.connect() as connection:
        return (
            connection.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
        )


def execute(engine, seeded, job_id):
    return execute_job(
        engine,
        job_id,
        "fixture-worker-" + uuid4().hex,
        make_revalidation_job_handlers(engine, seeded["store"], KEY),
    )


def drive(engine, seeded, *, limit=100):
    outcomes = []
    for _ in range(limit):
        with engine.connect() as connection:
            job = connection.scalar(
                select(job_runs.c.job_id)
                .where(
                    job_runs.c.tenant_id == seeded["tenant"],
                    job_runs.c.job_type.in_(("revalidate_change", "revalidate_assessment")),
                    job_runs.c.status == "queued",
                )
                .order_by(job_runs.c.created_at, job_runs.c.job_id)
                .limit(1)
            )
        if job is None:
            return outcomes
        outcomes.append((job, execute(engine, seeded, job)))
    raise AssertionError("owned finite work queue did not terminate")


def assessment_payloads(engine, seeded):
    with engine.connect() as connection:
        return (
            connection.execute(
                select(assessment_results.c.result_payload)
                .where(assessment_results.c.tenant_id == seeded["tenant"])
                .order_by(assessment_results.c.created_at)
            )
            .scalars()
            .all()
        )


def test_real_worker_recomputes_previously_unassessed_asset(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    job = queue_child(pg_engine, seeded)
    assert execute(pg_engine, seeded, job) == "succeeded"
    receipt = assessor(pg_engine, seeded).read(
        row(pg_engine, job)["result_ref"].removeprefix("pg:assessment:")
    )
    assert receipt.asset_snapshot_id == imported.snapshot.snapshot_id
    assert (
        receipt.status.value == "supported_applicability" and receipt.freshness.value == "current"
    )


def test_retirement_replaces_current_applicability_without_overwriting_old_history(
    pg_engine, tmp_path
):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    shared = assessor(pg_engine, seeded)
    old = shared.commit(
        shared.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    original = old.model_dump(mode="json")
    RuleService(pg_engine, seeded["reviewer_token"], seeded["store"]).retire(
        seeded["rule"].rule_id, 1
    )
    queue_change(pg_engine, seeded)
    outcomes = drive(pg_engine, seeded)
    assert all(result in {"succeeded", "partial"} for _, result in outcomes)
    results = assessment_payloads(pg_engine, seeded)
    assert original in results
    assert shared.read(old.assessment_id).freshness.value == "stale"
    newest = results[-1]
    assert newest["status"] == "insufficient_evidence" and newest["freshness"] == "current"
    assert "unsupported_rule" in newest["missing_requirements"]


def test_empty_unpublished_rule_assessment_is_rejudged_after_publication(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    imported = asset(pg_engine, seeded)
    shared = assessor(pg_engine, seeded)
    old = shared.commit(
        shared.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    assert old.rule_result is None and old.prepared.scope_watch.no_published_rule
    publish(pg_engine, seeded)
    queue_change(pg_engine, seeded)
    assert all(outcome in {"succeeded", "partial"} for _, outcome in drive(pg_engine, seeded))
    assert assessment_payloads(pg_engine, seeded)[-1]["status"] == "supported_applicability"
    assert shared.read(old.assessment_id).freshness.value == "stale"


def test_late_child_resolves_new_asset_snapshot_and_preserves_excluded_state(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    old_job = queue_child(pg_engine, seeded)
    changed = asset(pg_engine, seeded, "1.4.8", asset_id=imported.asset_id)
    assert execute(pg_engine, seeded, old_job) == "succeeded"
    current = assessment_payloads(pg_engine, seeded)[-1]
    assert current["asset_snapshot_id"] == changed.snapshot.snapshot_id
    assert current["status"] == "excluded_with_evidence" and current["freshness"] == "current"


def test_child_replay_does_not_duplicate_assessment_or_outbox_jobs(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    asset(pg_engine, seeded)
    job = queue_child(pg_engine, seeded)
    assert queue_child(pg_engine, seeded) == job
    assert execute(pg_engine, seeded, job) == "succeeded"
    assert execute(pg_engine, seeded, job) == "not_claimed"
    assert len(assessment_payloads(pg_engine, seeded)) == 1


def test_frozen_candidate_cursor_survives_new_assessment_but_not_new_asset(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    for _ in range(2):
        asset(pg_engine, seeded)
    original_candidates.synthetic_change(pg_engine, seeded)
    change = latest_change(pg_engine, seeded)
    active = service(pg_engine, seeded)
    first = active.plan_change(change["change_id"], change["epoch"])
    assert first.continuation
    with Session(pg_engine) as session, session.begin():
        children = enqueue_reassessment_plan(session, active.actor, first, datetime.now(UTC))
    assert execute(pg_engine, seeded, children[0]) == "succeeded"
    second = active.plan_change(
        change["change_id"],
        change["epoch"],
        assessment_created_before=first.assessment_created_before,
        continuation=first.continuation,
    )
    assert second.targets[0].asset_id != first.targets[0].asset_id
    asset(pg_engine, seeded)
    with pytest.raises(CandidateDiscoveryError, match="cursor_context_changed"):
        active.plan_change(
            change["change_id"],
            change["epoch"],
            assessment_created_before=first.assessment_created_before,
            continuation=first.continuation,
        )


@pytest.mark.parametrize("job_kind", ["parent", "child"])
def test_revoked_permission_blocks_durable_job_and_does_not_append_facts(
    pg_engine, tmp_path, job_kind
):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    asset(pg_engine, seeded)
    job = (
        queue_change(pg_engine, seeded) if job_kind == "parent" else queue_child(pg_engine, seeded)
    )
    with pg_engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == seeded["asset_actor"].user_id)
            .values(role="viewer")
        )
    assert execute(pg_engine, seeded, job) == "blocked"
    assert row(pg_engine, job)["error_code"] == "revalidation_authority_revoked"
    assert assessment_payloads(pg_engine, seeded) == []


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_real_binding_guard_rejects_history_rewrite(pg_engine, tmp_path, operation):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    asset(pg_engine, seeded)
    job = queue_child(pg_engine, seeded)
    statement = (
        "UPDATE revalidation_job_bindings SET payload_sha256=:digest WHERE job_id=:job"
        if operation == "update"
        else "DELETE FROM revalidation_job_bindings WHERE job_id=:job"
    )
    with pytest.raises(IntegrityError) as captured, pg_engine.begin() as connection:
        connection.execute(text(statement), {"job": job, "digest": "0" * 64})
    assert captured.value.orig.sqlstate == "23514"
    assert execute(pg_engine, seeded, job) == "succeeded"


def test_modified_job_payload_fails_digest_and_never_runs_reassessment(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    asset(pg_engine, seeded)
    job = queue_child(pg_engine, seeded)
    with pg_engine.begin() as connection:
        connection.execute(
            update(job_payloads).where(job_payloads.c.job_id == job).values(payload=b"{}")
        )
    assert execute(pg_engine, seeded, job) == "blocked"
    assert row(pg_engine, job)["error_code"] == "job_payload_digest_mismatch"
    assert assessment_payloads(pg_engine, seeded) == []


def test_wrong_owner_and_missing_binding_are_rejected_even_for_valid_tenant(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    change = latest_change(pg_engine, seeded)
    request = ReassessmentRequest(
        change_id=change["change_id"],
        target_epoch=change["epoch"],
        asset_id=imported.asset_id,
        asset_snapshot_id=imported.snapshot.snapshot_id,
        rule_id=seeded["rule"].rule_id,
        rule_version=1,
    )
    with Session(pg_engine) as session, session.begin():
        job = enqueue_job(
            session,
            seeded["tenant"],
            "revalidate_assessment",
            request.model_dump_json().encode(),
            datetime.now(UTC),
        )
    assert execute(pg_engine, seeded, job) == "blocked"
    assert row(pg_engine, job)["error_code"] == "revalidation_job_binding_unavailable"
    assert assessment_payloads(pg_engine, seeded) == []


def test_plan_epoch_drift_rolls_back_all_child_publications(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    asset(pg_engine, seeded)
    change = latest_change(pg_engine, seeded)
    active = service(pg_engine, seeded)
    plan = active.plan_change(change["change_id"], change["epoch"])
    asset(pg_engine, seeded)
    with (
        pytest.raises(RevalidationError, match="plan_inputs_changed"),
        Session(pg_engine) as session,
        session.begin(),
    ):
        enqueue_reassessment_plan(session, active.actor, plan, datetime.now(UTC))
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(job_runs)
                .where(
                    job_runs.c.tenant_id == seeded["tenant"],
                    job_runs.c.job_type == "revalidate_assessment",
                )
            )
            == 0
        )


def test_page_budget_preserves_blocked_owned_continuation(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    for _ in range(2):
        asset(pg_engine, seeded)
    original_candidates.synthetic_change(pg_engine, seeded)
    job = queue_change(pg_engine, seeded, remaining_pages=1)
    assert execute(pg_engine, seeded, job) == "partial"
    parent = row(pg_engine, job)
    assert parent["error_code"] == "revalidation_page_budget_exhausted"
    continuation = row(pg_engine, parent["result_ref"].removeprefix("pg:job:"))
    assert continuation["status"] == "blocked"
    assert execute(pg_engine, seeded, continuation["job_id"]) == "not_claimed"
    with pg_engine.connect() as connection:
        stored = bytes(
            connection.scalar(
                select(job_payloads.c.payload).where(
                    job_payloads.c.job_id == continuation["job_id"]
                )
            )
        )
    assert RevalidationChangeRequest.model_validate_json(stored).continuation


def test_published_rule_remains_selected_while_new_candidate_awaits_review(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    candidate = seeded["rule"].model_copy(update={"version": 2})
    seeded["service"].create_candidate(candidate, (seeded["binding"],))
    job = queue_child(pg_engine, seeded)
    assert execute(pg_engine, seeded, job) == "succeeded"
    current = assessment_payloads(pg_engine, seeded)[-1]
    assert current["asset_snapshot_id"] == imported.snapshot.snapshot_id
    assert current["rule_version"] == 1 and current["status"] == "supported_applicability"


def test_child_budget_does_not_schedule_an_incomplete_rule_batch(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    asset(pg_engine, seeded)
    other = seeded["rule"].model_copy(update={"rule_id": str(uuid4())})
    seeded["service"].create_candidate(other, (seeded["binding"],))
    job = queue_change(pg_engine, seeded, remaining_children=1)
    assert execute(pg_engine, seeded, job) == "partial"
    assert row(pg_engine, job)["error_code"] == "revalidation_child_budget_exhausted"
    assert assessment_payloads(pg_engine, seeded) == []


def test_same_asset_two_prepared_workers_reuse_one_authoritative_receipt(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    change = latest_change(pg_engine, seeded)
    request = ReassessmentRequest(
        change_id=change["change_id"],
        target_epoch=change["epoch"],
        asset_id=imported.asset_id,
        asset_snapshot_id=imported.snapshot.snapshot_id,
        rule_id=seeded["rule"].rule_id,
        rule_version=1,
    )
    active = service(pg_engine, seeded)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outputs = list(executor.map(lambda _: active.reassess(request), range(2)))
    assert outputs[0].assessment.assessment_id == outputs[1].assessment.assessment_id
    assert len(assessment_payloads(pg_engine, seeded)) == 1


def test_original_default_discovery_union_regression(pg_engine, tmp_path):
    original_candidates.test_union_covers_old_hit_empty_result_new_asset_and_full_final_snapshot(
        pg_engine, tmp_path
    )


def test_original_default_discovery_retired_rule_regression(pg_engine, tmp_path):
    original_candidates.test_retired_rule_preserves_readable_old_hit_and_exact_package_candidates(
        pg_engine, tmp_path
    )


def test_original_default_discovery_tenant_boundary_regression(pg_engine, tmp_path):
    original_candidates.test_private_change_and_cursor_cannot_cross_tenants(pg_engine, tmp_path)
