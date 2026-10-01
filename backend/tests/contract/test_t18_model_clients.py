"""T18 模型客户端合同验收测试: 覆盖 T18-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.infrastructure.models.clients import (
    EgressPolicyViolation,
    FixtureProvider,
    ModelContractError,
    ProductionFixtureForbidden,
    assert_runtime_allows_fixture_provider,
    describe_model_capability,
    enforce_egress_policy,
    validate_embedding_batch,
    validate_structured_output,
)


def test_valid_structured_output_keeps_usage_and_versions_t18_c01() -> None:
    """T18-C01: 合法结构化输出通过 schema 且保留用量与模型/提示词版本。"""
    result = validate_structured_output(
        '{"findings": [], "status": "clear"}',
        allowed_top_level_keys=("findings", "status"),
        model_version="gen-1",
        prompt_version="v1",
        usage_tokens=42,
    )
    assert result.structured_payload == {"findings": [], "status": "clear"}
    assert result.usage_tokens == 42
    assert result.model_version == "gen-1" and result.prompt_version == "v1"
    assert result.format_repair_used is False


def test_extra_fields_or_bad_json_fails_or_single_repair_only_t18_c02() -> None:
    """T18-C02: 多余字段/错误 JSON 报错或一次修复后失败, 不悄悄降级成功。"""
    with pytest.raises(ModelContractError):
        validate_structured_output(
            '{"findings": [], "secret_extra": 1}', ("findings",), "m", "p", 1
        )
    repairs = {"count": 0}

    def repair_once(raw: str) -> str:
        repairs["count"] += 1
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        return text[start : end + 1] if start >= 0 and end > start else text

    fixed = validate_structured_output(
        '```json\n{"ok": true}\n```', ("ok",), "m", "p", 5, repair_once=repair_once
    )
    assert fixed.format_repair_used is True and repairs["count"] == 1
    with pytest.raises(ModelContractError):
        validate_structured_output("not json at all", ("ok",), "m", "p", 5, repair_once=repair_once)
    assert repairs["count"] == 2


def test_wrong_vector_dimension_or_count_refused_for_indexing_t18_c03() -> None:
    """T18-C03: 向量维度或条目数量错 → 拒绝入索引。"""
    ok = validate_embedding_batch(
        [[1.0, 2.0], [3.0, 4.0]], expected_count=2, dimension=2, model_version="emb-1"
    )
    assert ok.dimension == 2 and len(ok.vectors) == 2
    with pytest.raises(ModelContractError):
        validate_embedding_batch([[1.0, 2.0]], expected_count=2, dimension=2, model_version="emb-1")
    with pytest.raises(ModelContractError):
        validate_embedding_batch([[1.0]], expected_count=1, dimension=2, model_version="emb-1")


def test_fixture_provider_rejected_in_production_t18_c04() -> None:
    """T18-C04: fixture provider 在 production 启动/调用被拒。"""
    provider = FixtureProvider(fixed_response={"answer": "fixed"})
    assert provider.generate_structured("test", "prompt")["fixture"] is True
    with pytest.raises(ProductionFixtureForbidden):
        provider.generate_structured("production", "prompt")
    with pytest.raises(ProductionFixtureForbidden):
        assert_runtime_allows_fixture_provider("production")


def test_private_content_without_egress_grant_blocked_t18_c05() -> None:
    """T18-C05: 私有资产未经外发许可 → 网关阻断, 原文不送外部模型。"""
    enforce_egress_policy(content_is_private=True, egress_granted=True)
    enforce_egress_policy(content_is_private=False, egress_granted=False)
    with pytest.raises(EgressPolicyViolation):
        enforce_egress_policy(content_is_private=True, egress_granted=False)


def test_missing_key_or_budget_reports_unavailable_not_fake_t18_c06() -> None:
    """T18-C06: 无 key 或无预算 → not_configured/blocked_live, 不伪称可用。"""
    assert describe_model_capability(configured=False, budget_authorized=False) == "not_configured"
    assert describe_model_capability(configured=True, budget_authorized=False) == "blocked_live"
    assert describe_model_capability(configured=True, budget_authorized=True) == "available"
    assert describe_model_capability(configured=False, budget_authorized=True) == "not_configured"
