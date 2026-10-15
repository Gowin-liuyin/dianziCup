"""模型客户端协议与校验: 结构化生成/向量/重排; SDK 不泄漏领域层; 外发策略闸门。"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass, field

from ai_intel.infrastructure.models.json_output import strict_json_object

MODEL_CLIENT_VERSION = "model-1.0.0"


class ModelContractError(RuntimeError):
    """输出/维度/批次不合合同: 明确失败, 不悄悄降级成功。"""


class ModelNotConfiguredError(RuntimeError):
    """能力未配置: not_configured, 不伪称模型可用。"""


class ProductionFixtureForbidden(RuntimeError):
    """production 禁用 fixture provider/固定答案/哈希向量。"""


class EgressPolicyViolation(PermissionError):
    """私有资产未经外发许可: 网关阻断, 原文不送外部模型。"""


@dataclass(frozen=True)
class GenerationResult:
    """结构化生成结果: 用量与模型/提示词版本必须保留。"""

    structured_payload: dict[str, object]
    model_version: str
    prompt_version: str
    usage_tokens: int
    format_repair_used: bool = False


@dataclass(frozen=True)
class EmbeddingResult:
    """向量结果: 维度与条目顺序校验后方可入索引。"""

    vectors: tuple[tuple[float, ...], ...]
    model_version: str
    dimension: int


def validate_structured_output(
    raw_text: str,
    allowed_top_level_keys: tuple[str, ...],
    model_version: str,
    prompt_version: str,
    usage_tokens: int,
    repair_once: Callable[[str], str] | None = None,
) -> GenerationResult:
    """JSON 输出校验: 多余字段/坏 JSON 报错或至多一次受限修复, 不降级成功。"""
    try:
        payload = strict_json_object(raw_text)
        repair_used = False
    except (ValueError, RecursionError):
        if repair_once is None:
            raise ModelContractError(
                "model output is not valid JSON; no repair available"
            ) from None
        repaired_text = repair_once(raw_text)
        try:
            payload = strict_json_object(repaired_text)
        except (ValueError, RecursionError) as error:
            raise ModelContractError("model output invalid even after single repair") from error
        repair_used = True
    if not isinstance(payload, dict):
        raise ModelContractError("structured output must be a JSON object")
    unexpected = sorted(set(payload) - set(allowed_top_level_keys))
    if unexpected:
        raise ModelContractError("unexpected top-level fields")
    return GenerationResult(
        structured_payload=payload,
        model_version=model_version,
        prompt_version=prompt_version,
        usage_tokens=usage_tokens,
        format_repair_used=repair_used,
    )


def validate_embedding_batch(
    vectors: list[list[float]],
    expected_count: int,
    dimension: int,
    model_version: str,
) -> EmbeddingResult:
    """拒绝无效空间、非有限数与余弦距离无定义的零向量，不替换坏值。"""
    if (
        type(expected_count) is not int
        or not 1 <= expected_count <= 256
        or type(dimension) is not int
        or not 1 <= dimension <= 4096
        or not isinstance(model_version, str)
        or not 1 <= len(model_version) <= 200
        or any(not 33 <= ord(character) <= 126 for character in model_version)
    ):
        raise ModelContractError("embedding space or batch boundary is invalid")
    if len(vectors) != expected_count:
        raise ModelContractError("embedding count does not match input batch order")
    for vector in vectors:
        if len(vector) != dimension:
            raise ModelContractError("embedding dimension mismatch; refused for indexing")
        if any(
            type(coordinate) is not float
            or not math.isfinite(coordinate)
            or abs(coordinate) > 3.4028234663852886e38
            for coordinate in vector
        ):
            raise ModelContractError("embedding coordinates must be finite float32 values")
        if not any(coordinate != 0.0 for coordinate in vector):
            raise ModelContractError("zero embedding has no cosine distance")
    frozen = tuple(tuple(vector) for vector in vectors)
    return EmbeddingResult(vectors=frozen, model_version=model_version, dimension=dimension)


def assert_runtime_allows_fixture_provider(environment_name: str) -> None:
    """DATA_MODE 隔离: production 启动/调用 fixture provider 一律拒绝。"""
    if environment_name == "production":
        raise ProductionFixtureForbidden("fixture provider is test-only; forbidden in production")


def enforce_egress_policy(content_is_private: bool, egress_granted: bool) -> None:
    """外发策略: 私有内容未经许可不得送外部模型。"""
    if content_is_private and not egress_granted:
        raise EgressPolicyViolation(
            "private content withheld from external model; egress not granted"
        )


def describe_model_capability(configured: bool, budget_authorized: bool) -> str:
    """能力状态: 无 key 或无预算即 not_configured/blocked_live, 不伪称可用。"""
    if not configured:
        return "not_configured"
    if not budget_authorized:
        return "blocked_live"
    return "available"


@dataclass(frozen=True)
class FixtureProvider:
    """仅测试用 fixture provider: 固定答案, 严禁 production。"""

    fixed_response: dict[str, object] = field(default_factory=dict)
    provider_version: str = "fixture-1.0.0"

    def generate_structured(self, environment_name: str, prompt_text: str) -> dict[str, object]:
        assert_runtime_allows_fixture_provider(environment_name)
        fingerprint = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]
        return {"fixture": True, "prompt_fingerprint": fingerprint, **self.fixed_response}
