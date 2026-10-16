"""W10 responsibilities share one frozen tool catalog across B2, B2b and B3."""

from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

from ai_intel.investigation.tool_contracts import ToolName

POLICY_VERSION = "r14-tool-gateway-1"


class AgentRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    COLLECTOR = "collector"
    TRIAGE = "triage"
    ENRICHER = "enricher"
    GRAPH_WRITER = "graph_writer"
    ASSESSOR = "assessor"
    QA = "qa"
    CRITIC = "critic"
    REPORTER = "reporter"


@dataclass(frozen=True)
class RoleCapability:
    responsibility: str
    allowed_tools: frozenset[ToolName]
    output_requirement: str
    unavailable_work: str


@dataclass(frozen=True)
class ToolSpec:
    name: ToolName
    fills: tuple[str, ...]
    input_schema: str | None
    output_schema: str | None
    configured: bool
    cache_policy: str
    permission: str
    timeout_seconds: float = 5.0


TOOL_SPECS = MappingProxyType(
    {
        ToolName.SEARCH_INTELLIGENCE: ToolSpec(
            ToolName.SEARCH_INTELLIGENCE,
            ("event", "mechanism"),
            None,
            None,
            False,
            "none",
            "read:public",
        ),
        ToolName.GET_ADVISORY: ToolSpec(
            ToolName.GET_ADVISORY,
            ("official_description", "remediation"),
            None,
            None,
            False,
            "none",
            "read:public",
        ),
        ToolName.GET_INVENTORY: ToolSpec(
            ToolName.GET_INVENTORY,
            ("asset_version", "configuration"),
            None,
            None,
            False,
            "none",
            "read:asset",
        ),
        ToolName.GET_PUBLIC_OBSERVATIONS: ToolSpec(
            ToolName.GET_PUBLIC_OBSERVATIONS,
            ("passive_observation",),
            None,
            None,
            False,
            "none",
            "read:asset",
        ),
        ToolName.COMPARE_VERSIONS: ToolSpec(
            ToolName.COMPARE_VERSIONS,
            ("version_ordering",),
            "CompareVersionsArguments",
            "VersionComparison",
            True,
            "pure_result",
            "read:public",
        ),
        ToolName.EVALUATE_RULE: ToolSpec(
            ToolName.EVALUATE_RULE,
            ("condition_evaluation",),
            None,
            None,
            False,
            "none",
            "read:asset",
        ),
        ToolName.SEARCH_PAPERS: ToolSpec(
            ToolName.SEARCH_PAPERS,
            ("paper_candidate", "mechanism"),
            None,
            None,
            False,
            "none",
            "read:public",
        ),
        ToolName.READ_EVIDENCE: ToolSpec(
            ToolName.READ_EVIDENCE,
            ("source_span", "current_support"),
            "ReadEvidenceArguments",
            "EvidenceResponse",
            True,
            "revalidate_every_read",
            "read:public",
        ),
        ToolName.FIND_CHANGES: ToolSpec(
            ToolName.FIND_CHANGES, ("historical_change",), None, None, False, "none", "read:public"
        ),
    }
)


READ_TOOL_SPECS = MappingProxyType(
    {
        name: replace(
            TOOL_SPECS[name],
            configured=True,
            input_schema=input_schema,
            output_schema=output_schema,
            cache_policy="revalidate_every_read",
        )
        for name, input_schema, output_schema in (
            (ToolName.GET_ADVISORY, "GetAdvisoryArguments", "EventDetailResponse"),
            (ToolName.GET_INVENTORY, "GetInventoryArguments", "AssetSnapshotResponse"),
            (ToolName.FIND_CHANGES, "FindChangesArguments", "ChangesPage"),
        )
    }
)


def _tools(*names: ToolName) -> frozenset[ToolName]:
    return frozenset(names)


ROLE_CAPABILITIES = MappingProxyType(
    {
        AgentRole.ORCHESTRATOR: RoleCapability(
            "可检查目标、预算与停止",
            _tools(),
            "目标、缺口、候选 action ID 与停止原因",
            "持久化编排和缺口选择尚未接线",
        ),
        AgentRole.COLLECTOR: RoleCapability(
            "受控来源采集",
            _tools(ToolName.GET_ADVISORY),
            "注册来源与不可变 revision 引用",
            "采集服务尚未接入本网关",
        ),
        AgentRole.TRIAGE: RoleCapability(
            "相关性与归并候选",
            _tools(ToolName.READ_EVIDENCE, ToolName.SEARCH_INTELLIGENCE),
            "候选事件与证据引用，线索不能写成确认",
            "相关性/归并模型节点尚未接线",
        ),
        AgentRole.ENRICHER: RoleCapability(
            "九维富化",
            _tools(ToolName.READ_EVIDENCE, ToolName.GET_ADVISORY, ToolName.SEARCH_PAPERS),
            "维度状态、字段来源与缺失原因",
            "九维富化服务尚未接入本网关",
        ),
        AgentRole.GRAPH_WRITER: RoleCapability(
            "仅投影已核验关系",
            _tools(ToolName.READ_EVIDENCE),
            "已核验关系 ID 与原文版本",
            "无图写工具，投影服务尚未接线",
        ),
        AgentRole.ASSESSOR: RoleCapability(
            "授权快照与条件执行",
            _tools(
                ToolName.GET_INVENTORY,
                ToolName.GET_PUBLIC_OBSERVATIONS,
                ToolName.COMPARE_VERSIONS,
                ToolName.EVALUATE_RULE,
                ToolName.READ_EVIDENCE,
            ),
            "固定快照、条件结果与未知项",
            "清单/FOFA/规则服务尚未接线；版本排序不是资产适用性",
        ),
        AgentRole.QA: RoleCapability(
            "组织检索与回答",
            _tools(ToolName.SEARCH_INTELLIGENCE, ToolName.READ_EVIDENCE, ToolName.SEARCH_PAPERS),
            "带支持引用的回答草案与范围限制",
            "真实检索/回答生成尚未接入本网关",
        ),
        AgentRole.CRITIC: RoleCapability(
            "核验关键论断及引用支持",
            _tools(ToolName.READ_EVIDENCE, ToolName.COMPARE_VERSIONS),
            "当前支持与未解决证据缺口",
            "引用存在不等于任意论断被支持",
        ),
        AgentRole.REPORTER: RoleCapability(
            "从有效事实生成报告",
            _tools(ToolName.READ_EVIDENCE, ToolName.FIND_CHANGES),
            "事实引用、时刻与限制",
            "报告生成/导出服务尚未接线",
        ),
    }
)

B2_ROLE_MAP = MappingProxyType(
    {
        "planner": (AgentRole.ORCHESTRATOR,),
        "intelligence_agent": (
            AgentRole.COLLECTOR,
            AgentRole.TRIAGE,
            AgentRole.ENRICHER,
            AgentRole.GRAPH_WRITER,
        ),
        "asset_agent": (AgentRole.ASSESSOR,),
        "answer_agent": (AgentRole.QA, AgentRole.CRITIC, AgentRole.REPORTER),
    }
)


def available_tools(
    strategy: str, configured_tools: frozenset[ToolName] | None = None
) -> frozenset[ToolName]:
    """Strategies change scheduling only; none can add a configured tool or permission."""
    if strategy not in {"B2", "B2b", "B3"}:
        raise ValueError("unknown investigation strategy")
    defaults = frozenset(name for name, spec in TOOL_SPECS.items() if spec.configured)
    if configured_tools is None:
        return defaults
    return configured_tools & (defaults | frozenset(READ_TOOL_SPECS))
