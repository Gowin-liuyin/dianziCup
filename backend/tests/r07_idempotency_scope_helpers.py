"""Explicit synthetic source fixtures use their own PG namespace and server-created identities."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from sqlalchemy import create_engine, insert, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.api.auth_state import auth_sessions
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import DocumentKind
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy, EventEnrichmentRequest
from ai_intel.enrichment.job_models import enrichment_workflows
from ai_intel.enrichment.job_service import (
    ENRICHMENT_PARENT_JOB_TYPE,
    RULE_VERSION,
    EnrichmentJobService,
    _digest,
)
from ai_intel.enrichment.job_types import EnrichmentJobPayload, json_payload
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion.catalog_documents import NormalizedSourceDocument, persist_catalog_documents
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.knowledge.event_linking import EventRepository, EventSubmission
from ai_intel.knowledge.models import users
from ai_intel.knowledge.revisions import register_response_content

NOW = datetime.now(UTC)


@pytest.fixture
def scope_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r07_execution_scope_20261016"
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_r07_scope_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated)
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0031_public_task_bindings"
        )
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def create_actor(engine, *, tenant_id=None, role=Role.SYSTEM_ADMIN, user_id=None):
    actor_id = user_id or str(uuid4())
    session_hash = hashlib.sha256(("synthetic-scope-session:" + actor_id).encode()).hexdigest()
    scope = AccessScope.for_authenticated_user(actor_id, tenant_id, role)
    with engine.begin() as connection:
        connection.execute(
            insert(users).values(
                user_id=actor_id,
                username="synthetic-scope-" + actor_id,
                password_hash="unusable synthetic hash",
                tenant_id=tenant_id,
                role=role.value,
                created_at=NOW,
            )
        )
        connection.execute(
            insert(auth_sessions).values(
                session_hash=session_hash,
                user_id=actor_id,
                csrf_token="synthetic-scope-csrf",
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
        )
    return scope, session_hash


def create_event(engine, store, scope):
    body = (
        b'{"title":"Synthetic bounded paper",'
        b'"abstract":"Explicit offline evidence, no external calls."}'
    )
    member = NormalizedSourceDocument(
        "2601.00001",
        DocumentKind.PAPER,
        "Synthetic bounded paper",
        "https://arxiv.org/abs/2601.00001v1",
        body,
        parse_json_document(body),
        None,
        None,
        {"version_label": "v1", "content_coverage": "metadata_only"},
    )
    event_id = uuid4()
    visibility = VisibilityScope(visibility="public")
    with Session(engine) as session, session.begin():
        ensure_source_registration(session, scope, "arxiv_security", NOW)
        response = register_response_content(
            session, store, b"synthetic-scope-source-response", NOW
        )
        saved = persist_catalog_documents(
            session,
            store,
            scope,
            "arxiv_security",
            (member,),
            response_hash=response.content_hash,
            observed_at=NOW,
            ingested_at=NOW,
        )
        EventRepository(session, scope).publish_events(
            "synthetic-scope-event:" + str(event_id),
            visibility,
            (
                EventSubmission(
                    event_id=Identifier(value=str(event_id)),
                    event_type="security_risk",
                    title="Synthetic bounded paper event",
                    scope=visibility,
                    source_revision_ids=tuple(
                        Identifier(value=value) for value in saved.revision_ids
                    ),
                ),
            ),
            NOW,
        )
    return event_id


def setup_scope(engine, tmp_path):
    scope, session_hash = create_actor(engine)
    store = ContentStore(tmp_path)
    event_id = create_event(engine, store, scope)
    service = EnrichmentJobService(
        engine,
        store,
        execution_policy=lambda: EnrichmentExecutionPolicy(data_mode="fixture"),
        clock=lambda: NOW,
    )
    request = EventEnrichmentRequest(expected_event_version=1, dimensions=("versions",))
    return service, scope, session_hash, event_id, request


def queue(service, scope, session_hash, event_id, request, key="synthetic-shared-key"):
    with Session(service.engine) as session, session.begin():
        return service.enqueue(
            session,
            scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key=key,
            created_at=NOW,
        )


def queue_legacy(service, scope, session_hash, event_id, request, key="synthetic-shared-key"):
    policy = service.execution_policy()
    workflow_id = uuid5(NAMESPACE_URL, "ai-intel:enrichment:" + repr((None, key)))
    binding = {
        "event_id": str(event_id),
        "actor_user_id": scope.user_id,
        "actor_session_hash": session_hash,
        "actor_tenant_id": scope.tenant_id,
        "actor_role": scope.role.value,
        "actor_permission_version": scope.permission_version,
        "request_sha256": _digest(request.model_dump(mode="json")),
        "execution_policy_sha256": _digest(policy.model_dump(mode="json")),
        "rule_version": RULE_VERSION,
    }
    with Session(service.engine) as session, session.begin():
        parent_id = enqueue_job(
            session,
            None,
            ENRICHMENT_PARENT_JOB_TYPE,
            json_payload(
                EnrichmentJobPayload(workflow_id=workflow_id, binding_sha256=_digest(binding))
            ),
            NOW,
            idempotency_key=key,
            max_attempts=3,
        )
        session.execute(
            insert(enrichment_workflows).values(
                **binding,
                workflow_id=str(workflow_id),
                parent_job_id=parent_id,
                visibility="public",
                tenant_id=None,
                request_payload=request.model_dump(mode="json"),
                execution_policy=policy.model_dump(mode="json"),
                created_at=NOW,
            )
        )
    return workflow_id, UUID(parent_id)
