"""Synthetic server actor references exercise authorization without external resources."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import Connection

from ai_intel.api.actor_references import (
    ActorJobOwner,
    ActorReference,
    InvalidActorReferenceError,
    actor_reference_from_payload,
    actor_reference_payload,
    create_actor_reference,
    lock_actor_job_scope,
    lock_actor_reference_scope,
)
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.credentials import API_KEY_RESOURCE, ApiKeyCredential, SessionCredential
from ai_intel.domain.access import Role

NOW = datetime(2026, 10, 16, 4, 30, tzinfo=UTC)
TOKEN = SecretStr("synthetic-reference-session")


def session_row() -> dict[str, object]:
    return {
        "session_hash": hashlib.sha256(TOKEN.get_secret_value().encode()).hexdigest(),
        "user_id": "synthetic-owner-a",
        "tenant_id": "synthetic-tenant-a",
        "role": "analyst",
        "issued_at": NOW - timedelta(hours=1),
        "expires_at": NOW + timedelta(hours=1),
        "revoked_at": None,
    }


def connection_for(row: dict[str, object]) -> MagicMock:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    connection.execute.return_value.mappings.return_value.first.return_value = row
    return connection


def test_reference_contains_only_server_identity_and_secretless_locator() -> None:
    connection = connection_for(session_row())
    reference = create_actor_reference(connection, SessionCredential(TOKEN), NOW)
    payload = actor_reference_payload(reference)
    assert reference.user_id == "synthetic-owner-a"
    assert reference.tenant_id == "synthetic-tenant-a"
    assert payload["session_hash"] == session_row()["session_hash"]
    assert "token" not in payload and TOKEN.get_secret_value() not in repr(reference)
    restored = actor_reference_from_payload(payload)
    assert restored == reference
    current = lock_actor_reference_scope(connection, restored, NOW)
    assert current.permissions == frozenset({"read:public", "read:asset"})


def test_payload_unknown_fields_fail_closed() -> None:
    reference = create_actor_reference(connection_for(session_row()), SessionCredential(TOKEN), NOW)
    payload = actor_reference_payload(reference)
    payload["token"] = TOKEN.get_secret_value()
    with pytest.raises(InvalidActorReferenceError):
        actor_reference_from_payload(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("credential_kind", "unknown"),
        ("user_id", None),
        ("tenant_id", None),
        ("role", "unknown"),
        ("permissions", []),
        ("permissions", ["manage:users"]),
        ("permissions", ["read:public", "read:public"]),
        ("permission_version", True),
        ("permission_version", 99),
        ("permissions_digest", "invalid"),
        ("resource", "urn:other"),
        ("session_hash", "invalid"),
        ("key_id", "key"),
        ("credential_version", 1),
        ("issued_at", None),
        ("issued_at", "2026-10-16T00:00:00"),
        ("created_at", "2026-10-15T00:00:00+00:00"),
    ],
)
def test_durable_payload_rejects_null_unknown_and_privilege_widening(
    field: str, value: object
) -> None:
    reference = create_actor_reference(connection_for(session_row()), SessionCredential(TOKEN), NOW)
    payload = actor_reference_payload(reference)
    payload[field] = value
    with pytest.raises(InvalidActorReferenceError):
        actor_reference_from_payload(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", "other-owner"),
        ("tenant_id", "other-tenant"),
        ("role", "viewer"),
        ("role", "tenant_admin"),
        ("role", "unknown"),
        ("revoked_at", NOW),
        ("expires_at", NOW),
        ("expires_at", None),
        ("issued_at", NOW + timedelta(seconds=1)),
    ],
)
def test_queue_resume_revalidates_current_session_and_owner(field: str, value: object) -> None:
    row = session_row()
    connection = connection_for(row)
    reference = create_actor_reference(connection, SessionCredential(TOKEN), NOW)
    row[field] = value
    with pytest.raises(InvalidActorReferenceError):
        lock_actor_reference_scope(connection, reference, NOW)


def key_row() -> dict[str, object]:
    return dict(
        session_row(),
        key_id="synthetic-key-id",
        version=3,
        resource=API_KEY_RESOURCE,
        scopes=["read:public", "read:asset"],
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", 4),
        ("version", None),
        ("resource", "other"),
        ("scopes", []),
        ("scopes", ["read:public"]),
        ("scopes", ["manage:users"]),
        ("revoked_at", NOW),
    ],
)
def test_queue_resume_revalidates_key_version_resource_and_scopes(
    field: str, value: object
) -> None:
    row = key_row()
    connection = connection_for(row)
    reference = create_actor_reference(connection, ApiKeyCredential(TOKEN), NOW)
    assert reference.session_hash is None and reference.credential_version == 3
    row[field] = value
    with pytest.raises(InvalidActorReferenceError):
        lock_actor_reference_scope(connection, reference, NOW)


@pytest.mark.parametrize("kind", ["session", "api_key"])
def test_lock_elapsed_time_reaches_exact_microsecond_expiry(
    kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = session_row() if kind == "session" else key_row()
    connection = connection_for(row)
    credential = SessionCredential(TOKEN) if kind == "session" else ApiKeyCredential(TOKEN)
    reference = create_actor_reference(connection, credential, NOW)
    row["expires_at"] = NOW + timedelta(microseconds=1)
    ticks = iter([100.0, 100.000001])
    monkeypatch.setattr("ai_intel.api.actor_references.monotonic", lambda: next(ticks))
    with pytest.raises(InvalidActorReferenceError):
        lock_actor_reference_scope(connection, reference, NOW)


def test_legacy_cookie_wait_expiry_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    row = session_row()
    row["expires_at"] = NOW + timedelta(seconds=1)
    ticks = iter([100.0, 101.0])
    monkeypatch.setattr("ai_intel.api.actor_references.monotonic", lambda: next(ticks))
    with pytest.raises(SessionExpiredError):
        lock_authenticated_scope(connection_for(row), TOKEN.get_secret_value(), NOW)


@pytest.mark.parametrize("input_value", [None, {}, SecretStr("synthetic-key")])
def test_lock_entry_refuses_untyped_reference_or_key(input_value: object) -> None:
    with pytest.raises(TypeError):
        lock_authenticated_scope(connection_for(session_row()), input_value, NOW)


def test_normal_constructor_cannot_self_report_actor_identity() -> None:
    reference = create_actor_reference(connection_for(session_row()), SessionCredential(TOKEN), NOW)
    with pytest.raises(TypeError, match="server factory"):
        ActorReference(
            reference.credential_kind,
            reference.user_id,
            reference.tenant_id,
            reference.role,
            reference.permissions,
            reference.permission_version,
            reference.permissions_digest,
            reference.resource,
            reference.issued_at,
            reference.created_at,
            reference.session_hash,
            reference.key_id,
            reference.credential_version,
        )


@pytest.mark.parametrize(
    "owner_user,owner_tenant,job_tenant,role",
    [
        ("other-user", "synthetic-tenant-a", "synthetic-tenant-a", Role.ANALYST),
        ("synthetic-owner-a", "other-tenant", "synthetic-tenant-a", Role.ANALYST),
        ("synthetic-owner-a", "synthetic-tenant-a", "other-tenant", Role.ANALYST),
        ("synthetic-owner-a", "synthetic-tenant-a", "synthetic-tenant-a", Role.VIEWER),
    ],
)
def test_real_job_and_owner_port_must_bind_both_owner_and_tenant(
    owner_user: str,
    owner_tenant: str,
    job_tenant: str,
    role: Role,
) -> None:
    connection = connection_for(session_row())
    reference = create_actor_reference(connection, SessionCredential(TOKEN), NOW)
    job_result = MagicMock()
    job_result.mappings.return_value.first.return_value = {"tenant_id": job_tenant}
    connection.execute.side_effect = [connection.execute.return_value, job_result]
    owner_port = MagicMock()
    owner_port.lock_actor_job_owner.return_value = ActorJobOwner(
        owner_user,
        owner_tenant,
        role,
        actor_reference_payload(reference),
    )
    with pytest.raises(InvalidActorReferenceError):
        lock_actor_job_scope(connection, reference, NOW, job_id="job-a", owner_port=owner_port)


def test_owner_wait_time_is_included_in_final_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    row = session_row()
    connection = connection_for(row)
    reference = create_actor_reference(connection, SessionCredential(TOKEN), NOW)
    row["expires_at"] = NOW + timedelta(seconds=1)
    job_result = MagicMock()
    job_result.mappings.return_value.first.return_value = {"tenant_id": reference.tenant_id}
    connection.execute.side_effect = [
        connection.execute.return_value,
        job_result,
        connection.execute.return_value,
    ]
    owner_port = MagicMock()
    owner_port.lock_actor_job_owner.return_value = ActorJobOwner(
        reference.user_id,
        reference.tenant_id,
        reference.role,
        actor_reference_payload(reference),
    )
    ticks = iter([100.0, 100.0, 100.0, 101.0, 101.0, 101.0])
    monkeypatch.setattr("ai_intel.api.actor_references.monotonic", lambda: next(ticks))
    with pytest.raises(InvalidActorReferenceError):
        lock_actor_job_scope(connection, reference, NOW, job_id="job-a", owner_port=owner_port)
    assert owner_port.lock_actor_job_owner.call_args.args == (connection, "job-a")


def test_factory_requires_transaction_and_explicit_credential() -> None:
    connection = connection_for(session_row())
    connection.in_transaction.return_value = False
    with pytest.raises(ValueError, match="caller transaction"):
        create_actor_reference(connection, SessionCredential(TOKEN), NOW)
    connection.in_transaction.return_value = True
    with pytest.raises(TypeError):
        create_actor_reference(connection, TOKEN, NOW)
