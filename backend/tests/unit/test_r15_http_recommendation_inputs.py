"""Public inputs reject identity grants and distinguish integers from booleans."""

import pytest
from pydantic import TypeAdapter, ValidationError

from ai_intel.api.recommendation_contracts import (
    CreateReport,
    CreateSubscription,
    GenerateRecommendations,
    SubscriptionPatch,
)
from ai_intel.recommendations.mutation_receipts import idempotency_key_digest


@pytest.mark.parametrize(
    "payload",
    [
        {"spec": {"product_keys": ["PyPI:alpha"], "minimum_priority": True}},
        {"spec": {"product_keys": ["PyPI:alpha"], "enabled": 1}},
        {"spec": {"product_keys": ["PyPI:alpha", "PyPI:alpha"]}},
        {"spec": {}},
        {"spec": {"product_keys": ["PyPI:alpha"], "tenant_id": "other"}},
        {"spec": {"product_keys": ["PyPI:alpha"]}, "user_id": "other"},
        {"spec": {"product_keys": ["PyPI:alpha"], "maximum_priority_bucket": 0}},
    ],
)
def test_public_spec_invalid_boundaries(payload):
    with pytest.raises(ValidationError):
        CreateSubscription.model_validate(payload)


@pytest.mark.parametrize("value", [0, 1, 2, 3])
def test_priority_maps_without_client_score_override(value):
    public = CreateSubscription.model_validate(
        {
            "spec": {
                "product_keys": ["PyPI:alpha"],
                "minimum_priority": value,
            }
        }
    )
    assert public.spec.internal_spec().maximum_priority_bucket == value


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_version": True, "enabled": False},
        {"expected_version": 0, "enabled": False},
        {"expected_version": 1, "enabled": False, "spec": {"product_keys": ["x"]}},
        {"expected_version": 1},
    ],
)
def test_patch_is_strictly_one_of_two_cas_shapes(payload):
    with pytest.raises(ValidationError):
        TypeAdapter(SubscriptionPatch).validate_python(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"max_candidates": True},
        {"max_candidates": 0},
        {"max_candidates": 201},
        {"event_ids": []},
        {"cutoff_at": "2026-10-16T00:00:00Z"},
    ],
)
def test_generate_only_accepts_bounded_server_generation_options(payload):
    with pytest.raises(ValidationError):
        GenerateRecommendations.model_validate(payload)


@pytest.mark.parametrize("key", [None, "", "a" * 201, "a b", "中文", "a\n"])
def test_idempotency_key_uses_existing_05_boundary(key):
    with pytest.raises(ValueError):
        idempotency_key_digest(key)


def test_key_digest_is_sha256_and_no_raw_key():
    assert idempotency_key_digest("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert GenerateRecommendations().max_candidates == 200
    with pytest.raises(ValidationError):
        CreateReport.model_validate(
            {"subscription_id": "bad", "generation_id": "bad", "frequency": "month"}
        )


@pytest.mark.parametrize(
    "value", [True, 1, "00000000000040008000000000000001", "{00000000-0000-4000-8000-000000000001}"]
)
def test_wire_uuid_matches_schema_format_without_coercing_body(value):
    with pytest.raises(ValidationError):
        CreateSubscription.model_validate({"spec": {"asset_ids": [value]}})
