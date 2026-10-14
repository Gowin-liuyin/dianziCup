"""管理 CLI: 安全创建预创建用户并持久化到 PostgreSQL; 无默认生产账号。

调用方式：backend venv 中执行 scripts/admin_user.py <username> --tenant <id|none> --role <role>。
密码经 ADMIN_USER_PASSWORD 环境变量或无回显提示提供, 不进入 argv/日志。
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid
from datetime import UTC, datetime

from psycopg.errors import UniqueViolation
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import MissingDatabaseUrlError
from ai_intel.infrastructure.settings import ConfigurationError


def describe_user_creation_failure(failure: SQLAlchemyError) -> str:
    """只按结构化错误分类；异常SQL/参数可能含密码哈希，不能转成日志文本。"""
    if (
        isinstance(failure, IntegrityError)
        and isinstance(failure.orig, UniqueViolation)
        and failure.orig.diag.constraint_name == "users_username_key"
    ):
        return "ERROR username already exists"
    if isinstance(failure, IntegrityError):
        return "ERROR integrity constraint violated"
    return "ERROR database unavailable"


def read_password_without_echo() -> str:
    """密码从环境变量或无回显提示读取; 不进入 argv/日志。"""
    from_environment = os.environ.get("ADMIN_USER_PASSWORD")
    if from_environment:
        return from_environment
    return getpass.getpass("password (输入不回显): ")


def main(argv: list[str] | None = None) -> int:
    """创建持久化预创建用户; 重复用户名返回非零, 账号重启后仍可用。

    运行前提: 环境或秘密管理提供 DATABASE_URL，不自动读取 .env。
    缺配置或连接失败只输出固定错误类别，不回显连接串/SQL/密码哈希。
    """
    parser = argparse.ArgumentParser(prog="admin_user.py", description="创建预创建用户(无公共注册)")
    parser.add_argument("username")
    parser.add_argument("--tenant", required=True, help="租户 id; system_admin 用 none 表示无租户")
    parser.add_argument("--role", required=True, choices=[role.value for role in Role])
    arguments = parser.parse_args(argv)
    password = read_password_without_echo()
    if not password:
        print("ERROR empty password refused", file=sys.stderr)
        return 2
    tenant_id = None if arguments.tenant == "none" else arguments.tenant
    if Role(arguments.role) == Role.SYSTEM_ADMIN and tenant_id is not None:
        print("ERROR system_admin must use --tenant none", file=sys.stderr)
        return 2
    if Role(arguments.role) != Role.SYSTEM_ADMIN and tenant_id is None:
        print("ERROR tenant role requires --tenant <id>", file=sys.stderr)
        return 2
    try:
        from argon2 import PasswordHasher

        from ai_intel.infrastructure.database import build_engine, session_scope
        from ai_intel.infrastructure.settings import load_application_settings
        from ai_intel.knowledge.models import users
    except ImportError as import_error:
        print(f"ERROR run inside backend venv: {import_error}", file=sys.stderr)
        return 2
    try:
        engine = build_engine(load_application_settings())
    except (ConfigurationError, MissingDatabaseUrlError):
        print("ERROR valid DATABASE_URL environment configuration is required", file=sys.stderr)
        return 2
    password_hash = PasswordHasher().hash(password)
    user_id = str(uuid.uuid4())
    try:
        with session_scope(engine) as session:
            session.execute(
                insert(users).values(
                    user_id=user_id,
                    username=arguments.username,
                    password_hash=password_hash,
                    tenant_id=tenant_id,
                    role=Role(arguments.role).value,
                    created_at=datetime.now(UTC),
                )
            )
    except SQLAlchemyError as failure:
        print(describe_user_creation_failure(failure), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(f"created user_id={user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
