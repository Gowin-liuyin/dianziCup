"""The aggregate persistence boundary reuses the frozen observation schema and query catalog."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from ai_intel.assets.aggregate_observations import AggregateObservation, total_result
from ai_intel.assets.aggregate_repository import (
    AggregateServerPolicy,
    PostgresAggregateRepository,
    canonical_observation,
)

NOW = datetime(2026, 10, 15, 20, tzinfo=UTC)


def test_canonical_payload_is_existing_observation_json_not_an_independent_value_schema():
    observation = total_result("hunter", "ollama", 0, NOW, "fixture")
    canonical, digest = canonical_observation(observation)
    assert AggregateObservation.model_validate_json(canonical) == observation
    assert json.loads(canonical)["schema_version"] == "r08-aggregate-observation-1"
    assert json.loads(canonical)["value"]["kind"] == "exposure_aggregate"
    assert len(digest) == 64


@pytest.mark.parametrize(
    "change",
    [
        {"query_version": "unapproved"},
        {"ttl_seconds": 5},
        {"limitations": ("provider-secret raw hosts",)},
        {"observed_at": NOW + timedelta(seconds=1)},
    ],
)
def test_boundary_rejects_unapproved_version_ttl_raw_text_and_future_observation(change):
    observation = total_result("hunter", "ollama", 0, NOW, "fixture")
    value = observation.value.model_copy(update=change)
    with pytest.raises(ValueError):
        canonical_observation(observation.model_copy(update={"value": value}))


@pytest.mark.parametrize("field", ["ip", "headers", "asset_records", "provider_raw", "api_key"])
def test_raw_fields_cannot_enter_observation_json(field):
    observation = total_result("hunter", "ollama", 1, NOW, "fixture")
    raw = observation.model_dump()
    raw[field] = "provider-secret"
    with pytest.raises(ValidationError):
        AggregateObservation.model_validate(raw)


def test_repository_does_not_silently_use_sqlite_or_fallback_truth():
    with pytest.raises(ValueError, match="PostgreSQL"):
        PostgresAggregateRepository(create_engine("sqlite://"))


@pytest.mark.parametrize("profile", ["", "api-key secret", "../tenant", "x" * 65])
def test_server_authorization_profile_is_closed_and_not_a_secret_or_path(profile):
    with pytest.raises(ValueError):
        AggregateServerPolicy(profile, "fixture", True)
