"""Authority scope uses the existing bounded string contract without hidden normalization."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ai_intel.domain.enrichment_values import CvssSignalValue

VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


@pytest.mark.parametrize("authority", ["nvd@nist.gov", "NVD@NIST.GOV", " nvd@nist.gov ", "unknown"])
def test_authority_literal_identity_survives_value_and_exported_schema(authority):
    value = {
        "kind": "cvss_signal",
        "standard_version": "3.1",
        "base_score": 9.8,
        "vector": VECTOR,
        "authority": authority,
    }
    parsed = CvssSignalValue.model_validate(value)
    assert parsed.authority == authority
    assert CvssSignalValue.model_validate_json(parsed.model_dump_json()) == parsed
    bundle = json.loads(
        (Path(__file__).resolve().parents[3] / "contracts/schemas/schema_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    schema = bundle["schemas"]["ClaimRecord"]["$defs"]["CvssSignalValue"]
    assert Draft202012Validator(schema).is_valid(value)
    assert schema["properties"]["authority"] == {
        "maxLength": 200,
        "minLength": 1,
        "title": "Authority",
        "type": "string",
    }


@pytest.mark.parametrize("authority", [None, "", 123, True, [], {}, "x" * 201])
def test_authority_missing_wrong_type_and_overlong_values_reject(authority):
    with pytest.raises(ValidationError):
        CvssSignalValue.model_validate(
            {"standard_version": "3.1", "base_score": 9.8, "vector": VECTOR, "authority": authority}
        )
