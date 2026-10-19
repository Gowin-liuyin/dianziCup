"""Actual repository writers meet the same real row-lock fence, without source/model network IO."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy
from ai_intel.enrichment.job_models import enrichment_workflows
from ai_intel.enrichment.job_types import FrozenEnrichmentInputs
from ai_intel.enrichment.publication import publish_enrichment_attempts
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.ingestion.catalog_documents import persist_catalog_documents
from ai_intel.ingestion.source_documents import SourceResponse, ensure_source_registration, persist_source_response
from ai_intel.knowledge.event_linking import EventRepository, EventSubmission
from ai_intel.knowledge.revisions import save_document_revision
from ai_intel.infrastructure.models.generation import GenerationLimits
from r07_input_audit_helpers import audit_engine, run
from test_r06_catalog_documents_pg import ADMIN, paper
from test_r07_job_execution_pg import children, setup
from tests.r06_source_worker_fixtures import source_response
from tests.security.test_r07_input_audit_security_pg import private_recorded_workflow
from tests.unit.test_r07_single_model_dimension import prepared_transport


def nvd_recorded(engine, tmp_path, monkeypatch):
    policy = EnrichmentExecutionPolicy(generation_enabled=True, generation_provider='openai', approved_model='fixture-model', data_mode='fixture')
    service, scope, session_hash, _, _, receipt = setup(engine, tmp_path, policy=policy)
    def factory():
        client, wire = prepared_transport(monkeypatch, outputs={'versions': {'candidates': []}})
        client.limits = GenerationLimits(total_timeout_seconds=20.0, max_calls=1)
        return client
    service.generation_client_factory = factory
    assert run(service, receipt.parent_job_id) == 'succeeded'
    step = next(item for item in children(service) if item['dimension'] == 'versions')
    assert run(service, step['job_id']) == 'partial'
    return service, scope, session_hash, receipt, step


@pytest.mark.parametrize('writer_path', ['source_registration', 'source_response', 'catalog_document', 'revision_save', 'event_publish', 'enrichment_publication'])
def test_actual_writers_get_lock_not_available_while_authorized_audit_is_open(audit_engine, tmp_path, monkeypatch, writer_path):
    if writer_path == 'source_response':
        service, scope, session_hash, receipt, step = nvd_recorded(audit_engine, tmp_path, monkeypatch)
    else:
        service, scope, session_hash, receipt, step, _ = private_recorded_workflow(audit_engine, tmp_path, monkeypatch)
    with Session(audit_engine) as session:
        workflow = session.execute(select(enrichment_workflows).where(enrichment_workflows.c.workflow_id == str(receipt.workflow_id))).mappings().one()
    frozen = FrozenEnrichmentInputs.model_validate_json(__import__('json').dumps(workflow['input_context']))
    document = frozen.documents[0]
    with Session(audit_engine) as reader, reader.begin():
        result = service.read_input_audit(reader, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())
        with pytest.raises(OperationalError) as blocked, Session(audit_engine) as writer, writer.begin():
            writer.execute(text("SET LOCAL lock_timeout='250ms'"))
            if writer_path == 'source_registration':
                ensure_source_registration(writer, ADMIN, 'arxiv_security', service.clock())
            elif writer_path == 'source_response':
                body, _ = source_response('nvd_ollama')
                response = SourceResponse('nvd_ollama', body, 'https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=1&startIndex=0', service.clock())
                persist_source_response(writer, service.store, ADMIN, response, ingested_at=service.clock())
            elif writer_path == 'catalog_document':
                persist_catalog_documents(writer, service.store, ADMIN, 'arxiv_security', (paper(),), response_hash=document.content_sha256, observed_at=service.clock(), ingested_at=service.clock())
            elif writer_path == 'revision_save':
                save_document_revision(writer, service.store, str(document.document_id), paper().payload, 'public', None, service.clock())
            elif writer_path == 'event_publish':
                EventRepository(writer, scope).publish_events('independent-writer-' + str(uuid4()), VisibilityScope(visibility='tenant', tenant_id=scope.tenant_id), (EventSubmission(event_id=Identifier(value=workflow['event_id']), event_type='security_risk', title='Synthetic bounded extraction source', scope=VisibilityScope(visibility='tenant', tenant_id=scope.tenant_id), source_revision_ids=tuple(Identifier(value=str(item)) for item in frozen.context.revision_ids)),), service.clock())
            else:
                loaded = frozen.loaded()
                publish_enrichment_attempts(writer, scope, loaded, enrich_structured_fields(loaded.context, loaded.documents), request_id=uuid4(), recorded_at=service.clock())
        assert blocked.value.orig.sqlstate == '55P03'
        assert result.audit_state == 'recorded' and result.record.input_selections[0].texts


def test_actual_source_registration_writer_then_reader_completes_without_deadlock(audit_engine, tmp_path, monkeypatch):
    service, scope, session_hash, _, step, _ = private_recorded_workflow(audit_engine, tmp_path, monkeypatch)
    def read():
        with Session(audit_engine) as session, session.begin():
            return service.read_input_audit(session, scope, UUID(step['job_id']), actor_session_hash=session_hash, at=service.clock())
    with ThreadPoolExecutor(max_workers=1) as workers, Session(audit_engine) as writer:
        transaction = writer.begin()
        ensure_source_registration(writer, ADMIN, 'arxiv_security', service.clock())
        result = workers.submit(read)
        try:
            with pytest.raises(TimeoutError):
                result.result(timeout=0.25)
        finally:
            transaction.commit()
        audit = result.result(timeout=5)
    assert audit.audit_state == 'recorded' and audit.record.input_selections[0].texts
