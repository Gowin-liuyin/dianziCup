"""Explicit session/API key credentials and PostgreSQL transaction authorization."""

from __future__ import annotations

import hashlib
import re
import secrets
import time
import uuid
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import SecretStr
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine, RowMapping

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.credential_models import api_key_rate_buckets, api_keys
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.knowledge.models import users

API_KEY_RESOURCE = "urn:dianzi:api:v1"
API_KEY_AUDIENCE = API_KEY_RESOURCE
API_KEY_DEFAULT_LIFETIME = timedelta(days=30)
API_KEY_MAX_LIFETIME = timedelta(days=90)
API_KEY_ALLOWED_SCOPES = frozenset({"read:public", "read:asset"})
API_KEY_RATE_LIMITS = {"read": 60, "ask": 10}
QUERY_CREDENTIAL_NAMES = frozenset(
    {
        "token",
        "access_token",
        "api_key",
        "apikey",
        "api-key",
        "key",
        "credential",
        "session_token",
        "session",
        "session_id",
        "cookie",
        "authorization",
        "bearer",
        "bearer_token",
        "x-api-key",
    }
)
BEARER_TOKEN = re.compile(r"[A-Za-z0-9._~+/-]+=*")


class CredentialParsingError(ValueError):
    """Malformed or ambiguous authentication without reflecting supplied values."""


class InvalidApiKeyError(PermissionError):
    """Unknown, expired, revoked or otherwise unusable key; map to HTTP 401."""


class ApiKeyNotFoundError(LookupError):
    """Missing and other-owner keys share HTTP 404 semantics."""


class ApiKeyRateLimitedError(RuntimeError):
    """A PG minute bucket is full; map to HTTP 429 with the bounded retry delay."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("API key rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


def _validate_secret(token: SecretStr) -> None:
    if not isinstance(token, SecretStr):
        raise TypeError("credential must use SecretStr")
    value = token.get_secret_value()
    if not value or len(value) > 4096 or not BEARER_TOKEN.fullmatch(value):
        raise ValueError("credential is not valid")


@dataclass(frozen=True, slots=True)
class SessionCredential:
    token: SecretStr

    def __post_init__(self) -> None:
        _validate_secret(self.token)


@dataclass(frozen=True, slots=True)
class ApiKeyCredential:
    token: SecretStr

    def __post_init__(self) -> None:
        _validate_secret(self.token)


type AuthenticatedCredential = SessionCredential | ApiKeyCredential


@dataclass(frozen=True, slots=True)
class ApiKeyMetadata:
    key_id: str
    user_id: str
    resource: str
    scopes: frozenset[str]
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class IssuedApiKey:
    """Only issue_key returns a secret; subsequent metadata operations cannot retrieve it."""

    metadata: ApiKeyMetadata
    token: SecretStr


def parse_request_credential(
    authorization_headers: Sequence[str],
    *,
    session_cookie: str | None = None,
    query_parameter_names: Collection[str] = (),
) -> AuthenticatedCredential:
    """Pass all raw Authorization values and query names, before framework coalescing."""
    if any(name.casefold() in QUERY_CREDENTIAL_NAMES for name in query_parameter_names):
        raise CredentialParsingError("query credentials are not allowed")
    if len(authorization_headers) > 1:
        raise CredentialParsingError("ambiguous authentication")
    if authorization_headers:
        if session_cookie is not None:
            raise CredentialParsingError("ambiguous authentication")
        value = authorization_headers[0]
        scheme, separator, token = value.partition(" ")
        if scheme.casefold() != "bearer" or separator != " " or not BEARER_TOKEN.fullmatch(token):
            raise CredentialParsingError("authorization header is not valid")
        try:
            return ApiKeyCredential(SecretStr(token))
        except ValueError:
            raise CredentialParsingError("authorization header is not valid") from None
    if session_cookie is not None:
        try:
            return SessionCredential(SecretStr(session_cookie))
        except ValueError:
            raise CredentialParsingError("session cookie is not valid") from None
    raise CredentialParsingError("authentication is required")


def _aware_utc(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("server time must be timezone aware")
    return now.astimezone(UTC)


def validate_key_expiration(now: datetime, expires_at: datetime | None) -> datetime:
    now = _aware_utc(now)
    expires_at = now + API_KEY_DEFAULT_LIFETIME if expires_at is None else _aware_utc(expires_at)
    if not now < expires_at <= now + API_KEY_MAX_LIFETIME:
        raise ValueError("API key expiration must be within 90 days")
    return expires_at


def validate_key_scopes(scope: AccessScope, scopes: frozenset[str]) -> tuple[str, ...]:
    if not isinstance(scopes, frozenset) or not scopes or not scopes <= API_KEY_ALLOWED_SCOPES:
        raise ValueError("API key scopes must be supported and nonempty")
    if not scopes <= scope.permissions:
        raise PermissionDeniedError("API key scopes exceed current permissions")
    return tuple(sorted(scopes))


def _require_transaction(connection: Connection) -> None:
    if not connection.in_transaction():
        raise ValueError("authentication requires the caller transaction")


def _token_hash(credential: ApiKeyCredential) -> str:
    return hashlib.sha256(credential.token.get_secret_value().encode("ascii")).hexdigest()


def _advance_server_time(server_now: datetime, started: float) -> datetime:
    """Advance the caller's trusted server clock by actual elapsed IO and lock waiting."""
    return server_now + timedelta(seconds=time.monotonic() - started)


def _validate_locked_api_key(row: RowMapping, now: datetime) -> None:
    if (
        row["resource"] != API_KEY_RESOURCE
        or row["issued_at"] > now
        or row["expires_at"] <= now
        or row["revoked_at"] is not None
    ):
        raise InvalidApiKeyError("API key is not valid")


def _lock_api_key(
    connection: Connection, credential: ApiKeyCredential, now: datetime
) -> tuple[AccessScope, RowMapping]:
    started = time.monotonic()
    row = (
        connection.execute(
            select(
                api_keys.c.key_id,
                api_keys.c.user_id,
                api_keys.c.scopes,
                api_keys.c.resource,
                api_keys.c.issued_at,
                api_keys.c.expires_at,
                api_keys.c.revoked_at,
                users.c.tenant_id,
                users.c.role,
            )
            .select_from(api_keys.join(users))
            .where(api_keys.c.token_hash == _token_hash(credential))
            .with_for_update(read=True, of=(api_keys, users))
        )
        .mappings()
        .first()
    )
    if row is None:
        raise InvalidApiKeyError("API key is not valid")
    _validate_locked_api_key(row, _advance_server_time(now, started))
    stored_scopes = row["scopes"]
    if not isinstance(stored_scopes, list) or not stored_scopes:
        raise InvalidApiKeyError("API key is not valid")
    if any(not isinstance(value, str) for value in stored_scopes):
        raise InvalidApiKeyError("API key is not valid")
    key_scopes = frozenset(stored_scopes)
    if not key_scopes <= API_KEY_ALLOWED_SCOPES:
        raise InvalidApiKeyError("API key is not valid")
    try:
        current = AccessScope.for_authenticated_user(
            str(row["user_id"]), row["tenant_id"], Role(row["role"])
        )
    except ValueError:
        raise InvalidApiKeyError("API key is not valid") from None
    permissions = key_scopes & current.permissions
    if not permissions:
        raise InvalidApiKeyError("API key is not valid")
    return (
        AccessScope(
            current.user_id,
            current.tenant_id,
            current.role,
            permissions,
            current.permission_version,
        ),
        row,
    )


def lock_authenticated_principal(
    connection: Connection, credential: AuthenticatedCredential, now: datetime
) -> AccessScope:
    """Pass fresh trusted server time; scope locks survive only until this transaction commits."""
    _require_transaction(connection)
    now = _aware_utc(now)
    if isinstance(credential, SessionCredential):
        return lock_authenticated_scope(connection, credential.token.get_secret_value(), now)
    if isinstance(credential, ApiKeyCredential):
        return _lock_api_key(connection, credential, now)[0]
    raise TypeError("explicit authenticated credential is required")


def consume_api_key_rate_limit(
    connection: Connection,
    credential: ApiKeyCredential,
    now: datetime,
    *,
    operation: Literal["read", "ask"] = "read",
) -> AccessScope:
    """Count once in the business transaction; failed operations roll back their reservation."""
    _require_transaction(connection)
    now = _aware_utc(now)
    if not isinstance(credential, ApiKeyCredential):
        raise TypeError("API key credential is required")
    if operation not in API_KEY_RATE_LIMITS:
        raise ValueError("API key rate operation is not supported")
    started = time.monotonic()
    scope, row = _lock_api_key(connection, credential, now)
    key_id = str(row["key_id"])
    while True:
        current_now = _advance_server_time(now, started)
        _validate_locked_api_key(row, current_now)
        window_start = current_now.replace(second=0, microsecond=0)
        bucket_filter = (
            api_key_rate_buckets.c.key_id == key_id,
            api_key_rate_buckets.c.operation == operation,
            api_key_rate_buckets.c.window_started_at == window_start,
        )
        connection.execute(
            pg_insert(api_key_rate_buckets)
            .values(
                key_id=key_id, operation=operation, window_started_at=window_start, request_count=0
            )
            .on_conflict_do_nothing()
        )
        request_count: int = connection.execute(
            select(api_key_rate_buckets.c.request_count).where(*bucket_filter).with_for_update()
        ).scalar_one()
        current_now = _advance_server_time(now, started)
        _validate_locked_api_key(row, current_now)
        if current_now.replace(second=0, microsecond=0) != window_start:
            continue
        if request_count >= API_KEY_RATE_LIMITS[operation]:
            raise ApiKeyRateLimitedError(60 - current_now.second)
        connection.execute(
            update(api_key_rate_buckets)
            .where(*bucket_filter)
            .values(request_count=request_count + 1)
        )
        return scope


def _key_metadata(row: RowMapping) -> ApiKeyMetadata:
    return ApiKeyMetadata(
        key_id=str(row["key_id"]),
        user_id=str(row["user_id"]),
        resource=str(row["resource"]),
        scopes=frozenset(row["scopes"]),
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        version=int(row["version"]),
    )


class PgApiKeyService:
    """Own-key management requires a session; caller HTTP boundaries retain Origin and CSRF."""

    def __init__(self, engine: Engine, clock: Callable[[], datetime] | None = None) -> None:
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue_key(
        self,
        credential: SessionCredential,
        scopes: frozenset[str],
        *,
        expires_at: datetime | None = None,
    ) -> IssuedApiKey:
        if not isinstance(credential, SessionCredential):
            raise TypeError("key management requires a session credential")
        now = _aware_utc(self._clock())
        expiration = validate_key_expiration(now, expires_at)
        with self._engine.begin() as connection:
            scope = lock_authenticated_principal(connection, credential, now)
            canonical_scopes = validate_key_scopes(scope, scopes)
            token = SecretStr("dzk_" + secrets.token_urlsafe(32))
            row = (
                connection.execute(
                    insert(api_keys)
                    .values(
                        key_id=str(uuid.uuid4()),
                        token_hash=_token_hash(ApiKeyCredential(token)),
                        user_id=scope.user_id,
                        resource=API_KEY_RESOURCE,
                        scopes=list(canonical_scopes),
                        issued_at=now,
                        expires_at=expiration,
                        revoked_at=None,
                        version=1,
                    )
                    .returning(api_keys)
                )
                .mappings()
                .one()
            )
            issued = IssuedApiKey(_key_metadata(row), token)
        return issued

    def revoke_key(self, credential: SessionCredential, key_id: str) -> ApiKeyMetadata:
        if not isinstance(credential, SessionCredential):
            raise TypeError("key management requires a session credential")
        now = _aware_utc(self._clock())
        with self._engine.begin() as connection:
            scope = lock_authenticated_principal(connection, credential, now)
            row = (
                connection.execute(
                    select(api_keys)
                    .where(api_keys.c.key_id == key_id, api_keys.c.user_id == scope.user_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ApiKeyNotFoundError("resource not found")
            if row["revoked_at"] is None:
                if now < row["issued_at"]:
                    raise ValueError("server time precedes key issuance")
                row = (
                    connection.execute(
                        update(api_keys)
                        .where(api_keys.c.key_id == key_id)
                        .values(revoked_at=now, version=api_keys.c.version + 1)
                        .returning(api_keys)
                    )
                    .mappings()
                    .one()
                )
            return _key_metadata(row)

    def list_keys(
        self, credential: SessionCredential, *, limit: int = 20
    ) -> tuple[ApiKeyMetadata, ...]:
        if not isinstance(credential, SessionCredential):
            raise TypeError("key management requires a session credential")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("API key listing limit must be between 1 and 100")
        now = _aware_utc(self._clock())
        with self._engine.begin() as connection:
            scope = lock_authenticated_principal(connection, credential, now)
            rows = connection.execute(
                select(api_keys)
                .where(api_keys.c.user_id == scope.user_id)
                .order_by(api_keys.c.issued_at.desc(), api_keys.c.key_id.desc())
                .limit(limit)
            ).mappings()
            return tuple(_key_metadata(row) for row in rows)
