"""ResultRecord 与 hash 规则: 每 case x 每 baseline 一条统一记录 (T47 实施第 1 步)。

可比性字段 (data/config/code sha256、seed、budget、模型非密标识) 是 T47-C01
"同任务资源可比" 的记录面; 指标一律 {numerator, denominator, status} 三元组,
0 gold 时 accuracy 恒 not_computable_no_gold, 不产出准确率数字。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FIXTURE_DISCLAIMER = "fixture-scale 非正式指标"
FIXTURE_SCALE = Literal["fixture"]
FIXTURE_DATA_MODE = Literal["fixture"]

RecordStatus = Literal[
    "completed",
    "partial",
    "failed",
    "blocked_model_missing",
    "blocked_baseline_missing",
    "not_applicable",
    "not_reproduced",
    "declared_behavior_pending_db",
]

BEIJING_FIXED_OFFSET = timezone(timedelta(hours=8))
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_GIT_HEAD_PATTERN = r"^[0-9a-f]{40}$"


class CodeFingerprintError(RuntimeError):
    """git HEAD 不可得: 记录面无法绑定代码版本, 不伪造指纹。"""


class CodeFingerprint(BaseModel):
    """代码版本绑定: HEAD sha256 与工作区 dirty 标志 (T47:33)。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code_sha256: str = Field(pattern=_GIT_HEAD_PATTERN)
    code_dirty: bool


class MetricTriple(BaseModel):
    """指标三元组: 分子/分母/状态, 每个指标显式可见分子分母 (T47:41)。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    numerator: int | None
    denominator: int = Field(ge=0)
    status: Literal[
        "not_computable_no_gold",
        "not_computable_model_missing",
        "computed_fixture_scale",
    ]


class ResultRecord(BaseModel):
    """每 case x 每 baseline 的统一记录, 字段全部显式 (r21_plan §3.2)。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=200)
    case_id: str = Field(min_length=1, max_length=200)
    baseline_id: str = Field(min_length=1, max_length=20)
    strategy: Literal["B2", "B2b", "B3"] | None
    ablation_flags: dict[str, bool]
    ablation_status: str = Field(min_length=1, max_length=200)
    data_sha256: str = Field(pattern=_SHA256_PATTERN)
    data_hash_verified: bool
    config_sha256: str = Field(pattern=_SHA256_PATTERN)
    code_sha256: str = Field(pattern=_GIT_HEAD_PATTERN)
    code_dirty: bool
    model_provider: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    budget: dict[str, int]
    seed: int | None
    hardware_note: str = Field(max_length=2000)
    started_at: str = Field(min_length=20, max_length=40)
    ended_at: str = Field(min_length=20, max_length=40)
    status: RecordStatus
    tool_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    error_code: str | None = None
    metrics: dict[str, MetricTriple]
    case_count: int = Field(ge=1)
    scale: FIXTURE_SCALE
    data_mode: FIXTURE_DATA_MODE
    disclaimer: str


def beijing_timestamp() -> str:
    """秒级 +08:00 时间戳, 与 prepare.py 的时间合同一致 (无微秒)。"""
    return datetime.now(BEIJING_FIXED_OFFSET).replace(microsecond=0).isoformat()


def canonical_sha256(value: object) -> str:
    """语义规范化 hash: 排序键/紧凑分隔, 同一配置重排版后 hash 不变。"""
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    """文件字节级 hash, 用于 data_ref 期望 sha256 绑定。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_code_fingerprint(repo_root: Path) -> CodeFingerprint:
    """git rev-parse HEAD + dirty 标志; git 不可用时显式失败, 不伪造版本。"""
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise CodeFingerprintError("code_fingerprint_unavailable") from error
    if len(head) != 40:
        raise CodeFingerprintError("code_fingerprint_unavailable")
    return CodeFingerprint(code_sha256=head, code_dirty=bool(status.strip()))
