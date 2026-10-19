"""A self-consistent synthetic legacy history has one real offline codec receipt and no new audit."""

import json
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from ai_intel.enrichment import evidence_selection, job_service, model_fields
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import ENRICHMENT_PARENT_JOB_TYPE, RULE_VERSION, _binding, _digest
from ai_intel.enrichment.job_types import EnrichmentJobPayload, FrozenEnrichmentInputs, json_payload
from ai_intel.infrastructure.models.generation import GenerationLimits
from ai_intel.infrastructure.outbox import enqueue_job
from r07_input_audit_helpers import audit_engine, run
from test_r07_job_execution_pg import children, setup
from tests.unit.test_r07_single_model_dimension import prepared_transport


def test_completed_legacy_paid_receipt_replays_without_rebinding_or_new_generation(audit_engine, tmp_path, monkeypatch):
    policy = EnrichmentExecutionPolicy(generation_enabled=True, generation_provider='openai', approved_model='fixture-model', data_mode='fixture')
    service, scope, session_hash, event_id, request, _ = setup(audit_engine, tmp_path, policy=policy, source_kind='synthetic_bounded_paper')
    workflow_id = uuid5(NAMESPACE_URL, 'ai-intel:enrichment:' + repr((None, 'legacy-completed-review1')))
    raw_policy = policy.model_dump(mode='json', exclude={'model_input_versions'})
    with Session(audit_engine) as session, session.begin():
        binding = _binding(session.execute(select(enrichment_workflows)).mappings().one())
        binding['execution_policy_sha256'] = _digest(raw_policy)
        parent = enqueue_job(session, None, ENRICHMENT_PARENT_JOB_TYPE, json_payload(EnrichmentJobPayload(workflow_id=workflow_id, binding_sha256=_digest(binding))), service.clock(), idempotency_key='legacy-completed-review1')
        session.execute(insert(enrichment_workflows).values(**binding, workflow_id=str(workflow_id), parent_job_id=parent, visibility='public', tenant_id=None, request_payload=request.model_dump(mode='json'), execution_policy=raw_policy, created_at=service.clock()))
    assert run(service, parent) == 'succeeded'
    step = next(item for item in children(service) if item['workflow_id'] == str(workflow_id) and item['dimension'] == 'versions')
    with Session(audit_engine) as session:
        workflow = session.execute(select(enrichment_workflows).where(enrichment_workflows.c.workflow_id == str(workflow_id))).mappings().one()
    frozen = FrozenEnrichmentInputs.model_validate_json(json.dumps(workflow['input_context']))
    client, wire = prepared_transport(monkeypatch, outputs={'versions': {'candidates': []}})
    client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
    generated = job_service.extract_model_dimension(frozen.context, frozen.loaded().documents, client, dimension='versions', budget_authorized=True, content_is_private=False, egress_granted=False)
    assert len(generated.model_attempts) == 1 and len(wire) == 1
    assert service._reserve_model_call(step['job_id'], service.clock())
    service._record_model_receipt(step['job_id'], generated.model_attempts, service.clock())
    monkeypatch.setattr(service, '_model_attempt', lambda *args, **kwargs: generated.attempts[0])
    assert run(service, step['job_id']) == 'partial'
    with audit_engine.connect() as connection:
        before = connection.scalar(text('SELECT to_jsonb(w) FROM enrichment_workflows w WHERE workflow_id=:wf'), {'wf': str(workflow_id)})
        before_step = connection.scalar(text('SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE job_id=:job'), {'job': step['job_id']})
    monkeypatch.undo()
    def forbidden_client():
        raise AssertionError('legacy history must not construct another model client')
    service.generation_client_factory = forbidden_client
    monkeypatch.setattr(model_fields, 'PROMPT_VERSION', 'future-prompt-review1')
    monkeypatch.setattr(model_fields, 'SCHEMA_VERSION', 'future-schema-review1')
    monkeypatch.setattr(evidence_selection, 'SELECTION_VERSION', 'future-selection-review1')
    with Session(audit_engine) as session, session.begin():
        replay = service.enqueue(session, scope, event_id, request, actor_session_hash=session_hash, idempotency_key='legacy-completed-review1', created_at=service.clock())
        audit = service.read_input_audit(session, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())
    with audit_engine.connect() as connection:
        after = connection.scalar(text('SELECT to_jsonb(w) FROM enrichment_workflows w WHERE workflow_id=:wf'), {'wf': str(workflow_id)})
        after_step = connection.scalar(text('SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE job_id=:job'), {'job': step['job_id']})
    assert replay.reused and replay.workflow_id == workflow_id and str(replay.parent_job_id) == parent
    assert before == after and before_step == after_step
    assert audit.audit_state == 'legacy_unavailable' and audit.record is None
    assert audit.model_attempts == generated.model_attempts and len(wire) == 1
    assert run(service, step['job_id']) == 'not_claimed'
    assert 'model_input_versions' not in after['execution_policy']
