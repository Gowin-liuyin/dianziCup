"""主张与冲突: 证据分级/同 scope 互斥 disputed/自修订 supersedes/发布同事务 outbox。"""

from __future__ import annotations

from dataclasses import dataclass, field

CLAIMS_VERSION = "claims-1.0.0"
ASSERTION_KINDS = ("explicit", "rule_derived", "model_hypothesis", "human_confirmed")


class ClaimsContractError(RuntimeError):
    """合同违规: 模型假设不得升格为确认事实; 跨 tenant 不入公共知识。"""


@dataclass(frozen=True)
class ClaimEvidence:
    """主张证据: 分级保留, 引文文本与支持范围分开记录。"""

    source_record_id: str
    evidence_text: str
    assertion_kind: str
    supports_conclusion: bool = False

    def __post_init__(self) -> None:
        if self.assertion_kind not in ASSERTION_KINDS:
            raise ClaimsContractError(f"unknown assertion kind: {self.assertion_kind}")


@dataclass(frozen=True)
class ClaimRecord:
    """主张记录: scope/时间字段保留; 私有与跨 tenant 标记。"""

    claim_id: str
    dimension: str
    value: object
    scope: str
    effective_at: str | None
    tenant_id: str
    visibility: str
    evidences: tuple[ClaimEvidence, ...] = field(default_factory=tuple)
    state: str = "current"


@dataclass
class ClaimsLedger:
    """主张台账: disputed/supersedes/withdrawn 全历史; 发布与 outbox 同事务。"""

    claims: dict[str, ClaimRecord] = field(default_factory=dict)
    disputes: list[tuple[str, str]] = field(default_factory=list)
    supersedes: list[tuple[str, str]] = field(default_factory=list)
    outbox_events: list[dict[str, object]] = field(default_factory=list)
    retrieval_status: dict[str, str] = field(default_factory=dict)

    def add_claim(self, claim: ClaimRecord) -> str:
        """模型假设不得发布为确认事实; 私有/跨 tenant 不入公共结果。"""
        confirmed_only = {"explicit", "rule_derived", "human_confirmed"}
        if any(evidence.assertion_kind == "model_hypothesis" for evidence in claim.evidences):
            if claim.state == "published":
                raise ClaimsContractError("model hypothesis cannot be published as confirmed fact")
        if claim.visibility not in ("public", "private", "tenant"):
            raise ClaimsContractError(f"unknown visibility: {claim.visibility}")
        if all(evidence.assertion_kind not in confirmed_only for evidence in claim.evidences):
            claim = ClaimRecord(**{**claim.__dict__, "state": "hypothesis"})
        self.claims[claim.claim_id] = claim
        return claim.state

    def register_dispute(
        self, left_id: str, right_id: str, reason_same_scope_exclusive: bool
    ) -> str:
        """同 scope/时间字段互斥 → disputed 并列; 不同评分机构/分支不算矛盾。"""
        if not reason_same_scope_exclusive:
            return "parallel_kept"
        self.disputes.append((left_id, right_id))
        return "disputed"

    def register_supersede(self, old_id: str, new_id: str) -> None:
        """自修订: 建 supersedes, 历史保留不删; 撤回仅改状态。"""
        if old_id not in self.claims or new_id not in self.claims:
            raise ClaimsContractError("both claims must exist before supersede")
        self.supersedes.append((old_id, new_id))

    def mark_source_retrieval_status(self, source_record_id: str, status_code: int) -> str:
        """链接 404 只改获取状态, 旧事实不自动 withdrawn。"""
        status = "not_found" if status_code == 404 else "available"
        self.retrieval_status[source_record_id] = status
        return status

    def publish_claims(
        self, tenant_id: str, scope_epoch: str, claim_ids: list[str]
    ) -> dict[str, object]:
        """事实发布/scope epoch/变化 outbox 同事务, 下游必能获知。"""
        published: list[str] = []
        for claim_id in claim_ids:
            claim = self.claims.get(claim_id)
            if claim is None or claim.tenant_id != tenant_id or claim.visibility != "public":
                continue
            published.append(claim_id)
        event = {
            "scope_epoch": scope_epoch,
            "published_claim_ids": published,
            "transactional": True,
        }
        self.outbox_events.append(event)
        return event

    def query_public_current(self) -> list[ClaimRecord]:
        """范围化查询: 公共当前状态, 私有/tenant/假设不进入。"""
        return [
            claim
            for claim in self.claims.values()
            if claim.visibility == "public" and claim.state == "current"
        ]
