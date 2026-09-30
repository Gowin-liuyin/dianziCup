"""领域数据传输对象: 来源、文档、证据、论断与研判的类型化记录。

职责: 把已进入业务的字段类型化; 原始外部 JSON 留在边界外; 多余字段一律拒绝,
避免模型输出或旧版本响应静默注入未定义字段。
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

SCHEMA_VERSION = 1
MAX_SUMMARY_LENGTH = 2000


class StrictRecord(BaseModel):
    """领域记录基类: 多余字段拒绝, 未知输入不静默吞掉。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


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

    schema_version: int = SCHEMA_VERSION
    claim_id: Identifier
    subject: Annotated[str, Field(min_length=1, max_length=500)]
    predicate: Annotated[str, Field(min_length=1, max_length=500)]
    object_value: Annotated[str, Field(min_length=1, max_length=MAX_SUMMARY_LENGTH)]
    claim_status: ClaimStatus
    claim_origin: ClaimOrigin
    condition_value: ConditionValue
    freshness: FreshnessStatus
    asserted_at: UtcTimestamp
    observed_at: UtcTimestamp | None = None
    scope: VisibilityScope

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
