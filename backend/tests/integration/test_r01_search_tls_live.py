"""真实 TLS 信任、认证与安全故障验证，仅使用本包独占搜索资源。"""

from __future__ import annotations

import json
import os
import re
import secrets
import socket
import ssl
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings

pytestmark = pytest.mark.real_search_tls


@dataclass(frozen=True)
class SearchTLSConnection:
    url: str
    username: str
    password: SecretStr
    ca_file: str
    wrong_ca_file: str
    run_id: str
    project: str
    container: str


@pytest.fixture()
def real_tls_settings() -> SearchTLSConnection:
    required = (
        "TEST_SEARCH_TLS_URL",
        "TEST_SEARCH_TLS_USERNAME",
        "TEST_SEARCH_TLS_CA_FILE",
        "TEST_SEARCH_TLS_WRONG_CA_FILE",
        "TEST_SEARCH_TLS_RUN_ID",
        "TEST_SEARCH_TLS_PROJECT",
        "TEST_SEARCH_TLS_CONTAINER",
    )
    configured = {name: os.environ.get(name, "") for name in required}
    password = SecretStr(os.environ.get("TEST_SEARCH_TLS_PASSWORD", ""))
    if not all(configured.values()) or not password.get_secret_value():
        raise pytest.UsageError("blocked: isolated secure OpenSearch TLS resources required")
    parsed = urlsplit(configured["TEST_SEARCH_TLS_URL"])
    assert parsed.scheme == "https" and parsed.hostname == "localhost" and parsed.port
    assert parsed.username is None and parsed.password is None
    assert parsed.path in ("", "/") and not parsed.query and not parsed.fragment
    assert Path(configured["TEST_SEARCH_TLS_CA_FILE"]).is_file()
    assert Path(configured["TEST_SEARCH_TLS_WRONG_CA_FILE"]).is_file()
    assert re.fullmatch(r"r01_tls_[a-z0-9_]{1,64}", configured["TEST_SEARCH_TLS_RUN_ID"])
    assert (
        configured["TEST_SEARCH_TLS_PROJECT"]
        == "dianzi-test-" + configured["TEST_SEARCH_TLS_RUN_ID"]
    )
    assert (
        configured["TEST_SEARCH_TLS_CONTAINER"]
        == configured["TEST_SEARCH_TLS_PROJECT"] + "-opensearch-1"
    )
    return SearchTLSConnection(
        url=configured["TEST_SEARCH_TLS_URL"],
        username=configured["TEST_SEARCH_TLS_USERNAME"],
        password=password,
        ca_file=configured["TEST_SEARCH_TLS_CA_FILE"],
        wrong_ca_file=configured["TEST_SEARCH_TLS_WRONG_CA_FILE"],
        run_id=configured["TEST_SEARCH_TLS_RUN_ID"],
        project=configured["TEST_SEARCH_TLS_PROJECT"],
        container=configured["TEST_SEARCH_TLS_CONTAINER"],
    )


@pytest.mark.parametrize("case", ["correct", "no_ca", "wrong_ca", "wrong_san", "wrong_password"])
def test_real_search_tls_trust_authentication_and_failure_are_observable(
    real_tls_settings: SearchTLSConnection, case: str
) -> None:
    url = real_tls_settings.url
    ca: str | None = real_tls_settings.ca_file
    password = real_tls_settings.password
    if case == "no_ca":
        ca = None
    elif case == "wrong_ca":
        ca = real_tls_settings.wrong_ca_file
    elif case == "wrong_san":
        url = url.replace("localhost", "127.0.0.1")
    elif case == "wrong_password":
        password = SecretStr(secrets.token_urlsafe(32))
    settings = ApplicationSettings(
        app_env="test",
        data_mode="live",
        database_url=None,
        redis_url=None,
        opensearch_url=url,
        opensearch_username=real_tls_settings.username,
        opensearch_password=password,
        opensearch_ca_file=ca,
        dependency_timeout_seconds=3,
    )
    with TestClient(create_application(settings=settings)) as client:
        response = client.get("/v1/health/ready")
    if (
        real_tls_settings.password.get_secret_value() in response.text
        or password.get_secret_value() in response.text
    ):
        pytest.fail("secret present in health response")
    assert response.status_code == 503
    payload = response.json()
    if case == "correct":
        assert payload["dependencies"]["search"] == {"state": "ready"}
    else:
        assert payload["dependencies"]["search"] == {
            "state": "unavailable",
            "reason": "search connection unavailable",
        }
    assert "Traceback" not in response.text


def test_real_certificate_chain_enforces_hostname_and_required_ca(
    real_tls_settings: SearchTLSConnection,
) -> None:
    context = ssl.create_default_context(cafile=real_tls_settings.ca_file)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    with (
        socket.create_connection(
            ("127.0.0.1", urlsplit(real_tls_settings.url).port), timeout=3
        ) as connection,
        context.wrap_socket(connection, server_hostname="localhost") as secured,
    ):
        certificate = secured.getpeercert()
        assert ("DNS", "localhost") in certificate["subjectAltName"]
        assert ("DNS", "opensearch") in certificate["subjectAltName"]


def test_real_search_fault_returns_safe_503_and_recovers(
    real_tls_settings: SearchTLSConnection,
) -> None:
    prefix = json.loads(os.environ["DIANZI_DOCKER_COMMAND_JSON"])
    container = real_tls_settings.container
    label = subprocess.run(
        [
            *prefix,
            "inspect",
            container,
            "--format",
            "{{json .Config.Labels}}",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    labels = json.loads(label.stdout)
    assert labels["com.docker.compose.project"] == real_tls_settings.project
    assert labels["com.docker.compose.service"] == "opensearch"
    assert labels["io.dianzi.search-tls.run-id"] == real_tls_settings.run_id
    subprocess.run([*prefix, "stop", container], capture_output=True, check=True, timeout=30)
    try:
        settings = ApplicationSettings(
            app_env="test",
            data_mode="live",
            database_url=None,
            redis_url=None,
            opensearch_url=real_tls_settings.url,
            opensearch_username=real_tls_settings.username,
            opensearch_password=real_tls_settings.password,
            opensearch_ca_file=real_tls_settings.ca_file,
        )
        with TestClient(create_application(settings=settings)) as client:
            response = client.get("/v1/health/ready")
        if real_tls_settings.password.get_secret_value() in response.text:
            pytest.fail("secret present in health response")
        assert response.status_code == 503
        assert response.json()["dependencies"]["search"] == {
            "state": "unavailable",
            "reason": "search connection unavailable",
        }
    finally:
        subprocess.run([*prefix, "start", container], capture_output=True, check=True, timeout=15)
        deadline = time.monotonic() + 120
        while True:
            observed = subprocess.run(
                [*prefix, "inspect", container, "--format", "{{.State.Health.Status}}"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            if observed.stdout.strip() == "healthy":
                break
            assert time.monotonic() < deadline, "secure test search did not recover"
            time.sleep(1)
