"""领域数据传输对象: 来源、文档、证据、论断与研判的类型化记录。

职责: 把已进入业务的字段类型化; 原始外部 JSON 留在边界外; 多余字段一律拒绝,
避免模型输出或旧版本响应静默注入未定义字段。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from pydantic.config import JsonDict, JsonValue

from ai_intel.domain.enrichment_values import ENRICHMENT_VALUE_MODELS, EnrichmentValue
from ai_intel.domain.enums import (
    AssessmentStatus,
    ClaimOrigin,
    ClaimStatus,
    ConditionValue,
    DocumentKind,
    FreshnessStatus,
    SourceCategory,
)
from ai_intel.domain.values import EvidenceSpan, Identifier, UtcTimestamp, VisibilityScope

SCHEMA_VERSION = 2
MAX_SUMMARY_LENGTH = 2000


class StrictRecord(BaseModel):
    """领域记录基类: 多余字段拒绝, 未知输入不静默吞掉。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ScoreValue(StrictRecord):
    """CVSS值保留评分机构/向量；没有数值不生成默认零分。"""

    kind: Literal["score"] = "score"
    score: Annotated[float, Field(ge=0, le=10, allow_inf_nan=False)]
    authority: Annotated[str, Field(min_length=1, max_length=200)]
    vector: Annotated[str, Field(max_length=500)] | None = None


class LinkValue(StrictRecord):
    """来源链接只是静态引用；存储不授予访问或运行PoC的权限。"""

    kind: Literal["link"] = "link"
    url: HttpUrl
    title: Annotated[str, Field(min_length=1, max_length=500)]


class VersionRangeValue(StrictRecord):
    """保存来源表达的版本范围，适用判断交给受支持的生态比较器。"""

    kind: Literal["version_range"] = "version_range"
    ecosystem: Annotated[str, Field(min_length=1, max_length=100)]
    expression: Annotated[str, Field(min_length=1, max_length=2000)]
    branch: Annotated[str, Field(min_length=1, max_length=200)] | None = None


ClaimObjectValue = (
    Annotated[str, Field(min_length=1, max_length=MAX_SUMMARY_LENGTH)]
    | Annotated[ScoreValue | LinkValue | VersionRangeValue, Field(discriminator="kind")]
    | EnrichmentValue
)

LEGACY_STRUCTURED_PREDICATES: dict[str, type[BaseModel]] = {
    "cvss_score": ScoreValue,
    "reference_link": LinkValue,
    "poc_link": LinkValue,
    "affected_version": VersionRangeValue,
    "affected_versions": VersionRangeValue,
}


def _predicate_value_constraints(
    predicate_models: Mapping[str, type[BaseModel]], *, allow_other_text: bool
) -> list[JsonValue]:
    predicate_constraints: list[JsonValue] = [
        {
            "if": {"properties": {"predicate": {"const": predicate}}},
            "then": {
                "properties": {
                    "object_value": {
                        "type": "object",
                        "properties": {"kind": {"const": model.model_fields["kind"].default}},
                        "required": ["kind"],
                    }
                }
            },
        }
        for predicate, model in predicate_models.items()
    ]
    if allow_other_text:
        predicate_constraints.append(
            {
                "if": {"properties": {"predicate": {"not": {"enum": list(predicate_models)}}}},
                "then": {"properties": {"object_value": {"type": "string"}}},
            }
        )
    else:
        predicate_constraints.append(
            {"properties": {"predicate": {"enum": list(predicate_models)}}}
        )
    return predicate_constraints


def _restrict_claim_json_schema(schema: JsonDict) -> None:
    """v1/v2 unchanged; v3 accepts only the registered, typed enrichment predicates."""
    schema["allOf"] = [
        {"properties": {"schema_version": {"enum": [1, 2, 3]}}},
        {
            "if": {"properties": {"schema_version": {"const": 1}}, "required": ["schema_version"]},
            "then": {"properties": {"object_value": {"type": "string"}}},
            "else": {
                "if": {"properties": {"schema_version": {"const": 2}}},
                "then": {
                    "allOf": _predicate_value_constraints(
                        LEGACY_STRUCTURED_PREDICATES, allow_other_text=True
                    )
                },
                "else": {
                    "allOf": _predicate_value_constraints(
                        ENRICHMENT_VALUE_MODELS, allow_other_text=False
                    )
                },
            },
        },
    ]


class SourceRecord(StrictRecord):
    """来源登记: category 决定连接器族, 不由标题猜测。"""

    schema_version: int = SCHEMA_VERSION
    source_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=500)]
    category: SourceCategory
    base_origin: Annotated[str, Field(min_length=1, max_length=2000)]
    scope: VisibilityScope


class DocumentRecord(StrictRecord):
    """文档快照: 修订不覆盖历史, 每个版本独立成记录。"""

    schema_version: int = SCHEMA_VERSION
    document_id: Identifier
    kind: DocumentKind
    title: Annotated[str, Field(min_length=1, max_length=500)]
    published_at: UtcTimestamp | None = None
    retrieved_at: UtcTimestamp
    content_hash: Annotated[str, Field(min_length=32, max_length=128)]
    scope: VisibilityScope


class EvidenceRecord(StrictRecord):
    """证据条目: 左闭右开区间 + 定位符 + 支撑/反驳语义。"""

    schema_version: int = SCHEMA_VERSION
    evidence_id: Identifier
    document_id: Identifier
    span: EvidenceSpan
    quote: Annotated[str, Field(min_length=1, max_length=MAX_SUMMARY_LENGTH)]
    supports_claim: bool


class ClaimRecord(StrictRecord):
    """事实论断: 状态、来源等级与条件判定三分, 不合并为单一 status。"""

    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_extra=_restrict_claim_json_schema
    )

    schema_version: int = SCHEMA_VERSION
    claim_id: Identifier
    subject: Annotated[str, Field(min_length=1, max_length=500)]
    predicate: Annotated[str, Field(min_length=1, max_length=500)]
    object_value: ClaimObjectValue
    claim_status: ClaimStatus
    claim_origin: ClaimOrigin
    condition_value: ConditionValue
    freshness: FreshnessStatus
    asserted_at: UtcTimestamp
    observed_at: UtcTimestamp | None = None
    scope: VisibilityScope

    @model_validator(mode="after")
    def validate_predicate_value_contract(self) -> ClaimRecord:
        """Old records retain their version; v3 cannot disguise candidates as legacy text."""
        if self.schema_version not in {1, 2, 3}:
            raise ValueError("unsupported claim schema version")
        if self.schema_version == 1:
            if not isinstance(self.object_value, str):
                raise ValueError("schema version 1 requires text claim value")
            return self
        if self.schema_version == 3:
            signal_type = ENRICHMENT_VALUE_MODELS.get(self.predicate)
            if signal_type is None or not isinstance(self.object_value, signal_type):
                raise ValueError(
                    "schema version 3 requires registered enrichment predicate and value"
                )
            return self
        expected_type = LEGACY_STRUCTURED_PREDICATES.get(self.predicate, str)
        if not isinstance(self.object_value, expected_type):
            raise ValueError("claim value does not match predicate contract")
        return self

    @model_validator(mode="after")
    def current_freshness_requires_observation_time(self) -> ClaimRecord:
        """freshness=current 必须有观察时间; 缺观察时间不得填 current。"""
        if self.freshness == FreshnessStatus.CURRENT and self.observed_at is None:
            raise ValueError("freshness=current requires observed_at")
        return self


class AssessmentRecord(StrictRecord):
    """资产研判: 结论与证据包绑定; 四态结论不等于入侵或安全断言。"""

    schema_version: int = SCHEMA_VERSION
    assessment_id: Identifier
    asset_id: Identifier
    claim_id: Identifier
    status: AssessmentStatus
    decided_at: UtcTimestamp
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1)
    scope: VisibilityScope
