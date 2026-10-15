"""Execution policy is a bounded server decision, separate from user selection."""

import pytest
from pydantic import ValidationError

from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy, EventEnrichmentRequest


def test_disabled_default_grants_no_external_authority():
    policy = EnrichmentExecutionPolicy()
    assert not policy.generation_enabled and not policy.private_egress_granted
    assert not policy.aggregate_enabled
    assert policy.generation_provider is None and policy.approved_model is None


def test_explicit_server_model_preserves_provider_and_data_mode():
    policy = EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="deepseek_openai",
        approved_model="deepseek-v4-flash",
        data_mode="fixture",
    )
    assert policy.data_mode == "fixture" and not policy.private_egress_granted


@pytest.mark.parametrize(
    "value",
    [
        {"generation_enabled": True},
        {"generation_enabled": True, "generation_provider": "openai"},
        {"generation_enabled": True, "approved_model": "approved-test-model"},
        {"generation_enabled": "true"},
        {"private_egress_granted": True},
        {"generation_provider": "arbitrary_endpoint"},
        {"approved_model": "name with unsafe whitespace"},
        {"generation_api_key": "synthetic-forbidden-value"},
    ],
)
def test_invalid_or_secret_bearing_policy_is_rejected(value):
    with pytest.raises(ValidationError):
        EnrichmentExecutionPolicy.model_validate(value)


@pytest.mark.parametrize(
    "field", ["generation_enabled", "private_egress_granted", "aggregate_enabled"]
)
def test_user_request_cannot_supply_execution_authority(field):
    with pytest.raises(ValidationError):
        EventEnrichmentRequest.model_validate({"expected_event_version": 1, field: True})
