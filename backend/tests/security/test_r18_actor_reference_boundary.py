"""Synthetic secrets and request-like inputs never become durable actor authority."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import SessionExpiredError


def test_api_key_string_keeps_legacy_cookie_lookup_and_fixed_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    connection.execute.return_value.mappings.return_value.first.return_value = None
    supplied_value = "synthetic-public-key-string"
    with pytest.raises(SessionExpiredError) as error:
        lock_authenticated_scope(connection, supplied_value, datetime.now(UTC))
    assert supplied_value not in str(error.value) and supplied_value not in caplog.text
    statement = connection.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "auth_sessions JOIN users" in sql and "api_keys" not in sql


def test_request_body_self_reported_reference_is_not_a_typed_actor() -> None:
    connection = MagicMock(spec=Connection)
    body = {"user_id": "other-owner", "tenant_id": "other-tenant", "role": "system_admin"}
    with pytest.raises(TypeError, match="internal actor reference"):
        lock_authenticated_scope(connection, body, datetime.now(UTC))
    connection.execute.assert_not_called()
