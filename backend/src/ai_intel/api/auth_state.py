"""PostgreSQL认证状态；使用既有0006表和短事务，不产生第二套业务真相。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Table,
    Text,
    delete,
    func,
    insert,
    select,
    tuple_,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine

from ai_intel.api.authentication import (
    LOGIN_WINDOW_SECONDS,
    MAX_LOGIN_ATTEMPTS,
    AuditEvent,
    AuditEventError,
    AuditPage,
    LoginRateLimitedError,
    Principal,
    SessionExpiredError,
    SessionRecord,
)
from ai_intel.domain.access import READ_AUDIT, AccessScope, PermissionDeniedError, Role
from ai_intel.knowledge.models import metadata, users

auth_sessions = Table(
    "auth_sessions",
    metadata,
    Column("session_hash", Text, primary_key=True),
    Column("user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("csrf_token", Text, nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
)
auth_login_buckets = Table(
    "auth_login_buckets", metadata, Column("client_key_hash", Text, primary_key=True)
)
auth_login_attempts = Table(
    "auth_login_attempts",
    metadata,
    Column("attempt_id", Text, primary_key=True),
    Column(
        "client_key_hash", Text, ForeignKey("auth_login_buckets.client_key_hash"), nullable=False
    ),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
)
auth_audit_events = Table(
    "auth_audit_events",
    metadata,
    Column("audit_id", Text, primary_key=True),
    Column("event_type", Text, nullable=False),
    Column("actor_user_id", Text, ForeignKey("users.user_id")),
    Column("tenant_id", Text),
    Column("trace_id", Text, nullable=False),
    Column("reason", Text),
    Column("submitted_keys", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class PgAuthenticationStateStore:
    """跨服务实例共享会话、失败/在途限制及授权审计，IO错误交由HTTP边界转503。"""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def reserve_login_attempt(self, client_key: str, now: datetime) -> str:
        """锁定客户端桶并提交占位；目录及Argon2 IO不占用数据库锁。"""
        client_hash = hashlib.sha256(client_key.encode("utf-8")).hexdigest()
        with self._engine.begin() as connection:
            connection.execute(
                pg_insert(auth_login_buckets)
                .values(client_key_hash=client_hash)
                .on_conflict_do_nothing()
            )
            connection.execute(
                select(auth_login_buckets.c.client_key_hash)
                .where(auth_login_buckets.c.client_key_hash == client_hash)
                .with_for_update()
            ).one()
            connection.execute(
                delete(auth_login_attempts).where(
                    auth_login_attempts.c.client_key_hash == client_hash,
                    auth_login_attempts.c.attempted_at
                    <= now - timedelta(seconds=LOGIN_WINDOW_SECONDS),
                )
            )
            attempt_count = connection.execute(
                select(func.count())
                .select_from(auth_login_attempts)
                .where(auth_login_attempts.c.client_key_hash == client_hash)
            ).scalar_one()
            if attempt_count >= MAX_LOGIN_ATTEMPTS:
                raise LoginRateLimitedError("too many login attempts")
            attempt_id = str(uuid.uuid4())
            connection.execute(
                insert(auth_login_attempts).values(
                    attempt_id=attempt_id, client_key_hash=client_hash, attempted_at=now
                )
            )
        return attempt_id

    def successful_login(
        self, client_key: str, attempt_id: str, record: SessionRecord, now: datetime
    ) -> None:
        """仅释放本次占位；会话保存和审计失败时整个事务回滚。"""
        client_hash = hashlib.sha256(client_key.encode("utf-8")).hexdigest()
        with self._engine.begin() as connection:
            connection.execute(
                insert(auth_sessions).values(
                    session_hash=record.session_id,
                    user_id=record.user_id,
                    csrf_token=record.csrf_token,
                    issued_at=now,
                    expires_at=record.expires_at,
                )
            )
            connection.execute(
                delete(auth_login_attempts).where(
                    auth_login_attempts.c.attempt_id == attempt_id,
                    auth_login_attempts.c.client_key_hash == client_hash,
                )
            )
            self._insert_audit(connection, "login_succeeded", {"user_id": record.user_id}, now)

    def authenticated_session(
        self, session_hash: str, now: datetime
    ) -> tuple[Principal, SessionRecord]:
        """单查询读取会话与当前用户身份，角色变更无需等待Cookie重签。"""
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        auth_sessions.c.session_hash,
                        auth_sessions.c.user_id,
                        auth_sessions.c.expires_at,
                        auth_sessions.c.csrf_token,
                        users.c.tenant_id,
                        users.c.role,
                    )
                    .select_from(auth_sessions.join(users))
                    .where(
                        auth_sessions.c.session_hash == session_hash,
                        auth_sessions.c.revoked_at.is_(None),
                        auth_sessions.c.expires_at > now,
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise SessionExpiredError("session is not valid")
        return (
            Principal(row["user_id"], row["tenant_id"], Role(row["role"])),
            SessionRecord(
                row["session_hash"], row["user_id"], row["expires_at"], row["csrf_token"]
            ),
        )

    def revoke_session(self, session_hash: str, now: datetime) -> None:
        """行锁防止并发重复撤销产生重复审计；提交后所有进程立即可见。"""
        with self._engine.begin() as connection:
            row = connection.execute(
                select(auth_sessions.c.user_id, auth_sessions.c.revoked_at)
                .where(auth_sessions.c.session_hash == session_hash)
                .with_for_update()
            ).first()
            if row is None or row.revoked_at is not None:
                return
            connection.execute(
                auth_sessions.update()
                .where(auth_sessions.c.session_hash == session_hash)
                .values(revoked_at=now)
            )
            self._insert_audit(connection, "logout", {"user_id": row.user_id}, now)

    def append_audit(self, event_type: str, fields: dict[str, str], now: datetime) -> None:
        """固定列审计，不保存未经约束的请求正文或敏感字段。"""
        with self._engine.begin() as connection:
            self._insert_audit(connection, event_type, fields, now)

    @staticmethod
    def _insert_audit(
        connection: Connection, event_type: str, fields: dict[str, str], now: datetime
    ) -> None:
        if event_type not in {
            "login_failed",
            "login_succeeded",
            "logout",
            "identity_spoof_attempt",
        }:
            raise AuditEventError("unsupported authentication audit event")
        if not set(fields) <= {"user_id", "trace_id", "reason", "submitted_keys"}:
            raise AuditEventError("unsupported authentication audit field")
        if fields.get("reason") not in {None, "invalid_credentials"}:
            raise AuditEventError("unsupported authentication audit reason")
        actor_id = fields.get("user_id")
        tenant_id: str | None = None
        if actor_id is not None:
            tenant_id = connection.execute(
                select(users.c.tenant_id).where(users.c.user_id == actor_id)
            ).scalar_one()
        connection.execute(
            insert(auth_audit_events).values(
                audit_id=str(uuid.uuid4()),
                event_type=event_type,
                actor_user_id=actor_id,
                tenant_id=tenant_id,
                trace_id=fields.get("trace_id", str(uuid.uuid4())),
                reason=fields.get("reason"),
                submitted_keys=fields.get("submitted_keys"),
                created_at=now,
            )
        )

    def read_audit_events(
        self, scope: AccessScope, *, limit: int = 20, cursor: str | None = None
    ) -> AuditPage:
        """审计权限与租户先过滤，最多100条；未知账户失败仅系统管理员可见。"""
        scope.requires(READ_AUDIT)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("audit limit must be between 1 and 100")
        query = select(auth_audit_events)
        if scope.role != Role.SYSTEM_ADMIN:
            if scope.tenant_id is None:
                raise PermissionDeniedError("audit access requires tenant scope")
            query = query.where(auth_audit_events.c.tenant_id == scope.tenant_id)
        if cursor is not None:
            before_time, before_id = self._decode_cursor(cursor)
            query = query.where(
                tuple_(auth_audit_events.c.created_at, auth_audit_events.c.audit_id)
                < tuple_(before_time, before_id)
            )
        query = query.order_by(
            auth_audit_events.c.created_at.desc(), auth_audit_events.c.audit_id.desc()
        ).limit(limit + 1)
        with self._engine.connect() as connection:
            rows = connection.execute(query).mappings().all()
        events = tuple(AuditEvent(**row) for row in rows[:limit])
        next_cursor = None
        if len(rows) > limit:
            last = events[-1]
            next_cursor = base64.urlsafe_b64encode(
                f"{last.created_at.isoformat()}|{last.audit_id}".encode()
            ).decode()
        return AuditPage(events, next_cursor)

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, str]:
        if len(cursor) > 200:
            raise ValueError("invalid audit cursor")
        try:
            stamp, audit_id = (
                base64.b64decode(cursor, altchars=b"-_", validate=True).decode().split("|")
            )
            before_time = datetime.fromisoformat(stamp)
            uuid.UUID(audit_id)
            if before_time.tzinfo is None:
                raise ValueError("invalid audit cursor")
        except (ValueError, UnicodeError, binascii.Error):
            raise ValueError("invalid audit cursor") from None
        return before_time, audit_id
