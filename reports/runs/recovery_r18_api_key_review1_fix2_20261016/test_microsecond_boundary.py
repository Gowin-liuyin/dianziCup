"""Independent expiry boundary at datetime's one-microsecond resolution; no PG IO."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import Connection

from ai_intel.api.credentials import ApiKeyCredential, InvalidApiKeyError, lock_authenticated_principal


@pytest.mark.parametrize("elapsed,denied", [(0.0000004, False), (0.000001, True)])
def test_elapsed_microsecond_boundary(elapsed, denied):
    now = datetime(2026, 10, 16, 1, 0, tzinfo=UTC)
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    connection.execute.return_value.mappings.return_value.first.return_value = {
        "key_id": "review-key", "user_id": "review-owner", "scopes": ["read:public"],
        "resource": "urn:dianzi:api:v1", "issued_at": now-timedelta(days=1),
        "expires_at": now+timedelta(microseconds=1), "revoked_at": None,
        "tenant_id": "review-tenant", "role": "viewer",
    }
    with patch("time.monotonic", side_effect=[100.0, 100.0+elapsed]):
        if denied:
            with pytest.raises(InvalidApiKeyError):
                lock_authenticated_principal(connection, ApiKeyCredential(SecretStr("reviewsynthetic")), now)
        else:
            scope = lock_authenticated_principal(connection, ApiKeyCredential(SecretStr("reviewsynthetic")), now)
            assert scope.permissions == frozenset({"read:public"})
