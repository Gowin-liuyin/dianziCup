import { describe, expect, it } from "vitest";
import { ApiProblem } from "../../api/client";
import { parseGraphSnapshot } from "./graph-contracts";
import { graphFixture, fixtureGraphId } from "./graph.fixture";

describe("R17 frozen graph schema boundary", () => {
  it("preserves all six node/relation kinds and provenance", () => {
    const result = parseGraphSnapshot(graphFixture());
    expect(result.nodes.map((node) => node.kind)).toEqual(["event", "source_revision", "component_version", "atlas", "paper", "remediation"]);
    expect(result.edges.map((edge) => edge.relation_type)).toEqual(["same_event", "affects_component_version", "mapped_atlas", "related_paper", "remediated_by", "component_version_vulnerability"]);
    expect(result.edges[0]?.evidence_span_ids).toEqual([fixtureGraphId(30)]);
  });
  it("retains unknown and truncated without inventing negative facts", () => {
    expect(parseGraphSnapshot({ ...graphFixture(), truncated: true, gaps: [{ relation_type: "related_paper", status: "unknown", reason: "truncated" }] }).gaps[0]?.status).toBe("unknown");
  });
  it("accepts the exact approved 1.1 metadata without changing the schema", () => {
    const result = parseGraphSnapshot(graphFixture("r10-graph-1.1.0"));
    expect(result.schema_version).toBe(1); expect(result.rule_version).toBe("r10-graph-1.1.0"); expect(result.edges.every((edge) => edge.rule_or_model_version === "r10-graph-1.1.0")).toBe(true);
  });
  it.each([
    ["extra field", { ...graphFixture(), source_uri: "javascript:alert(1)" }],
    ["schema", { ...graphFixture(), schema_version: 2 }],
    ["fraction version", { ...graphFixture(), business_version: 1.5 }],
    ["missing root", { ...graphFixture(), event_id: fixtureGraphId(999) }],
    ["node limit", { ...graphFixture(), nodes: Array.from({ length: 201 }, (_, index) => ({ ...graphFixture().nodes[0], id: fixtureGraphId(index + 1) })) }],
    ["edge limit", { ...graphFixture(), edges: Array.from({ length: 401 }, (_, index) => ({ ...graphFixture().edges[0], id: fixtureGraphId(index + 1000) })) }],
    ["duplicate node", { ...graphFixture(), nodes: [...graphFixture().nodes, graphFixture().nodes[0]] }],
    ["dangling edge", { ...graphFixture(), edges: [{ ...graphFixture().edges[0], object_id: fixtureGraphId(999) }] }],
    ["candidate edge", { ...graphFixture(), edges: [{ ...graphFixture().edges[0], status: "candidate" }] }],
    ["no evidence", { ...graphFixture(), edges: [{ ...graphFixture().edges[0], evidence_span_ids: [] }] }],
    ["unsafe id", { ...graphFixture(), edges: [{ ...graphFixture().edges[0], evidence_span_ids: ["javascript:alert(1)"] }] }],
    ["wide scope", { ...graphFixture(), nodes: graphFixture().nodes.map((node) => ({ ...node, scope: { visibility: "tenant", tenant_id: "private" } })) }],
    ["scope mismatch", { ...graphFixture(), nodes: [{ ...graphFixture().nodes[0], scope: { visibility: "public", tenant_id: "private" } }, ...graphFixture().nodes.slice(1)] }],
    ["future gap", { ...graphFixture(), gaps: [{ relation_type: "related_paper", status: "unknown", reason: "invented" }] }],
    ["hash", { ...graphFixture(), content_sha256: "broken" }],
    ["unknown rule", { ...graphFixture(), rule_version: "r10-graph-1.2.0" }],
    ["unknown edge rule", { ...graphFixture(), edges: [{ ...graphFixture().edges[0], rule_or_model_version: "r10-graph-1.2.0" }] }],
  ])("rejects %s rather than falling back to a demo", (_label, input) => {
    expect(() => parseGraphSnapshot(input)).toThrow(ApiProblem);
  });
});
