"""Only explicit server configuration authorizes paid generation and private egress."""

import secrets

import pytest
from pydantic import SecretStr

from ai_intel.enrichment.runtime_policy import (
    build_enrichment_execution_policy,
    build_enrichment_generation_client,
)
from ai_intel.infrastructure.settings import ConfigurationError, load_application_settings


def test_credentials_alone_do_not_authorize_an_enrichment_call():
    settings = load_application_settings(generation_api_key=SecretStr(secrets.token_urlsafe(24)))
    policy = build_enrichment_execution_policy(settings)
    assert policy.generation_enabled is False
    assert policy.private_egress_granted is False
    assert policy.aggregate_enabled is False
    assert policy.generation_provider is None and policy.approved_model is None
    assert build_enrichment_generation_client(settings) is None


@pytest.mark.parametrize("credential", [None, SecretStr("")])
def test_enabled_generation_requires_a_nonempty_credential(credential):
    with pytest.raises(ConfigurationError, match="enrichment generation requires"):
        load_application_settings(
            enrichment_generation_enabled=True,
            generation_api_key=credential,
        )


def test_private_egress_cannot_be_granted_with_generation_disabled():
    with pytest.raises(ConfigurationError, match="private enrichment egress requires"):
        load_application_settings(enrichment_private_egress_granted=True)


@pytest.mark.parametrize(
    "provider", ["deepseek_openai", "deepseek_anthropic", "openai", "anthropic"]
)
def test_enabled_server_policy_excludes_secret_and_bounds_each_fresh_client(provider):
    credential = secrets.token_urlsafe(24)
    model = "deepseek-flash" if provider.startswith("deepseek") else "approved-test-model"
    settings = load_application_settings(
        app_env="test",
        data_mode="fixture",
        enrichment_generation_enabled=True,
        generation_api_key=SecretStr(credential),
        generation_provider=provider,
        generation_model=model,
        dns_resolver="cloudflare_doh",
    )
    policy = build_enrichment_execution_policy(settings)
    assert policy.generation_enabled and not policy.private_egress_granted
    assert policy.generation_provider == provider
    assert policy.approved_model == model and policy.data_mode == "fixture"
    assert credential not in policy.model_dump_json()
    first = build_enrichment_generation_client(settings)
    second = build_enrichment_generation_client(settings)
    assert first is not None and second is not None and first is not second
    assert first.limits.max_calls == 1
    assert first.limits.total_timeout_seconds == 20.0
    assert first.limits.max_concurrent_requests == 1


def test_private_egress_and_aggregate_selection_are_explicit_server_policy():
    settings = load_application_settings(
        enrichment_generation_enabled=True,
        generation_api_key=SecretStr(secrets.token_urlsafe(24)),
        enrichment_private_egress_granted=True,
        enrichment_aggregate_enabled=True,
    )
    policy = build_enrichment_execution_policy(settings)
    assert policy.generation_enabled and policy.private_egress_granted and policy.aggregate_enabled


@pytest.mark.parametrize("model", ["invalid model", "https://unexpected.invalid?secret=anything"])
def test_enabled_generation_rejects_an_unsafe_model_without_echoing_it(model):
    with pytest.raises(ConfigurationError) as error:
        load_application_settings(
            enrichment_generation_enabled=True,
            generation_api_key=SecretStr(secrets.token_urlsafe(24)),
            generation_model=model,
        )
    assert model not in str(error.value)


def test_unapproved_deepseek_model_is_rejected_before_worker_client_construction():
    with pytest.raises(ConfigurationError, match="unapproved DeepSeek enrichment model"):
        load_application_settings(
            enrichment_generation_enabled=True,
            generation_api_key=SecretStr(secrets.token_urlsafe(24)),
            generation_model="unapproved-test-model",
        )
