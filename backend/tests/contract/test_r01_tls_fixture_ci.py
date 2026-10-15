"""TLS 夹具的隔离输入、Compose配置和CI装配顺序合同。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.prepare_search_tls_test import require_owned_container, validate_identity
from test_r01_compose_configuration import configuration_environment, render_configuration

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("run_id", ["production", "r01_tls_../shared", "r01_tls_", "r01_tls_UPPER"])
def test_tls_fixture_rejects_nonisolated_run_id(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError):
        validate_identity(run_id, tmp_path)


def test_tls_fixture_rejects_repository_private_directory() -> None:
    with pytest.raises(ValueError):
        validate_identity("r01_tls_contract", ROOT / "private-pki")


def test_tls_cleanup_checks_project_service_and_run_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import prepare_search_tls_test

    replies = iter(
        [
            "container-id\n",
            "container-id\n",
            json.dumps(
                {
                    "com.docker.compose.project": "dianzi-test-r01_tls_contract",
                    "com.docker.compose.service": "opensearch",
                    "io.dianzi.search-tls.run-id": "r01_tls_another",
                }
            ),
        ]
    )
    monkeypatch.setattr(
        prepare_search_tls_test, "run_command", lambda *args, **kwargs: next(replies)
    )
    with pytest.raises(ValueError, match="ownership"):
        require_owned_container(["docker"], "dianzi-test-r01_tls_contract", "r01_tls_contract")


def test_tls_fixture_configuration_has_only_pinned_secure_search() -> None:
    environment = configuration_environment()
    environment.update(
        TEST_SEARCH_TLS_RUN_ID="r01_tls_contract",
        TEST_SEARCH_TLS_USERNAME="ai_intel_search",
        TEST_SEARCH_TLS_PASSWORD=environment["OPENSEARCH_INITIAL_ADMIN_PASSWORD"],
        TEST_SEARCH_TLS_CA_FILE="/tmp/contract/root-ca.pem",
        TEST_SEARCH_TLS_NODE_CERT="/tmp/contract/node.pem",
        TEST_SEARCH_TLS_NODE_KEY="/tmp/contract/node-key.pem",
        TEST_SEARCH_TLS_PORT="29204",
    )
    result = render_configuration("compose.search-secure.test.yaml", environment)
    assert result.returncode == 0
    services = json.loads(result.stdout)["services"]
    assert set(services) == {"opensearch"}
    search = services["opensearch"]
    assert "@sha256:" in search["image"]
    assert search["user"] == "1000:1000"
    assert int(search["mem_limit"]) == 2147483648
    assert search["ports"][0]["host_ip"] == "127.0.0.1"
    assert "DISABLE_SECURITY_PLUGIN" not in search["environment"]
    assert search["environment"]["DISABLE_INSTALL_DEMO_CONFIG"] == "true"
    assert search["labels"]["io.dianzi.search-tls.run-id"] == "r01_tls_contract"
    assert all(volume["read_only"] for volume in search["volumes"] if volume["type"] == "bind")


def test_ci_prepares_waited_tls_fixture_before_all_integration_and_always_cleans_up() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    create = workflow.index("python scripts/prepare_search_tls_test.py create")
    integration = workflow.index("python scripts/dev.py check --scope integration")
    cleanup = workflow.index("python scripts/prepare_search_tls_test.py cleanup")
    assert create < integration < cleanup
    assert '--github-env "$GITHUB_ENV"' in workflow[create:integration]
    assert "if: always()" in workflow[integration:cleanup]
    assert "--scope integration --timeout-seconds 600" in workflow
    assert "-m 'not real_search_tls'" not in workflow
    script = (ROOT / "scripts/prepare_search_tls_test.py").read_text(encoding="utf-8")
    assert script.index("wait_for_listener(arguments.port)") < script.index("securityadmin.sh")
    assert '"--wait-timeout"' in script and '"180"' in script
    assert '"TEST_SEARCH_TLS_PASSWORD": password' in script
