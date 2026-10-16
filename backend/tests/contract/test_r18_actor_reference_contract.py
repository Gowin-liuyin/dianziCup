"""Internal durable payload contract; no public schema or HTTP authority is introduced."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from pydantic import SecretStr
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from ai_intel.api.actor_references import (
    actor_reference_from_payload,
    actor_reference_payload,
    create_actor_reference,
)
from ai_intel.api.credentials import API_KEY_RESOURCE, ApiKeyCredential


def test_factory_context_is_server_derived_and_payload_is_json_durable() -> None:
    now = datetime(2026, 10, 16, 4, 30, tzinfo=UTC)
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    connection.execute.return_value.mappings.return_value.first.return_value = {
        "key_id": "synthetic-key",
        "user_id": "synthetic-owner",
        "tenant_id": "synthetic-tenant",
        "role": "analyst",
        "resource": API_KEY_RESOURCE,
        "scopes": ["read:public"],
        "issued_at": now - timedelta(days=1),
        "expires_at": now + timedelta(days=1),
        "revoked_at": None,
        "version": 2,
    }
    secret = SecretStr("synthetic-contract-key-token")
    reference = create_actor_reference(connection, ApiKeyCredential(secret), now)
    payload = actor_reference_payload(reference)
    encoded = json.dumps(payload, sort_keys=True)
    assert secret.get_secret_value() not in encoded
    assert reference.permissions == frozenset({"read:public"})
    assert payload["key_id"] == "synthetic-key" and payload["credential_version"] == 2
    assert payload["session_hash"] is None
    assert actor_reference_from_payload(json.loads(encoded)) == reference
    assert set(inspect.signature(create_actor_reference).parameters) == {
        "connection",
        "credential",
        "now",
    }
    statement = connection.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "api_keys JOIN users" in sql
    assert "FOR SHARE OF api_keys, users" in sql
