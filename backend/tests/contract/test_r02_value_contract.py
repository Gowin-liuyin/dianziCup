"""冻结谓词/结构值联合合同，旧v1文本明确兼容而非静默升级。"""

import json
from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ai_intel.domain.records import ClaimRecord, LinkValue, ScoreValue, VersionRangeValue


def claim_payload(predicate: str, value: object, version: int = 2) -> dict[str, object]:
    return {
        "schema_version": version,
        "claim_id": {"value": "12345678-1234-5678-1234-567812345678"},
        "subject": "test-component",
        "predicate": predicate,
        "object_value": value,
        "claim_status": "unverified",
        "claim_origin": "structured_source",
        "condition_value": "unknown",
        "freshness": "unknown",
        "asserted_at": datetime.now(UTC),
        "scope": {"visibility": "public", "tenant_id": None},
    }


@pytest.mark.parametrize(
    ("predicate", "value", "expected_type"),
    [
        ("affected_by", "synthetic-advisory", str),
        ("cvss_score", {"kind": "score", "score": 9.8, "authority": "fixture-CNA"}, ScoreValue),
        (
            "poc_link",
            {"kind": "link", "url": "https://example.invalid/poc", "title": "Static reference"},
            LinkValue,
        ),
        (
            "affected_version",
            {"kind": "version_range", "ecosystem": "pypi", "expression": "<2.1"},
            VersionRangeValue,
        ),
    ],
)
def test_value_roundtrip_is_typed_and_preserves_predicate(
    predicate: str, value: object, expected_type: type
) -> None:
    record = ClaimRecord.model_validate(claim_payload(predicate, value))
    restored = ClaimRecord.model_validate_json(record.model_dump_json())
    assert restored == record and isinstance(restored.object_value, expected_type)


@pytest.mark.parametrize(
    ("predicate", "value", "version"),
    [
        ("cvss_score", "9.8", 2),
        ("cvss_score", {"kind": "score", "score": 10.1, "authority": "fixture-CNA"}, 2),
        (
            "cvss_score",
            {"kind": "score", "score": 5, "authority": "fixture-CNA", "skip_validation": True},
            2,
        ),
        ("affected_by", {"kind": "score", "score": 5, "authority": "fixture-CNA"}, 2),
        ("cvss_score", {"kind": "score", "score": 5, "authority": "fixture-CNA"}, 1),
        ("affected_by", "synthetic-advisory", 3),
    ],
)
def test_incompatible_or_unbounded_value_is_rejected(
    predicate: str, value: object, version: int
) -> None:
    with pytest.raises(ValidationError):
        ClaimRecord.model_validate(claim_payload(predicate, value, version))


def test_legacy_text_requires_explicit_version_one_and_is_not_upgraded() -> None:
    record = ClaimRecord.model_validate(claim_payload("cvss_score", "9.8", 1))
    assert record.schema_version == 1 and record.object_value == "9.8"


@pytest.mark.parametrize(
    ("predicate", "value", "version", "valid"),
    [
        ("cvss_score", {"kind": "score", "score": 5, "authority": "fixture-CNA"}, 2, True),
        ("cvss_score", "5", 1, True),
        ("cvss_score", "5", 2, False),
        ("affected_by", {"kind": "score", "score": 5, "authority": "fixture-CNA"}, 2, False),
        ("cvss_score", {"kind": "score", "score": 5, "authority": "fixture-CNA"}, 1, False),
    ],
)
def test_exported_json_schema_enforces_same_predicate_contract(
    predicate: str, value: object, version: int, valid: bool
) -> None:
    payload = claim_payload(predicate, value, version)
    payload["asserted_at"] = "2026-10-15T00:00:00+00:00"
    validator = Draft202012Validator(ClaimRecord.model_json_schema())
    assert validator.is_valid(json.loads(json.dumps(payload))) is valid
