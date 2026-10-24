"""复跑比较: 同 config/data/code 指纹下再执行, 输出字段级 diff (r21_plan §3.5)。

时延与时间戳属墙钟量, 不参与行为比较; 行为字段 (状态/调用数/错误码/指标/
消融声明) 逐字段比较。FixtureProvider 确定性保证 fixture 路线可复现;
真实模型路线本批不存在, 不做跨基线比较数字。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

RECORD_DIFF_FIELDS = (
    "status",
    "error_code",
    "tool_calls",
    "model_calls",
    "ablation_status",
    "ablation_flags",
    "metrics",
    "model_provider",
    "model_name",
    "budget",
    "seed",
)
SUMMARY_DIFF_FIELDS = (
    "baseline_id",
    "strategy",
    "case_count",
    "data_kind_counts",
    "status_counts",
    "metrics",
    "ablation_flags",
    "ablation_status",
    "exit_code",
)
TIMING_FIELDS_EXCLUDED = ("run_id", "started_at", "ended_at", "latency_ms")

MISSING_SENTINEL = "<missing>"


class ReceiptReadError(RuntimeError):
    """收据读取失败: 缺文件/坏 JSON, 显式失败。"""


@dataclass(frozen=True)
class ReplayDiff:
    """两次 run 的字段级比较结果; hash 门 + 行为字段差异。"""

    run_a: str
    run_b: str
    config_sha256_equal: bool
    data_sha256_equal: bool
    code_sha256_equal: bool
    summary_field_diffs: dict[str, list[object]]
    record_diffs: dict[str, dict[str, list[object]]]

    @property
    def behaviorally_identical(self) -> bool:
        return not self.summary_field_diffs and not self.record_diffs

    def to_json_dict(self) -> dict[str, object]:
        """JSON 可序列化视图 (tuple 转 list 由 dataclass 字段本就为 list)。"""
        return {
            "run_a": self.run_a,
            "run_b": self.run_b,
            "config_sha256_equal": self.config_sha256_equal,
            "data_sha256_equal": self.data_sha256_equal,
            "code_sha256_equal": self.code_sha256_equal,
            "behaviorally_identical": self.behaviorally_identical,
            "timing_fields_excluded": list(TIMING_FIELDS_EXCLUDED),
            "summary_field_diffs": self.summary_field_diffs,
            "record_diffs": self.record_diffs,
        }


def load_receipt(receipt_dir: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    """读取 run_summary.json + records.jsonl; 缺失/损坏显式失败。"""
    summary_path = receipt_dir / "run_summary.json"
    records_path = receipt_dir / "records.jsonl"
    if not summary_path.is_file() or not records_path.is_file():
        raise ReceiptReadError(f"receipt_incomplete: {receipt_dir}")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        records = [
            json.loads(line)
            for line in records_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (ValueError, UnicodeDecodeError) as error:
        raise ReceiptReadError(f"receipt_corrupt: {receipt_dir}") from error
    if not isinstance(summary, dict):
        raise ReceiptReadError(f"receipt_corrupt: {receipt_dir}")
    return summary, records


def _field_diffs(
    left: dict[str, object], right: dict[str, object], fields: tuple[str, ...]
) -> dict[str, list[object]]:
    diffs: dict[str, list[object]] = {}
    for field_name in fields:
        left_value = left.get(field_name, MISSING_SENTINEL)
        right_value = right.get(field_name, MISSING_SENTINEL)
        if left_value != right_value:
            diffs[field_name] = [left_value, right_value]
    return diffs


def compare_runs(receipt_dir_a: Path, receipt_dir_b: Path) -> ReplayDiff:
    """比较两次 run: hash 门相等性 + summary/record 行为字段级 diff。

    record 以 (baseline_id, case_id) 对齐; 单侧缺失以 MISSING_SENTINEL 呈现,
    不静默丢弃任何 case。
    """
    summary_a, records_a = load_receipt(receipt_dir_a)
    summary_b, records_b = load_receipt(receipt_dir_b)
    summary_diffs = _field_diffs(summary_a, summary_b, SUMMARY_DIFF_FIELDS)

    records_by_key_a = {
        (str(record.get("baseline_id")), str(record.get("case_id"))): record for record in records_a
    }
    records_by_key_b = {
        (str(record.get("baseline_id")), str(record.get("case_id"))): record for record in records_b
    }
    record_diffs: dict[str, dict[str, list[object]]] = {}
    for key in sorted(set(records_by_key_a) | set(records_by_key_b)):
        record_a = records_by_key_a.get(key, {})
        record_b = records_by_key_b.get(key, {})
        key_diffs = _field_diffs(record_a, record_b, RECORD_DIFF_FIELDS)
        if not record_a:
            key_diffs["presence"] = [MISSING_SENTINEL, "present"]
        elif not record_b:
            key_diffs["presence"] = ["present", MISSING_SENTINEL]
        if key_diffs:
            record_diffs[f"{key[0]}::{key[1]}"] = key_diffs

    return ReplayDiff(
        run_a=str(summary_a.get("run_id", receipt_dir_a.name)),
        run_b=str(summary_b.get("run_id", receipt_dir_b.name)),
        config_sha256_equal=summary_a.get("config_sha256") == summary_b.get("config_sha256"),
        data_sha256_equal=summary_a.get("data_sha256") == summary_b.get("data_sha256"),
        code_sha256_equal=summary_a.get("code_sha256") == summary_b.get("code_sha256"),
        summary_field_diffs=summary_diffs,
        record_diffs=record_diffs,
    )
