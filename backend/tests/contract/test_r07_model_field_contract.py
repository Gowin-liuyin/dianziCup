"""The existing internal/public candidate seam remains unchanged by private extraction schemas."""

import json

import pytest
from jsonschema import Draft202012Validator
from tests.unit.test_r07_model_fields import execute

from ai_intel.enrichment.contracts import DimensionAttempt
from ai_intel.enrichment.model_fields import (
    ExtractedArtifactValue,
    ExtractedLiteratureValue,
    ExtractedVersionValue,
    GeneratedFieldBatch,
)
from ai_intel.infrastructure.models.generation import require_strict_schema


def test_returned_attempts_roundtrip_through_frozen_seam(monkeypatch):
    result, _ = execute(monkeypatch)
    validator = Draft202012Validator(DimensionAttempt.model_json_schema())
    for attempt in result.attempts:
        serialized = attempt.model_dump_json()
        assert DimensionAttempt.model_validate_json(serialized) == attempt
        assert not list(validator.iter_errors(json.loads(serialized)))


@pytest.mark.parametrize(
    "value_type",
    [
        ExtractedArtifactValue,
        ExtractedLiteratureValue,
        ExtractedVersionValue,
    ],
)
def test_private_extraction_schema_recursively_forbids_extra_fields(value_type):
    schema = GeneratedFieldBatch[value_type]
    require_strict_schema(schema)
    assert schema.model_json_schema()["additionalProperties"] is False
