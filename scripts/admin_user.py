"""管理 CLI: 安全创建预创建用户; 无默认生产账号, 密码不走命令行参数。"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InMemoryUserDirectory,
)
from ai_intel.domain.access import Role


def read_password_without_echo() -> str:
    """密码从环境变量或无回显提示读取; 不进入 argv/日志。"""
    from_environment = os.environ.get("ADMIN_USER_PASSWORD")
    if from_environment:
        return from_environment
    return getpass.getpass("password (输入不回显): ")


def main(argv: list[str] | None = None) -> int:
    """创建预创建用户并输出用户 id; 重复用户名返回非零。"""
    parser = argparse.ArgumentParser(prog="admin_user.py", description="创建预创建用户(无公共注册)")
    parser.add_argument("username")
    parser.add_argument("--tenant", required=True, help="租户 id; system_admin 可用 none 表示无租户")
    parser.add_argument("--role", required=True, choices=[role.value for role in Role])
    arguments = parser.parse_args(argv)
    password = read_password_without_echo()
    if not password:
        print("ERROR empty password refused", file=sys.stderr)
        return 2
    tenant_id = None if arguments.tenant == "none" else arguments.tenant
    service = AuthenticationSessionService(InMemoryUserDirectory(), allowed_origins=(), cookie_secure=True)
    try:
        account = service.create_precreated_user(arguments.username, password, tenant_id, Role(arguments.role))
    except ValueError as duplicate:
        print(f"ERROR {duplicate}", file=sys.stderr)
        return 1
    print(f"created user_id={account.user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())