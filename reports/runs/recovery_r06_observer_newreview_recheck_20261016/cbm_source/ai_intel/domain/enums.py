"""领域公共枚举（docs/plan/03_data_contracts.md §2 合同实现）。

各状态语义严格分离: ClaimStatus 描述事实记录状态, ConditionValue 描述条件真假,
FreshnessStatus 描述时效, JobStatus 描述任务执行——不得合并为单一 status 字符串。
"""

from enum import StrEnum


class SourceCategory(StrEnum):
    """来源类别: 八类建设目标的分类依据。"""

    STRUCTURED_VULNERABILITY = "structured_vulnerability"
    VENDOR_ADVISORY = "vendor_advisory"
    SECURITY_COMMUNITY = "security_community"
    CODE_REPOSITORY = "code_repository"
    TECHNICAL_BLOG = "technical_blog"
    ACADEMIC_PAPER = "academic_paper"
    TECHNICAL_STANDARD = "technical_standard"
    POLICY_REGULATION = "policy_regulation"


class DocumentKind(StrEnum):
    """文档种类: 决定解析与证据定位策略。"""

    ADVISORY = "advisory"
    ARTICLE = "article"
    PAPER = "paper"
    REPOSITORY_RECORD = "repository_record"
    STANDARD = "standard"
    POLICY = "policy"
    ASSET_INVENTORY = "asset_inventory"


class ClaimOrigin(StrEnum):
    """论断来源等级: 区分原文明确、结构化来源、规则推导、模型假设与人工确认。"""

    SOURCE_EXPLICIT = "source_explicit"
    STRUCTURED_SOURCE = "structured_source"
    RULE_DERIVED = "rule_derived"
    MODEL_HYPOTHESIS = "model_hypothesis"
    HUMAN_CONFIRMED = "human_confirmed"


class ClaimStatus(StrEnum):
    """事实记录状态; 不与条件真假混用。"""

    SUPPORTED = "supported"
    DISPUTED = "disputed"
    UNVERIFIED = "unverified"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class ConditionValue(StrEnum):
    """条件判定值: unknown 与 false 语义不同, 序列化后仍须可区分。"""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class DimensionStatus(StrEnum):
    """富化维度状态: not_applicable 不计缺失, not_found 计召回损失。"""

    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    NOT_APPLICABLE = "not_applicable"
    CONFLICT = "conflict"
    BLOCKED = "blocked"
    FAILED = "failed"
    PENDING = "pending"


class FreshnessStatus(StrEnum):
    """时效状态: 缺观察时间不得填 current。"""

    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"


class RuleStatus(StrEnum):
    """条件规则生命周期。"""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PUBLISHED = "published"
    RETIRED = "retired"


class AssessmentStatus(StrEnum):
    """研判结论: 四态表达, 不等价于已入侵或绝对安全。"""

    SUPPORTED_APPLICABILITY = "supported_applicability"
    EXCLUDED_WITH_EVIDENCE = "excluded_with_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class ToolStatus(StrEnum):
    """工具调用结果状态: denied 与 failed 语义不同。"""

    SUCCEEDED = "succeeded"
    NO_RESULT = "no_result"
    PARTIAL = "partial"
    FAILED = "failed"
    DENIED = "denied"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NOT_CONFIGURED = "not_configured"


class JobStatus(StrEnum):
    """任务执行状态: 与事实状态、条件判定严格分离。"""

    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PocStatus(StrEnum):
    """PoC 核查状态: static_reviewed 不等于 lab_verified。"""

    CANDIDATE_FOUND = "candidate_found"
    STATIC_REVIEWED = "static_reviewed"
    LAB_VERIFIED = "lab_verified"
    VERIFICATION_FAILED = "verification_failed"
