"""指标三元组构造与 run 级汇总 (r21_plan §3.2, T47-C02/C05/C06)。

dev-set 0 gold: accuracy/critical_claim_accuracy/evidence_support 恒
not_computable_no_gold, numerator=null, denominator=case_count, 不产出准确率数字。
completion/unknown/timeout 三率可算但必须带 computed_fixture_scale 标注,
denominator 固定 case_count, 失败/阻塞 case 不从分母消失 (AGENTS §6, T47-C05)。
"""

from __future__ import annotations

from ai_intel.evaluation.records import MetricTriple, ResultRecord

ACCURACY_METRIC_NAMES = ("accuracy", "critical_claim_accuracy", "evidence_support")
RATE_METRIC_NAMES = ("completion_rate", "unknown_rate", "timeout_rate")
MODEL_BLOCKED_STATUSES = frozenset({"blocked_model_missing"})
NO_METRIC_STATUSES = frozenset(
    {
        "blocked_baseline_missing",
        "not_reproduced",
        "declared_behavior_pending_db",
        "not_applicable",
    }
)
TIMEOUT_ERROR_CODE = "wall_clock_budget_exceeded"


def no_gold_metric(case_count: int) -> MetricTriple:
    """0 gold 的准确率类指标: 不可算, 分母保留全部 case, 不删分母。"""
    return MetricTriple(numerator=None, denominator=case_count, status="not_computable_no_gold")


def model_blocked_metric(case_count: int) -> MetricTriple:
    """模型未配置/无预算授权: 数值不可得, 如实标注而非伪 0。"""
    return MetricTriple(
        numerator=None, denominator=case_count, status="not_computable_model_missing"
    )


def computed_rate_metric(numerator: int, case_count: int) -> MetricTriple:
    """fixture 规模下真实可算的三率指标, 状态显式带 fixture 标注。"""
    return MetricTriple(
        numerator=numerator, denominator=case_count, status="computed_fixture_scale"
    )


def metrics_for_outcome(
    status: str, error_code: str | None, case_count: int
) -> dict[str, MetricTriple]:
    """按结果状态构造指标面: 登记/不适用基线不产出任何指标值 (T47-C02 诚实版)。

    在构造 frozen ResultRecord 之前调用, record.metrics 与状态永远同源。
    """
    if status in NO_METRIC_STATUSES:
        return {}
    if status in MODEL_BLOCKED_STATUSES:
        return {
            **{name: no_gold_metric(case_count) for name in ACCURACY_METRIC_NAMES},
            **{name: model_blocked_metric(case_count) for name in RATE_METRIC_NAMES},
        }
    completion = 1 if status == "completed" else 0
    unknown = 1 if status == "partial" else 0
    timeout = 1 if error_code == TIMEOUT_ERROR_CODE else 0
    return {
        **{name: no_gold_metric(case_count) for name in ACCURACY_METRIC_NAMES},
        "completion_rate": computed_rate_metric(completion, case_count),
        "unknown_rate": computed_rate_metric(unknown, case_count),
        "timeout_rate": computed_rate_metric(timeout, case_count),
    }


def metrics_for_record(record: ResultRecord) -> dict[str, MetricTriple]:
    """从已落成记录重算指标面, 供校验与复跑比较使用。"""
    return metrics_for_outcome(record.status, record.error_code, record.case_count)


def summarize_run_metrics(
    records: tuple[ResultRecord, ...], case_count: int
) -> dict[str, MetricTriple]:
    """run 级汇总: 有可算记录才产出三率, 否则如实为空, 无跨基线比较数字。

    任一记录模型阻塞则三率整体降级为 not_computable_model_missing;
    blocked 登记 (B1/B4_ref/B5) 的 run 汇总 metrics 为空字典。
    """
    metric_bearing = [record for record in records if record.metrics]
    if not metric_bearing:
        return {}
    if any(record.status in MODEL_BLOCKED_STATUSES for record in metric_bearing):
        return {
            **{name: no_gold_metric(case_count) for name in ACCURACY_METRIC_NAMES},
            **{name: model_blocked_metric(case_count) for name in RATE_METRIC_NAMES},
        }
    return {
        **{name: no_gold_metric(case_count) for name in ACCURACY_METRIC_NAMES},
        "completion_rate": computed_rate_metric(
            sum(1 for record in metric_bearing if record.status == "completed"), case_count
        ),
        "unknown_rate": computed_rate_metric(
            sum(1 for record in metric_bearing if record.status == "partial"), case_count
        ),
        "timeout_rate": computed_rate_metric(
            sum(1 for record in metric_bearing if record.error_code == TIMEOUT_ERROR_CODE),
            case_count,
        ),
    }


def coverage_matrix(records: tuple[ResultRecord, ...]) -> tuple[dict[str, str], ...]:
    """逐 case 覆盖矩阵: 每条记录 (含 not_applicable/blocked) 全部可见, 不删 case。"""
    return tuple(
        {
            "case_id": record.case_id,
            "baseline_id": record.baseline_id,
            "status": record.status,
        }
        for record in records
    )


SINGLE_METRIC_CLAIM_KEYS = frozenset({"improvement", "lift", "regression", "delta", "提升", "改进"})


class MetricsContractError(ValueError):
    """指标合同失败: 单指标提升声明被拒绝, 固定错误码。"""


def assert_metric_pair_present(summary: dict[str, object]) -> None:
    """任何含提升/退化声明的结构必须同时携带 completion_rate 与 unknown_rate (T47-C05)。"""
    if not SINGLE_METRIC_CLAIM_KEYS & set(summary):
        return
    metrics_block = summary.get("metrics")
    rate_keys = set(metrics_block) if isinstance(metrics_block, dict) else set(summary)
    present = {"completion_rate", "unknown_rate"} & rate_keys
    if present != {"completion_rate", "unknown_rate"}:
        raise MetricsContractError("single_metric_improvement_claim_rejected")
