"""Independent observable probes use explicit fixtures and real owned PostgreSQL transactions."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import null, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ai_intel.enrichment import evidence_selection, job_service, model_fields
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import EnrichmentWorkflowError, _audit_sql_digest
from ai_intel.enrichment.job_types import FrozenEnrichmentInputs, FieldEvidenceSelectionAudit, validate_input_selection
from ai_intel.infrastructure.models.generation import GenerationLimits
from ai_intel.knowledge.models import document_revisions, job_runs, users
from ai_intel.workers.executor import JobExecutionError
from r07_input_audit_helpers import audit_engine, prepared_workflow, run
from test_r07_input_audit_receipts_pg import recorded_workflow
from test_r07_input_audit_legacy_pg import old_workflow
from tests.security.test_r07_input_audit_security_pg import private_recorded_workflow
from test_r07_job_execution_pg import children, setup
from tests.unit.test_r07_single_model_dimension import prepared_transport
from checks import RUN, now

pytestmark = pytest.mark.real_pg


def test_original_nvd_current_bounded_selection_is_wire_exact_and_keeps_all_refs(audit_engine, tmp_path, monkeypatch):
    policy = EnrichmentExecutionPolicy(generation_enabled=True, generation_provider='openai', approved_model='fixture-model', data_mode='fixture')
    service, scope, session_hash, _, _, receipt = setup(audit_engine, tmp_path, policy=policy)
    calls = []
    def factory():
        client, wire = prepared_transport(monkeypatch)
        client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
        calls.append(wire)
        return client
    service.generation_client_factory = factory
    assert run(service, receipt.parent_job_id) == 'succeeded'
    with audit_engine.connect() as connection:
        frozen, size = connection.execute(text('SELECT input_context,octet_length(input_context::text) FROM enrichment_workflows WHERE workflow_id=:wf'), {'wf': str(receipt.workflow_id)}).one()
    assert sum(len(document['blocks']) for document in frozen['documents']) == 67
    assert size == 25956
    observation = {'at': now(), 'fixture_mode': True, 'context_bytes': size, 'roster_blocks': 67, 'original_input_sha256': hashlib.sha256((RUN.parents[2] / 'fixtures/recorded/nvd_api_20261015_public.json').read_bytes()).hexdigest(), 'dimensions': []}
    model_rows = []
    publication = None
    for step in children(service):
        if step['dimension'] is None:
            publication = step
            continue
        outcome = run(service, step['job_id'])
        if step['dimension'] not in ('atlas', 'versions', 'literature', 'poc'):
            continue
        with Session(audit_engine) as session:
            audit = service.read_input_audit(session, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())
            error = session.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == step['job_id']))
        entry = {'dimension': step['dimension'], 'outcome': outcome, 'error_code': error, 'audit_state': audit.audit_state, 'receipts': len(audit.model_attempts)}
        if step['dimension'] == 'atlas':
            assert outcome == 'partial' and error == 'atlas_taxonomy_missing' and audit.record is None
            assert not audit.model_attempts
        else:
            assert outcome == 'failed' and error == 'field_evidence_revision_invalid'
            assert audit.audit_state == 'recorded' and len(audit.model_attempts) == 1
            selection = audit.record.input_selections[0]
            wire = next(call for group in calls for call in group if call[0] == step['dimension'])
            sent = json.loads(wire[1]['messages'][1]['content'])['untrusted_evidence']
            assert sent == list(selection.texts)
            assert len(sent) <= 50 and len(selection.selected) <= 49
            assert max(len(record) for record in sent) <= 16384
            assert sum(len(record.encode()) for record in sent) <= 65536
            assert selection.incomplete and len(selection.source_versions) == len(frozen['documents'])
            for source, document in zip(selection.source_versions, frozen['documents'], strict=True):
                assert str(source.revision_id) == document['revision_id'] and source.content_sha256 == document['content_sha256']
                assert str(source.document_id) == document['document_id'] and str(source.source_id) == document['source_id']
                assert source.source_version == document['source_version'] and source.canonical_uri == document['canonical_uri']
            validate_input_selection(selection, FrozenEnrichmentInputs.model_validate_json(json.dumps(frozen)))
            assert wire[1]['max_completion_tokens'] == 1024
            assert all(attempt.fee == 'unknown' for attempt in audit.model_attempts)
            entry.update(selected=len(selection.selected), records=len(sent), bytes=sum(len(record.encode()) for record in sent), omitted=len(selection.omitted_ranges), all_source_refs=len(selection.source_versions), incomplete=selection.incomplete)
        observation['dimensions'].append(entry)
        model_rows.append(step)
    assert sum(len(group) for group in calls) == 3
    assert run(service, publication['job_id']) == 'partial'
    with Session(audit_engine) as session:
        workflow = service.read_workflow(session, scope, receipt.workflow_id, actor_session_hash=session_hash, at=service.clock())
    assert next(item for item in workflow.logical_dimensions if item.dimension == 'cvss').result_status == 'available'
    observation.update(external_calls=0, offline_codec_calls=3, publication='partial', cvss='available', original_case_red='retained')
    (RUN / 'independent_nvd_observation.json').write_bytes(json.dumps(observation, indent=2).encode())


def test_first_reservation_race_has_one_winner_and_never_calls_generator(audit_engine, tmp_path, monkeypatch):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    gate = Barrier(2)
    def reserve():
        gate.wait()
        return service._reserve_model_call(step['job_id'], service.clock())
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: reserve(), range(2)))
    assert sorted(results) == [False, True]
    assert run(service, step['job_id']) == 'failed'
    with audit_engine.connect() as connection:
        row = connection.execute(select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step['job_id'])).mappings().one()
        assert connection.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == step['job_id'])) == 'incomplete_interrupted'
    assert row['model_call_completed_at'] is None and row['model_trace'] == [] and row['input_audit_payload'] is None
    assert sum(len(group) for group in calls) == 0


def test_first_receipt_race_records_once_and_conflicting_trace_cannot_overwrite(audit_engine, tmp_path, monkeypatch):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    with Session(audit_engine) as session:
        workflow = session.execute(select(enrichment_workflows)).mappings().one()
    frozen = FrozenEnrichmentInputs.model_validate_json(json.dumps(workflow['input_context']))
    generated = job_service.extract_model_dimension(frozen.context, frozen.loaded().documents, service.generation_client_factory(), dimension='versions', budget_authorized=True, content_is_private=False, egress_granted=False)
    audit = service._build_input_audit(workflow, step, generated.input_selections)
    assert service._reserve_model_call(step['job_id'], service.clock())
    gate = Barrier(2)
    def record(index):
        gate.wait()
        service._record_model_receipt(step['job_id'], generated.model_attempts, service.clock() + timedelta(seconds=index), input_audit=audit)
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(record, range(2)))
    with audit_engine.connect() as connection:
        before = connection.scalar(text('SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE job_id=:job'), {'job': step['job_id']})
    changed = (replace(generated.model_attempts[0], usage=replace(generated.model_attempts[0].usage, output_tokens=99)),)
    with pytest.raises(JobExecutionError):
        service._record_model_receipt(step['job_id'], changed, service.clock(), input_audit=audit)
    with audit_engine.connect() as connection:
        after = connection.scalar(text('SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE job_id=:job'), {'job': step['job_id']})
    assert before == after and len(before['model_trace']) == 1 and before['input_audit_payload'] is not None
    assert sum(len(group) for group in calls) == 1


@pytest.mark.parametrize('versions', ['prompt', 'selection', 'schema'])
def test_execution_version_changes_block_before_offline_wire(audit_engine, tmp_path, monkeypatch, versions):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    module, name = (evidence_selection, 'SELECTION_VERSION') if versions == 'selection' else (model_fields, 'PROMPT_VERSION' if versions == 'prompt' else 'SCHEMA_VERSION')
    monkeypatch.setattr(module, name, getattr(module, name) + '-review-mutated')
    assert run(service, step['job_id']) == 'blocked'
    assert sum(len(group) for group in calls) == 0


def test_completed_legacy_replay_keeps_original_rows_no_new_wire_no_new_audit(audit_engine, tmp_path, monkeypatch):
    service, scope, session_hash, event_id, request, workflow_id, parent_id = old_workflow(audit_engine, tmp_path)
    assert run(service, parent_id) == 'succeeded'
    own_steps = [step for step in children(service) if step['workflow_id'] == str(workflow_id)]
    version_step = next(step for step in own_steps if step['dimension'] == 'versions')
    def forbidden_client():
        raise AssertionError('completed legacy replay must not construct a model client')
    service.generation_client_factory = forbidden_client
    assert run(service, next(step for step in own_steps if step['dimension'] == 'cvss')['job_id']) == 'succeeded'
    with audit_engine.connect() as connection:
        before = connection.scalar(text('SELECT to_jsonb(w) FROM enrichment_workflows w WHERE workflow_id=:wf'), {'wf': str(workflow_id)})
        steps_before = connection.execute(text('SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE workflow_id=:wf ORDER BY step_key'), {'wf': str(workflow_id)}).scalars().all()
    monkeypatch.setattr(model_fields, 'PROMPT_VERSION', 'independent-new-prompt')
    monkeypatch.setattr(model_fields, 'SCHEMA_VERSION', 'independent-new-schema')
    monkeypatch.setattr(evidence_selection, 'SELECTION_VERSION', 'independent-new-selection')
    with Session(audit_engine) as session, session.begin():
        receipt = service.enqueue(session, scope, event_id, request, actor_session_hash=session_hash, idempotency_key='legacy-audit-key', created_at=service.clock())
        read = service.read_input_audit(session, scope, UUID(version_step['job_id']), actor_session_hash=session_hash, at=service.clock())
    with audit_engine.connect() as connection:
        after = connection.scalar(text('SELECT to_jsonb(w) FROM enrichment_workflows w WHERE workflow_id=:wf'), {'wf': str(workflow_id)})
        steps_after = connection.execute(text('SELECT to_jsonb(s) FROM enrichment_job_steps s WHERE workflow_id=:wf ORDER BY step_key'), {'wf': str(workflow_id)}).scalars().all()
    assert receipt.reused and str(receipt.parent_job_id) == parent_id and receipt.workflow_id == workflow_id
    assert before == after and steps_before == steps_after
    assert read.audit_state == 'legacy_unavailable' and read.record is None
    assert 'model_input_versions' not in after['execution_policy']


def test_json_null_is_rejected_while_sql_null_pair_is_accepted(audit_engine, tmp_path, monkeypatch):
    _, _, _, _, _, _, step, _ = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    with pytest.raises(IntegrityError), audit_engine.begin() as connection:
        connection.execute(update(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step['job_id']).values(input_audit_payload=None, input_audit_sha256=None))
    with audit_engine.begin() as connection:
        connection.execute(update(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step['job_id']).values(input_audit_payload=null(), input_audit_sha256=None))
        assert connection.scalar(text('SELECT input_audit_payload IS NULL AND input_audit_sha256 IS NULL FROM enrichment_job_steps WHERE job_id=:job'), {'job': step['job_id']})


def test_real_postgresql_jsonb_hash_is_order_independent_and_not_python_json_hash(audit_engine):
    variants = ('{"长名🙂":2,"a":"中"}', '{ "a": "中", "长名🙂": 2 }')
    digests = []
    for payload in variants:
        with audit_engine.connect() as connection:
            canonical, actual = connection.execute(text("SELECT CAST(CAST(:payload AS jsonb) AS text), encode(sha256(convert_to(CAST(CAST(:payload AS jsonb) AS text),'UTF8')),'hex')"), {'payload': payload}).one()
        assert actual == hashlib.sha256(canonical.encode()).hexdigest()
        digests.append(actual)
    assert digests[0] == digests[1]
    assert digests[0] != hashlib.sha256(json.dumps(json.loads(variants[0]), sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def test_cap_blocks_before_extract_or_reservation(audit_engine, tmp_path, monkeypatch):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    with Session(audit_engine) as session:
        row = session.execute(select(enrichment_workflows)).mappings().one()
    frozen = FrozenEnrichmentInputs.model_validate_json(json.dumps(row['input_context']))
    preview = service._build_input_audit(row, step, (evidence_selection.select_field_evidence(frozen.loaded().documents, 'versions'),))
    actual_limit = service._input_audit_bytes(preview) - 1
    monkeypatch.setattr(job_service, 'MAX_INPUT_AUDIT_BYTES', actual_limit)
    def forbidden_generator(*args, **kwargs):
        raise AssertionError('capacity must be checked before actual generation')
    monkeypatch.setattr(job_service, 'extract_model_dimension', forbidden_generator)
    assert run(service, step['job_id']) == 'blocked'
    with audit_engine.connect() as connection:
        row = connection.execute(select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step['job_id'])).mappings().one()
        assert connection.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == step['job_id'])) == 'input_audit_budget_exhausted'
    assert row['model_call_reserved_at'] is None and row['input_audit_payload'] is None
    assert sum(len(group) for group in calls) == 0


def test_real_4mib_tamper_is_rejected_by_database_and_reader(audit_engine, tmp_path, monkeypatch):
    service, scope, session_hash, _, step, _, observed = recorded_workflow(audit_engine, tmp_path, monkeypatch)
    payload = observed.record.model_dump(mode='json')
    payload['unexpected_large_field'] = '🙂' * (1024 * 1024 + 1)
    with audit_engine.begin() as connection:
        connection.execute(text('ALTER TABLE enrichment_job_steps DISABLE TRIGGER enrichment_input_audit_guard'))
    with pytest.raises(IntegrityError), audit_engine.begin() as connection:
        connection.execute(update(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step['job_id']).values(input_audit_payload=payload, input_audit_sha256=_audit_sql_digest(payload)))
    with audit_engine.begin() as connection:
        connection.execute(text('ALTER TABLE enrichment_job_steps DISABLE TRIGGER enrichment_input_audit_guard'))
        connection.execute(text('ALTER TABLE enrichment_job_steps DROP CONSTRAINT ck_enrichment_step_input_audit'))
        connection.execute(update(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step['job_id']).values(input_audit_payload=payload, input_audit_sha256=_audit_sql_digest(payload)))
        assert connection.scalar(text('SELECT octet_length(input_audit_payload::text)>4194304 FROM enrichment_job_steps WHERE job_id=:job'), {'job': step['job_id']})
    with pytest.raises(EnrichmentWorkflowError), Session(audit_engine) as session:
        service.read_input_audit(session, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())


def test_corrupt_cas_blocks_new_step_before_generation(audit_engine, tmp_path, monkeypatch):
    service, _, _, _, _, _, step, calls = prepared_workflow(audit_engine, tmp_path, monkeypatch)
    with audit_engine.connect() as connection:
        frozen = connection.scalar(select(enrichment_workflows.c.input_context))
    path = service.store.object_path_for_hash(frozen['documents'][0]['content_sha256'])
    path.write_bytes(b'synthetic reviewer corruption')
    assert run(service, step['job_id']) == 'blocked'
    assert sum(len(group) for group in calls) == 0


def test_history_revision_change_does_not_reconstruct_recorded_selection(audit_engine, tmp_path, monkeypatch):
    service, scope, session_hash, _, step, _, before = recorded_workflow(audit_engine, tmp_path, monkeypatch)
    with audit_engine.begin() as connection:
        connection.execute(update(document_revisions).values(is_current=False))
    def forbidden_selector(*args, **kwargs):
        raise AssertionError('historical actual input must not be rerun')
    monkeypatch.setattr(evidence_selection, 'select_field_evidence', forbidden_selector)
    with Session(audit_engine) as session:
        after = service.read_input_audit(session, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())
    assert before == after and after.audit_state == 'recorded'


@pytest.mark.parametrize('parent', ['source', 'document', 'revision'])
def test_parent_acl_writer_cannot_commit_between_acl_check_and_private_audit_return(audit_engine, tmp_path, monkeypatch, parent):
    service, scope, session_hash, _, step, _ = private_recorded_workflow(audit_engine, tmp_path, monkeypatch)
    original = service._read_input_audit_record
    observed = {'writer_blocked': False, 'writer_committed': False, 'reader_denied': False}
    table = {'source': 'sources', 'document': 'documents', 'revision': 'document_revisions'}[parent]
    def concurrent_writer(session, workflow, step_row):
        try:
            with audit_engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout='300ms'"))
                connection.execute(text('UPDATE ' + table + " SET visibility='tenant',tenant_id='synthetic-independent-revoked-parent'"))
            observed['writer_committed'] = True
        except OperationalError:
            observed['writer_blocked'] = True
        return original(session, workflow, step_row)
    monkeypatch.setattr(service, '_read_input_audit_record', concurrent_writer)
    with Session(audit_engine) as session, session.begin():
        try:
            result = service.read_input_audit(session, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())
            observed['returned_texts'] = bool(result.record.input_selections[0].texts)
        except PermissionError:
            observed['reader_denied'] = True
    (RUN / ('independent_parent_acl_race_' + parent + '.json')).write_bytes(json.dumps(observed, indent=2).encode())
    assert observed['writer_blocked'] or observed['reader_denied'], observed


def test_current_actor_row_remains_locked_during_private_audit_read(audit_engine, tmp_path, monkeypatch):
    service, scope, session_hash, _, step, _ = private_recorded_workflow(audit_engine, tmp_path, monkeypatch)
    with Session(audit_engine) as session, session.begin():
        audit = service.read_input_audit(session, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())
        with pytest.raises(OperationalError), audit_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='300ms'"))
            connection.execute(update(users).where(users.c.user_id == scope.user_id).values(role='viewer'))
    assert audit.audit_state == 'recorded'
