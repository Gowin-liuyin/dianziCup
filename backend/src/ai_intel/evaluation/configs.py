"""实验配置 schema 校验与 R19 dev-set manifest 输入面 (r21_plan §3.1)。

配置用 pydantic extra=forbid 拒绝未知字段 (对齐 prepare.py 的拒绝式校验风格);
manifest 读取只做最小合同校验: 缺失/无效/hash 不符/holdout 混入显式 blocked,
不伪造 case 集合, 不触碰 benchmarks/ 目录。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_intel.evaluation.records import canonical_sha256, file_sha256


class ConfigContractError(ValueError):
    """配置或注册表合同失败, 携带固定错误码, 不静默修正。"""

    def __init__(self, error_code: str, detail: str = "") -> None:
        self.error_code = error_code
        message = error_code if not detail else f"{error_code}: {detail}"
        super().__init__(message)


class ManifestInputError(RuntimeError):
    """dev-set manifest 输入面失败; error_code 决定 CLI 退出码 (4 或 3)。"""

    def __init__(self, error_code: str, detail: str = "") -> None:
        self.error_code = error_code
        message = error_code if not detail else f"{error_code}: {detail}"
        super().__init__(message)


class AblationFlags(BaseModel):
    """五个声明式消融轴, default 全 on; 本批仅策略轴真实生效 (r21_plan §3.4)。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_retention: bool = True
    evidence_check: bool = True
    conflict_handling: bool = True
    scope_watch: bool = True
    dynamic_dispatch: bool = True


ABLATION_DEFAULT_ON_STATUS = "declared_default_on_matches_current_behavior"
ABLATION_NOT_WIRED_STATUS = "switch_declared_mechanism_not_wired"


def ablation_status(flags: AblationFlags) -> str:
    """default 全 on 与现行为一致; 任一置 off 即声明未接线, 不产出消融效果数字。"""
    if all(getattr(flags, field_name) for field_name in type(flags).model_fields):
        return ABLATION_DEFAULT_ON_STATUS
    return ABLATION_NOT_WIRED_STATUS


class DataRef(BaseModel):
    """dev-set manifest 相对路径 (仓库根) + 期望 sha256。

    expected_sha256=null 表示 manifest 尚未装配/未冻结: 只记录实测 hash 且
    data_hash_verified=false, 不虚构期望值。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_path: str = Field(min_length=1, max_length=500)
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ModelRef(BaseModel):
    """provider/approved_model 名与凭据环境变量名, 不存任何凭据值 (T47:33)。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=100)
    approved_model: str = Field(min_length=1, max_length=200)
    credential_env_var: str | None = Field(default=None, min_length=1, max_length=200)


class BudgetRef(BaseModel):
    """预算记录位; 本批费用上限恒 0, 任何真实模型调用被 blocked_model_missing 门拦下。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_model_calls: int = Field(ge=0, le=64)
    max_tool_calls: int = Field(ge=0, le=64)
    cost_cap: Literal[0] = 0


class CodeRef(BaseModel):
    """期望 HEAD; null 表示只记录实测 HEAD+dirty, 不作强校验 (分支仍在推进)。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_head: str | None = Field(default=None, min_length=7, max_length=40)


class ExperimentConfig(BaseModel):
    """单基线实验配置; data_mode 本批常量 fixture (r21_plan §3.1/§6.6)。"""

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, protected_namespaces=()
    )

    baseline_id: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=300)
    strategy: Literal["B2", "B2b", "B3"] | None = None
    ablation: AblationFlags = AblationFlags()
    data_mode: Literal["fixture"]
    data_ref: DataRef
    model_configuration: ModelRef = Field(alias="model_config")
    budget: BudgetRef
    seed: int | None = None
    hardware_note: str = Field(min_length=1, max_length=2000)
    code_ref: CodeRef = CodeRef()


def load_experiment_config(path: Path) -> ExperimentConfig:
    """读取并校验配置; schema 失败/未知字段/JSON 损坏都以 config_schema_invalid 拒绝。"""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigContractError("config_unreadable", str(error)) from error
    try:
        payload = json.loads(raw_text)
    except (ValueError, UnicodeDecodeError) as error:
        raise ConfigContractError("config_schema_invalid", "not valid JSON") from error
    if not isinstance(payload, dict):
        raise ConfigContractError("config_schema_invalid", "top level must be an object")
    try:
        return ExperimentConfig.model_validate(payload)
    except ValidationError as error:
        raise ConfigContractError("config_schema_invalid", str(error.errors()[:3])) from error


def config_digest(config: ExperimentConfig) -> str:
    """config_sha256: 语义规范化 hash, 重排版不改变可比性绑定。"""
    return canonical_sha256(config.model_dump(mode="json", by_alias=True))


@dataclass(frozen=True)
class DevSetCase:
    """dev-set 内单 case 的骨架可见字段; 0 gold, label 只是候选状态。"""

    case_id: str
    data_kind: str
    split: str
    label_status: str | None


@dataclass(frozen=True)
class DevSetManifest:
    """已校验的 dev-set manifest: case 列表 + hash 绑定, 无任何金标。"""

    path: Path
    dev_set_id: str
    cases: tuple[DevSetCase, ...]
    data_kind_counts: dict[str, int]
    sha256: str
    hash_verified: bool


def resolve_manifest_path(repo_root: Path, manifest_path: str) -> Path:
    """相对路径按仓库根解析; 绝对路径原样使用 (证据目录 fixture manifest 用)。"""
    candidate = Path(manifest_path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def load_dev_set_manifest(path: Path, expected_sha256: str | None) -> DevSetManifest:
    """读取 dev-set manifest 并做最小合同校验; 失败路径全部显式 blocked。

    缺文件 blocked_input_missing; 结构损坏 blocked_input_invalid; holdout 混入
    blocked_holdout_split_detected; 声明金标时 gold_scoring_not_implemented
    (骨架无金标评分路径); hash 不符 blocked_data_hash_mismatch。
    """
    if not path.is_file():
        raise ManifestInputError("blocked_input_missing", str(path))
    raw_bytes = path.read_bytes()
    actual_sha256 = file_sha256(path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ManifestInputError("blocked_data_hash_mismatch", str(path))
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise ManifestInputError("blocked_input_invalid", "not valid JSON") from error
    if not isinstance(payload, dict):
        raise ManifestInputError("blocked_input_invalid", "top level must be an object")
    summary_block = payload.get("summary")
    summary_fields: Mapping = summary_block if isinstance(summary_block, Mapping) else {}
    dev_set_id = payload.get("dev_set_id", summary_fields.get("dev_set_id"))
    raw_cases = payload.get("cases")
    if not isinstance(dev_set_id, str) or not dev_set_id.strip():
        raise ManifestInputError("blocked_input_invalid", "dev_set_id missing")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ManifestInputError("blocked_input_invalid", "cases must be a non-empty list")

    cases: list[DevSetCase] = []
    case_ids: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict) or not isinstance(raw_case.get("case_id"), str):
            raise ManifestInputError("blocked_input_invalid", "case_id missing or not a string")
        case_id = raw_case["case_id"]
        if not case_id.strip() or case_id in case_ids:
            raise ManifestInputError(
                "blocked_input_invalid", f"duplicate or empty case_id {case_id}"
            )
        case_ids.add(case_id)
        split = raw_case.get("split")
        if split == "holdout":
            raise ManifestInputError("blocked_holdout_split_detected", case_id)
        label_status = raw_case.get("label_status")
        cases.append(
            DevSetCase(
                case_id=case_id,
                data_kind=str(raw_case.get("data_kind", "unspecified")),
                split=str(split) if isinstance(split, str) else "unspecified",
                label_status=label_status if isinstance(label_status, str) else None,
            )
        )

    gold_block = payload.get("gold", summary_fields.get("gold"))
    if isinstance(gold_block, Mapping):
        declared_gold = gold_block.get("human_gold_count")
        if (
            isinstance(declared_gold, int)
            and not isinstance(declared_gold, bool)
            and declared_gold > 0
        ):
            raise ManifestInputError(
                "gold_scoring_not_implemented", "skeleton has no gold scoring path"
            )

    data_kind_counts: dict[str, int] = {}
    for case in cases:
        data_kind_counts[case.data_kind] = data_kind_counts.get(case.data_kind, 0) + 1

    return DevSetManifest(
        path=path,
        dev_set_id=dev_set_id,
        cases=tuple(cases),
        data_kind_counts=data_kind_counts,
        sha256=actual_sha256,
        hash_verified=expected_sha256 is not None,
    )
