"""认证与会话: 预创建用户、Argon2id 哈希、不透明会话、限流与安全策略。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.engine import Engine, RowMapping

from ai_intel.domain.access import AccessScope, Role

SESSION_TTL_SECONDS = 30 * 60
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60


class InvalidCredentialsError(PermissionError):
    """凭证无效: 不区分用户不存在与密码错误, 不泄露账户细节。"""


class SessionExpiredError(PermissionError):
    """会话过期或已注销: 与凭证错误分离, 同样不泄露内部状态。"""


class CsrfRejectionError(PermissionError):
    """写请求缺少或不匹配 CSRF 令牌, 或 Origin 不在允许清单。"""


class LoginRateLimitedError(PermissionError):
    """登录尝试超限: 拒绝时不确认账号是否存在。"""


class AuditEventError(ValueError):
    """审计事件携带敏感字段名: 拒绝记录, 防止密码/令牌入日志。"""


SENSITIVE_AUDIT_MARKERS = ("password", "cookie", "token", "secret", "authorization")


@dataclass(frozen=True)
class Principal:
    """已认证主体: 由服务端从有效会话得出。"""

    user_id: str
    tenant_id: str | None
    role: Role


@dataclass
class UserAccount:
    """预创建用户: 仅存哈希, 不存明文密码。"""

    user_id: str
    username: str
    password_hash: str
    tenant_id: str | None
    role: Role


@dataclass
class SessionRecord:
    """不透明会话记录: 过期或注销即失效。"""

    session_id: str
    user_id: str
    expires_at: datetime
    csrf_token: str
    revoked: bool = False


def cookie_secure_for_environment(app_env: str) -> bool:
    """production 必须 Secure Cookie; 其余环境显式 False, 不默认放行。"""
    return app_env == "production"


class InMemoryUserDirectory:
    """预创建用户目录(管理 CLI 与测试共用的最小实现); 无公共注册入口。"""

    def __init__(self) -> None:
        self._accounts_by_username: dict[str, UserAccount] = {}

    def add_precreated_user(self, account: UserAccount) -> None:
        """仅允许预创建路径; 不提供任何自助注册接口。"""
        if account.username in self._accounts_by_username:
            raise ValueError("username already exists")
        self._accounts_by_username[account.username] = account

    def find_by_username(self, username: str) -> UserAccount | None:
        """按用户名查找; 不存在返回 None, 调用方不得据此向客户端区分。"""
        return self._accounts_by_username.get(username)

    def find_by_id(self, user_id: str) -> UserAccount | None:
        """按用户 id 查找, 服务端会话校验使用。"""
        for account in self._accounts_by_username.values():
            if account.user_id == user_id:
                return account
        return None


class UserDirectory(Protocol):
    """认证使用相同目录合同；真实运行接PG，内存目录仅显式fixture。"""

    def add_precreated_user(self, account: UserAccount) -> None: ...

    def find_by_username(self, username: str) -> UserAccount | None: ...

    def find_by_id(self, user_id: str) -> UserAccount | None: ...


class DatabaseUserDirectory:
    """数据库用户目录: 预创建用户持久化到 PostgreSQL, 重启后仍可用。"""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_precreated_user(self, account: UserAccount) -> None:
        """持久化预创建用户; 用户名重复由唯一键拒绝。"""
        from sqlalchemy import insert
        from sqlalchemy.exc import IntegrityError

        from ai_intel.knowledge.models import users

        try:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(users).values(
                        user_id=account.user_id,
                        username=account.username,
                        password_hash=account.password_hash,
                        tenant_id=account.tenant_id,
                        role=account.role.value,
                        created_at=datetime.now(UTC),
                    )
                )
        except IntegrityError as duplicate:
            raise ValueError("username already exists") from duplicate

    def find_by_username(self, username: str) -> UserAccount | None:
        """按用户名查找持久化账户。"""
        from sqlalchemy import select

        from ai_intel.knowledge.models import users

        with self._engine.connect() as connection:
            row = (
                connection.execute(select(users).where(users.c.username == username))
                .mappings()
                .first()
            )
        return self._row_to_account(row)

    def find_by_id(self, user_id: str) -> UserAccount | None:
        """按用户 id 查找持久化账户。"""
        from sqlalchemy import select

        from ai_intel.knowledge.models import users

        with self._engine.connect() as connection:
            row = (
                connection.execute(select(users).where(users.c.user_id == user_id))
                .mappings()
                .first()
            )
        return self._row_to_account(row)

    @staticmethod
    def _row_to_account(row: RowMapping | None) -> UserAccount | None:
        """把数据库行映射回账户对象; 无行返回 None。"""
        if row is None:
            return None
        fields = row
        tenant_value = fields["tenant_id"]
        return UserAccount(
            user_id=str(fields["user_id"]),
            username=str(fields["username"]),
            password_hash=str(fields["password_hash"]),
            tenant_id=str(tenant_value) if tenant_value is not None else None,
            role=Role(str(fields["role"])),
        )


class AuthenticationSessionService:
    """登录/注销/会话校验 + 登录限流 + 审计事件(脱敏)。"""

    def __init__(
        self,
        user_directory: UserDirectory,
        allowed_origins: tuple[str, ...],
        cookie_secure: bool,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._user_directory = user_directory
        self._allowed_origins = allowed_origins
        self._cookie_secure = cookie_secure
        self._clock = clock or (lambda: datetime.now(UTC))
        self._password_hasher = PasswordHasher()
        self._sessions: dict[str, SessionRecord] = {}
        self._login_attempts: dict[str, list[float]] = {}
        self._login_lock = Lock()
        self._audit_events: list[dict[str, str]] = []

    def create_precreated_user(
        self, username: str, password: str, tenant_id: str | None, role: Role
    ) -> UserAccount:
        """管理路径创建用户: 仅存 Argon2id 哈希, 重复用户名拒绝。"""
        account = UserAccount(
            user_id=str(uuid.uuid4()),
            username=username,
            password_hash=self._password_hasher.hash(password),
            tenant_id=tenant_id,
            role=role,
        )
        self._user_directory.add_precreated_user(account)
        return account

    def login(
        self, username: str, password: str, origin: str | None, client_key: str
    ) -> tuple[str, SessionRecord]:
        """登录: 凭证与 Origin 校验后签发不透明会话; 失败统一报错。"""
        if origin is not None and origin not in self._allowed_origins:
            raise CsrfRejectionError("origin not allowed")
        self._reserve_login_attempt(client_key)
        account = self._user_directory.find_by_username(username)
        if account is None:
            self._append_audit(
                "login_failed", {"reason": "invalid_credentials", "trace_id": str(uuid.uuid4())}
            )
            raise InvalidCredentialsError("invalid credentials")
        try:
            self._password_hasher.verify(account.password_hash, password)
        except VerifyMismatchError:
            self._append_audit(
                "login_failed", {"reason": "invalid_credentials", "trace_id": str(uuid.uuid4())}
            )
            raise InvalidCredentialsError("invalid credentials") from None
        session_token = secrets.token_urlsafe(32)
        session_record = SessionRecord(
            session_id=self._session_key(session_token),
            user_id=account.user_id,
            expires_at=self._clock() + timedelta(seconds=SESSION_TTL_SECONDS),
            csrf_token=secrets.token_urlsafe(32),
        )
        self._sessions[self._session_key(session_token)] = session_record
        self._append_audit(
            "login_succeeded", {"user_id": account.user_id, "trace_id": str(uuid.uuid4())}
        )
        return session_token, session_record

    def logout(self, session_token: str) -> None:
        """注销: 立即失效, 重复注销幂等。"""
        session_record = self._sessions.get(self._session_key(session_token))
        if session_record is not None:
            session_record.revoked = True
            self._append_audit(
                "logout", {"user_id": session_record.user_id, "trace_id": str(uuid.uuid4())}
            )

    def validate_session(self, session_token: str) -> Principal:
        """校验会话得到主体; 过期/注销/未知统一 SessionExpiredError。"""
        principal, _ = self.authenticated_session(session_token)
        return principal

    def authenticated_session(self, session_token: str) -> tuple[Principal, SessionRecord]:
        """一次会话及账户读取，绑定身份与CSRF；不组合两次HTTP会话快照。"""
        session_record = self._sessions.get(self._session_key(session_token))
        if (
            session_record is None
            or session_record.revoked
            or session_record.expires_at <= self._clock()
        ):
            raise SessionExpiredError("session is not valid")
        account = self._user_directory.find_by_id(session_record.user_id)
        if account is None:
            raise SessionExpiredError("session is not valid")
        return (
            Principal(user_id=account.user_id, tenant_id=account.tenant_id, role=account.role),
            session_record,
        )

    def session_record(self, session_token: str) -> SessionRecord:
        """返回有效会话记录(含 CSRF 令牌), 供 /auth/csrf 下发; 无效/过期/撤销抛对应错误。"""
        _, record = self.authenticated_session(session_token)
        return record

    def build_access_scope(self, session_token: str) -> AccessScope:
        """服务端由会话构造 AccessScope; 请求体自报身份在此无入口。"""
        principal = self.validate_session(session_token)
        return AccessScope.for_authenticated_user(
            principal.user_id, principal.tenant_id, principal.role
        )

    def validate_write_request(
        self, session_token: str, csrf_token: str, origin: str | None
    ) -> None:
        """写请求必须会话有效、CSRF 令牌匹配且 Origin 合法。"""
        session_record = self._sessions.get(self._session_key(session_token))
        if (
            session_record is None
            or session_record.revoked
            or session_record.expires_at <= self._clock()
        ):
            raise SessionExpiredError("session is not valid")
        if not csrf_token.isascii() or not hmac.compare_digest(
            session_record.csrf_token, csrf_token
        ):
            raise CsrfRejectionError("csrf token mismatch")
        if origin is None or origin not in self._allowed_origins:
            raise CsrfRejectionError("origin not allowed")

    def cookie_attributes(self) -> dict[str, str | bool]:
        """Cookie 策略: HttpOnly + SameSite=Strict; production 强制 Secure。"""
        return {"httponly": True, "samesite": "strict", "secure": self._cookie_secure}

    def audit_events(self) -> list[dict[str, str]]:
        """审计事件副本: 供测试与审计接口消费。"""
        return [dict(event) for event in self._audit_events]

    def record_identity_spoof_attempt(self, submitted_fields: dict[str, str]) -> None:
        """请求体携带自报身份字段时记录安全审计事件(仅记字段名与 trace_id, 不记值)。"""
        self._append_audit(
            "identity_spoof_attempt",
            {"submitted_keys": ",".join(sorted(submitted_fields)), "trace_id": str(uuid.uuid4())},
        )

    @staticmethod
    def _session_key(session_token: str) -> str:
        """会话以服务端哈希为键存储, 落库/内存不保存明文 token(05 §1 合同)。"""
        return hashlib.sha256(session_token.encode("utf-8")).hexdigest()

    def _reserve_login_attempt(self, client_key: str) -> None:
        """昂贵目录/密码IO前原子占位；成功登录不能清除其他在途尝试。"""
        with self._login_lock:
            now_epoch = time.time()
            attempts = [
                stamp
                for stamp in self._login_attempts.get(client_key, [])
                if now_epoch - stamp < LOGIN_WINDOW_SECONDS
            ]
            if len(attempts) >= MAX_LOGIN_ATTEMPTS:
                raise LoginRateLimitedError("too many login attempts")
            attempts.append(now_epoch)
            self._login_attempts[client_key] = attempts

    def _append_audit(self, event_type: str, fields: dict[str, str]) -> None:
        """写入审计事件: 拒绝敏感字段名, 事件带 trace_id。"""
        if "trace_id" not in fields:
            raise AuditEventError("audit event requires trace_id")
        for key in fields:
            lowered = key.lower()
            if any(marker in lowered for marker in SENSITIVE_AUDIT_MARKERS):
                raise AuditEventError(f"sensitive field refused in audit event: {key}")
        self._audit_events.append({"event_type": event_type, **fields})
