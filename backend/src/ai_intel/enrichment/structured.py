"""结构化富化: 字段级幂等; 分歧并列记录; 失败不覆盖可信事实; 私有维度范围隔离。"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_intel.enrichment.dimensions import dimension_status_for_kind


class EnrichmentConflictError(RuntimeError):
    """多来源分歧: 并列记录, 不静默取最高分/最新值。"""


@dataclass(frozen=True)
class Claim:
    """Claim: 带 EvidenceSpan/JSON 路径, 保留来源与评分机构。"""

    dimension: str
    value: object
    source_record_id: str
    json_path: str
    evidence_span_text: str = ""
    scoring_authority: str = ""
    scope: str = "public"


@dataclass
class EnrichmentLedger:
    """富化台账: 字段级幂等, 部分成功可保存, 失败不覆盖先前事实。"""

    facts: dict[str, list[Claim]] = field(default_factory=dict)
    processed_input_fingerprints: set[str] = field(default_factory=set)
    job_results: list[dict[str, object]] = field(default_factory=list)

    def apply_claims(self, input_fingerprint: str, claims: list[Claim], document_kind: str) -> str:
        """幂等应用: 相同输入不生成重复事实; 分歧并列; 私有范围标记随事实保留。"""
        if input_fingerprint in self.processed_input_fingerprints:
            return "idempotent_skip"
        self.processed_input_fingerprints.add(input_fingerprint)
        for claim in claims:
            status = dimension_status_for_kind(claim.dimension, document_kind)
            if status == "not_applicable":
                continue
            existing = self.facts.setdefault(claim.dimension, [])
            duplicate = any(
                prior.value == claim.value and prior.source_record_id == claim.source_record_id
                for prior in existing
            )
            if duplicate:
                continue
            existing.append(claim)
        return "applied"

    def record_job_result(
        self, job_id: str, succeeded_dimensions: list[str], failed_dimensions: list[str]
    ) -> str:
        """部分成功可保存; 失败维度不覆盖先前可信事实, 仅登记 failed。"""
        outcome = "complete" if not failed_dimensions else "partial"
        self.job_results.append(
            {
                "job_id": job_id,
                "outcome": outcome,
                "succeeded": list(succeeded_dimensions),
                "failed": list(failed_dimensions),
            }
        )
        return outcome

    def public_event_summary(self) -> dict[str, object]:
        """公共事件返回: 私有资产维度不进入公共摘要。"""
        public_facts = {
            dimension: [claim.value for claim in claims if claim.scope == "public"]
            for dimension, claims in self.facts.items()
        }
        return {key: values for key, values in public_facts.items() if values}

    def private_dimensions_present(self) -> list[str]:
        """私有资产维度存在性检查(用于隔离断言)。"""
        return [
            dimension
            for dimension, claims in self.facts.items()
            if any(c.scope == "private" for c in claims)
        ]
