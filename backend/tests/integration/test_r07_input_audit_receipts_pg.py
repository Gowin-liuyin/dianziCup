"""PG receipt immutability, recovery and byte budgets retain actual offline call evidence."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import auth_sessions
from ai_intel.enrichment import evidence_selection, job_service, model_fields
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import EnrichmentJobService
from ai_intel.enrichment.job_types import FrozenEnrichmentInputs
from ai_intel.knowledge.models import job_runs
from ai_intel.workers.executor import JobExecutionError
from r07_input_audit_helpers import audit_engine as audit_engine
from r07_input_audit_helpers import install_audit_proposal, prepared_workflow, run
from r07_input_audit_helpers import legacy_audit_engine as legacy_audit_engine

pytestmark = pytest.mark.real_pg


def recorded_workflow(engine, tmp_path, monkeypatch):
    service, scope, session_hash, _, _, receipt, step, calls = prepared_workflow(
        engine, tmp_path, monkeypatch
    )
    assert run(service, step["job_id"]) == "partial"
    with Session(engine) as session:
        view = service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    return service, scope, session_hash, receipt, step, calls, view


def test_pg16_jsonb_unicode_hash_uses_postgresql_bytes(audit_engine):
    payload = json.dumps({"中文": "模型🙂", "nested": {"z": 2, "a": "原文"}}, ensure_ascii=False)
    with audit_engine.connect() as connection:
        version = connection.scalar(text("SHOW server_version_num"))
        normalized, digest = connection.execute(
            text(
                "SELECT CAST(CAST(:payload AS jsonb) AS text), "
                "encode(sha256(convert_to(CAST(CAST(:payload AS jsonb) AS text),'UTF8')),'hex')"
            ),
            {"payload": payload},
        ).one()
    assert int(version) // 10000 == 16
    assert hashlib.sha256(normalized.encode()).hexdigest() == digest
    assert hashlib.sha256(payload.encode()).hexdigest() != digest
    assert "模型🙂" in normalized


def test_receipt_survives_new_service_and_is_not_reconstructed(audit_engine, tmp_path, monkeypatch):
    service, scope, session_hash, _, step, calls, original = recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )

    def forbidden_selector(*args, **kwargs):
        raise AssertionError("stored input audit must not reconstruct selection")

    monkeypatch.setattr(evidence_selection, "select_field_evidence", forbidden_selector)
    restarted = EnrichmentJobService(
        audit_engine, service.store, execution_policy=service.execution_policy, clock=service.clock
    )
    with Session(audit_engine) as session:
        observed = restarted.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    assert observed == original and observed.audit_state == "recorded"
    assert run(restarted, step["job_id"]) == "not_claimed"
    assert sum(len(wire) for wire in calls) == 1


def test_audit_capacity_is_checked_before_reservation_or_wire(audit_engine, tmp_path, monkeypatch):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    monkeypatch.setattr(job_service, "MAX_INPUT_AUDIT_BYTES", 1)
    assert run(service, step["job_id"]) == "blocked"
    with Session(audit_engine) as session:
        persisted = (
            session.execute(
                select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step["job_id"])
            )
            .mappings()
            .one()
        )
        code = session.scalar(
            select(job_runs.c.error_code).where(job_runs.c.job_id == step["job_id"])
        )
    assert code == "input_audit_budget_exhausted"
    assert persisted["model_call_reserved_at"] is None and persisted["input_audit_payload"] is None
    assert sum(len(wire) for wire in calls) == 0


def test_completed_receipt_and_audit_remain_when_business_transaction_rolls_back(
    audit_engine, tmp_path, monkeypatch
):
    service, _, session_hash, _, _, _, step, calls = prepared_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    original = job_service.extract_model_dimension

    def revoke_after_wire(*args, **kwargs):
        generated = original(*args, **kwargs)
        with audit_engine.begin() as connection:
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.session_hash == session_hash)
                .values(revoked_at=service.clock())
            )
        return generated

    monkeypatch.setattr(job_service, "extract_model_dimension", revoke_after_wire)
    assert run(service, step["job_id"]) == "blocked"
    with Session(audit_engine) as session:
        persisted = (
            session.execute(
                select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step["job_id"])
            )
            .mappings()
            .one()
        )
    assert persisted["result_payload"] is None
    assert persisted["input_audit_payload"] is not None and len(persisted["model_trace"]) == 1
    assert run(service, step["job_id"]) == "not_claimed" and sum(len(wire) for wire in calls) == 1


def test_duplicate_concurrent_receipt_is_immutable_and_conflicting_trace_is_rejected(
    audit_engine, tmp_path, monkeypatch
):
    service, _, _, _, step, calls, observed = recorded_workflow(audit_engine, tmp_path, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(
            workers.map(
                lambda _: service._record_model_receipt(
                    step["job_id"],
                    observed.model_attempts,
                    service.clock() + timedelta(seconds=1),
                    input_audit=observed.record,
                ),
                range(2),
            )
        )
    with audit_engine.begin() as connection:
        before = connection.scalar(
            text("SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE job_id=:job"),
            {"job": step["job_id"]},
        )
    with pytest.raises(JobExecutionError):
        service._record_model_receipt(step["job_id"], (), service.clock() + timedelta(seconds=2))
    with audit_engine.connect() as connection:
        after = connection.scalar(
            text("SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE job_id=:job"),
            {"job": step["job_id"]},
        )
    assert before == after and sum(len(wire) for wire in calls) == 1


@pytest.mark.parametrize("mutation", ["audit", "trace", "completed", "reserved", "sha"])
def test_database_rejects_changes_to_completed_audit_receipt(
    audit_engine, tmp_path, monkeypatch, mutation
):
    _, _, _, _, step, _, _ = recorded_workflow(audit_engine, tmp_path, monkeypatch)
    values = {
        "audit": {"input_audit_payload": {}},
        "trace": {"model_trace": []},
        "completed": {"model_call_completed_at": None},
        "reserved": {"model_call_reserved_at": None},
        "sha": {"input_audit_sha256": "0" * 64},
    }[mutation]
    with pytest.raises(IntegrityError), audit_engine.begin() as connection:
        connection.execute(
            update(enrichment_job_steps)
            .where(enrichment_job_steps.c.job_id == step["job_id"])
            .values(**values)
        )


def test_audit_receipt_update_does_not_wait_for_executor_job_lock(
    audit_engine, tmp_path, monkeypatch
):
    service, _, _, _, _, _, step, _ = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    with Session(audit_engine) as session:
        workflow = session.execute(select(enrichment_workflows)).mappings().one()
        frozen = FrozenEnrichmentInputs.model_validate_json(json.dumps(workflow["input_context"]))
    generated = job_service.extract_model_dimension(
        frozen.context,
        frozen.loaded().documents,
        service.generation_client_factory(),
        dimension="versions",
        budget_authorized=True,
        content_is_private=False,
        egress_granted=False,
    )
    audit = service._build_input_audit(workflow, step, generated.input_selections)
    with Session(audit_engine) as locked, locked.begin():
        locked.execute(
            select(job_runs).where(job_runs.c.job_id == step["job_id"]).with_for_update()
        ).one()
        with ThreadPoolExecutor(max_workers=1) as worker:
            assert worker.submit(
                service._reserve_model_call, step["job_id"], service.clock()
            ).result(timeout=5)
            worker.submit(
                service._record_model_receipt,
                step["job_id"],
                generated.model_attempts,
                service.clock(),
                input_audit=audit,
            ).result(timeout=5)
    with audit_engine.connect() as connection:
        assert connection.scalar(
            text(
                "SELECT input_audit_payload IS NOT NULL FROM enrichment_job_steps WHERE job_id=:job"
            ),
            {"job": step["job_id"]},
        )


def test_model_step_blocks_after_runtime_code_version_changes(audit_engine, tmp_path, monkeypatch):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    monkeypatch.setattr(model_fields, "PROMPT_VERSION", model_fields.PROMPT_VERSION + "-new")
    assert run(service, step["job_id"]) == "blocked"
    assert sum(len(wire) for wire in calls) == 0


def test_faulty_returned_selector_preserves_trace_without_faking_audit(
    audit_engine, tmp_path, monkeypatch
):
    service, scope, session_hash, _, _, _, step, calls = prepared_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    original = job_service.extract_model_dimension

    def faulty_selector(*args, **kwargs):
        generated = original(*args, **kwargs)
        selection = generated.input_selections[0]
        forged = replace(selection.source_versions[0], content_sha256="0" * 64)
        return replace(generated, input_selections=(replace(selection, source_versions=(forged,)),))

    monkeypatch.setattr(job_service, "extract_model_dimension", faulty_selector)
    assert run(service, step["job_id"]) == "failed"
    with Session(audit_engine) as session:
        observed = service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    assert observed.audit_state == "not_recorded" and observed.record is None
    assert len(observed.model_attempts) == 1 and sum(len(wire) for wire in calls) == 1


def test_forward_audit_proposal_preserves_all_old_0017_values(legacy_audit_engine, tmp_path):
    from test_r07_enrichment_job_metadata_pg import seed_workflow

    seed_workflow(legacy_audit_engine, tmp_path)
    with legacy_audit_engine.connect() as connection:
        before_workflows = (
            connection.execute(text("SELECT to_jsonb(w) FROM enrichment_workflows w"))
            .scalars()
            .all()
        )
        before_steps = (
            connection.execute(text("SELECT to_jsonb(s) FROM enrichment_job_steps s"))
            .scalars()
            .all()
        )
    install_audit_proposal(legacy_audit_engine)
    with legacy_audit_engine.connect() as connection:
        after_workflows = (
            connection.execute(text("SELECT to_jsonb(w) FROM enrichment_workflows w"))
            .scalars()
            .all()
        )
        after_steps = (
            connection.execute(
                text(
                    "SELECT to_jsonb(s)-'input_audit_payload'-'input_audit_sha256' "
                    "FROM enrichment_job_steps s"
                )
            )
            .scalars()
            .all()
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM enrichment_job_steps WHERE "
                    "input_audit_payload IS NOT NULL OR input_audit_sha256 IS NOT NULL"
                )
            )
            == 0
        )
    assert before_workflows == after_workflows and before_steps == after_steps
