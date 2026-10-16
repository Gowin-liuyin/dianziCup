"""The fixed public projection rejects identity input and preserves original result types."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from tests.r11_assessment_http_fixtures import synthetic_receipt

from ai_intel.assessment.http_contracts import AssessmentRequest, AssessmentResponse
from ai_intel.assessment.persistence_contracts import AssessmentReceipt


def request_payload():
    return dict(
        asset_id=str(uuid4()), asset_snapshot_id=str(uuid4()), rule_id="rule", rule_version=1
    )


def test_request_round_trip_and_original_label_boundaries():
    payload = request_payload()
    request = AssessmentRequest.model_validate(payload)
    assert isinstance(request.asset_id, UUID)
    assert request.model_dump(mode="json") == payload
    assert AssessmentRequest.model_validate(dict(payload, rule_id="r" * 200)).rule_id == "r" * 200
    assert (
        AssessmentRequest.model_validate(dict(payload, rule_version=2147483647)).rule_version
        == 2147483647
    )


@pytest.mark.parametrize("field", ["asset_id", "asset_snapshot_id", "rule_id", "rule_version"])
def test_required_fields(field):
    payload = request_payload()
    del payload[field]
    with pytest.raises(ValidationError):
        AssessmentRequest.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "user_id", "role", "permissions", "cutoff", "prepared", "actor", "credential"],
)
def test_extra_identity_and_preparation_fields_are_forbidden(field):
    with pytest.raises(ValidationError):
        AssessmentRequest.model_validate(dict(request_payload(), **{field: "private-marker"}))


@pytest.mark.parametrize("version", [True, False, "1", 1.0, 0, -1, 2147483648, None])
def test_version_is_a_bounded_strict_integer(version):
    with pytest.raises(ValidationError):
        AssessmentRequest.model_validate(dict(request_payload(), rule_version=version))


@pytest.mark.parametrize(
    "field,value",
    [
        ("asset_id", "invalid"),
        ("asset_snapshot_id", 1),
        ("rule_id", ""),
        ("rule_id", "r" * 201),
        ("rule_id", 1),
    ],
)
def test_invalid_identifiers(field, value):
    with pytest.raises(ValidationError):
        AssessmentRequest.model_validate(dict(request_payload(), **{field: value}))


def test_projection_has_every_receipt_field_except_prepared_and_preserves_values():
    receipt = synthetic_receipt()
    response = AssessmentResponse.from_receipt(receipt)
    assert set(AssessmentResponse.model_fields) == set(AssessmentReceipt.model_fields) - {
        "prepared"
    }
    expected = receipt.model_dump(mode="json", exclude={"prepared"})
    expected["schema_version"] = "r11-assessment-http-1"
    assert response.model_dump(mode="json") == expected
    serialized = response.model_dump_json()
    assert (
        "private-preparation-marker" not in serialized and "private-actor-marker" not in serialized
    )
    assert response.status == "insufficient_evidence" and response.freshness == "unknown"
    assert response.knowledge_epoch is None


def test_response_reuses_original_rule_result_enum_and_timestamp_types():
    for field in (
        "rule_result",
        "status",
        "freshness",
        "created_at",
        "exposure_result",
        "exploit_evidence_status",
    ):
        assert (
            AssessmentResponse.model_fields[field].annotation
            == AssessmentReceipt.model_fields[field].annotation
        )
    payload = AssessmentResponse.from_receipt(synthetic_receipt()).model_dump(mode="json")
    with pytest.raises(ValidationError):
        AssessmentResponse.model_validate(dict(payload, prepared={}))
