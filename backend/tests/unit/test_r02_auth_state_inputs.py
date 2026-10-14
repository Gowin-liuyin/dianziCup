"""认证审计纯输入校验，不连接数据库、不计持久化验证。"""

import base64
import uuid
from datetime import UTC, datetime

import pytest

from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InMemoryUserDirectory,
    SessionRecord,
    UserAccount,
)
from ai_intel.domain.access import Role


@pytest.mark.parametrize("cursor", ["!", "x" * 201, "", "YWJj", "////", "aGVsbG98bm90LXV1aWQ="])
def test_invalid_audit_cursor_uses_fixed_error(cursor: str) -> None:
    with pytest.raises(ValueError, match=r"^invalid audit cursor$"):
        PgAuthenticationStateStore._decode_cursor(cursor)


def test_audit_cursor_rejects_naive_time_and_roundtrips_timezone() -> None:
    audit_id = str(uuid.uuid4())
    naive = base64.urlsafe_b64encode(f"2026-10-15T00:00:00|{audit_id}".encode()).decode()
    with pytest.raises(ValueError, match=r"^invalid audit cursor$"):
        PgAuthenticationStateStore._decode_cursor(naive)
    stamp = datetime(2026, 10, 15, tzinfo=UTC)
    cursor = base64.urlsafe_b64encode(f"{stamp.isoformat()}|{audit_id}".encode()).decode()
    assert PgAuthenticationStateStore._decode_cursor(cursor) == (stamp, audit_id)


def test_authentication_secrets_are_excluded_from_dataclass_repr() -> None:
    account = UserAccount("fixture-id", "fixture-user", "fixture-hash", "tenant-a", Role.VIEWER)
    record = SessionRecord("fixture-session", "fixture-id", datetime.now(UTC), "fixture-csrf")
    assert "fixture-hash" not in repr(account)
    assert "fixture-session" not in repr(record)
    assert "fixture-csrf" not in repr(record)


def test_fixture_service_does_not_claim_persistent_audit_page() -> None:
    from ai_intel.api.authentication import AuditEventError
    from ai_intel.domain.access import AccessScope

    service = AuthenticationSessionService(InMemoryUserDirectory(), (), False)
    scope = AccessScope.for_authenticated_user("fixture", None, Role.SYSTEM_ADMIN)
    with pytest.raises(AuditEventError, match="not configured"):
        service.read_audit_events(scope)
