"""Synthetic IO exposes time crossing real authorization and quota lock boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import Connection

from ai_intel.api.credentials import (
    API_KEY_RESOURCE,
    ApiKeyCredential,
    InvalidApiKeyError,
    consume_api_key_rate_limit,
    lock_authenticated_principal,
)

NOW = datetime(2026, 10, 16, 1, 0, 12, tzinfo=UTC)
KEY = ApiKeyCredential(SecretStr("synthetic-lock-time-credential"))


def locked_key_result(expires_at: datetime) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.first.return_value = {
        "key_id": "synthetic-key",
        "user_id": "synthetic-owner",
        "scopes": ["read:public", "read:asset"],
        "tenant_id": "synthetic-current-tenant",
        "role": "analyst",
        "resource": API_KEY_RESOURCE,
        "issued_at": NOW - timedelta(days=1),
        "expires_at": expires_at,
        "revoked_at": None,
    }
    return result


@pytest.mark.parametrize("elapsed,expiry_seconds", [(3.0, 3.0), (4.0, 3.0)])
def test_key_expiring_while_key_and_owner_locks_wait_is_denied(
    elapsed: float, expiry_seconds: float
) -> None:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    connection.execute.return_value = locked_key_result(NOW + timedelta(seconds=expiry_seconds))
    with (
        patch("time.monotonic", side_effect=[100.0, 100.0 + elapsed]),
        pytest.raises(InvalidApiKeyError, match="API key is not valid"),
    ):
        lock_authenticated_principal(connection, KEY, NOW)


def test_lock_wait_before_expiry_keeps_current_role_tenant_and_scope() -> None:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    result = locked_key_result(NOW + timedelta(seconds=3))
    result.mappings.return_value.first.return_value.update(role="viewer")
    connection.execute.return_value = result
    with patch("time.monotonic", side_effect=[100.0, 101.0]):
        scope = lock_authenticated_principal(connection, KEY, NOW)
    assert scope.tenant_id == "synthetic-current-tenant"
    assert scope.role.value == "viewer" and scope.permissions == frozenset({"read:public"})


def test_key_not_yet_issued_at_post_lock_server_time_is_denied() -> None:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    result = locked_key_result(NOW + timedelta(seconds=10))
    result.mappings.return_value.first.return_value.update(issued_at=NOW + timedelta(seconds=4))
    connection.execute.return_value = result
    with (
        patch("time.monotonic", side_effect=[100.0, 103.0]),
        pytest.raises(InvalidApiKeyError),
    ):
        lock_authenticated_principal(connection, KEY, NOW)


@pytest.mark.parametrize(
    "server_now",
    [
        datetime(2026, 11, 1, 1, 59, 59, tzinfo=timezone(timedelta(hours=-4))),
        datetime(2026, 3, 8, 1, 59, 59, tzinfo=timezone(timedelta(hours=-5))),
    ],
)
def test_post_lock_expiry_uses_absolute_utc_elapsed_across_dst_boundaries(
    server_now: datetime,
) -> None:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    row = locked_key_result(server_now.astimezone(UTC) + timedelta(seconds=1))
    row.mappings.return_value.first.return_value.update(issued_at=server_now - timedelta(hours=1))
    connection.execute.return_value = row
    with (
        patch("time.monotonic", side_effect=[100.0, 102.0]),
        pytest.raises(InvalidApiKeyError),
    ):
        lock_authenticated_principal(connection, KEY, server_now)


def test_quota_wait_that_crosses_expiry_never_increments_request_count() -> None:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    count = MagicMock()
    count.scalar_one.return_value = 0
    connection.execute.side_effect = [
        locked_key_result(NOW + timedelta(seconds=2)),
        MagicMock(),
        count,
    ]
    with (
        patch("time.monotonic", side_effect=[100.0, 100.0, 100.0, 100.0, 103.0]),
        pytest.raises(InvalidApiKeyError, match="API key is not valid"),
    ):
        consume_api_key_rate_limit(connection, KEY, NOW, operation="ask")
    assert connection.execute.call_count == 3


def test_quota_wait_crossing_a_minute_consumes_only_the_new_window() -> None:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    old_count, new_count = MagicMock(), MagicMock()
    old_count.scalar_one.return_value = 10
    new_count.scalar_one.return_value = 0
    connection.execute.side_effect = [
        locked_key_result(NOW + timedelta(hours=1)),
        MagicMock(),
        old_count,
        MagicMock(),
        new_count,
        MagicMock(),
    ]
    server_now = NOW.replace(second=59, microsecond=500000)
    with patch("time.monotonic", side_effect=[100.0, 100.0, 100.0, 100.0, 101.0, 101.0, 101.0]):
        scope = consume_api_key_rate_limit(connection, KEY, server_now, operation="ask")
    assert scope.user_id == "synthetic-owner"
    statements = [call.args[0] for call in connection.execute.call_args_list]
    inserted = [statement.compile().params for statement in statements if statement.is_insert]
    assert [values["window_started_at"] for values in inserted] == [
        datetime(2026, 10, 16, 1, 0, tzinfo=UTC),
        datetime(2026, 10, 16, 1, 1, tzinfo=UTC),
    ]
    updated = [statement.compile().params for statement in statements if statement.is_update]
    assert len(updated) == 1 and updated[0]["request_count"] == 1
