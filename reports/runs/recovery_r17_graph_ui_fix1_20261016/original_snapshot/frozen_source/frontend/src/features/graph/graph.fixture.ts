import { graphRelationKinds, type GraphRuleVersion, type GraphSnapshot } from "./graph-contracts";

export function fixtureGraphId(index: number): string {
  return `71000000-0000-4000-8000-${String(index).padStart(12, "0")}`;
}

export const graphFixtureEventId = fixtureGraphId(1);
export const graphFixtureEvidenceId = fixtureGraphId(30);
export const graphFixtureRevisionId = fixtureGraphId(31);

/** 显式合成图，只供隔离合同/组件/浏览器测试导入。 */
export function graphFixture(ruleVersion: GraphRuleVersion = "r10-graph-1.0.0"): GraphSnapshot {
  const scope = { visibility: "public", tenant_id: null } as const;
  return {
    schema_version: 1, event_id: graphFixtureEventId, business_version: 3, rule_version: ruleVersion, truncated: false, content_sha256: "a".repeat(64), gaps: [],
    nodes: [
      { id: graphFixtureEventId, kind: "event", label: "合成 Fixture · AI 组件安全事件", scope },
      { id: fixtureGraphId(2), kind: "source_revision", label: "合成厂商公告 · 历史修订", scope },
      { id: fixtureGraphId(3), kind: "component_version", label: "Fixture · package 1.0 < 1.4（仅合成）", scope },
      { id: fixtureGraphId(4), kind: "atlas", label: "Fixture · AML.T0000", scope },
      { id: fixtureGraphId(5), kind: "paper", label: "Fixture · 条件与缓解机制研究", scope },
      { id: fixtureGraphId(6), kind: "remediation", label: "Fixture · 需要核查的修复版本 1.4", scope },
    ],
    edges: graphRelationKinds.map((relation, index) => ({
      id: fixtureGraphId(index + 10), relation_type: relation, subject_id: index === 5 ? fixtureGraphId(3) : graphFixtureEventId, object_id: index === 5 ? graphFixtureEventId : fixtureGraphId(index + 2), scope,
      source_revision_ids: [graphFixtureRevisionId], evidence_span_ids: [graphFixtureEvidenceId], supporting_claim_ids: [fixtureGraphId(32)], rule_or_model_version: ruleVersion, reason: "合成 Fixture：来自当前支持断言；不代表真实情报或受影响资产。", status: "supported",
    })),
  };
}
