"""配置与依赖边界unit；MockTransport明确不计OpenSearch live。"""

import httpx
import pytest
from fastapi.testclient import TestClient

from ai_intel.api import app as app_module
from ai_intel.infrastructure.settings import (
    ApplicationSettings,
    ConfigurationError,
    load_application_settings,
)


@pytest.mark.parametrize("status", [[], {}, None, "red"])
def test_malformed_search_health_is_unavailable_instead_of_server_error(
    monkeypatch: pytest.MonkeyPatch, status: object
) -> None:
    original_client = httpx.Client

    def fixture_client(**arguments: object) -> httpx.Client:
        return original_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"status": status})
            )
        )

    monkeypatch.setattr(app_module.httpx, "Client", fixture_client)
    settings = ApplicationSettings(app_env="test", opensearch_url="http://127.0.0.1:29200")
    client = TestClient(app_module.create_application(settings=settings))
    response = client.get("/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["search"]["state"] == "unavailable"


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.invalid",
        "https://user:synthetic@host.invalid",
        "https://host.invalid/path",
        "https://host.invalid?secret=synthetic",
    ],
)
def test_invalid_credential_origins_are_rejected_without_echoing_inputs(origin: str) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_application_settings(app_env="test", allowed_origins=(origin,))
    assert origin not in str(error.value)


def test_settings_use_authorized_environment_without_implicit_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "live")
    settings = load_application_settings()
    assert settings.app_env == "test" and settings.data_mode == "live"
    assert settings.model_config["env_file"] is None
