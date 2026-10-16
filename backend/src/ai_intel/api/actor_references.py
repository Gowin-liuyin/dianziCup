"""Internal, secretless actor references for durable server-owned jobs.

References are locators, not credentials. Only server authentication factories and
trusted PostgreSQL workflow records may construct them; HTTP must never decode them.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.engine import Connection, RowMapping

from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.credential_models import api_keys
from ai_intel.api.credentials import (
    API_KEY_ALLOWED_SCOPES,
    API_KEY_RESOURCE,
    ApiKeyCredential,
    AuthenticatedCredential,
    SessionCredential,
)
from ai_intel.domain.access import PERMISSION_VERSION, AccessScope, PermissionDeniedError, Role
from ai_intel.knowledge.models import job_runs, users

_FACTORY_MARKER = object()
_PAYLOAD_FIELDS = frozenset(
    {
        "credential_kind",
        "user_id",
        "tenant_id",
        "role",
        "permissions",
        "permission_version",
        "permissions_digest",
        "resource",
        "issued_at",
        "created_at",
        "session_hash",
        "key_id",
        "credential_version",
    }
)


class InvalidActorReferenceError(PermissionDeniedError):
    """Invalid or stale authority; error text never reflects a locator or credential."""


@dataclass(frozen=True, slots=True)
class ActorReference:
    """Frozen authentication context; no raw session or API key may enter this object."""

    credential_kind: Literal["session", "api_key"]
    user_id: str
    tenant_id: str | None
    role: Role
    permissions: frozenset[str]
    permission_version: int
    permissions_digest: str
    resource: str
    issued_at: datetime
    created_at: datetime
    session_hash: str | None = field(repr=False)
    key_id: str | None
    credential_version: int | None
    _factory: InitVar[object | None] = None

    def __post_init__(self, _factory: object | None) -> None:
        if _factory is not _FACTORY_MARKER:
            raise TypeError("actor references require the internal server factory")


@dataclass(frozen=True, slots=True)
class ActorJobOwner:
    """Values read from the locked, immutable PostgreSQL workflow/generation owner row."""

    user_id: str
    tenant_id: str | None
    authorized_role: Role
    actor_reference: Mapping[str, object]


class ActorJobOwnerPort(Protocol):
    """Server factory supplies a concrete PG reader; it must use this exact transaction."""

    def lock_actor_job_owner(self, connection: Connection, job_id: str) -> ActorJobOwner | None:
        """Read and FOR UPDATE the real workflow/generation owner by its job foreign key."""
        ...


def _deny() -> InvalidActorReferenceError:
    return InvalidActorReferenceError("actor reference is not valid")


def _text(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise _deny()
    return value


def _time(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise _deny()
    return value.astimezone(UTC)


def _payload_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise _deny()
    try:
        return _time(datetime.fromisoformat(value))
    except ValueError:
        raise _deny() from None


def _permissions_digest(permissions: frozenset[str]) -> str:
    encoded = json.dumps(sorted(permissions), separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _require_transaction(connection: Connection) -> None:
    if not connection.in_transaction():
        raise ValueError("actor authentication requires the caller transaction")


def _current_scope(row: RowMapping, kind: Literal["session", "api_key"]) -> AccessScope:
    user_id = _text(row["user_id"])
    tenant_id = row["tenant_id"]
    try:
        role = Role(_text(row["role"]))
    except ValueError:
        raise _deny() from None
    if tenant_id is not None:
        tenant_id = _text(tenant_id)
    elif role is not Role.SYSTEM_ADMIN:
        raise _deny()
    current = AccessScope.for_authenticated_user(user_id, tenant_id, role)
    if kind == "api_key":
        values = row["scopes"]
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) for value in values)
        ):
            raise _deny()
        scopes = frozenset(_text(value) for value in values)
        if not scopes <= API_KEY_ALLOWED_SCOPES:
            raise _deny()
        permissions = current.permissions & scopes
        if not permissions:
            raise _deny()
        return AccessScope(user_id, tenant_id, role, permissions, current.permission_version)
    return current


def _validate_lifetime(row: RowMapping, now: datetime) -> None:
    issued_at, expires_at = _time(row["issued_at"]), _time(row["expires_at"])
    if row["revoked_at"] is not None or not issued_at <= now < expires_at:
        raise _deny()


def _lock_row(
    connection: Connection,
    kind: Literal["session", "api_key"],
    locator: str,
    *,
    by_secret_hash: bool = False,
) -> RowMapping:
    table = auth_sessions if kind == "session" else api_keys
    locator_column = table.c.session_hash if kind == "session" else table.c.key_id
    if kind == "api_key" and by_secret_hash:
        locator_column = table.c.token_hash
    row = (
        connection.execute(
            select(table, users.c.tenant_id, users.c.role)
            .select_from(table.join(users))
            .where(locator_column == locator)
            .with_for_update(read=True, of=(table, users))
        )
        .mappings()
        .first()
    )
    if row is None:
        raise _deny()
    return row


def lock_session_scope(connection: Connection, session_token: str, now: datetime) -> AccessScope:
    """Legacy cookie authentication includes actual lock elapsed time in expiry validation."""
    _require_transaction(connection)
    started = monotonic()
    try:
        now = _time(now)
        if not isinstance(session_token, str) or not session_token or len(session_token) > 4096:
            raise _deny()
        locator = hashlib.sha256(session_token.encode()).hexdigest()
        row = _lock_row(connection, "session", locator)
        _validate_lifetime(row, now + timedelta(seconds=monotonic() - started))
        return _current_scope(row, "session")
    except InvalidActorReferenceError:
        raise SessionExpiredError("session is not valid") from None


def create_actor_reference(
    connection: Connection,
    credential: AuthenticatedCredential,
    now: datetime,
) -> ActorReference:
    """Authenticate and freeze context in the same transaction that enqueues its job."""
    _require_transaction(connection)
    now = _time(now)
    started = monotonic()
    if isinstance(credential, SessionCredential):
        kind: Literal["session", "api_key"] = "session"
    elif isinstance(credential, ApiKeyCredential):
        kind = "api_key"
    else:
        raise TypeError("explicit authenticated credential is required")
    locator = hashlib.sha256(credential.token.get_secret_value().encode()).hexdigest()
    row = _lock_row(connection, kind, locator, by_secret_hash=True)
    _validate_lifetime(row, now + timedelta(seconds=monotonic() - started))
    current = _current_scope(row, kind)
    payload: dict[str, object] = {
        "credential_kind": kind,
        "user_id": current.user_id,
        "tenant_id": current.tenant_id,
        "role": current.role.value,
        "permissions": sorted(current.permissions),
        "permission_version": current.permission_version,
        "permissions_digest": _permissions_digest(current.permissions),
        "resource": API_KEY_RESOURCE if kind == "session" else row["resource"],
        "issued_at": _time(row["issued_at"]).isoformat(),
        "created_at": now.isoformat(),
        "session_hash": locator if kind == "session" else None,
        "key_id": None if kind == "session" else row["key_id"],
        "credential_version": None if kind == "session" else row["version"],
    }
    return actor_reference_from_payload(payload)


def actor_reference_payload(reference: ActorReference) -> dict[str, object]:
    """Serialize only for a server-owned PG workflow record, never a public response."""
    if not isinstance(reference, ActorReference):
        raise TypeError("internal actor reference is required")
    return {
        "credential_kind": reference.credential_kind,
        "user_id": reference.user_id,
        "tenant_id": reference.tenant_id,
        "role": reference.role.value,
        "permissions": sorted(reference.permissions),
        "permission_version": reference.permission_version,
        "permissions_digest": reference.permissions_digest,
        "resource": reference.resource,
        "issued_at": reference.issued_at.isoformat(),
        "created_at": reference.created_at.isoformat(),
        "session_hash": reference.session_hash,
        "key_id": reference.key_id,
        "credential_version": reference.credential_version,
    }


def actor_reference_from_payload(payload: Mapping[str, object]) -> ActorReference:
    """Decode an internal PG record; request/body input is never an authorized source."""
    if not isinstance(payload, Mapping) or frozenset(payload) != _PAYLOAD_FIELDS:
        raise _deny()
    kind = payload["credential_kind"]
    if kind not in ("session", "api_key"):
        raise _deny()
    try:
        role = Role(_text(payload["role"]))
    except ValueError:
        raise _deny() from None
    tenant_id = payload["tenant_id"]
    if tenant_id is not None:
        tenant_id = _text(tenant_id)
    elif role is not Role.SYSTEM_ADMIN:
        raise _deny()
    values = payload["permissions"]
    if not isinstance(values, list) or not values:
        raise _deny()
    permissions = frozenset(_text(value) for value in values)
    if len(permissions) != len(values):
        raise _deny()
    current = AccessScope.for_authenticated_user(_text(payload["user_id"]), tenant_id, role)
    permission_version = payload["permission_version"]
    if (
        type(permission_version) is not int
        or permission_version != PERMISSION_VERSION
        or not permissions <= current.permissions
        or payload["permissions_digest"] != _permissions_digest(permissions)
        or payload["resource"] != API_KEY_RESOURCE
    ):
        raise _deny()
    session_hash = payload["session_hash"]
    key_id, version = payload["key_id"], payload["credential_version"]
    if kind == "session":
        if (
            not isinstance(session_hash, str)
            or not re.fullmatch("[0-9a-f]{64}", session_hash)
            or key_id is not None
            or version is not None
        ):
            raise _deny()
    else:
        if (
            session_hash is not None
            or not isinstance(key_id, str)
            or not key_id
            or len(key_id) > 256
            or type(version) is not int
            or version < 1
            or not permissions <= API_KEY_ALLOWED_SCOPES
        ):
            raise _deny()
    issued_at = _payload_time(payload["issued_at"])
    created_at = _payload_time(payload["created_at"])
    if issued_at > created_at:
        raise _deny()
    return ActorReference(
        "session" if kind == "session" else "api_key",
        current.user_id,
        tenant_id,
        role,
        permissions,
        permission_version,
        _permissions_digest(permissions),
        API_KEY_RESOURCE,
        issued_at,
        created_at,
        session_hash if isinstance(session_hash, str) else None,
        key_id if isinstance(key_id, str) else None,
        version if type(version) is int else None,
        _factory=_FACTORY_MARKER,
    )


def lock_actor_reference_scope(
    connection: Connection,
    reference: ActorReference,
    now: datetime,
) -> AccessScope:
    """Revalidate the current credential and user; an old reference never expands authority."""
    _require_transaction(connection)
    if not isinstance(reference, ActorReference):
        raise TypeError("internal actor reference is required")
    now = _time(now)
    started = monotonic()
    locator = reference.session_hash if reference.credential_kind == "session" else reference.key_id
    if locator is None:
        raise _deny()
    row = _lock_row(connection, reference.credential_kind, locator)
    final_now = now + timedelta(seconds=monotonic() - started)
    _validate_lifetime(row, final_now)
    current = _current_scope(row, reference.credential_kind)
    if (
        current.user_id != reference.user_id
        or current.tenant_id != reference.tenant_id
        or current.role != reference.role
        or current.permission_version != reference.permission_version
        or reference.created_at > final_now
        or _time(row["issued_at"]) != reference.issued_at
        or not reference.permissions <= current.permissions
        or reference.permissions_digest != _permissions_digest(reference.permissions)
        or reference.resource != API_KEY_RESOURCE
    ):
        raise _deny()
    if reference.credential_kind == "api_key" and (
        row["key_id"] != reference.key_id
        or type(row["version"]) is not int
        or row["version"] != reference.credential_version
        or row["resource"] != reference.resource
    ):
        raise _deny()
    return AccessScope(
        current.user_id,
        current.tenant_id,
        current.role,
        reference.permissions & current.permissions,
        current.permission_version,
    )


def validate_actor_job_binding(
    connection: Connection,
    reference: ActorReference,
    job_id: str,
    owner_port: ActorJobOwnerPort,
) -> None:
    """After credential locks, bind the PG job and locked workflow owner, never body fields."""
    _require_transaction(connection)
    if not isinstance(reference, ActorReference):
        raise TypeError("internal actor reference is required")
    job = (
        connection.execute(
            select(job_runs.c.tenant_id).where(job_runs.c.job_id == _text(job_id)).with_for_update()
        )
        .mappings()
        .first()
    )
    if job is None or job["tenant_id"] != reference.tenant_id:
        raise _deny()
    owner = owner_port.lock_actor_job_owner(connection, job_id)
    if (
        not isinstance(owner, ActorJobOwner)
        or owner.user_id != reference.user_id
        or owner.tenant_id != reference.tenant_id
        or owner.authorized_role != reference.role
        or actor_reference_from_payload(owner.actor_reference) != reference
    ):
        raise _deny()


def lock_actor_job_scope(
    connection: Connection,
    reference: ActorReference,
    now: datetime,
    *,
    job_id: str,
    owner_port: ActorJobOwnerPort,
) -> AccessScope:
    """Lock credential/users, PG job and real owner, then check expiry in the same transaction."""
    now = _time(now)
    started = monotonic()
    lock_actor_reference_scope(connection, reference, now)
    validate_actor_job_binding(connection, reference, job_id, owner_port)
    return lock_actor_reference_scope(
        connection,
        reference,
        now + timedelta(seconds=monotonic() - started),
    )
