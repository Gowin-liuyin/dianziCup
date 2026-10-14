"""T03-C01–C06：真实隔离服务验收；缺资源非通过，不触碰常规开发项目。"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.request
from urllib.parse import unquote, urlsplit

import pytest
from scripts.dev import TestEnvironmentError as IsolationError
from scripts.dev import require_test_service_url, run_compose_services
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.infrastructure.settings import (
    ConfigurationError,
    describe_dependency_readiness,
    load_application_settings,
)

pytestmark = pytest.mark.real_services


def run_compose(*arguments: str):
    """仅运行与隔离 DSN/run_id 一致的专用 Compose 项目。"""
    try:
        completed = run_compose_services(*arguments, test_project=True)
    except (IsolationError, OSError) as unavailable:
        message = (
            str(unavailable)
            if isinstance(unavailable, IsolationError)
            else type(unavailable).__name__
        )
        raise pytest.UsageError(f"blocked: isolated Compose unavailable: {message}") from None
    assert completed.returncode == 0, "isolated Compose command failed"
    return completed


def _require_running_test_compose(database_url: str) -> None:
    """生命周期测试先证明目标由本项目 Compose 管理，不操作裸 Docker 实例。"""
    probe = run_compose("ps", "--format", "json")
    rows = (
        json.loads(probe.stdout)
        if probe.stdout.strip().startswith("[")
        else [json.loads(line) for line in probe.stdout.splitlines() if line.strip()]
    )
    assert any(
        row.get("Service") == "postgres" and row.get("State") == "running" for row in rows
    ), "blocked: lifecycle requires its own running Compose PostgreSQL"
    configuration = json.loads(run_compose("config", "--format", "json").stdout)
    assert configuration["name"] == os.environ["DIANZI_TEST_COMPOSE_PROJECT"]
    configured_database = configuration["services"]["postgres"]["environment"]["POSTGRES_DB"]
    assert configured_database == urlsplit(database_url).path.removeprefix("/")


def _wait_for_database(database_url: str) -> None:
    engine = create_engine(database_url, connect_args={"connect_timeout": 2})
    deadline = time.monotonic() + 30
    try:
        while True:
            try:
                with engine.connect() as connection:
                    assert connection.execute(text("SELECT 1")).scalar_one() == 1
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise
            except SQLAlchemyError as not_ready:
                if time.monotonic() >= deadline:
                    raise AssertionError("isolated PostgreSQL did not become ready") from not_ready
            time.sleep(0.25)
    finally:
        engine.dispose()


def _probe_authenticated_redis() -> None:
    redis_url = require_test_service_url("TEST_REDIS_URL", "redis", 6379)
    parsed = urlsplit(redis_url)
    with socket.create_connection(
        (parsed.hostname or "", parsed.port or 0), timeout=5
    ) as connection:
        connection.settimeout(5)
        with connection.makefile("rb") as response:
            if parsed.password:
                password = unquote(parsed.password).encode()
                connection.sendall(
                    b"*2\r\n$4\r\nAUTH\r\n$"
                    + str(len(password)).encode()
                    + b"\r\n"
                    + password
                    + b"\r\n"
                )
                assert response.readline(1024) == b"+OK\r\n", "isolated Redis authentication failed"
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            assert response.readline(1024) == b"+PONG\r\n"


def test_dependencies_report_health_and_accept_application_queries(
    isolated_test_database_url,
) -> None:
    """T03-C01：隔离项目健康、应用侧 PG/Redis/OpenSearch 实际响应。"""
    running = run_compose("ps", "--format", "json")
    rows = (
        json.loads(running.stdout)
        if running.stdout.strip().startswith("[")
        else [json.loads(line) for line in running.stdout.splitlines() if line.strip()]
    )
    assert {row["Service"] for row in rows if row.get("Health") == "healthy"} >= {
        "postgres",
        "redis",
        "opensearch",
    }
    _wait_for_database(isolated_test_database_url)
    _probe_authenticated_redis()
    search_url = require_test_service_url("TEST_OPENSEARCH_URL", "http", 9200)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(search_url.rstrip("/") + "/_cluster/health", timeout=10) as search_response:
        assert search_response.status == 200
        assert json.loads(search_response.read(65536))["status"] in {"green", "yellow"}


def test_persisted_row_survives_container_restart(isolated_test_database_url) -> None:
    """T03-C02：仅重启专用 test Compose PG，持久数据仍可读。"""
    _require_running_test_compose(isolated_test_database_url)
    engine = create_engine(isolated_test_database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS t03_persistence_probe "
                    "(id int PRIMARY KEY, note text)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO t03_persistence_probe VALUES (1, 'survives-restart') "
                    "ON CONFLICT DO NOTHING"
                )
            )
        run_compose("restart", "postgres")
        engine.dispose()
        _wait_for_database(isolated_test_database_url)
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT note FROM t03_persistence_probe WHERE id = 1")
                ).scalar_one()
                == "survives-restart"
            )
    finally:
        engine.dispose()


def test_search_dependency_absent_is_reported_as_degraded_not_ready() -> None:
    """T03-C03：搜索未配置的语义明确降级，不算实际健康。"""
    settings = load_application_settings(
        app_env="development",
        data_mode="fixture",
        database_url="postgresql://user:pass@127.0.0.1:5432/db",
        redis_url="redis://127.0.0.1:6379/0",
        opensearch_url=None,
    )
    readiness = describe_dependency_readiness(settings)
    assert readiness["search"] == "degraded_search_not_configured"
    assert readiness["database"] == "configured"
    assert "ready" not in readiness.values()


def test_production_rejects_fixture_data_mode() -> None:
    """T03-C04：production fixture 被拒绝。"""
    with pytest.raises(ConfigurationError):
        load_application_settings(
            app_env="production",
            data_mode="fixture",
            database_url="postgresql://user:strong-secret@127.0.0.1:5432/db",
        )


def test_production_rejects_placeholder_secret() -> None:
    """T03-C04：production 默认开发秘密被拒绝。"""
    with pytest.raises(ConfigurationError):
        load_application_settings(
            app_env="production",
            data_mode="live",
            database_url="postgresql://ai_intel:dev-only-not-a-secret@127.0.0.1:5432/db",
        )


def test_stop_services_preserves_volumes_and_user_data(isolated_test_database_url) -> None:
    """T03-C06：专用 Compose down/up 不删除卷，真实测试行保留。"""
    _require_running_test_compose(isolated_test_database_url)
    engine = create_engine(isolated_test_database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE IF NOT EXISTS t03_volume_probe (id int PRIMARY KEY, note text)")
            )
            connection.execute(
                text(
                    "INSERT INTO t03_volume_probe VALUES (1, 'survives-down-up') "
                    "ON CONFLICT DO NOTHING"
                )
            )
        before = run_compose("config", "--format", "json")
        configuration = json.loads(before.stdout)
        assert configuration["name"] == os.environ["DIANZI_TEST_COMPOSE_PROJECT"]
        assert configuration.get("volumes"), "test PostgreSQL must use a persistent volume"
        run_compose("down")
        run_compose("up", "-d", "--wait", "--wait-timeout", "90")
        engine.dispose()
        _wait_for_database(isolated_test_database_url)
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT note FROM t03_volume_probe WHERE id = 1")
                ).scalar_one()
                == "survives-down-up"
            )
    finally:
        engine.dispose()
