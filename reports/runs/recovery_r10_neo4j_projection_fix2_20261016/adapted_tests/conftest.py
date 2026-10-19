"""测试资源仅在 fixture 执行时连接；导入及 collect-only 不访问外部资源。"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from ai_intel.infrastructure.database import run_migrations

PROJECT_ROOT = Path('D:\\wt\\r10-neo4j-projection-fix2')
REGISTERED_FAILURE_CREDENTIALS = pytest.StashKey[list[SecretStr]]()
SENSITIVE_FAILURE_FIELDS = frozenset(
    {
        "token",
        "session_token",
        "session_hash",
        "session_id",
        "csrf_token",
        "password",
        "authorization",
        "cookie",
        "secret_key",
        "access_key",
    }
)


def collect_failure_credentials(call: pytest.CallInfo[None]) -> tuple[str, ...]:
    """最多32帧/256局部值/128容器项/4层/4096字符，不执行对象表示或属性。"""
    if call.excinfo is None:
        return ()
    credentials: set[str] = set()
    remaining_items = 128
    visited_containers: set[int] = set()

    def collect(value: object, sensitive: bool, depth: int) -> None:
        nonlocal remaining_items
        if remaining_items <= 0 or depth > 4:
            return
        remaining_items -= 1
        if type(value) is SecretStr and isinstance(value, SecretStr):
            if sensitive and value.get_secret_value() and len(value.get_secret_value()) <= 4096:
                credentials.add(value.get_secret_value())
        elif type(value) is str:
            if sensitive and value and len(value) <= 4096:
                credentials.add(value)
        elif type(value) in (dict, list, tuple):
            if id(value) in visited_containers:
                return
            visited_containers.add(id(value))
            if isinstance(value, dict):
                for name, child in value.items():
                    collect(
                        child,
                        sensitive
                        or (type(name) is str and name.casefold() in SENSITIVE_FAILURE_FIELDS),
                        depth + 1,
                    )
                    if remaining_items <= 0:
                        break
            elif isinstance(value, (list, tuple)):
                for child in value:
                    collect(child, sensitive, depth + 1)
                    if remaining_items <= 0:
                        break

    frames = [list(entry.frame.f_locals.items())[:256] for entry in call.excinfo.traceback[:32]]
    for locals_items in frames:
        for name, value in locals_items:
            if name.casefold() in SENSITIVE_FAILURE_FIELDS:
                collect(value, True, 0)
    for locals_items in frames:
        for name, value in locals_items:
            if name.casefold() in {"params", "parameters"}:
                collect(value, True, 0)
    for locals_items in frames:
        for _name, value in locals_items:
            if type(value) in (dict, list, tuple):
                collect(value, False, 0)
    return tuple(sorted(credentials, key=len, reverse=True))


def redact_test_connection_output(output: str, dynamic_credentials: tuple[str, ...] = ()) -> str:
    """测试断言失败也不得把 fixture 参数的真实连接串/密码写入终端或 JUnit。"""
    credentials = [os.environ.get("TEST_SEARCH_TLS_PASSWORD", ""), *dynamic_credentials]
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL"):
        value = os.environ.get(name, "")
        if not value:
            continue
        output = output.replace(value, "[redacted test connection]")
        try:
            password = unquote(urlsplit(value).password or "")
        except ValueError:
            continue
        credentials.append(password)
    for credential in credentials:
        if not credential:
            continue
        output = output.replace(credential, "[redacted test credential]")
        if len(credential) >= 8:
            fragments = {credential[index : index + 8] for index in range(len(credential) - 7)}
            output = re.sub(
                "|".join(re.escape(fragment) for fragment in sorted(fragments)),
                "[redacted test credential fragment]",
                output,
            )
    return output


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """仅脱敏报告内容，保留测试 outcome、错误/失败/skip 数量。"""
    report = yield
    credentials = collect_failure_credentials(call)
    credentials += tuple(
        value.get_secret_value() for value in item.stash.get(REGISTERED_FAILURE_CREDENTIALS, [])
    )
    if report.longrepr is not None:
        original = report.longreprtext
        redacted = redact_test_connection_output(original, credentials)
        if redacted != original:
            report.longrepr = redacted
    report.sections = [
        (name, redact_test_connection_output(value, credentials)) for name, value in report.sections
    ]
    return report


@pytest.fixture()
def register_sensitive_failure_value(request: pytest.FixtureRequest) -> Callable[[SecretStr], None]:
    """对象属性或泛型局部名中的已知秘密，由fixture显式登记，仅作用于当前用例。"""
    values = request.node.stash.setdefault(REGISTERED_FAILURE_CREDENTIALS, [])

    def register(value: SecretStr) -> None:
        if type(value) is not SecretStr:
            raise TypeError("test credentials must be registered as SecretStr")
        values.append(value)

    return register


def pytest_configure(config: pytest.Config) -> None:
    """注册真实资源标记并使测试共享唯一脚本隔离规则，生产不依赖脚本。"""
    sys.path.insert(0, str(PROJECT_ROOT))
    config.addinivalue_line(
        "markers", "real_pg: requires an explicitly isolated PostgreSQL test database"
    )
    config.addinivalue_line(
        "markers", "real_services: requires an explicitly isolated Compose test project"
    )
    config.addinivalue_line(
        "markers", "real_search_tls: requires an explicitly isolated secure OpenSearch test project"
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

@pytest.fixture(autouse=True)
def review_register_resources(register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(unquote(urlsplit(os.environ["TEST_DATABASE_URL"]).password or "")))
    register_sensitive_failure_value(SecretStr(os.environ["TEST_DATABASE_URL"]))
