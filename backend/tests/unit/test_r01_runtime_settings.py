"""配置与依赖边界unit；MockTransport明确不计OpenSearch live。"""

import base64
import secrets
import ssl

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


def test_search_credentials_are_paired_and_never_embedded_in_url() -> None:
    secret_value = secrets.token_urlsafe(16)
    for overrides in [
        {"opensearch_username": "test-search"},
        {"opensearch_password": secret_value},
        {"opensearch_url": f"https://test-search:{secret_value}@host.invalid:9200"},
    ]:
        with pytest.raises(ConfigurationError) as failure:
            load_application_settings(app_env="test", **overrides)
        assert secret_value not in str(failure.value)


def test_search_https_health_uses_verified_context_and_separate_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_value = secrets.token_urlsafe(16)
    original_client = httpx.Client
    observed_authorization: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        observed_authorization.append(request.headers["Authorization"])
        return httpx.Response(200, json={"status": "green"})

    def fixture_client(**arguments: object) -> httpx.Client:
        context = arguments["verify"]
        assert isinstance(context, ssl.SSLContext)
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        auth = arguments["auth"]
        assert isinstance(auth, httpx.BasicAuth)
        return original_client(transport=httpx.MockTransport(respond), auth=auth)

    monkeypatch.setattr(app_module.httpx, "Client", fixture_client)
    settings = load_application_settings(
        app_env="test",
        opensearch_url="https://host.invalid:9200",
        opensearch_username="test-search",
        opensearch_password=secret_value,
    )
    response = TestClient(app_module.create_application(settings=settings)).get("/v1/health/ready")
    expected_auth = "Basic " + base64.b64encode(f"test-search:{secret_value}".encode()).decode()
    assert observed_authorization == [expected_auth]
    assert response.json()["dependencies"]["search"]["state"] == "ready"
    assert secret_value not in response.text


def test_missing_explicit_search_ca_is_unavailable_without_echoing_path() -> None:
    missing_path = "/synthetic-unavailable-search-ca.pem"
    settings = load_application_settings(
        app_env="test",
        opensearch_url="https://host.invalid:9200",
        opensearch_ca_file=missing_path,
    )
    response = TestClient(app_module.create_application(settings=settings)).get("/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["search"]["state"] == "unavailable"
    assert missing_path not in response.text


def test_production_search_requires_https() -> None:
    with pytest.raises(ConfigurationError, match="OPENSEARCH_URL requires HTTPS"):
        load_application_settings(app_env="production", opensearch_url="http://host.invalid:9200")
