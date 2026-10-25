"""Input selection and execution versions are durable PostgreSQL evidence, not reconstructed."""

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from test_r07_job_execution_pg import children, setup
from tests.unit.test_r07_single_model_dimension import prepared_transport

from ai_intel.enrichment import evidence_selection, job_service, model_fields
from ai_intel.enrichment.job_models import enrichment_workflows
from ai_intel.infrastructure.models.generation import GenerationLimits
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.models import job_runs
from r07_input_audit_helpers import audit_engine as audit_engine
from r07_input_audit_helpers import prepared_workflow, run

pytestmark = pytest.mark.real_pg


def test_enqueue_binds_actual_prompt_selection_and_schema_versions(audit_engine, tmp_path):
    service, _, _, _, _, _ = setup(audit_engine, tmp_path)
    with Session(service.engine) as session:
        policy = session.scalar(select(enrichment_workflows.c.execution_policy))
    assert policy["model_input_versions"] == {
        "prompt_version": model_fields.PROMPT_VERSION,
        "selection_version": evidence_selection.SELECTION_VERSION,
        "schema_version": model_fields.SCHEMA_VERSION,
    }


@pytest.mark.parametrize(
    "module, name",
    [
        (model_fields, "PROMPT_VERSION"),
        (model_fields, "SCHEMA_VERSION"),
        (evidence_selection, "SELECTION_VERSION"),
    ],
)
def test_same_scope_key_cannot_reuse_a_changed_model_input_version(
    audit_engine, tmp_path, monkeypatch, module, name
):
    service, scope, session_hash, event_id, request, _ = setup(audit_engine, tmp_path)
    monkeypatch.setattr(module, name, getattr(module, name) + "-changed")
    with (
        pytest.raises(IdempotencyConflictError),
        Session(service.engine) as session,
        session.begin(),
    ):
        service.enqueue(
            session,
            scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="synthetic-request",
            created_at=service.clock(),
        )


def test_receipt_persists_the_exact_returned_selection(audit_engine, tmp_path, monkeypatch):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    observed = []
    original = job_service.extract_model_dimension

    def capture(*args, **kwargs):
        generated = original(*args, **kwargs)
        observed.append(generated)
        return generated

    monkeypatch.setattr(job_service, "extract_model_dimension", capture)
    assert run(service, step["job_id"]) == "partial"
    with service.engine.connect() as connection:
        payload = connection.scalar(
            text("SELECT input_audit_payload FROM enrichment_job_steps WHERE job_id=:job"),
            {"job": step["job_id"]},
        )
    assert payload is not None
    assert payload["input_selections"][0]["texts"] == list(observed[0].input_selections[0].texts)
    assert len(calls) == 1 and len(calls[0]) == 1
    assert (
        payload["input_selections"][0]["incomplete"] == observed[0].input_selections[0].incomplete
    )
    assert len(payload["input_selections"][0]["source_versions"]) == len(
        asdict(observed[0].input_selections[0])["source_versions"]
    )
    assert payload["input_selections"] == json.loads(
        TypeAdapter(tuple[evidence_selection.FieldEvidenceSelection, ...]).dump_json(
            observed[0].input_selections
        )
    )


def test_recorded_nvd_selection_budget_observation_keeps_all_dependencies(
    audit_engine, tmp_path, monkeypatch
):
    from uuid import UUID

    from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy

    policy = EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="openai",
        approved_model="fixture-model",
        data_mode="fixture",
    )
    service, scope, session_hash, _, _, receipt = setup(audit_engine, tmp_path, policy=policy)
    calls = []

    def factory():
        client, wire = prepared_transport(monkeypatch)
        client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
        calls.append(wire)
        return client

    service.generation_client_factory = factory
    assert run(service, receipt.parent_job_id) == "succeeded"
    with audit_engine.connect() as connection:
        snapshot, context_bytes = connection.execute(
            text(
                "SELECT input_context, octet_length(input_context::text) "
                "FROM enrichment_workflows WHERE workflow_id=:wf"
            ),
            {"wf": str(receipt.workflow_id)},
        ).one()
    outcomes = []
    for step in children(service):
        if step["dimension"] is None:
            publication = step
            continue
        outcome = run(service, step["job_id"])
        if step["dimension"] in {"atlas", "versions", "literature", "poc"}:
            with Session(audit_engine) as session:
                observed = service.read_input_audit(
                    session,
                    scope,
                    UUID(step["job_id"]),
                    actor_session_hash=session_hash,
                    at=service.clock(),
                )
                error = session.scalar(
                    select(job_runs.c.error_code).where(job_runs.c.job_id == step["job_id"])
                )
            selections = [] if observed.record is None else observed.record.input_selections
            outcomes.append(
                {
                    "dimension": step["dimension"],
                    "outcome": outcome,
                    "error_code": error,
                    "audit_state": observed.audit_state,
                    "wire_receipts": len(observed.model_attempts),
                    "selections": [
                        {
                            "selected_ranges": len(item.selected),
                            "input_records": len(item.texts),
                            "input_utf8_bytes": sum(len(record.encode()) for record in item.texts),
                            "all_source_dependencies": len(item.source_versions),
                            "omitted_blocks": len(item.omitted_block_ids),
                            "omitted_ranges": len(item.omitted_ranges),
                            "incomplete": item.incomplete,
                        }
                        for item in selections
                    ],
                }
            )
            for item in selections:
                assert (
                    len(item.texts) <= 50
                    and sum(len(record.encode()) for record in item.texts) <= 65536
                )
                assert len(item.source_versions) == len(snapshot["documents"]) and item.incomplete
    publication_outcome = run(service, publication["job_id"])
    observation = {
        "observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "data_mode": "fixture",
        "source": "recorded_nvd_ollama",
        "full_context_jsonb_utf8_bytes": context_bytes,
        "full_source_documents": len(snapshot["documents"]),
        "full_roster_blocks": sum(len(document["blocks"]) for document in snapshot["documents"]),
        "old_case_expected_wire_calls": 0,
        "actual_offline_codec_wire_calls": sum(len(wire) for wire in calls),
        "external_wire_calls": 0,
        "model_outcomes": outcomes,
        "publication_outcome": publication_outcome,
        "fees": "unknown",
        "original_case_red": "not_closed",
    }
    # 观察输出目录默认即冻结证据目录；重跑环境可用环境变量把"写"改指专属
    # 目录（镜像 test_r06_source_excerpt_event_proof_pg 的读写分离模式）。
    default_trace_dir = Path(__file__).resolve().parents[3] / (
        "reports/runs/recovery_r07_input_audit_20261016"
    )
    trace_dir = Path(os.environ.get("R07_INPUT_AUDIT_TRACE_DIR", str(default_trace_dir)))
    path = trace_dir / "nvd_current_selection_observation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(observation, indent=2).encode())
    assert observation["full_roster_blocks"] > 50
    assert observation["actual_offline_codec_wire_calls"] == 3 and publication_outcome == "partial"
