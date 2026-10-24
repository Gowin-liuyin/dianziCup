"""CaseRunner 协议与基线 stub adapters (r21_plan §3.3)。

B2/B2b/B3 以 evaluation stub 执行器驱动既有 build_investigation_graph(graph.py:59),
B0 面向 HybridRetriever.retrieve(hybrid.py:360) 的调用规格; unit 层全部无 DB、
无网络、无真实模型调用。真实模型路径被费用上限=0 的门拦为 blocked_model_missing。
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from langgraph.checkpoint.memory import InMemorySaver

from ai_intel.evaluation.configs import ExperimentConfig, ablation_status
from ai_intel.evaluation.metrics import metrics_for_outcome
from ai_intel.evaluation.records import (
    FIXTURE_DISCLAIMER,
    RecordStatus,
    ResultRecord,
    beijing_timestamp,
    canonical_sha256,
)
from ai_intel.evaluation.registry import BaselineSpec
from ai_intel.infrastructure.models.clients import assert_runtime_allows_fixture_provider
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph import build_investigation_graph
from ai_intel.investigation.graph_contracts import Strategy, WorkflowState

FIXTURE_PROVIDER_NAME = "fixture"
DEFAULT_EVALUATION_ENVIRONMENT = "evaluation-fixture"
MODEL_CREDENTIAL_MISSING = "model_credential_missing"
MODEL_BUDGET_NOT_AUTHORIZED = "model_budget_not_authorized"

ERROR_CODE_BY_REGISTRATION = {
    "B1": "baseline_not_implemented",
    "B4_ref": "external_baseline_not_reproduced",
    "B5": "behavior_verification_pending_db",
}


@dataclass(frozen=True)
class CaseRunContext:
    """单次 run 的共享可比性上下文: 所有 case 的 hash/预算/模型绑定完全一致 (T47-C01)。"""

    run_id: str
    config: ExperimentConfig
    config_sha256: str
    data_sha256: str
    data_hash_verified: bool
    code_sha256: str
    code_dirty: bool
    case_count: int
    environment_name: str = DEFAULT_EVALUATION_ENVIRONMENT
    environ: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))


class CaseRunner(Protocol):
    """runner 协议: 每 case 产出一条 ResultRecord, 不共享可变状态。"""

    def run_case(self, case_id: str, context: CaseRunContext) -> ResultRecord: ...


def resolve_model_gate(config: ExperimentConfig, environ: Mapping[str, str]) -> str | None:
    """fixture provider 直接放行 (仍受 production 禁令约束); 真实 provider 一律阻塞。

    本批 cost_cap 恒 0 且无预算授权, 因此即使凭据环境变量存在,
    真实模型调用仍以 model_budget_not_authorized 阻塞, 不产生任何 API 费用。
    """
    model_ref = config.model_configuration
    if model_ref.provider == FIXTURE_PROVIDER_NAME:
        return None
    credential_env_var = model_ref.credential_env_var
    if not credential_env_var or credential_env_var not in environ:
        return MODEL_CREDENTIAL_MISSING
    return MODEL_BUDGET_NOT_AUTHORIZED


def build_result_record(
    context: CaseRunContext,
    case_id: str,
    *,
    status: RecordStatus,
    error_code: str | None,
    tool_calls: int,
    model_calls: int,
    latency_ms: float,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> ResultRecord:
    """统一记录构造: 指标与状态同源, fixture-scale 标注为固定字段, 不可绕过。"""
    return ResultRecord(
        run_id=context.run_id,
        case_id=case_id,
        baseline_id=context.config.baseline_id,
        strategy=context.config.strategy,
        ablation_flags=context.config.ablation.model_dump(),
        ablation_status=ablation_status(context.config.ablation),
        data_sha256=context.data_sha256,
        data_hash_verified=context.data_hash_verified,
        config_sha256=context.config_sha256,
        code_sha256=context.code_sha256,
        code_dirty=context.code_dirty,
        model_provider=context.config.model_configuration.provider,
        model_name=context.config.model_configuration.approved_model,
        budget=context.config.budget.model_dump(),
        seed=context.config.seed,
        hardware_note=context.config.hardware_note,
        started_at=started_at or beijing_timestamp(),
        ended_at=ended_at or beijing_timestamp(),
        status=status,
        tool_calls=tool_calls,
        model_calls=model_calls,
        latency_ms=latency_ms,
        error_code=error_code,
        metrics=metrics_for_outcome(status, error_code, context.case_count),
        case_count=context.case_count,
        scale="fixture",
        data_mode="fixture",
        disclaimer=FIXTURE_DISCLAIMER,
    )


def evaluation_stub_execute_role(role: AgentRole, state: WorkflowState) -> WorkflowState:
    """evaluation 专用 stub 执行器: 只追加角色回执, 不调用模型/工具/DB。"""
    return {
        **state,
        "receipts": [
            *state["receipts"],
            {
                "role": role.value,
                "status": "succeeded",
                "reason_code": "evaluation_stub",
                "evidence_ids": [],
                "operation_keys": [],
                "output": {},
            },
        ],
        "status": "succeeded",
    }


class InvestigationGraphStubRunner:
    """B2/B2b/B3 stub adapter: 真实策略分组图 + stub 执行器, 驱动记录结构。"""

    def __init__(self, spec: BaselineSpec) -> None:
        self._spec = spec

    def run_case(self, case_id: str, context: CaseRunContext) -> ResultRecord:
        gate = resolve_model_gate(context.config, context.environ)
        if gate is not None:
            return build_result_record(
                context,
                case_id,
                status="blocked_model_missing",
                error_code=gate,
                tool_calls=0,
                model_calls=0,
                latency_ms=0.0,
            )
        assert_runtime_allows_fixture_provider(context.environment_name)
        if self._spec.strategy is None:
            raise ValueError("investigation graph baseline requires a strategy")
        strategy: Strategy = self._spec.strategy
        started_at = beijing_timestamp()
        clock_start = time.perf_counter()
        initial_state: WorkflowState = {
            "input_sha256": canonical_sha256(
                {"case_id": case_id, "baseline_id": self._spec.baseline_id}
            ),
            "receipts": [],
            "evidence": [],
            "draft": None,
            "verified": False,
            "candidate_action_id": None,
            "status": "running",
            "stop_reason": "",
        }
        graph = build_investigation_graph(strategy, evaluation_stub_execute_role, InMemorySaver())
        final_state = graph.invoke(
            initial_state, {"configurable": {"thread_id": f"{context.run_id}:{case_id}"}}
        )
        latency_ms = (time.perf_counter() - clock_start) * 1000.0
        completed = final_state["status"] == "succeeded"
        return build_result_record(
            context,
            case_id,
            status="completed" if completed else "partial",
            error_code=None if completed else "graph_stopped_early",
            tool_calls=0,
            model_calls=0,
            latency_ms=latency_ms,
            started_at=started_at,
        )


def evaluation_stub_retrieve(scope: object, query: object) -> tuple[object, ...]:
    """B0 检索 stub: 调用规格面向 HybridRetriever.retrieve(scope, query) (hybrid.py:360)。

    返回空命中且不做任何外部调用; 真实 B0 行为需 PG+语义模型, 属 integration 路线。
    """
    return ()


class RetrievalStubRunner:
    """B0 stub adapter: 记录检索调用规格, unit 层以空命中 stub 产出记录结构。"""

    def __init__(self, spec: BaselineSpec) -> None:
        self._spec = spec

    def run_case(self, case_id: str, context: CaseRunContext) -> ResultRecord:
        gate = resolve_model_gate(context.config, context.environ)
        if gate is not None:
            return build_result_record(
                context,
                case_id,
                status="blocked_model_missing",
                error_code=gate,
                tool_calls=0,
                model_calls=0,
                latency_ms=0.0,
            )
        assert_runtime_allows_fixture_provider(context.environment_name)
        started_at = beijing_timestamp()
        clock_start = time.perf_counter()
        evaluation_stub_retrieve(scope=object(), query=object())
        latency_ms = (time.perf_counter() - clock_start) * 1000.0
        return build_result_record(
            context,
            case_id,
            status=self._spec.record_status,
            error_code=None,
            tool_calls=0,
            model_calls=0,
            latency_ms=latency_ms,
            started_at=started_at,
        )


class RegistrationOnlyRunner:
    """B1/B4_ref/B5: 只产出如实登记记录, 不产出任何指标值。"""

    def __init__(self, spec: BaselineSpec) -> None:
        self._spec = spec

    def run_case(self, case_id: str, context: CaseRunContext) -> ResultRecord:
        started_at = beijing_timestamp()
        clock_start = time.perf_counter()
        latency_ms = (time.perf_counter() - clock_start) * 1000.0
        return build_result_record(
            context,
            case_id,
            status=self._spec.record_status,
            error_code=ERROR_CODE_BY_REGISTRATION.get(self._spec.baseline_id),
            tool_calls=0,
            model_calls=0,
            latency_ms=latency_ms,
            started_at=started_at,
        )


def build_runner(spec: BaselineSpec) -> CaseRunner:
    """按注册条目的 runner 种类构造 runner; 未知种类显式失败。"""
    if spec.runner_kind == "investigation_graph_stub":
        return InvestigationGraphStubRunner(spec)
    if spec.runner_kind == "retrieval_stub":
        return RetrievalStubRunner(spec)
    if spec.runner_kind == "registration_only":
        return RegistrationOnlyRunner(spec)
    raise ValueError(f"unknown runner kind: {spec.runner_kind}")


__all__ = [
    "CaseRunContext",
    "CaseRunner",
    "InvestigationGraphStubRunner",
    "RegistrationOnlyRunner",
    "RetrievalStubRunner",
    "build_result_record",
    "build_runner",
    "resolve_model_gate",
]
