"""Dedicated real-PG cases using synthetic evidence; collection never opens a database."""

import hashlib
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from tests.integration import test_r11_pg_assessments as original
from tests.unit.test_public_write_adapters import fixture_request

from ai_intel.api.auth_state import auth_sessions, lock_authenticated_scope
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.api.public_component_selector import select_current_component_assessments
from ai_intel.api.public_write_adapters import stack_current_assessments
from ai_intel.domain.access import PermissionDeniedError, Role
from ai_intel.knowledge.models import document_revisions, scope_epochs, users

pytestmark = pytest.mark.real_pg
HEAD = "0030_revalidation_actor_bindings"


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    """Root provisions the owned database and forward migrations before this fixture runs."""
    run_id = os.environ["DIANZI_TEST_RUN_ID"]
    assert re.fullmatch(r"r18_component_selector_[a-z0-9_]{8,80}", run_id)
    database = "test_dianzi_" + run_id
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, database)
    assert url.username and url.username.startswith("test_")
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == database
        assert str(connection.scalar(text("SELECT current_user"))).startswith("test_")
        assert str(connection.scalar(text("SELECT current_schema()"))).startswith(
            "test_r18_component_"
        )
        if "DIANZI_TEST_ROLE_OID" in os.environ:
            identity = connection.execute(
                text(
                    "SELECT oid, shobj_description(oid, 'pg_authid') AS comment "
                    "FROM pg_roles WHERE rolname = :name"
                ),
                {"name": url.username},
            ).one()
            assert identity.oid == int(os.environ["DIANZI_TEST_ROLE_OID"])
            assert identity.comment == (os.environ["DIANZI_TEST_ROLE_COMMENT"] or None)
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def sensitive_failure_guard(register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(make_url(os.environ["TEST_DATABASE_URL"]).password))


def create_assessment(engine, directory):
    seeded = original.seed(engine, directory)
    with engine.begin() as connection:
        connection.execute(
            update(document_revisions)
            .where(
                document_revisions.c.revision_id == seeded["revision_id"],
                document_revisions.c.document_id == seeded["document_id"],
            )
            .values(
                canonical_uri="https://example.invalid/fixture/revisions/" + seeded["revision_id"]
            )
        )
    original.publish(engine, seeded)
    imported = original.asset(engine, seeded)
    service = original.assessor(engine, seeded)
    receipt = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    return seeded, imported, service, receipt


def select_for_actor(engine, seeded, service, request):
    with Session(engine) as session, session.begin():
        scope = lock_authenticated_scope(
            session.connection(), seeded["asset_token"], datetime.now(UTC)
        )
        knowledge = KnowledgeReadService(session, scope, "fixture")
        selection = select_current_component_assessments(request, service, knowledge)
        result = stack_current_assessments(request, selection.assessment_ids, service, knowledge)
        assert (
            lock_authenticated_scope(session.connection(), seeded["asset_token"], datetime.now(UTC))
            == scope
        )
        return selection, result


def test_real_pg_exact_current_component_returns_shared_current_result(pg_engine, tmp_path):
    seeded, _imported, service, receipt = create_assessment(pg_engine, tmp_path)
    selection, result = select_for_actor(
        pg_engine, seeded, service, fixture_request(version="1.4.1")
    )
    assert selection.assessment_ids == (UUID(receipt.assessment_id),)
    assert result.results[0].status == "supported_applicability"
    assert result.results[0].freshness == "current" and result.results[0].citations


def test_real_pg_wrong_version_or_unknown_version_never_borrows_current_result(pg_engine, tmp_path):
    seeded, _imported, service, _receipt = create_assessment(pg_engine, tmp_path)
    for version in ("2.0", None):
        selection, result = select_for_actor(
            pg_engine, seeded, service, fixture_request(version=version)
        )
        assert selection.assessment_ids == (None,)
        assert (
            result.results[0].status == "insufficient_evidence" and not result.results[0].citations
        )


def test_real_pg_foreign_tenant_identical_component_is_invisible(pg_engine, tmp_path):
    create_assessment(pg_engine, tmp_path)
    foreign = original.seed(pg_engine, tmp_path / "foreign")
    foreign_service = original.assessor(pg_engine, foreign)
    selection, result = select_for_actor(
        pg_engine, foreign, foreign_service, fixture_request(version="1.4.1")
    )
    assert selection.assessment_ids == (None,) and selection.reason_codes == ("no_match",)
    assert result.results[0].status == "insufficient_evidence" and not result.results[0].citations


def test_real_pg_new_asset_snapshot_removes_old_assessment_from_current_selection(
    pg_engine, tmp_path
):
    seeded, imported, service, receipt = create_assessment(pg_engine, tmp_path)
    original.asset(pg_engine, seeded, "2.0", asset_id=imported.asset_id)
    selection, result = select_for_actor(
        pg_engine, seeded, service, fixture_request(version="1.4.1")
    )
    assert selection.assessment_ids == (None,)
    assert result.results[0].status == "insufficient_evidence"
    assert service.read(receipt.assessment_id).freshness == "stale"


def test_real_pg_changed_knowledge_epoch_cannot_reuse_current_database_column(pg_engine, tmp_path):
    seeded, _imported, service, _receipt = create_assessment(pg_engine, tmp_path)
    with pg_engine.begin() as connection:
        connection.execute(
            update(scope_epochs)
            .where(scope_epochs.c.scope_key == "tenant:" + seeded["tenant"])
            .values(epoch=scope_epochs.c.epoch + 1)
        )
    selection, result = select_for_actor(
        pg_engine, seeded, service, fixture_request(version="1.4.1")
    )
    assert selection.assessment_ids == (None,) and selection.reason_codes == ("assessment_stale",)
    assert result.results[0].status == "insufficient_evidence"


@pytest.mark.parametrize("change", ["expired", "role_downgrade"])
def test_real_pg_authentication_change_rejects_even_an_empty_selection(pg_engine, tmp_path, change):
    seeded, _imported, service, _receipt = create_assessment(pg_engine, tmp_path)
    with pg_engine.begin() as connection:
        if change == "expired":
            fixture_now = datetime.now(UTC)
            connection.execute(
                update(auth_sessions)
                .where(
                    auth_sessions.c.session_hash
                    == hashlib.sha256(seeded["asset_token"].encode()).hexdigest()
                )
                .values(
                    issued_at=fixture_now - timedelta(seconds=2),
                    expires_at=fixture_now - timedelta(seconds=1),
                )
            )
        else:
            connection.execute(
                update(users)
                .where(users.c.user_id == seeded["asset_actor"].user_id)
                .values(role=Role.VIEWER.value)
            )
    with pytest.raises(SessionExpiredError if change == "expired" else PermissionDeniedError):
        select_for_actor(pg_engine, seeded, service, fixture_request(version="2.0"))
