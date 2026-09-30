"""T06 访问判定与认证生命周期单元测试: 纯逻辑矩阵, 无外部依赖。"""

from __future__ import annotations

import pytest

from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InMemoryUserDirectory,
    SessionExpiredError,
)
from ai_intel.domain.access import (
    READ_PUBLIC,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
    Role,
)


def build_scope(role: Role, tenant_id: str | None) -> AccessScope:
    """按角色与租户构造服务端访问范围。"""
    return AccessScope.for_authenticated_user("user-1", tenant_id, role)


def test_role_permission_matrix_matches_table() -> None:
    """权限矩阵: analyst 读不可写; admin 可写; 越权一律抛出。"""
    analyst = build_scope(Role.ANALYST, "tenant-alpha")
    tenant_admin = build_scope(Role.TENANT_ADMIN, "tenant-alpha")
    analyst.requires(READ_PUBLIC)
    tenant_admin.requires(WRITE_ASSET)
    with pytest.raises(PermissionDeniedError):
        analyst.requires(WRITE_ASSET)
    assert WRITE_ASSET in tenant_admin.permissions
    assert WRITE_ASSET not in analyst.permissions


def test_visibility_matrix_enforces_tenant_isolation() -> None:
    """可见性矩阵: public 全员; tenant 仅同租户; 未知可见性一律不可见。"""
    scope = build_scope(Role.ANALYST, "tenant-alpha")
    assert scope.can_access("public", None) is True
    assert scope.can_access("public", "tenant-beta") is True
    assert scope.can_access("tenant", "tenant-alpha") is True
    assert scope.can_access("tenant", "tenant-beta") is False
    assert scope.can_access("tenant", None) is False
    assert scope.can_access("unknown-visibility", "tenant-alpha") is False
    stateless = build_scope(Role.SYSTEM_ADMIN, None)
    assert stateless.can_access("tenant", "tenant-alpha") is False
    with pytest.raises(CrossTenantAccessError):
        scope.enforce_visible("tenant", "tenant-beta")


def test_session_lifecycle_and_idempotent_logout() -> None:
    """会话生命周期: 登录→校验→注销幂等→失效。"""
    service = AuthenticationSessionService(
        InMemoryUserDirectory(), ("https://workbench.test",), cookie_secure=True
    )
    service.create_precreated_user("analyst-a", "Str0ng-Passphrase!", "tenant-alpha", Role.ANALYST)
    session_token, _ = service.login(
        "analyst-a", "Str0ng-Passphrase!", "https://workbench.test", "client-1"
    )
    assert service.validate_session(session_token).user_id != ""
    service.logout(session_token)
    service.logout(session_token)
    with pytest.raises(SessionExpiredError):
        service.validate_session(session_token)


def test_password_is_stored_only_as_argon2_hash() -> None:
    """密码只存 Argon2id 哈希: 账户对象不含明文。"""
    service = AuthenticationSessionService(
        InMemoryUserDirectory(), ("https://workbench.test",), cookie_secure=True
    )
    account = service.create_precreated_user(
        "analyst-a", "Str0ng-Passphrase!", "tenant-alpha", Role.ANALYST
    )
    assert "Str0ng-Passphrase!" not in account.password_hash
    assert account.password_hash.startswith("$argon2")
