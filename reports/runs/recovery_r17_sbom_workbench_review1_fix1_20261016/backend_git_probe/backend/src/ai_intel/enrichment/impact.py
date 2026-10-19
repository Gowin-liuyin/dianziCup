"""评分与影响: CVSS 并列保留/缺失不臆造; KEV/EPSS 语义分立; 修复与影响概览可解释。"""

from __future__ import annotations

from dataclasses import dataclass

IMPACT_VERSION = "impact-1.0.0"


class ImpactContractError(RuntimeError):
    """评分/影响合同违规: 缺失不编造, 估计必须标记, 不合成入侵概率。"""


@dataclass(frozen=True)
class CvssScore:
    """CVSS 记录: 标准版本/向量/来源/评分方/时间; 缺失不臆造。"""

    standard_version: str
    vector: str
    base_score: str
    source: str
    scoring_authority: str
    scored_at: str
    is_system_estimate: bool = False


@dataclass(frozen=True)
class ExploitSignal:
    """KEV/EPSS 补充信号: 各自语义与时间保留, 不合成资产已被攻破概率。"""

    signal_kind: str
    value_text: str
    observed_at: str
    source: str

    def __post_init__(self) -> None:
        if self.signal_kind not in ("kev", "epss"):
            raise ImpactContractError(f"unknown exploit signal kind: {self.signal_kind}")


@dataclass(frozen=True)
class RemediationRecord:
    """修复/缓解: 官方措施与项目建议分立, 版本边界保留引用。"""

    remediation_kind: str
    description: str
    source_reference: str
    is_official: bool
    fixed_version: str | None = None


def combine_exploit_signals(signals: list[ExploitSignal]) -> dict[str, object]:
    """信号汇总: 并列显示来源与日期, 不宣称某资产已入侵/被攻破概率。"""
    return {
        "signals": [
            {
                "kind": signal.signal_kind,
                "value": signal.value_text,
                "observed_at": signal.observed_at,
                "source": signal.source,
            }
            for signal in signals
        ],
        "asset_compromise_claimed": False,
    }


def build_impact_overview(
    affected_asset_count: int | None,
    remediations: list[RemediationRecord],
    scoring_notes: list[str],
) -> dict[str, object]:
    """影响概览: 无真实资产数据不生成虚假受影响资产数量; 估计须标记。"""
    if affected_asset_count is None:
        asset_statement = "unknown; no real asset inventory available; count not fabricated"
    else:
        asset_statement = f"{affected_asset_count} assets matched by project rules"
    return {
        "asset_statement": asset_statement,
        "official_remediations": [r.description for r in remediations if r.is_official],
        "project_recommendations": [r.description for r in remediations if not r.is_official],
        "scoring_notes": list(scoring_notes),
    }
