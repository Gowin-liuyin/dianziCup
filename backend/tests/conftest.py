"""测试资源仅在 fixture 执行时连接；导入及 collect-only 不访问外部资源。"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator, Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from ai_intel.infrastructure.database import run_migrations

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def redact_test_connection_output(output: str) -> str:
    """测试断言失败也不得把 fixture 参数的真实连接串/密码写入终端或 JUnit。"""
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL"):
        value = os.environ.get(name, "")
        if not value:
            continue
        output = output.replace(value, "[redacted test connection]")
        try:
            password = unquote(urlsplit(value).password or "")
        except ValueError:
            continue
        if password:
            output = output.replace(password, "[redacted test credential]")
    return output


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """仅脱敏报告内容，保留测试 outcome、错误/失败/skip 数量。"""
    report = yield
    if report.longrepr is not None:
        original = report.longreprtext
        redacted = redact_test_connection_output(original)
        if redacted != original:
            report.longrepr = redacted
    report.sections = [
        (name, redact_test_connection_output(value)) for name, value in report.sections
    ]
    return report


def pytest_configure(config: pytest.Config) -> None:
    """注册真实资源标记并使测试共享唯一脚本隔离规则，生产不依赖脚本。"""
    sys.path.insert(0, str(PROJECT_ROOT))
    config.addinivalue_line(
        "markers", "real_pg: requires an explicitly isolated PostgreSQL test database"
    )
    config.addinivalue_line(
        "markers", "real_services: requires an explicitly isolated Compose test project"
    )


@pytest.fixture()
def isolated_test_database_url() -> str:
    """缺少隔离资源记错误/blocked，不通过 skip 隐藏缺测。"""
    from scripts.dev import TestEnvironmentError, require_isolated_test_database

    try:
        return require_isolated_test_database()
    except TestEnvironmentError as blocked:
        raise pytest.UsageError(f"blocked: {blocked}") from None


@pytest.fixture()
def migrated_engine(isolated_test_database_url: str) -> Iterator[Engine]:
    """验证实际库/用户身份后迁移；只访问经隔离规则核准的 PostgreSQL。"""
    engine = create_engine(
        isolated_test_database_url,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=20000 -c lock_timeout=5000",
        },
    )
    try:
        with engine.connect() as connection:
            database_name, username = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()
            assert database_name == engine.url.database
            assert username == engine.url.username
        migration_url = engine.url.update_query_dict(
            {"connect_timeout": "5", "options": "-c statement_timeout=20000 -c lock_timeout=5000"}
        ).render_as_string(hide_password=False)
        run_migrations(migration_url)
    except OperationalError:
        engine.dispose()
        raise pytest.UsageError(
            "blocked: isolated PostgreSQL connection/migration unavailable"
        ) from None
    try:
        yield engine
    finally:
        engine.dispose()
