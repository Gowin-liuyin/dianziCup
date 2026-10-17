"""Offline SQLite observes synthetic PG fixture input; no live source or PG is opened."""

import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from pydantic import HttpUrl
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from tests.integration import test_r18_public_component_selector_pg as selector_fixture
from tests.unit.test_public_write_adapters import (
    fixture_receipt,
    fixture_request,
    fixture_services,
)

from ai_intel.api import actor_references
from ai_intel.api.auth_state import auth_sessions, lock_authenticated_scope
from ai_intel.api.knowledge_read_service import safe_source_uri
from ai_intel.api.public_write_adapters import PublicWriteMappingError, stack_current_assessments
from ai_intel.domain.access import Role
from ai_intel.domain.enums import AssessmentStatus
from ai_intel.knowledge.models import document_revisions


@pytest.fixture
def assessment_input(monkeypatch, tmp_path, request):
    receipt = fixture_receipt(AssessmentStatus.SUPPORTED_APPLICABILITY)
    reference = receipt.prepared.inputs.supports[0].evidence
    seeded = {
        "revision_id": reference.revision_id,
        "document_id": reference.document_id,
        "event_id": receipt.event_id,
        "rule": receipt.prepared.inputs.rule,
    }
    imported = SimpleNamespace(
        asset_id=receipt.asset_id, snapshot=SimpleNamespace(snapshot_id=receipt.asset_snapshot_id)
    )
    assessor = Mock()
    assessor.commit.return_value = receipt
    assessor.read_in_session.return_value = receipt
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE document_revisions (revision_id TEXT PRIMARY KEY, "
                "document_id TEXT NOT NULL, canonical_uri TEXT, revision_number INTEGER, "
                "visibility TEXT, tenant_id TEXT, parse_status TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO document_revisions VALUES "
                "(:revision, :document, NULL, 1, 'tenant', :tenant, 'parsed'), "
                "(:other_revision, :other_document, :other_uri, 2, 'public', NULL, 'parsed')"
            ),
            {
                "revision": reference.revision_id,
                "document": reference.document_id,
                "tenant": receipt.tenant_id,
                "other_revision": str(UUID(int=101)),
                "other_document": str(UUID(int=102)),
                "other_uri": "https://example.invalid/fixture/unrelated",
            },
        )
        before = connection.execute(text("SELECT * FROM document_revisions ORDER BY revision_id"))
        rows_before = [dict(row) for row in before.mappings()]
    monkeypatch.setattr(selector_fixture.original, "seed", Mock(return_value=seeded))
    monkeypatch.setattr(selector_fixture.original, "publish", Mock())
    monkeypatch.setattr(selector_fixture.original, "asset", Mock(return_value=imported))
    monkeypatch.setattr(selector_fixture.original, "assessor", Mock(return_value=assessor))
    binding_field = getattr(request, "param", None)
    if binding_field is not None:
        seeded[binding_field] = str(UUID(int=103))
    try:
        created = selector_fixture.create_assessment(engine, tmp_path)
        assert created == (seeded, imported, assessor, receipt)
        yield engine, receipt, assessor, rows_before
    finally:
        engine.dispose()


def projection_from_fixture_input(engine, receipt):
    reference = receipt.prepared.inputs.supports[0].evidence
    with engine.connect() as connection:
        source_uri = connection.scalar(
            select(document_revisions.c.canonical_uri).where(
                document_revisions.c.revision_id == reference.revision_id,
                document_revisions.c.document_id == reference.document_id,
            )
        )
    _assessment, knowledge = fixture_services(receipt)
    projected = knowledge.read_evidence.return_value
    knowledge.read_evidence.return_value = projected.model_copy(
        update={"source_uri": safe_source_uri(source_uri)}
    )
    return knowledge


def test_fixture_uri_is_typed_bound_and_accepted_without_other_metadata_changes(assessment_input):
    engine, receipt, assessor, rows_before = assessment_input
    reference = receipt.prepared.inputs.supports[0].evidence
    with engine.connect() as connection:
        rows_after = [
            dict(row)
            for row in connection.execute(
                text("SELECT * FROM document_revisions ORDER BY revision_id")
            ).mappings()
        ]
    changed = next(row for row in rows_after if row["revision_id"] == reference.revision_id)
    assert isinstance(changed["canonical_uri"], str)
    uri = urlsplit(changed["canonical_uri"])
    assert (uri.scheme, uri.netloc, uri.path) == (
        "https",
        "example.invalid",
        "/fixture/revisions/" + reference.revision_id,
    )
    assert changed["document_id"] == reference.document_id
    assert receipt.event_id == receipt.prepared.inputs.rule.event_id
    restored = [dict(row) for row in rows_after]
    restored_revision = next(row for row in restored if row["revision_id"] == reference.revision_id)
    restored_revision["canonical_uri"] = None
    assert restored == rows_before
    knowledge = projection_from_fixture_input(engine, receipt)
    assert isinstance(knowledge.read_evidence.return_value.source_uri, HttpUrl)
    assert knowledge.data_mode == "fixture"
    result = stack_current_assessments(
        fixture_request(), (UUID(receipt.assessment_id),), assessor, knowledge
    )
    citation = result.results[0].citations[0]
    assert citation.revision_id == UUID(reference.revision_id)
    assert citation.evidence_id == UUID(reference.evidence_id)
    assert citation.quote == reference.quote_text
    assert str(citation.source_uri) == changed["canonical_uri"]


def test_missing_fixture_uri_still_rejects_current_evidence(assessment_input):
    engine, receipt, assessor, _rows_before = assessment_input
    reference = receipt.prepared.inputs.supports[0].evidence
    with engine.begin() as connection:
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == reference.revision_id)
            .values(canonical_uri=None)
        )
    knowledge = projection_from_fixture_input(engine, receipt)
    assert knowledge.read_evidence.return_value.source_uri is None
    with pytest.raises(PublicWriteMappingError, match=r"^assessment_evidence_changed$"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessor, knowledge
        )


@pytest.mark.parametrize("assessment_input", ["revision_id", "document_id"], indirect=True)
def test_fixture_uri_does_not_bind_a_different_revision_or_document(assessment_input):
    engine, receipt, assessor, rows_before = assessment_input
    with engine.connect() as connection:
        rows_after = [
            dict(row)
            for row in connection.execute(
                text("SELECT * FROM document_revisions ORDER BY revision_id")
            ).mappings()
        ]
    assert rows_after == rows_before
    knowledge = projection_from_fixture_input(engine, receipt)
    with pytest.raises(PublicWriteMappingError, match=r"^assessment_evidence_changed$"):
        stack_current_assessments(
            fixture_request(), (UUID(receipt.assessment_id),), assessor, knowledge
        )


@pytest.fixture
def expiry_input(monkeypatch):
    stamp = datetime(2026, 10, 17, tzinfo=UTC)
    fixture_token = "synthetic-r18-expired-session"
    session_hash = hashlib.sha256(fixture_token.encode()).hexdigest()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE auth_sessions (session_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
                "csrf_token TEXT NOT NULL, issued_at DATETIME NOT NULL, "
                "expires_at DATETIME NOT NULL, "
                "revoked_at DATETIME, CONSTRAINT ck_auth_session_expiry "
                "CHECK (expires_at > issued_at))"
            )
        )
        connection.execute(
            insert(auth_sessions),
            [
                {
                    "session_hash": session_hash,
                    "user_id": "fixture-user",
                    "csrf_token": "synthetic-unused-csrf",
                    "issued_at": stamp,
                    "expires_at": stamp + timedelta(hours=2),
                },
                {
                    "session_hash": "a" * 64,
                    "user_id": "fixture-other-user",
                    "csrf_token": "synthetic-other-csrf",
                    "issued_at": stamp,
                    "expires_at": stamp + timedelta(hours=2),
                },
            ],
        )
        rows_before = [
            dict(row)
            for row in connection.execute(
                select(auth_sessions).order_by(auth_sessions.c.session_hash)
            ).mappings()
        ]

    def observe_pg_session(_connection, kind, locator):
        """Read only local rows and restore PG's timezone-aware datetime IO."""
        assert kind == "session"
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(auth_sessions).where(auth_sessions.c.session_hash == locator)
                )
                .mappings()
                .one()
            )
        return {
            **row,
            "issued_at": row["issued_at"].replace(tzinfo=UTC),
            "expires_at": row["expires_at"].replace(tzinfo=UTC),
            "tenant_id": "fixture-tenant",
            "role": Role.ANALYST.value,
        }

    authenticated_connection = Mock(spec=Connection)
    authenticated_connection.in_transaction.return_value = True
    monkeypatch.setattr(actor_references, "_lock_row", observe_pg_session)
    clock = Mock(spec=datetime)
    clock.now.return_value = stamp
    monkeypatch.setattr(selector_fixture, "datetime", clock)
    seeded = {"asset_token": fixture_token}
    monkeypatch.setattr(
        selector_fixture, "create_assessment", Mock(return_value=(seeded, None, None, None))
    )

    def authenticate(_engine, _seeded, _service, _request):
        return lock_authenticated_scope(authenticated_connection, fixture_token, stamp)

    monkeypatch.setattr(selector_fixture, "select_for_actor", authenticate)
    try:
        yield engine, session_hash, stamp, clock, rows_before, authenticate
    finally:
        engine.dispose()


def test_expired_fixture_reaches_shared_auth_rejection_with_legal_timestamps(
    expiry_input, tmp_path
):
    engine, session_hash, stamp, clock, rows_before, _authenticate = expiry_input
    selector_fixture.test_real_pg_authentication_change_rejects_even_an_empty_selection(
        engine, tmp_path, "expired"
    )
    clock.now.assert_called_once_with(UTC)
    with engine.connect() as connection:
        rows_after = [
            dict(row)
            for row in connection.execute(
                select(auth_sessions).order_by(auth_sessions.c.session_hash)
            ).mappings()
        ]
    expired = next(row for row in rows_after if row["session_hash"] == session_hash)
    assert (
        expired["issued_at"].replace(tzinfo=UTC) < expired["expires_at"].replace(tzinfo=UTC) < stamp
    )
    restored = [dict(row) for row in rows_after]
    session_before = next(row for row in rows_before if row["session_hash"] == session_hash)
    session_after = next(row for row in restored if row["session_hash"] == session_hash)
    session_after["issued_at"] = session_before["issued_at"]
    session_after["expires_at"] = session_before["expires_at"]
    assert restored == rows_before


def test_shared_auth_accepts_the_original_unexpired_fixture_lifetime(expiry_input):
    _engine, _session_hash, _stamp, _clock, _rows_before, authenticate = expiry_input
    scope = authenticate(None, None, None, None)
    assert (scope.user_id, scope.tenant_id, scope.role) == (
        "fixture-user",
        "fixture-tenant",
        Role.ANALYST,
    )


@pytest.mark.parametrize("invalid_field", ["issued_at", "expires_at"])
def test_missing_fixture_session_time_remains_rejected_by_the_database(expiry_input, invalid_field):
    engine, session_hash, _stamp, _clock, _rows_before, _authenticate = expiry_input
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.session_hash == session_hash)
            .values({invalid_field: None})
        )


@pytest.mark.parametrize("offset", [0, -1])
def test_invalid_fixture_session_order_remains_rejected_by_the_database(expiry_input, offset):
    engine, session_hash, stamp, _clock, _rows_before, _authenticate = expiry_input
    with (
        pytest.raises(IntegrityError, match="ck_auth_session_expiry"),
        engine.begin() as connection,
    ):
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.session_hash == session_hash)
            .values(expires_at=stamp + timedelta(seconds=offset))
        )
