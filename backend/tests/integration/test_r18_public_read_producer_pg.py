"""Real PostgreSQL and HTTP boundaries with explicit synthetic source fixtures."""

import hashlib
import importlib.util
import secrets
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, insert, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool
from test_r04_knowledge_api_pg import seed_event, seed_source_document

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.credential_models import api_keys
from ai_intel.api.credentials import PgApiKeyService, SessionCredential
from ai_intel.api.public_extension_routes import build_public_extension_router
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import document_revisions, evidence, users
from ai_intel.knowledge.persistence_models import event_documents

pytestmark = pytest.mark.real_pg


def frozen_models():
    path = Path(__file__).resolve().parents[3] / "sdk/python/ai_intel_client/models.py"
    spec = importlib.util.spec_from_file_location("frozen_r18_public_models", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def pg_engine(isolated_test_database_url: str) -> Iterator[Engine]:
    schema = "test_r18_public_read_" + uuid4().hex
    original = make_url(isolated_test_database_url)
    assert original.database == "test_dianzi_r18_public_read_20261016"
    base = create_engine(original, poolclass=NullPool, hide_parameters=True)
    created = False
    try:
        with base.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == original.database
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        created = True
        configured = original.update_query_dict(
            {
                "options": (
                    f"-c search_path={schema} -c statement_timeout=12000 -c lock_timeout=5000"
                )
            }
        )
        run_migrations(configured.render_as_string(hide_password=False), "0026")
        engine = create_engine(configured, poolclass=NullPool, hide_parameters=True)
        try:
            yield engine
        finally:
            engine.dispose()
    finally:
        if created:
            with base.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        base.dispose()


@pytest.fixture()
def case(pg_engine: Engine, register_sensitive_failure_value):
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    credential = SessionCredential(SecretStr(token))
    register_sensitive_failure_value(credential.token)
    user_id = str(uuid4())
    with pg_engine.begin() as connection:
        connection.execute(
            insert(users).values(
                user_id=user_id,
                username=user_id,
                password_hash="synthetic-non-login",
                tenant_id="fixture-tenant",
                role="analyst",
                created_at=now,
            )
        )
        connection.execute(
            insert(auth_sessions).values(
                session_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user_id,
                csrf_token="synthetic-csrf",
                issued_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
    application = FastAPI()
    application.include_router(
        build_public_extension_router(
            pg_engine,
            "fixture",
            source_polling_enabled=False,
        ),
        prefix="/api/v1",
    )
    with TestClient(application) as client:
        client.cookies.set(SESSION_COOKIE_NAME, token)
        yield client, credential, user_id
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM api_key_rate_buckets WHERE key_id IN "
                "(SELECT key_id FROM api_keys WHERE user_id=:user)"
            ),
            {"user": user_id},
        )
        connection.execute(api_keys.delete().where(api_keys.c.user_id == user_id))
        connection.execute(auth_sessions.delete().where(auth_sessions.c.user_id == user_id))
        connection.execute(users.delete().where(users.c.user_id == user_id))


def seed_intelligence(engine: Engine, *, mode="fixture", title="fixture public event"):
    document = seed_source_document(engine)
    with engine.begin() as connection:
        connection.execute(
            update(document_revisions)
            .where(
                document_revisions.c.revision_id == document["revision_id"],
            )
            .values(source_metadata={"data_mode": mode})
        )
    event_id = seed_event(engine, [document["revision_id"]], title=title)
    return event_id, document


def test_public_pg_http_projects_distinct_event_and_document_id(pg_engine, case):
    client, _, _ = case
    event_id, document = seed_intelligence(pg_engine)
    response = client.get("/api/v1/vulns/" + event_id)
    assert response.status_code == 200, response.text
    model = frozen_models().VulnerabilityDetailPage.model_validate_json(response.content)
    assert str(model.vulnerability.event_id) == event_id
    assert str(model.vulnerability.intel_id) == document["document_id"]
    assert event_id != document["document_id"]
    assert str(model.advisories[0].revision_id) == document["revision_id"]
    assert model.advisories[0].citations[0].quote == "中文🙂 old evidence"
    assert model.vulnerability.freshness == "unknown"
    page = client.get("/api/v1/vulns", params={"q": "fixture public event"})
    assert page.status_code == 200, page.text
    frozen_models().VulnerabilityPage.model_validate_json(page.content)
    sources = client.get("/api/v1/sources")
    assert sources.status_code == 200, sources.text
    model_sources = frozen_models().SourcePage.model_validate_json(sources.content)
    source = next(item for item in model_sources.items if item.source_id == document["source_id"])
    assert source.health == "never_polled"
    assert source.enabled is False


def test_long_query_reaches_pg_without_500_character_truncation(pg_engine, case):
    client, _, _ = case
    response = client.get("/api/v1/vulns", params={"q": "z" * 4096})
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


def test_public_read_excludes_private_events_and_nested_evidence(pg_engine, case):
    client, _, _ = case
    private = seed_event(pg_engine, [], visibility="tenant", tenant="fixture-tenant")
    assert client.get("/api/v1/vulns/" + private).status_code == 404
    event_id, document = seed_intelligence(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(
            update(evidence)
            .where(evidence.c.evidence_id == document["evidence_id"])
            .values(visibility="tenant", tenant_id="fixture-tenant")
        )
    response = client.get("/api/v1/vulns/" + event_id)
    assert response.status_code == 503
    assert "中文" not in response.text


def test_old_revision_and_inactive_event_link_fail_closed(pg_engine, case):
    client, _, _ = case
    event_id, document = seed_intelligence(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(
            update(event_documents)
            .where(
                event_documents.c.event_id == event_id,
            )
            .values(active=False)
        )
    response = client.get("/api/v1/vulns/" + event_id)
    assert response.status_code == 503
    with pg_engine.begin() as connection:
        connection.execute(
            update(event_documents)
            .where(
                event_documents.c.event_id == event_id,
            )
            .values(active=True)
        )
        connection.execute(
            update(document_revisions)
            .where(
                document_revisions.c.revision_id == document["revision_id"],
            )
            .values(is_current=False)
        )
    assert client.get("/api/v1/vulns/" + event_id).status_code == 503


def test_mixed_source_modes_do_not_return_fixture_as_live(pg_engine, case):
    client, _, _ = case
    event_id, _ = seed_intelligence(pg_engine, mode="live")
    response = client.get("/api/v1/vulns/" + event_id)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_configured"


def test_api_key_expiry_revoke_and_permission_are_current(pg_engine, case):
    client, credential, user_id = case
    service = PgApiKeyService(pg_engine)
    issued = service.issue_key(credential, frozenset({"read:public"}))
    client.cookies.clear()
    client.headers["authorization"] = "Bearer " + issued.token.get_secret_value()
    assert client.get("/api/v1/vulns", params={"q": "absent-case"}).status_code == 200
    service.revoke_key(credential, issued.metadata.key_id)
    assert client.get("/api/v1/vulns").status_code == 401
    issued = service.issue_key(credential, frozenset({"read:asset"}))
    client.headers["authorization"] = "Bearer " + issued.token.get_secret_value()
    assert client.get("/api/v1/vulns").status_code == 403
    with pg_engine.begin() as connection:
        connection.execute(
            update(api_keys)
            .where(api_keys.c.user_id == user_id)
            .values(
                issued_at=datetime.now(UTC) - timedelta(hours=1),
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
    assert client.get("/api/v1/vulns").status_code == 401


def test_task_without_typed_owner_is_not_configured_and_no_secret_reflection(case):
    client, _, _ = case
    response = client.get("/api/v1/tasks/" + str(uuid4()))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_configured"
    assert "fixture-tenant" not in response.text


def test_sources_cursor_binds_principal_query_and_acl(pg_engine, case):
    client, _, user_id = case
    seed_intelligence(pg_engine)
    seed_intelligence(pg_engine)
    response = client.get("/api/v1/sources", params={"limit": 1})
    assert response.status_code == 200, response.text
    cursor = response.json()["next_cursor"]
    assert cursor
    assert client.get("/api/v1/sources", params={"limit": 2, "cursor": cursor}).status_code == 422
    with pg_engine.begin() as connection:
        connection.execute(update(users).where(users.c.user_id == user_id).values(role="viewer"))
    assert client.get("/api/v1/sources", params={"limit": 1, "cursor": cursor}).status_code == 422


def test_read_expiry_during_response_production_is_rechecked(pg_engine, case):
    client, _, _ = case
    seed_intelligence(pg_engine, title="expiry-fixture")
    changed = False

    def expire_same_transaction(connection, clause, multiparams, params, execution_options):
        nonlocal changed
        if not changed and "FROM events" in str(clause):
            changed = True
            connection.execute(
                text(
                    "UPDATE auth_sessions SET issued_at=now()-interval '1 hour', "
                    "expires_at=now()-interval '1 second'"
                )
            )

    event.listen(pg_engine, "before_execute", expire_same_transaction)
    try:
        response = client.get("/api/v1/vulns", params={"q": "expiry-fixture"})
    finally:
        event.remove(pg_engine, "before_execute", expire_same_transaction)
    assert changed
    assert response.status_code == 401, response.text
