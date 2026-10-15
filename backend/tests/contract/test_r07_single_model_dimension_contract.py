"""Synthetic one-call wire and frozen DimensionAttempt contract checks; live is not run."""

import json

import pytest
from jsonschema import Draft202012Validator
from tests.unit.test_r07_single_model_dimension import DIMENSIONS, extract, prepared_transport

from ai_intel.domain.enums import DimensionStatus
from ai_intel.enrichment.contracts import DimensionAttempt


@pytest.mark.parametrize("dimension", DIMENSIONS)
@pytest.mark.parametrize(
    "provider", ["openai", "anthropic", "deepseek_openai", "deepseek_anthropic"]
)
def test_all_real_codecs_preserve_single_attempt_contract_and_metadata(
    monkeypatch, dimension, provider
):
    client, calls = prepared_transport(monkeypatch, provider=provider)
    result = extract(client, dimension)
    assert len(result.attempts) == len(result.model_attempts) == len(calls) == 1
    attempt = result.attempts[0]
    assert attempt.status == DimensionStatus.PENDING
    serialized = attempt.model_dump_json()
    assert DimensionAttempt.model_validate_json(serialized) == attempt
    assert not list(
        Draft202012Validator(DimensionAttempt.model_json_schema()).iter_errors(
            json.loads(serialized)
        )
    )
    metadata = result.model_attempts[0]
    assert metadata.provider == provider
    assert metadata.requested_model == metadata.response_model == client.approved_model
    assert metadata.outcome == "succeeded"
    assert metadata.http_status == 200
    assert metadata.prompt_version == "r07-model-fields-1"
    assert metadata.schema_version == "r07-model-field-extraction-1"
    assert metadata.call_id == "offline-fixture-call"
    assert metadata.usage.input_tokens == 20
    assert metadata.usage.output_tokens == 1
    assert metadata.fee == "unknown"
    assert (
        len(metadata.prompt_sha256)
        == len(metadata.body_sha256)
        == len(metadata.response_sha256)
        == 64
    )
    maximum_key = "max_completion_tokens" if provider == "openai" else "max_tokens"
    assert calls[0][1][maximum_key] == 1024


@pytest.mark.parametrize("dimension", DIMENSIONS)
@pytest.mark.parametrize("failure", ["format", "network", "timeout", 401, 429, 503, 302])
def test_failure_is_one_wire_call_no_repair_and_only_one_dimension(monkeypatch, dimension, failure):
    client, calls = prepared_transport(monkeypatch, failure=failure)
    result = extract(client, dimension)
    assert [attempt.dimension for attempt in result.attempts] == [dimension]
    assert len(calls) == len(result.model_attempts) == 1
    assert result.attempts[0].status in (DimensionStatus.BLOCKED, DimensionStatus.FAILED)
    assert result.attempts[0].candidates == ()
    assert result.attempts[0].error_code == result.model_attempts[0].outcome
    assert result.model_attempts[0].outcome != "succeeded"
    assert result.model_attempts[0].fee == "unknown"
