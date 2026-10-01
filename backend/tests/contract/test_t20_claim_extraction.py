"""T20 声明抽取合同验收测试: 覆盖 T20-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.enrichment.extraction import (
    ExtractionBatch,
    ExtractionValidationError,
    FewShotLeakageError,
    guard_few_shot_leakage,
    locate_quote,
    record_citation_support,
    reject_unsupported_identifiers,
    summarize_field_errors,
    validate_identifier_field,
    validate_negation,
    validate_version_field,
)


def test_version_fix_paragraph_extracts_value_condition_and_quote_t20_c01() -> None:
    """T20-C01: 明确版本与修复段落 → 提取值、条件和原文片段一致。"""
    text = "Version 2.1 is affected. Fixed in 2.2."
    located, unique = locate_quote(text, "Fixed in 2.2.", block_id="b1")
    assert located and unique
    version = validate_version_field("2.1", ())
    assert version.value == "2.1" and version.status == "extracted"
    fix = validate_version_field("2.2", ())
    assert fix.value == "2.2"


def test_config_gated_condition_preserved_as_qualifier_t20_c02() -> None:
    """T20-C02: 只有在配置开启时受影响 → 必要限定条件保留。"""
    gated = validate_version_field("3.0", ("only_when_feature_flag_enabled",))
    assert gated.qualifiers == ("only_when_feature_flag_enabled",)
    assert gated.value == "3.0"


def test_source_negation_not_extracted_as_positive_impact_t20_c03() -> None:
    """T20-C03: 来源否定某版本受影响 → 不抽成正向影响。"""
    negated = validate_negation(claim_positive=True, source_negates=True)
    assert negated.value == "not_affected" and negated.field_name == "affected_status"
    positive = validate_negation(claim_positive=True, source_negates=False)
    assert positive.value == "affected"


def test_quote_absent_or_ambiguous_without_block_fails_validation_t20_c04() -> None:
    """T20-C04: quote 不在原文或多次出现未定位 → 校验失败而非虚构偏移。"""
    text = "same line same line other text"
    located, _ = locate_quote(text, "missing quote", block_id=None)
    assert located is False
    with pytest.raises(ExtractionValidationError):
        locate_quote(text, "same line", block_id=None)
    ok, _ = locate_quote(text, "same line", block_id="b2")
    assert ok is True


def test_benchmark_event_in_few_shot_candidates_rejected_with_leak_report_t20_c05() -> None:
    """T20-C05: 测试集事件进入 few-shot 候选 → 拒绝并报告泄漏。"""
    guard_few_shot_leakage("dev-event-1", ("benchmark-event-1", "benchmark-event-2"))
    with pytest.raises(FewShotLeakageError) as captured:
        guard_few_shot_leakage("benchmark-event-1", ("benchmark-event-1",))
    assert "benchmark-event-1" in str(captured.value)


def test_model_added_unverified_cve_cvss_candidates_rejected_t20_c06() -> None:
    """T20-C06: 模型附加无证据 CVE/CVSS → 候选拒绝, 不发布事实。"""
    rejected = reject_unsupported_identifiers(["CVE-2021-44228", "NOT-A-CVE", "CVSS-10.0"])
    assert rejected == ["NOT-A-CVE", "CVSS-10.0"]
    batch = ExtractionBatch(
        material_type="vulnerability_advisory",
        candidate_claims=(
            validate_identifier_field("CVE-2021-44228"),
            validate_identifier_field("junk-id"),
        ),
        model_hypotheses=(),
        field_error_stats={"cve_id": 1},
    )
    statuses = [claim.status for claim in batch.candidate_claims]
    assert "extracted" in statuses and "unverified" in statuses
    assert summarize_field_errors([batch]) == {"cve_id": 1}
    citation, support = record_citation_support(True, False)
    assert citation is True and support is False
