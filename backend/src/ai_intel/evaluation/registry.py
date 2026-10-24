"""基线注册表: B0–B5/B4_ref 的映射与如实登记 (r21_plan §2.2/§3.3)。

注册只登记映射与调用规格 (call_spec 指向既有生产入口 file:line), 不改生产模块;
B1 无实现、B4 未复现、B5 行为待 DB, 全部以 registration_status 如实表达,
不虚设 runner、不预填提升数字。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_intel.evaluation.configs import ConfigContractError, ExperimentConfig
from ai_intel.evaluation.records import RecordStatus

BaselineRegistrationStatus = Literal["available", "not_implemented", "not_reproduced", "partial"]
RunnerKind = Literal["investigation_graph_stub", "retrieval_stub", "registration_only"]


@dataclass(frozen=True)
class BaselineSpec:
    """单基线的注册条目: 状态、runner 种类、策略轴与生产调用规格。"""

    baseline_id: str
    title: str
    registration_status: BaselineRegistrationStatus
    runner_kind: RunnerKind
    strategy: Literal["B2", "B2b", "B3"] | None
    call_spec: str
    record_status: RecordStatus


BASELINE_REGISTRY: dict[str, BaselineSpec] = {
    "B0": BaselineSpec(
        baseline_id="B0",
        title="强检索基线: 同资料+精确检索+BM25+向量+重排 (06_testing_and_evaluation.md:105)",
        registration_status="available",
        runner_kind="retrieval_stub",
        strategy=None,
        call_spec=(
            "backend/src/ai_intel/retrieval/hybrid.py:347 (HybridRetriever), "
            ":360 (retrieve(scope, query) -> HybridSelection); 重排协议 retrieval/service.py:47"
        ),
        record_status="completed",
    ),
    "B1": BaselineSpec(
        baseline_id="B1",
        title=(
            "单 Agent 基线: 无实现, 如实登记 "
            "(全 backend/src 无 B1; graph_contracts.py:26 Strategy 无该值)"
        ),
        registration_status="not_implemented",
        runner_kind="registration_only",
        strategy=None,
        call_spec="unavailable: 单 Agent 基线无生产实现, 不扩 Strategy Literal, 不虚设 runner",
        record_status="blocked_baseline_missing",
    ),
    "B2": BaselineSpec(
        baseline_id="B2",
        title=(
            "固定四角色基线: planner+intelligence/asset/answer agent "
            "(06_testing_and_evaluation.md:109)"
        ),
        registration_status="available",
        runner_kind="investigation_graph_stub",
        strategy="B2",
        call_spec=(
            "backend/src/ai_intel/investigation/graph.py:59 "
            "(build_investigation_graph, B2_ROLE_MAP 分组)"
        ),
        record_status="completed",
    ),
    "B2b": BaselineSpec(
        baseline_id="B2b",
        title="固定九职责基线: 九角色逐段 (06_testing_and_evaluation.md:111, CR-R01)",
        registration_status="available",
        runner_kind="investigation_graph_stub",
        strategy="B2b",
        call_spec=(
            "backend/src/ai_intel/investigation/graph.py:59 "
            "(build_investigation_graph, 逐角色分支 :69)"
        ),
        record_status="completed",
    ),
    "B3": BaselineSpec(
        baseline_id="B3",
        title="缺口调度基线: 同图只换 planner 候选选择 (06_testing_and_evaluation.md:113)",
        registration_status="available",
        runner_kind="investigation_graph_stub",
        strategy="B3",
        call_spec=(
            "backend/src/ai_intel/investigation/graph.py:59 (build_investigation_graph); "
            "graph.py:64: B3 与 B2b 共享图结构, 差异在生产 planner 执行器, stub 层不含该差异"
        ),
        record_status="completed",
    ),
    "B4_ref": BaselineSpec(
        baseline_id="B4_ref",
        title="外部公开实现参照: 未复现, 如实登记 (T47:39, 06_testing_and_evaluation.md:115)",
        registration_status="not_reproduced",
        runner_kind="registration_only",
        strategy=None,
        call_spec="unavailable: 无公开实现复现记录, 不能冒充官方实跑, 不预填提升百分比",
        record_status="not_reproduced",
    ),
    "B5": BaselineSpec(
        baseline_id="B5",
        title=(
            "全量重算基线: 同快照对全部评估重算的变化任务正确性参照 "
            "(06_testing_and_evaluation.md:117)"
        ),
        registration_status="partial",
        runner_kind="registration_only",
        strategy=None,
        call_spec=(
            "backend/src/ai_intel/revalidation/service.py:65 (RevalidationService), "
            ":88 (plan_change), :199 (reassess); 全量重算行为验证需真实 PG, 本批仅 config+记录"
        ),
        record_status="declared_behavior_pending_db",
    ),
}


def validate_config_against_registry(config: ExperimentConfig) -> BaselineSpec:
    """baseline 必须已注册且策略轴一致; 失败以固定错误码拒绝 (r21_plan §3.1)。"""
    spec = BASELINE_REGISTRY.get(config.baseline_id)
    if spec is None:
        known = ", ".join(sorted(BASELINE_REGISTRY))
        raise ConfigContractError("baseline_unknown", f"known ids: {known}")
    if spec.strategy != config.strategy:
        raise ConfigContractError(
            "strategy_mismatch",
            f"{config.baseline_id} expects strategy {spec.strategy!r}, got {config.strategy!r}",
        )
    return spec
