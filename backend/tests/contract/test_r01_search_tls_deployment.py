"""R01 安全搜索配置合同；不联网、不读取秘密、不启动服务。"""

from __future__ import annotations

import json
import secrets
from urllib.parse import urlsplit

import pytest
from test_r01_compose_configuration import configuration_environment, render_configuration


def test_base_pairs_readonly_ca_with_separate_search_authentication() -> None:
    environment = configuration_environment()
    environment.update(
        COMPOSE_OPENSEARCH_USERNAME="ai_intel_search",
        COMPOSE_OPENSEARCH_PASSWORD=secrets.token_urlsafe(32),
        OPENSEARCH_CA_HOST_FILE="/tmp/r01-config-root-ca.pem",
    )
    result = render_configuration("compose.yaml", environment)
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name in ("api", "worker", "scheduler"):
        service = services[name]
        settings = service["environment"]
        assert urlsplit(settings["OPENSEARCH_URL"]).scheme == "https"
        assert urlsplit(settings["OPENSEARCH_URL"]).username is None
        assert settings["OPENSEARCH_USERNAME"] == "ai_intel_search"
        assert settings["OPENSEARCH_PASSWORD"] == environment["COMPOSE_OPENSEARCH_PASSWORD"]
        ca_mount = next(
            volume
            for volume in service["volumes"]
            if volume["target"] == settings["OPENSEARCH_CA_FILE"]
        )
        assert ca_mount["source"] == "/tmp/r01-config-root-ca.pem"
        assert ca_mount["read_only"] is True
        assert ca_mount["bind"]["create_host_path"] is False
        assert all("node-key" not in volume["target"] for volume in service["volumes"])
    search = services["opensearch"]
    health = search["healthcheck"]["test"][-1]
    assert "--cacert" in health
    assert "-k" not in health and "--insecure" not in health
    assert search["environment"]["DISABLE_INSTALL_DEMO_CONFIG"] == "true"
    assert "DISABLE_SECURITY_PLUGIN" not in search["environment"]


def test_base_does_not_supply_a_default_search_identity() -> None:
    environment = configuration_environment()
    environment.pop("COMPOSE_OPENSEARCH_USERNAME", None)
    result = render_configuration("compose.yaml", environment)
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name in ("api", "worker", "scheduler", "opensearch"):
        assert services[name]["environment"]["OPENSEARCH_USERNAME"] == ""


@pytest.mark.parametrize("filename", ["compose.test.yaml", "compose.test.host.yaml"])
def test_http_overlay_explicitly_removes_secure_auth_and_ca(filename: str) -> None:
    result = render_configuration(filename, configuration_environment())
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name in ("api", "worker", "scheduler"):
        settings = services[name]["environment"]
        assert settings["OPENSEARCH_URL"].startswith("http://")
        assert (
            not {"OPENSEARCH_USERNAME", "OPENSEARCH_PASSWORD", "OPENSEARCH_CA_FILE"}
            & settings.keys()
        )
    search = services["opensearch"]
    assert search["environment"]["DISABLE_SECURITY_PLUGIN"] == "true"
    assert not any(volume["type"] == "bind" for volume in search["volumes"])


def test_secure_host_profile_keeps_tls_and_loopback_without_published_ports() -> None:
    environment = configuration_environment()
    environment.update(SECURE_OPENSEARCH_PORT="29202", SECURE_OPENSEARCH_TRANSPORT_PORT="29302")
    result = render_configuration("compose.search.secure.host.yaml", environment, "search")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert set(services) == {"opensearch"}
    search = services["opensearch"]
    assert search["network_mode"] == "host"
    assert not search.get("ports")
    assert search["environment"]["network.host"] == "127.0.0.1"
    assert "DISABLE_SECURITY_PLUGIN" not in search["environment"]
    assert "--cacert" in search["healthcheck"]["test"][-1]
