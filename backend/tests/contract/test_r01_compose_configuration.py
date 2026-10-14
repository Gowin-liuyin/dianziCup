"""R01 Compose 实际配置渲染与隔离边界；config 不启动或下载服务。"""

from __future__ import annotations

import json
import os
import secrets
import shlex
import subprocess
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

import pytest
from scripts.dev import TestEnvironmentError as IsolationError
from scripts.dev import require_isolated_test_database

PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_DIRECTORY = PROJECT_ROOT / "infra" / "compose"


def configuration_environment() -> dict[str, str]:
    """显式合成配置，不读取开发 .env 或产品秘密，不连接任何服务。"""
    password = secrets.token_urlsafe(32)
    redis_password = secrets.token_urlsafe(32)
    environment = dict(os.environ)
    environment.update(
        COMPOSE_DISABLE_ENV_FILE="1",
        DIANZI_TEST_RUN_ID="r01_config",
        POSTGRES_DB="dianzi_config",
        POSTGRES_USER="dianzi_config",
        POSTGRES_PASSWORD=password,
        POSTGRES_PORT="25430",
        REDIS_PASSWORD=redis_password,
        REDIS_PORT="26380",
        OPENSEARCH_INITIAL_ADMIN_PASSWORD=secrets.token_urlsafe(32) + "aA1!",
        OPENSEARCH_PORT="29200",
        DATABASE_URL=f"postgresql+psycopg://dianzi_config:{password}@postgres:5432/dianzi_config",
        REDIS_URL=f"redis://:{redis_password}@redis:6379/0",
        ALLOWED_ORIGINS='["http://127.0.0.1:25201"]',
        API_PORT="28201",
        FRONTEND_PORT="25201",
        VITE_API_BASE_URL="http://127.0.0.1:28201",
        PYTHON_IMAGE="unused-config@sha256:" + "0" * 64,
        UV_IMAGE="unused-config@sha256:" + "0" * 64,
        NODE_IMAGE="unused-config@sha256:" + "0" * 64,
        TEST_POSTGRES_USER="test_dianzi_r01_config",
        TEST_POSTGRES_PASSWORD=password,
        TEST_POSTGRES_PORT="25436",
        TEST_REDIS_PASSWORD=redis_password,
        TEST_REDIS_PORT="26383",
        TEST_OPENSEARCH_PORT="29201",
        TEST_OPENSEARCH_TRANSPORT_PORT="29301",
        TEST_DATABASE_URL=(
            f"postgresql+psycopg://test_dianzi_r01_config:{password}"
            "@127.0.0.1:25436/test_dianzi_r01_config"
        ),
        TEST_REDIS_URL=f"redis://:{redis_password}@127.0.0.1:26383/0",
        TEST_OPENSEARCH_URL="http://127.0.0.1:29201",
    )
    transferred_names = {
        name
        for name in environment
        if name.startswith(("POSTGRES_", "REDIS_", "OPENSEARCH_", "TEST_"))
        or name
        in {
            "COMPOSE_DISABLE_ENV_FILE",
            "DIANZI_TEST_RUN_ID",
            "DATABASE_URL",
            "ALLOWED_ORIGINS",
            "API_PORT",
            "FRONTEND_PORT",
            "VITE_API_BASE_URL",
            "PYTHON_IMAGE",
            "UV_IMAGE",
            "NODE_IMAGE",
        }
    }
    environment["WSLENV"] = ":".join(sorted(transferred_names))
    return environment


def render_configuration(
    filename: str, environment: dict[str, str], profile: str = "*"
) -> subprocess.CompletedProcess[str]:
    """使用真实 Compose 解析 include/override 和 profile，无 shell/eval。"""
    prefix = json.loads(os.environ.get("DIANZI_DOCKER_COMMAND_JSON", '["docker"]'))
    compose_path = COMPOSE_DIRECTORY / filename
    argument = str(compose_path)
    if Path(prefix[0]).name.lower() == "wsl.exe":
        windows_path = PureWindowsPath(compose_path.resolve())
        argument = f"/mnt/{windows_path.drive[0].lower()}/" + "/".join(windows_path.parts[1:])
    return subprocess.run(
        [
            *prefix,
            "compose",
            "--project-name",
            "dianzi-test-r01_config",
            "-f",
            argument,
            "--profile",
            profile,
            "config",
            "--format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=25,
        check=False,
    )


@pytest.mark.parametrize("profile", ["core", "search", "app", "worker", "scheduler", "frontend"])
def test_profiles_render_real_service_entrypoints(profile: str) -> None:
    result = render_configuration("compose.yaml", configuration_environment(), profile)
    assert result.returncode == 0, result.stderr
    configuration = json.loads(result.stdout)
    assert configuration["services"]
    if profile == "core":
        assert set(configuration["services"]) == {"postgres", "redis"}
    if profile == "worker":
        assert configuration["services"]["worker"]["command"] == [
            "celery",
            "-A",
            "ai_intel.workers.runtime:celery_app",
            "worker",
            "--concurrency=1",
        ]
    if profile == "scheduler":
        assert "beat" in configuration["services"]["scheduler"]["command"]
    if profile == "app":
        assert "ai_intel.api.app:app" in configuration["services"]["api"]["command"]


@pytest.mark.parametrize(
    "variable", ["POSTGRES_PASSWORD", "REDIS_PASSWORD", "OPENSEARCH_INITIAL_ADMIN_PASSWORD"]
)
def test_missing_credentials_fail_configuration(variable: str) -> None:
    environment = configuration_environment()
    environment.pop(variable)
    result = render_configuration("compose.yaml", environment)
    assert result.returncode != 0
    assert variable in result.stderr


def test_development_services_are_local_bounded_and_persistent() -> None:
    result = render_configuration("compose.yaml", configuration_environment())
    assert result.returncode == 0, result.stderr
    configuration = json.loads(result.stdout)
    assert configuration["networks"]["private"]["internal"] is True
    for service in configuration["services"].values():
        assert service["healthcheck"]["test"]
        assert int(service["mem_limit"]) > 0
        assert float(service["cpus"]) > 0
        assert int(service["pids_limit"]) > 0
        for port in service.get("ports", []):
            assert port["host_ip"] == "127.0.0.1"
    for name in ("postgres", "redis", "opensearch"):
        service = configuration["services"][name]
        assert "@sha256:" in service["image"]
        assert any(volume["type"] == "volume" for volume in service["volumes"])
    assert "DISABLE_SECURITY_PLUGIN" not in configuration["services"]["opensearch"]["environment"]


def test_test_overlay_replaces_development_ports_and_database() -> None:
    environment = configuration_environment()
    result = render_configuration("compose.test.yaml", environment)
    assert result.returncode == 0, result.stderr
    configuration = json.loads(result.stdout)
    postgres = configuration["services"]["postgres"]
    assert postgres["environment"]["POSTGRES_DB"] == "test_dianzi_r01_config"
    assert len(postgres["ports"]) == 1
    assert postgres["ports"][0]["published"] == "25436"
    assert configuration["services"]["redis"]["ports"][0]["published"] == "26383"
    assert configuration["services"]["opensearch"]["ports"][0]["published"] == "29201"
    for name in ("api", "worker", "scheduler"):
        service = configuration["services"][name]
        assert service["environment"]["APP_ENV"] == "test"
        assert urlsplit(service["environment"]["DATABASE_URL"]).hostname == "postgres"


def test_host_overlay_binds_services_internally_to_loopback() -> None:
    result = render_configuration("compose.test.host.yaml", configuration_environment())
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for service in services.values():
        assert service["network_mode"] == "host"
        assert not service.get("ports")
        assert not service.get("networks")
    assert "listen_addresses=127.0.0.1" in services["postgres"]["command"]
    assert "--bind 127.0.0.1 --port 26383" in services["redis"]["command"][-1]
    search = services["opensearch"]["environment"]
    assert search["network.host"] == "127.0.0.1"
    assert search["http.port"] == "29201"
    assert search["transport.port"] == "29301"
    assert search["DISABLE_SECURITY_PLUGIN"] == "true"
    assert "127.0.0.1" in services["api"]["command"]
    assert "127.0.0.1" in services["frontend"]["command"]


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://test_user:secret@127.0.0.1:25436/ai_intel",
        "postgresql://test_user:secret@127.0.0.1:5432/test_dianzi_r01_config",
        "postgresql://test_user:secret@example.com:25436/test_dianzi_r01_config",
    ],
)
def test_compose_caller_rejects_nonisolated_database(database_url: str) -> None:
    environment = configuration_environment()
    environment["TEST_DATABASE_URL"] = database_url
    with pytest.raises(IsolationError):
        require_isolated_test_database(environment)


def test_dockerfiles_install_locked_packages_and_use_nonroot_users() -> None:
    backend = (PROJECT_ROOT / "infra/docker/backend.Dockerfile").read_text(encoding="utf-8")
    frontend = (PROJECT_ROOT / "infra/docker/frontend.Dockerfile").read_text(encoding="utf-8")
    assert "uv sync --locked --no-dev" in backend
    assert "USER 10001:10001" in backend
    assert "COPY backend/migrations ./migrations" in backend
    assert "RUN npm ci" in frontend
    assert "USER node" in frontend
    assert "COPY . " not in backend + frontend
    for dockerfile in (backend, frontend):
        for line in dockerfile.splitlines():
            if line.startswith("COPY ") and "--from=" not in line:
                arguments = [part for part in shlex.split(line)[1:] if not part.startswith("--")]
                for source in arguments[:-1]:
                    assert (PROJECT_ROOT / source).exists(), f"missing Docker build input: {source}"
