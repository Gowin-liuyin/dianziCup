"""T04 领域合同验收测试: 覆盖 T04-C01—C06 与关键 DTO 的正常/缺失/矛盾/多余字段输入。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ai_intel.domain.enums import (
    ClaimOrigin,
    ClaimStatus,
    ConditionValue,
    FreshnessStatus,
)
from ai_intel.domain.records import SCHEMA_VERSION, ClaimRecord, EvidenceRecord
from ai_intel.domain.schema_export import build_schema_bundle, render_schema_bundle
from ai_intel.domain.values import EvidenceSpan, Identifier, VisibilityScope

UUID_A = "12345678-1234-5678-1234-567812345678"
UUID_B = "abcdefab-cdef-5678-1234-567812345678"


def build_claim_record(**overrides: object) -> ClaimRecord:
    """构造一条合法论断记录, 测试用覆盖字段替换个别输入。"""
    payload: dict[str, object] = {
        "claim_id": {"value": UUID_A},
        "subject": "component libdemo",
        "predicate": "affected_by",
        "object_value": "CVE-like synthetic entry",
        "claim_status": ClaimStatus.UNVERIFIED,
        "claim_origin": ClaimOrigin.SOURCE_EXPLICIT,
        "condition_value": ConditionValue.UNKNOWN,
        "freshness": FreshnessStatus.UNKNOWN,
        "asserted_at": datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
        "observed_at": None,
        "scope": {"visibility": "public", "tenant_id": None},
    }
    payload.update(overrides)
    return ClaimRecord.model_validate(payload)


def test_claim_roundtrip_preserves_utc_and_enum_semantics() -> None:
    """T04-C01: 合法 UTC 输入 roundtrip 后字段语义保持, 时区换算为 UTC。"""
    record = build_claim_record(asserted_at=datetime(2026, 9, 30, 14, 0, tzinfo=UTC))
    restored = ClaimRecord.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.asserted_at.tzinfo == UTC
    assert restored.condition_value is ConditionValue.UNKNOWN


def test_public_scope_with_tenant_id_is_rejected() -> None:
    """T04-C02: public 记录携带 tenant_id 属矛盾输入, 必须拒绝。"""
    with pytest.raises(ValidationError):
        VisibilityScope.model_validate({"visibility": "public", "tenant_id": UUID_B})


def test_tenant_scope_without_tenant_id_is_rejected() -> None:
    """T04-C02: tenant 记录缺 tenant_id 必须拒绝, 不允许含糊中间态。"""
    with pytest.raises(ValidationError):
        VisibilityScope.model_validate({"visibility": "tenant", "tenant_id": None})


def test_unknown_and_false_condition_values_stay_distinct_after_serialization() -> None:
    """T04-C03: unknown 与 false 序列化/反序列化后仍是不同值。"""
    unknown_record = build_claim_record()
    false_record = build_claim_record(condition_value=ConditionValue.FALSE)
    unknown_restored = ClaimRecord.model_validate_json(unknown_record.model_dump_json())
    false_restored = ClaimRecord.model_validate_json(false_record.model_dump_json())
    assert unknown_restored.condition_value == ConditionValue.UNKNOWN
    assert false_restored.condition_value == ConditionValue.FALSE
    assert unknown_restored.condition_value != false_restored.condition_value


def test_naive_datetime_is_rejected_without_timezone_guessing() -> None:
    """T04-C04: 无时区时间直接拒绝, 不猜时区。"""
    with pytest.raises(ValidationError):
        build_claim_record(asserted_at=datetime(2026, 9, 30, 12, 0))


def test_inverted_evidence_span_is_rejected_without_swapping_bounds() -> None:
    """T04-C04: 倒置区间拒绝, 不取绝对值也不交换端点。"""
    with pytest.raises(ValidationError):
        EvidenceSpan.model_validate({"start_offset": 50, "end_offset": 10, "locator": "line 3"})


def test_negative_length_input_is_rejected() -> None:
    """T04-C04: 负长度/负偏移拒绝。"""
    with pytest.raises(ValidationError):
        EvidenceSpan.model_validate({"start_offset": -1, "end_offset": 5, "locator": "line 1"})


def test_extra_field_skip_validation_is_rejected() -> None:
    """T04-C05: 模型响应多出 skip_validation 字段必须拒绝, 不静默吞掉。"""
    payload = build_claim_record().model_dump()
    payload["skip_validation"] = True
    with pytest.raises(ValidationError):
        ClaimRecord.model_validate(payload)


def test_missing_required_field_reports_locatable_problem() -> None:
    """T04-C05: 缺失字段的错误信息必须指向具体字段。"""
    payload = build_claim_record().model_dump()
    del payload["predicate"]
    with pytest.raises(ValidationError) as captured:
        ClaimRecord.model_validate(payload)
    assert "predicate" in str(captured.value)


def test_current_freshness_without_observation_time_is_rejected() -> None:
    """矛盾输入: freshness=current 但无观察时间必须拒绝。"""
    with pytest.raises(ValidationError):
        build_claim_record(freshness=FreshnessStatus.CURRENT, observed_at=None)


def test_identifier_rejects_non_uuid_primary_key() -> None:
    """标识边界: 主键必须是 UUID 字符串, 标题类字符串拒绝。"""
    with pytest.raises(ValidationError):
        Identifier.model_validate({"value": "just-a-title"})


def test_evidence_record_requires_at_least_one_locator() -> None:
    """缺失输入: 证据记录必须携带定位区间。"""
    payload = {
        "evidence_id": {"value": UUID_A},
        "document_id": {"value": UUID_B},
        "quote": "synthetic quote",
        "supports_claim": True,
    }
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(payload)


def test_schema_bundle_generation_is_deterministic_with_stable_version() -> None:
    """T04-C06: schema 重复生成无漂移, 版本记录一致。"""
    first = render_schema_bundle()
    second = render_schema_bundle()
    assert first == second
    bundle = build_schema_bundle()
    assert bundle["schema_version"] == SCHEMA_VERSION
    schemas = bundle["schemas"]
    assert isinstance(schemas, dict)
    assert set(schemas) == {
        "SourceRecord",
        "DocumentRecord",
        "EvidenceRecord",
        "ClaimRecord",
        "AssessmentRecord",
    }
