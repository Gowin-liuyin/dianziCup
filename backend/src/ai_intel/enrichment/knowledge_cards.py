"""知识卡: 论文卡/标准政策卡分立; 原文与摘要分开; 验证等级不升级。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from ai_intel.api.document_contracts import ContentCoverage, DocumentKindFilter
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.infrastructure.models.generation import AttemptMetadata

KNOWLEDGE_CARDS_VERSION = "knowledge-cards-1.1.0"
VERIFICATION_LEVELS = ("unknown", "author_reported", "team_reproduced", "rule_inferred_for_asset")
PAPER_FIELDS = (
    "risk_mechanism",
    "attacker_capability",
    "input_path",
    "model_or_task",
    "tool_permissions",
    "author_validation_environment",
    "conclusion",
    "limitations",
)
PUBLICATION_FIELDS = (
    "issuer",
    "document_number",
    "version_label",
    "publication_status",
    "published_at",
    "effective_at",
    "scope",
    "clause_text",
    "summary",
)


class KnowledgeCardError(RuntimeError):
    """卡片字段/验证等级合同违规。"""


@dataclass(frozen=True)
class PaperCard:
    """论文卡: 前提字段(工具权限/输入路径/模型任务)保留, 不推广至弱环境。"""

    paper_id: str
    attacker_capability: str = "unknown"
    input_path: str = "unknown"
    model_or_task: str = "unknown"
    tool_permissions: str = "unknown"
    author_validation_environment: str = "unknown"
    conclusion_text: str = ""
    limitations_text: str = ""
    cve_ids: tuple[str, ...] = field(default_factory=tuple)
    has_exploit_artifact: bool = False

    def cve_status(self) -> str:
        """无 CVE 材料正确标 not_applicable/not_found, 不编造标识。"""
        return "not_applicable" if not self.cve_ids else "available"


@dataclass(frozen=True)
class PolicyCard:
    """标准/政策卡: 机构/编号/版本/状态/时间/范围/条款; 原文与摘要分开。"""

    document_id: str
    issuer: str
    document_number: str
    version_label: str
    status: str
    published_at: str | None
    effective_at: str | None
    scope_text: str
    clause_reference: str
    original_text: str
    summary_text: str

    def time_fields_distinct(self) -> bool:
        return self.published_at != self.effective_at or (self.published_at is None) != (
            self.effective_at is None
        )


def describe_policy_applicability(card: PolicyCard) -> str:
    """范围不明: 给原文与局限, 不生成合规裁决/法律判断。"""
    if card.scope_text.strip() in ("", "unknown"):
        return (
            f"scope uncertain; quoting clause {card.clause_reference} verbatim:"
            f" {card.original_text}; "
            "applicability limitation recorded; no compliance ruling generated"
        )
    return f"scope stated by source: {card.scope_text}"


def verification_label(author_claimed: bool, team_reproduced: bool) -> str:
    """验证等级: 作者报告/团队复现/规则推断分立; 未复现不写系统验证通过。"""
    if team_reproduced and not author_claimed:
        raise KnowledgeCardError("team reproduction requires an author-reported claim")
    if team_reproduced:
        return "team_reproduced"
    if author_claimed:
        return "author_reported"
    return "unknown"


@dataclass(frozen=True)
class KnowledgeCardCitation:
    """程序核验过的原文子片段；定位通过不表示语义支持已经核验。"""

    document_id: UUID
    revision_id: UUID
    revision_number: int
    evidence_id: UUID
    block_id: UUID
    start_offset: int
    end_offset: int
    quote_text: str
    quote_sha256: str
    source_span_sha256: str
    locator_kind: str
    page_number: int | None
    json_pointer: str | None


@dataclass(frozen=True)
class KnowledgeCardValue:
    """模型值与来源引文分开保存；值可以是改写，不能当作原文或已确认事实。"""

    value: str
    citations: tuple[KnowledgeCardCitation, ...]
    origin: Literal["model_hypothesis"] = "model_hypothesis"


@dataclass(frozen=True)
class KnowledgeCardField:
    """缺失和冲突均保留；每个字段绑定固定原文版本，未知不生成默认值。"""

    field_name: str
    document_id: UUID
    revision_id: UUID
    revision_number: int
    proposed_values: tuple[KnowledgeCardValue, ...]
    status: Literal["unknown", "candidate", "conflict"]
    semantic_support: Literal["unverified"] = "unverified"


@dataclass(frozen=True)
class KnowledgeCardDraft:
    """内部待审候选，调用方后续持久化到既有PG账本；本对象不是业务存储。"""

    document_id: UUID
    revision_id: UUID
    revision_number: int
    document_kind: DocumentKindFilter
    fields: tuple[KnowledgeCardField, ...]
    content_coverage: ContentCoverage
    parse_status: str
    data_mode: DataMode
    limitations: tuple[str, ...]
    attempts: tuple[AttemptMetadata, ...]
    extractor_version: str = KNOWLEDGE_CARDS_VERSION
    confirmation_status: Literal["awaiting_review"] = "awaiting_review"
    verification_level: Literal["unknown"] = "unknown"
