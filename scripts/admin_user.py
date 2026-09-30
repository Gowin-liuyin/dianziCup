"""管理 CLI: 安全创建预创建用户并持久化到 PostgreSQL; 无默认生产账号。

调用方式(项目 venv): cd backend && uv run python ..\\scripts\\admin_user.py <username> --tenant <id|none> --role <role>
密码经 ADMIN_USER_PASSWORD 环境变量或无回显提示提供, 不进入 argv/日志。
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert

from ai_intel.domain.access import Role


def read_password_without_echo() -> str:
    """密码从环境变量或无回显提示读取; 不进入 argv/日志。"""
    from_environment = os.environ.get("ADMIN_USER_PASSWORD")
    if from_environment:
        return from_environment
    return getpass.getpass("password (输入不回显): ")


def main(argv: list[str] | None = None) -> int:
    """创建持久化预创建用户; 重复用户名返回非零, 账号重启后仍可用。"""
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
        from sqlalchemy.exc import IntegrityError

        from ai_intel.infrastructure.database import build_engine, session_scope
        from ai_intel.infrastructure.settings import load_application_settings
        from ai_intel.knowledge.models import users
    except ImportError as import_error:
        print(f"ERROR run inside backend venv: {import_error}", file=sys.stderr)
        return 2
    engine = build_engine(load_application_settings())
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
                    created_at=datetime.now(timezone.utc),
                )
            )
    except IntegrityError as duplicate:
        print(f"ERROR username already exists: {duplicate}", file=sys.stderr)
        return 1
    print(f"created user_id={user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())