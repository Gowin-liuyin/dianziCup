"""Cross-field structure rules must reject the same malformed v3 values at both boundaries."""

import json

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from tests.contract.test_r02_value_contract import claim_payload
from tests.unit.test_r07_enrichment_contracts import SIGNALS

from ai_intel.domain.records import ClaimRecord


@pytest.mark.parametrize(
    "value",
    [
        {**SIGNALS[5], "intervals": [{"fixed": "1.2", "last_affected": "1.1"}]},
        {**SIGNALS[5], "intervals": [{"branch": "stable"}]},
        {**SIGNALS[6], "target_document_id": "12345678-1234-5678-1234-567812345678"},
        {**SIGNALS[6], "target_revision_id": "12345678-1234-5678-1234-567812345678"},
    ],
)
def test_malformed_cross_field_value_is_rejected_by_schema_and_runtime(value):
    payload = claim_payload(value["kind"], value, 3)
    payload["asserted_at"] = "2026-10-15T00:00:00+00:00"
    encoded = json.dumps(payload)
    with pytest.raises(ValidationError):
        ClaimRecord.model_validate_json(encoded)
    assert not Draft202012Validator(
        ClaimRecord.model_json_schema(), format_checker=FormatChecker()
    ).is_valid(json.loads(encoded))


@pytest.mark.parametrize(
    "value",
    [
        {**SIGNALS[5], "intervals": [{"introduced": "0", "fixed": None, "last_affected": None}]},
        {**SIGNALS[5], "intervals": [{"fixed": "1.2", "last_affected": None}]},
        {**SIGNALS[5], "intervals": [{"last_affected": "1.1", "fixed": None}]},
        {**SIGNALS[6], "target_document_id": None},
        {**SIGNALS[6], "target_revision_id": None},
        {
            **SIGNALS[6],
            "target_document_id": "12345678-1234-5678-1234-567812345678",
            "target_revision_id": "12345678-1234-5678-1234-567812345678",
        },
    ],
)
def test_null_or_paired_fields_retain_valid_version_and_reference_meaning(value):
    record = ClaimRecord.model_validate(claim_payload(value["kind"], value, 3))
    assert Draft202012Validator(
        ClaimRecord.model_json_schema(), format_checker=FormatChecker()
    ).is_valid(json.loads(record.model_dump_json()))
