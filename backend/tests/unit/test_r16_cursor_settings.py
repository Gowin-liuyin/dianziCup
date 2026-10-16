"""Persisted cursor-key configuration rejects malformed and known fixture inputs safely."""

import secrets

import pytest
from pydantic import SecretStr, ValidationError

from ai_intel.infrastructure.settings import ApplicationSettings


def test_missing_cursor_key_does_not_create_process_local_authority() -> None:
    configuration = ApplicationSettings(app_env="test", _env_file=None)
    assert configuration.revalidation_cursor_signing_key is None


def test_same_persisted_cursor_key_survives_settings_reconstruction() -> None:
    key = secrets.token_hex(32)
    first = ApplicationSettings(app_env="test", revalidation_cursor_signing_key=SecretStr(key))
    second = ApplicationSettings(app_env="test", revalidation_cursor_signing_key=SecretStr(key))
    assert first.revalidation_cursor_signing_key is not None
    assert second.revalidation_cursor_signing_key is not None
    assert first.revalidation_cursor_signing_key.get_secret_value() == key
    assert second.revalidation_cursor_signing_key.get_secret_value() == key
    assert key not in repr(first)
    assert key not in first.model_dump_json()


@pytest.mark.parametrize(
    "candidate", ["", "short-private-value", "g" * 64, "A" * 64, "0" * 63, "0" * 65]
)
def test_malformed_cursor_key_is_rejected_without_echo(candidate: str) -> None:
    with pytest.raises(ValidationError) as caught:
        ApplicationSettings(app_env="test", revalidation_cursor_signing_key=SecretStr(candidate))
    rendered = str(caught.value)
    assert "REVALIDATION_CURSOR_SIGNING_KEY" in rendered
    if candidate:
        assert candidate not in rendered


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize(
    "fixture_key", [bytes(32).hex(), bytes([1] * 32).hex(), bytes(range(32)).hex()]
)
def test_non_test_deployment_rejects_known_fixture_cursor_keys(
    environment: str, fixture_key: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        ApplicationSettings.model_validate(
            {"app_env": environment, "revalidation_cursor_signing_key": fixture_key}
        )
    assert "cannot use a fixture key" in str(caught.value)
    assert fixture_key not in str(caught.value)
