"""fixture-scale 强制 writer 与运行收据落盘 (r21_plan §3.5/§3.6)。

record/summary 缺 fixture 标注或 disclaimer 一律拒绝落盘 (固定错误码);
真实模型结果通道在本批恒拒绝 (费用上限=0), 防止 fixture 结果静默混写。
收据目录独占创建, 不覆盖既有 run。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_intel.evaluation.records import FIXTURE_DISCLAIMER, MetricTriple, ResultRecord

RECEIPT_HEADER_NOTE = "fixture-scale，非正式指标，不是官方评分材料"
RATE_METRIC_PAIR = ("completion_rate", "unknown_rate")


class ReceiptWriteError(RuntimeError):
    """收据合同失败, 携带固定错误码。"""


class LiveResultsForbidden(RuntimeError):
    """live 结果通道拒绝; 本批恒拒绝, 错误码固定。"""


class RunSummary(BaseModel):
    """run 级收据: 命令/cwd/起止/退出码/case 计数/状态分布/指标/覆盖矩阵 (对齐 06:68)。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=200)
    baseline_id: str = Field(min_length=1, max_length=20)
    strategy: str | None
    title: str = Field(min_length=1, max_length=300)
    config_sha256: str
    data_sha256: str
    data_ref_path: str
    data_hash_verified: bool
    code_sha256: str
    code_dirty: bool
    model_provider: str
    model_name: str
    budget: dict[str, int]
    seed: int | None
    hardware_note: str
    ablation_flags: dict[str, bool]
    ablation_status: str
    command: str
    cwd: str
    started_at: str
    ended_at: str
    exit_code: int
    case_count: int = Field(ge=1)
    data_kind_counts: dict[str, int]
    status_counts: dict[str, int]
    metrics: dict[str, MetricTriple]
    coverage: tuple[dict[str, str], ...]
    scale: Literal["fixture"]
    data_mode: Literal["fixture"]
    disclaimer: str
    cross_baseline_comparison: Literal["not_generated"] = "not_generated"
    header_note: str = RECEIPT_HEADER_NOTE


def validate_fixture_scale_record(record: ResultRecord) -> None:
    """三条固定标注缺一即拒: scale=fixture / data_mode=fixture / 固定 disclaimer。"""
    annotated = (
        record.scale == "fixture"
        and record.data_mode == "fixture"
        and record.disclaimer == FIXTURE_DISCLAIMER
    )
    if not annotated:
        raise ReceiptWriteError("fixture_scale_annotation_missing")


def validate_run_summary(summary: RunSummary) -> None:
    """summary 标注合同 + 指标成对合同 (T47-C05: completion/unknown 必须同时在场)。"""
    annotated = (
        summary.scale == "fixture"
        and summary.data_mode == "fixture"
        and summary.disclaimer == FIXTURE_DISCLAIMER
        and summary.header_note == RECEIPT_HEADER_NOTE
    )
    if not annotated:
        raise ReceiptWriteError("fixture_scale_annotation_missing")
    if summary.metrics and not set(RATE_METRIC_PAIR) <= set(summary.metrics):
        raise ReceiptWriteError("incomplete_metric_pair")


def write_run_receipt(
    summary: RunSummary, records: tuple[ResultRecord, ...], receipt_dir: Path
) -> Path:
    """独占创建 eval_<run_id>/ 收据目录: records.jsonl 每记录一行 + run_summary.json。"""
    validate_run_summary(summary)
    if len(records) != summary.case_count:
        raise ReceiptWriteError("record_case_count_mismatch")
    for record in records:
        validate_fixture_scale_record(record)
    if receipt_dir.exists():
        raise ReceiptWriteError("run_receipt_directory_exists")
    receipt_dir.mkdir(parents=True)
    records_path = receipt_dir / "records.jsonl"
    with records_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(record.model_dump_json())
            handle.write("\n")
    summary_path = receipt_dir / "run_summary.json"
    summary_path.write_text(
        json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return receipt_dir


def write_live_results_receipt(payload: Mapping[str, object], receipt_dir: Path) -> None:
    """真实模型结果通道: 本批恒拒绝。

    通道形状保留 (scale=live + 显式授权门), 但费用上限=0 且无预算授权,
    任何调用都以 live_results_forbidden_budget_zero 拒绝, 不落盘、不静默混写。
    """
    raise LiveResultsForbidden("live_results_forbidden_budget_zero")
