"""T03 开发服务集成验收测试: 在真实容器上验证依赖、持久化与配置校验。

覆盖 T03-C01—C06。容器不可用时整组标记 blocked 跳过, 绝不使用 SQLite 冒充真实依赖。
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

from ai_intel.infrastructure.settings import (
    ConfigurationError,
    describe_dependency_readiness,
    load_application_settings,
)

COMPOSE_FILE = str(Path(__file__).resolve().parents[3] / "infra" / "compose" / "compose.yaml")
COMPOSE_PROFILES = ["--profile", "core", "--profile", "search"]


def run_compose(*arguments: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    """对本项目开发编排执行 docker compose 子命令并捕获输出。"""
    return subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, *COMPOSE_PROFILES, *arguments],
        capture_output=True,
        text=True,
        check=check,
    )


def containers_available() -> bool:
    """探测 docker compose 是否可用且本项目服务在运行; 不可用即 blocked。"""
    probe = run_compose("ps")
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not containers_available(),
    reason="blocked: 容器环境不可用（T03-C05）, 集成验证挂起; 不使用 SQLite 冒充",
)


def test_dependencies_report_health_and_accept_application_queries() -> None:
    """T03-C01: 依赖健康检查可用, 且从应用侧可执行真实查询。"""
    ready_probe = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "--profile",
            "core",
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-U",
            "ai_intel",
            "-d",
            "ai_intel",
        ],
        capture_output=True,
        text=True,
    )
    assert ready_probe.returncode == 0
    query_probe = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "--profile",
            "core",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "ai_intel",
            "-d",
            "ai_intel",
            "-t",
            "-c",
            "SELECT 1;",
        ],
        capture_output=True,
        text=True,
    )
    assert query_probe.returncode == 0
    assert "1" in query_probe.stdout
    redis_probe = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "--profile",
            "core",
            "exec",
            "-T",
            "redis",
            "redis-cli",
            "ping",
        ],
        capture_output=True,
        text=True,
    )
    assert redis_probe.returncode == 0
    assert "PONG" in redis_probe.stdout
    search_probe = urllib.request.urlopen("http://127.0.0.1:9200/_cluster/health", timeout=10)
    assert search_probe.status == 200
    search_payload = json.loads(search_probe.read().decode("utf-8"))
    assert search_payload["status"] in {"green", "yellow"}


def test_persisted_row_survives_container_restart() -> None:
    """T03-C02: 容器重启后已写数据保留, 证明卷挂载真实生效。"""
    write_probe = run_compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "ai_intel",
        "-d",
        "ai_intel",
        "-c",
        "CREATE TABLE IF NOT EXISTS t03_persistence_probe (id int PRIMARY KEY, note text);"
        "INSERT INTO t03_persistence_probe VALUES (1, 'survives-restart') ON CONFLICT DO NOTHING;",
    )
    assert write_probe.returncode == 0
    run_compose("restart", "postgres")
    read_probe = run_compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "ai_intel",
        "-d",
        "ai_intel",
        "-t",
        "-c",
        "SELECT note FROM t03_persistence_probe WHERE id = 1;",
    )
    assert read_probe.returncode == 0
    assert "survives-restart" in read_probe.stdout


def test_search_dependency_absent_is_reported_as_degraded_not_ready() -> None:
    """T03-C03: 搜索依赖未配置时识别为降级, 不谎报全依赖就绪。"""
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
    """T03-C04: production 配 fixture 数据模式必须被配置校验拒绝。"""
    with pytest.raises(ConfigurationError):
        load_application_settings(
            app_env="production",
            data_mode="fixture",
            database_url="postgresql://user:strong-secret@127.0.0.1:5432/db",
        )


def test_production_rejects_placeholder_secret() -> None:
    """T03-C04: production 携带默认开发秘密必须被配置校验拒绝。"""
    with pytest.raises(ConfigurationError):
        load_application_settings(
            app_env="production",
            data_mode="live",
            database_url="postgresql://ai_intel:dev-only-not-a-secret@127.0.0.1:5432/db",
        )


def test_stop_services_preserves_volumes_and_user_data() -> None:
    """T03-C06: 关闭开发服务不删除卷与用户数据; 销毁需显式确认路径。"""
    write_probe = run_compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "ai_intel",
        "-d",
        "ai_intel",
        "-c",
        "CREATE TABLE IF NOT EXISTS t03_volume_probe (id int PRIMARY KEY, note text);"
        "INSERT INTO t03_volume_probe VALUES (1, 'survives-down-up') ON CONFLICT DO NOTHING;",
    )
    assert write_probe.returncode == 0
    down_probe = run_compose("down")
    assert down_probe.returncode == 0
    volume_probe = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
    )
    assert "compose_postgres_data" in volume_probe.stdout
    up_probe = run_compose("up", "-d")
    assert up_probe.returncode == 0
    read_probe = run_compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "ai_intel",
        "-d",
        "ai_intel",
        "-t",
        "-c",
        "SELECT note FROM t03_volume_probe WHERE id = 1;",
    )
    assert read_probe.returncode == 0
    assert "survives-down-up" in read_probe.stdout
