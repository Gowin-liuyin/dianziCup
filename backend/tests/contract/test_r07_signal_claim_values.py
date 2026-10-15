"""Versioned signal claims retain old text/typed contracts and agree with JSON Schema."""

import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.contract.test_r02_value_contract import claim_payload
from tests.unit.test_r07_enrichment_contracts import SIGNALS

from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.schema_export import build_schema_bundle


@pytest.mark.parametrize("value", SIGNALS)
def test_v3_typed_signals_roundtrip_and_match_exported_json_schema(value):
    record = ClaimRecord.model_validate(claim_payload(value["kind"], value, 3))
    dumped = record.model_dump_json()
    assert ClaimRecord.model_validate_json(dumped) == record
    validator = Draft202012Validator(ClaimRecord.model_json_schema())
    assert validator.is_valid(json.loads(dumped))
    rejected_v2 = json.loads(dumped)
    rejected_v2["schema_version"] = 2
    assert not validator.is_valid(rejected_v2)
    with pytest.raises(ValidationError):
        ClaimRecord.model_validate(rejected_v2)


@pytest.mark.parametrize(
    "predicate,value,version",
    [
        ("affected_by", "legacy text", 3),
        ("epss_signal", "0.2", 3),
        ("kev_signal", SIGNALS[1], 3),
        ("epss_signal", SIGNALS[1], 4),
    ],
)
def test_unregistered_predicates_wrong_values_and_unknown_versions_reject(
    predicate, value, version
):
    with pytest.raises(ValidationError):
        ClaimRecord.model_validate(claim_payload(predicate, value, version))


def test_schema_bundle_records_explicit_signal_version_without_upgrading_legacy_defaults():
    bundle = build_schema_bundle()
    assert bundle["schema_version"] == 2
    old = ClaimRecord.model_validate(claim_payload("affected_by", "legacy text", 1))
    assert old.schema_version == 1
    assert (
        ClaimRecord.model_validate(
            claim_payload("affected_by", "new old-style text")
        ).schema_version
        == 2
    )
