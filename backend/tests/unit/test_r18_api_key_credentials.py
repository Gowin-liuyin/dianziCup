"""Credential boundary tests use synthetic secrets and no database."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from ai_intel.api.credentials import (
    API_KEY_RESOURCE,
    ApiKeyCredential,
    CredentialParsingError,
    SessionCredential,
    parse_request_credential,
    validate_key_expiration,
    validate_key_scopes,
)
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role

NOW = datetime(2026, 10, 16, 1, 0, tzinfo=UTC)


@pytest.mark.parametrize("credential_type", [SessionCredential, ApiKeyCredential])
def test_secret_credentials_are_immutable_and_redacted(
    credential_type: type[SessionCredential] | type[ApiKeyCredential],
) -> None:
    token = SecretStr("synthetic-credential-value")
    credential = credential_type(token)
    assert token.get_secret_value() not in repr(credential)
    with pytest.raises(FrozenInstanceError):
        credential.__setattr__("token", SecretStr("replacement"))


@pytest.mark.parametrize("value", ["", "bad\nvalue", "bad value", "非ASCII"])
def test_credentials_reject_invalid_secret(value: str) -> None:
    with pytest.raises(ValueError, match="credential is not valid"):
        ApiKeyCredential(SecretStr(value))


@pytest.mark.parametrize(
    "headers,cookie,query_names",
    [
        (["Bearer synthetic", "Bearer second"], None, ()),
        (["Bearer synthetic"], "session-value", ()),
        (["Bearer synthetic"], None, ("access_token",)),
        ([], "session-value", ("API_KEY",)),
        (["Bearer\tsynthetic"], None, ()),
        (["Bearer  synthetic"], None, ()),
        (["Bearer synthetic, Bearer second"], None, ()),
        (["Basic synthetic"], None, ()),
        (["Bearer synthetic\r\n"], None, ()),
        (["Bearer"], None, ()),
        ([""], None, ()),
        ([], None, ()),
    ],
)
def test_reject_ambiguous_or_malformed_request_credentials(
    headers: list[str], cookie: str | None, query_names: tuple[str, ...]
) -> None:
    with pytest.raises(CredentialParsingError) as error:
        parse_request_credential(headers, session_cookie=cookie, query_parameter_names=query_names)
    assert "synthetic" not in str(error.value)
    assert "session-value" not in str(error.value)


def test_request_parser_keeps_session_and_key_distinct() -> None:
    key = parse_request_credential(["bEaReR synthetic_key-42"], query_parameter_names=("q",))
    session = parse_request_credential([], session_cookie="synthetic-session")
    assert isinstance(key, ApiKeyCredential)
    assert isinstance(session, SessionCredential)
    assert key.token.get_secret_value() == "synthetic_key-42"
    assert API_KEY_RESOURCE == "urn:dianzi:api:v1"


def test_expiration_default_and_maximum() -> None:
    assert validate_key_expiration(NOW, None) == NOW + timedelta(days=30)
    assert validate_key_expiration(NOW, NOW + timedelta(days=90)) == NOW + timedelta(days=90)


@pytest.mark.parametrize(
    "now,expires_at",
    [
        (NOW.replace(tzinfo=None), None),
        (NOW, NOW.replace(tzinfo=None)),
        (NOW, NOW),
        (NOW, NOW - timedelta(seconds=1)),
        (NOW, NOW + timedelta(days=90, microseconds=1)),
    ],
)
def test_reject_invalid_expiration(now: datetime, expires_at: datetime | None) -> None:
    with pytest.raises(ValueError):
        validate_key_expiration(now, expires_at)


def test_key_scopes_cannot_add_admin_or_missing_role_permissions() -> None:
    viewer = AccessScope.for_authenticated_user("viewer", "tenant-a", Role.VIEWER)
    admin = AccessScope.for_authenticated_user("admin", None, Role.SYSTEM_ADMIN)
    assert validate_key_scopes(viewer, frozenset({"read:public"})) == ("read:public",)
    for scopes in (frozenset(), frozenset({"read:asset"}), frozenset({"manage:users"})):
        with pytest.raises((ValueError, PermissionDeniedError)):
            validate_key_scopes(viewer, scopes)
    with pytest.raises(ValueError):
        validate_key_scopes(admin, frozenset({"read:audit"}))
