"""访问范围与权限判定: 租户隔离优先, 身份只由服务端从认证上下文构造。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    """预定义角色: 权限由权限表决定, 不接受请求体自报。"""

    TENANT_ADMIN = "tenant_admin"
    SYSTEM_ADMIN = "system_admin"
    ANALYST = "analyst"


READ_ASSET = "read:asset"
WRITE_ASSET = "write:asset"
READ_PUBLIC = "read:public"
MANAGE_USERS = "manage:users"
READ_AUDIT = "read:audit"

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.TENANT_ADMIN: frozenset({READ_ASSET, WRITE_ASSET, READ_PUBLIC, MANAGE_USERS, READ_AUDIT}),
    Role.SYSTEM_ADMIN: frozenset({READ_ASSET, WRITE_ASSET, READ_PUBLIC, MANAGE_USERS, READ_AUDIT}),
    Role.ANALYST: frozenset({READ_ASSET, READ_PUBLIC}),
}


class PermissionDeniedError(PermissionError):
    """权限不足: 拒绝时不回显目标对象存在性。"""


class CrossTenantAccessError(PermissionError):
    """跨租户访问: 统一按不可见处理, 不泄露名称与存在性。"""


@dataclass(frozen=True)
class AccessScope:
    """认证上下文构造的访问范围; 请求体自报身份不进入本对象。"""

    user_id: str
    tenant_id: str | None
    role: Role
    permissions: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def for_authenticated_user(cls, user_id: str, tenant_id: str | None, role: Role) -> AccessScope:
        """从服务端认证结果构造; 权限一律来自角色表。"""
        return cls(
            user_id=user_id, tenant_id=tenant_id, role=role, permissions=ROLE_PERMISSIONS[role]
        )

    def requires(self, permission: str) -> None:
        """缺失权限抛出拒绝; 不静默降级。"""
        if permission not in self.permissions:
            raise PermissionDeniedError(f"permission required: {permission}")

    def can_access(self, record_visibility: str, record_tenant_id: str | None) -> bool:
        """可见性判定: public 全员可读; tenant 仅同租户; 派生范围不得宽于输入。"""
        if record_visibility == "public":
            return True
        if record_visibility == "tenant":
            return self.tenant_id is not None and self.tenant_id == record_tenant_id
        return False

    def enforce_visible(self, record_visibility: str, record_tenant_id: str | None) -> None:
        """不可见对象统一 404 语义(由调用方转换), 不泄露对象名称或存在性。"""
        if not self.can_access(record_visibility, record_tenant_id):
            raise CrossTenantAccessError("resource not found")
