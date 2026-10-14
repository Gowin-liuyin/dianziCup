"""T06 认证与租户权限安全验收测试: 覆盖 T06-C01—C06 与边界负例。"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ai_intel.api.authentication import (
    MAX_LOGIN_ATTEMPTS,
    AuditEventError,
    AuthenticationSessionService,
    CsrfRejectionError,
    InMemoryUserDirectory,
    InvalidCredentialsError,
    LoginRateLimitedError,
    SessionExpiredError,
    cookie_secure_for_environment,
)
from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
    Role,
    filter_visible_rows,
)


def is_public_authentication_failure_comparison(content: str, source_line: int) -> bool:
    """公开PG错误文案作为布尔比较不是密码赋值；直接字面量凭据仍拒绝。"""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or node.lineno != source_line:
            continue
        value = node.value
        if (
            isinstance(value, ast.Compare)
            and isinstance(value.left, ast.Constant)
            and value.left.value == "password authentication failed"
            and len(value.ops) == 1
            and isinstance(value.ops[0], ast.In)
        ):
            return True
    return False


REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_ORIGIN = "https://workbench.test"


def build_service(clock_now: list[datetime] | None = None) -> AuthenticationSessionService:
    """构造认证服务; 可注入时钟以测试过期路径。"""
    mutable_now = clock_now if clock_now is not None else [datetime(2026, 9, 30, 12, 0, tzinfo=UTC)]

    def fixed_clock() -> datetime:
        return mutable_now[0]

    return AuthenticationSessionService(
        user_directory=InMemoryUserDirectory(),
        allowed_origins=(ALLOWED_ORIGIN,),
        cookie_secure=True,
        clock=fixed_clock,
    )


def test_login_logout_session_lifecycle_t06_c01() -> None:
    """T06-C01: 正确账号登录生成有效会话, 注销后立即失效。"""
    service = build_service()
    service.create_precreated_user("analyst-a", "Str0ng-Passphrase!", "tenant-alpha", Role.ANALYST)
    session_token, session_record = service.login(
        "analyst-a", "Str0ng-Passphrase!", ALLOWED_ORIGIN, "client-1"
    )
    principal = service.validate_session(session_token)
    assert principal.user_id == session_record.user_id
    assert principal.tenant_id == "tenant-alpha"
    service.logout(session_token)
    with pytest.raises(SessionExpiredError):
        service.validate_session(session_token)


def test_cross_tenant_objects_are_invisible_without_name_leak_t06_c02() -> None:
    """T06-C02: tenant B 请求 tenant A 资产/证据一律不可见, 错误信息无名称泄露。"""
    scope_b = AccessScope.for_authenticated_user("user-b", "tenant-beta", Role.ANALYST)
    with pytest.raises(CrossTenantAccessError) as captured:
        scope_b.enforce_visible("tenant", "tenant-alpha")
    assert "tenant-alpha" not in str(captured.value)
    assert "asset" not in str(captured.value).lower()
    assert scope_b.can_access("public", None) is True
    assert scope_b.can_access("tenant", "tenant-beta") is True
    assert scope_b.can_access("tenant", "tenant-alpha") is False


def test_request_body_self_reported_identity_is_ignored_t06_c03() -> None:
    """T06-C03: 伪造请求体 tenant_id/role 不获得权限, AccessScope 只认服务端会话。"""
    service = build_service()
    service.create_precreated_user("analyst-a", "Str0ng-Passphrase!", "tenant-alpha", Role.ANALYST)
    session_token, _ = service.login("analyst-a", "Str0ng-Passphrase!", ALLOWED_ORIGIN, "client-1")
    forged_request_body = {
        "tenant_id": "tenant-beta",
        "role": "system_admin",
        "user_id": "someone-else",
    }
    scope = service.build_access_scope(session_token)
    assert scope.tenant_id == "tenant-alpha"
    assert scope.role == Role.ANALYST
    assert forged_request_body["role"] not in {str(scope.role)}
    with pytest.raises(PermissionDeniedError):
        scope.requires(WRITE_ASSET)


def test_write_requests_require_csrf_and_allowed_origin_t06_c04() -> None:
    """T06-C04: 无 CSRF 或错误 Origin 的写请求被拒绝。"""
    service = build_service()
    service.create_precreated_user(
        "admin-a", "Str0ng-Passphrase!", "tenant-alpha", Role.TENANT_ADMIN
    )
    session_token, session_record = service.login(
        "admin-a", "Str0ng-Passphrase!", ALLOWED_ORIGIN, "client-1"
    )
    with pytest.raises(CsrfRejectionError):
        service.validate_write_request(session_token, "forged-csrf", ALLOWED_ORIGIN)
    with pytest.raises(CsrfRejectionError):
        service.validate_write_request(
            session_token, session_record.csrf_token, "https://evil.example"
        )
    with pytest.raises(CsrfRejectionError):
        service.validate_write_request(session_token, session_record.csrf_token, None)
    service.validate_write_request(session_token, session_record.csrf_token, ALLOWED_ORIGIN)


def test_expired_or_unknown_session_and_brute_force_are_rejected_t06_c05() -> None:
    """T06-C05: 过期/错误会话正确拒绝; 暴力登录限流; 失败信息不泄露账户细节。"""
    now_bucket = [datetime(2026, 9, 30, 12, 0, tzinfo=UTC)]
    service = build_service(now_bucket)
    service.create_precreated_user("analyst-a", "Str0ng-Passphrase!", "tenant-alpha", Role.ANALYST)
    session_token, _ = service.login("analyst-a", "Str0ng-Passphrase!", ALLOWED_ORIGIN, "client-1")
    now_bucket[0] = now_bucket[0] + timedelta(seconds=31 * 60)
    with pytest.raises(SessionExpiredError):
        service.validate_session(session_token)
    with pytest.raises(SessionExpiredError):
        service.validate_session("unknown-session-token")
    for _ in range(MAX_LOGIN_ATTEMPTS):
        with pytest.raises(InvalidCredentialsError):
            service.login("analyst-a", "wrong-password", ALLOWED_ORIGIN, "client-2")
    with pytest.raises(LoginRateLimitedError):
        service.login("analyst-a", "Str0ng-Passphrase!", ALLOWED_ORIGIN, "client-2")
    with pytest.raises(InvalidCredentialsError) as unknown_user_error:
        service.login("ghost-user", "whatever", ALLOWED_ORIGIN, "client-3")
    with pytest.raises(InvalidCredentialsError) as wrong_password_error:
        service.login("analyst-a", "whatever", ALLOWED_ORIGIN, "client-3")
    assert str(unknown_user_error.value) == str(wrong_password_error.value)


def test_audit_and_sources_carry_no_secret_values_t06_c06() -> None:
    """T06-C06: 审计事件与源码/日志扫描无密码、cookie、token 或真实密钥值。"""
    service = build_service()
    service.create_precreated_user("analyst-a", "Str0ng-Passphrase!", "tenant-alpha", Role.ANALYST)
    session_token, _ = service.login("analyst-a", "Str0ng-Passphrase!", ALLOWED_ORIGIN, "client-1")
    service.logout(session_token)
    for event in service.audit_events():
        serialized = str(event).lower()
        assert "str0ng-passphrase!" not in serialized
        assert session_token not in str(event)
        assert "trace_id" in event
    with pytest.raises(AuditEventError):
        service._append_audit("manual_probe", {"password": "should-not-be-logged"})
    import re

    secret_pattern = re.compile(
        r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|token|password)"
        r"\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
        re.IGNORECASE,
    )
    scan_roots = (
        REPO_ROOT / "backend" / "src",
        REPO_ROOT / "scripts",
        REPO_ROOT / "frontend" / "src",
        REPO_ROOT / "frontend" / "dist",
        REPO_ROOT / "reports" / "runs",
    )
    documented_dev_placeholders = {"dev-only-not-a-secret", "Dev-Only-Not-A-Secret-1!"}
    secret_value_pattern = re.compile(
        r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|password|passwd|token|jwt)"
        r"\s*[:=]\s*['\"]([^'\"]{6,})['\"]",
        re.IGNORECASE,
    )
    for source_root in scan_roots:
        if not source_root.exists():
            continue
        for source_path in source_root.rglob("*"):
            if not source_path.is_file() or source_path.suffix not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".log",
                ".json",
                ".html",
            }:
                continue
            content = source_path.read_text(encoding="utf-8", errors="ignore")
            assert not secret_pattern.search(content), source_path
            for secret_match in secret_value_pattern.finditer(content):
                source_line = content[: secret_match.start()].count("\n") + 1
                if (
                    source_path.suffix == ".py"
                    and secret_match.group(2) == "password authentication failed"
                    and is_public_authentication_failure_comparison(content, source_line)
                ):
                    continue
                assert secret_match.group(2) in documented_dev_placeholders, (
                    source_path,
                    secret_match.group(1),
                )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("rejected_password = 'password authentication failed' in str(failure)", True),
        ("password = 'password authentication failed'", False),
        ("password = 'synthetic-credential'", False),
    ],
)
def test_secret_scan_distinguishes_public_failure_check_from_credential_literal(
    source: str, expected: bool
) -> None:
    assert is_public_authentication_failure_comparison(source, 1) is expected


def test_precreated_users_only_and_no_default_production_account() -> None:
    """边界: 无公共注册入口; 新建服务不含任何预置账号。"""
    directory = InMemoryUserDirectory()
    assert directory.find_by_username("admin") is None
    service = AuthenticationSessionService(directory, (ALLOWED_ORIGIN,), cookie_secure=True)
    assert service.audit_events() == []
    assert not hasattr(service, "register")


def test_cookie_policy_requires_secure_in_production() -> None:
    """边界: production Secure Cookie 强制; 非 production 显式为 False 而非默认放行。"""
    production_service = AuthenticationSessionService(
        InMemoryUserDirectory(),
        (ALLOWED_ORIGIN,),
        cookie_secure=cookie_secure_for_environment("production"),
    )
    development_service = AuthenticationSessionService(
        InMemoryUserDirectory(),
        (ALLOWED_ORIGIN,),
        cookie_secure=cookie_secure_for_environment("development"),
    )
    assert cookie_secure_for_environment("production") is True
    assert cookie_secure_for_environment("development") is False
    production_cookie = production_service.cookie_attributes()
    development_cookie = development_service.cookie_attributes()
    assert production_cookie["secure"] is True
    assert production_cookie["httponly"] is True
    assert production_cookie["samesite"] == "strict"
    assert development_cookie["secure"] is False


def test_tenant_admin_permission_table_and_scope_epoch_role_separation() -> None:
    """边界: 角色权限来自权限表; tenant_admin 不具备 system_admin 越权能力。"""
    tenant_admin = AccessScope.for_authenticated_user("admin-1", "tenant-alpha", Role.TENANT_ADMIN)
    system_admin = AccessScope.for_authenticated_user("root-1", None, Role.SYSTEM_ADMIN)
    assert tenant_admin.permissions < system_admin.permissions
    assert MANAGE_PUBLIC_SOURCES in system_admin.permissions
    assert MANAGE_PUBLIC_SOURCES not in tenant_admin.permissions
    assert tenant_admin.tenant_id == "tenant-alpha"
    assert system_admin.tenant_id is None
    tenant_admin.requires(WRITE_ASSET)


def test_identity_spoof_attempt_is_audited_and_write_gate_checks_expiry() -> None:
    """M5-4/C1: 伪造身份字段记审计; 过期会话过不了写闸门。"""
    now_bucket = [datetime(2026, 9, 30, 12, 0, tzinfo=UTC)]
    service = build_service(now_bucket)
    service.create_precreated_user(
        "admin-a", "Str0ng-Passphrase!", "tenant-alpha", Role.TENANT_ADMIN
    )
    session_token, session_record = service.login(
        "admin-a", "Str0ng-Passphrase!", ALLOWED_ORIGIN, "client-1"
    )
    service.record_identity_spoof_attempt({"tenant_id": "tenant-beta", "role": "system_admin"})
    spoof_events = [
        event for event in service.audit_events() if event["event_type"] == "identity_spoof_attempt"
    ]
    assert len(spoof_events) == 1
    assert "tenant_id" in spoof_events[0]["submitted_keys"]
    assert "tenant-beta" not in str(spoof_events[0])
    now_bucket[0] = now_bucket[0] + timedelta(seconds=31 * 60)
    with pytest.raises(SessionExpiredError):
        service.validate_write_request(session_token, session_record.csrf_token, ALLOWED_ORIGIN)


def test_filter_visible_rows_separates_public_and_private() -> None:
    """M6: 范围化查询范式——公共证据与私有资产按可见性规则分离, 不可见行不进结果。"""
    scope = AccessScope.for_authenticated_user("user-1", "tenant-alpha", Role.ANALYST)
    rows = [
        ("public", None),
        ("tenant", "tenant-alpha"),
        ("tenant", "tenant-beta"),
        ("public", "tenant-beta"),
    ]
    assert filter_visible_rows(scope, rows) == [0, 1, 3]


def test_viewer_role_has_read_public_only() -> None:
    """M5-1: viewer 角色只有 read:public, 不能读资产或写。"""
    viewer = AccessScope.for_authenticated_user("viewer-1", "tenant-alpha", Role.VIEWER)
    viewer.requires("read:public")
    with pytest.raises(PermissionDeniedError):
        viewer.requires("read:asset")
    assert viewer.permission_version >= 1
