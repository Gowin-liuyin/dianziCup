import { ApiProblem } from "../../api/client";

export const graphNodeKinds = ["event", "source_revision", "component_version", "atlas", "paper", "remediation"] as const;
export const graphRelationKinds = ["same_event", "affects_component_version", "mapped_atlas", "related_paper", "remediated_by", "component_version_vulnerability"] as const;
export type GraphNodeKind = typeof graphNodeKinds[number];
export type GraphRelationKind = typeof graphRelationKinds[number];
export type GraphRuleVersion = "r10-graph-1.0.0" | "r10-graph-1.1.0" | "r10-graph-1.2.0";
export interface GraphScope { visibility: "public" | "tenant"; tenant_id: string | null }
export interface GraphNode { id: string; kind: GraphNodeKind; label: string; scope: GraphScope }
export interface GraphEdge {
  id: string; relation_type: GraphRelationKind; subject_id: string; object_id: string; scope: GraphScope;
  source_revision_ids: string[]; evidence_span_ids: string[]; supporting_claim_ids: string[];
  rule_or_model_version: GraphRuleVersion; reason: string; status: "supported";
}
export interface GraphGap { relation_type: GraphRelationKind; status: "unknown"; reason: "no_current_supported_relation" | "truncated" }
export interface GraphSnapshot {
  schema_version: 1; event_id: string; business_version: number; rule_version: GraphRuleVersion;
  nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean; gaps: GraphGap[]; content_sha256: string;
}

function invalidGraph(): never { throw new ApiProblem(502, "invalid_response", true); }
function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalidGraph();
  const fields = Object.keys(value);
  if (fields.length !== keys.length || !fields.every((key) => keys.includes(key))) return invalidGraph();
  return Object.fromEntries(Object.entries(value));
}
function text(value: unknown, maximum: number): string {
  if (typeof value !== "string" || !value.trim() || [...value].length > maximum) return invalidGraph();
  return value;
}
export function graphIdentifier(value: unknown): string {
  const id = text(value, 36);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) return invalidGraph();
  return id.toLowerCase();
}
function enumeration<T extends string>(value: unknown, allowed: readonly T[]): T {
  const selected = allowed.find((item) => item === value);
  return selected === undefined ? invalidGraph() : selected;
}
function list<T>(value: unknown, parse: (item: unknown) => T, minimum: number, maximum: number): T[] {
  if (!Array.isArray(value) || value.length < minimum || value.length > maximum) return invalidGraph();
  return value.map((item: unknown) => parse(item));
}
function identifiers(value: unknown): string[] {
  const result = list(value, graphIdentifier, 1, 2000);
  if (new Set(result).size !== result.length) return invalidGraph();
  return result;
}
function scope(value: unknown): GraphScope {
  const fields = record(value, ["visibility", "tenant_id"]);
  const visibility = enumeration(fields.visibility, ["public", "tenant"]);
  const tenant = fields.tenant_id === null ? null : text(fields.tenant_id, 2500);
  if ((visibility === "public" && tenant !== null) || (visibility === "tenant" && tenant === null)) return invalidGraph();
  return { visibility, tenant_id: tenant };
}
function ruleVersion(value: unknown): GraphRuleVersion {
  return enumeration(value, ["r10-graph-1.0.0", "r10-graph-1.1.0", "r10-graph-1.2.0"]);
}
function node(value: unknown): GraphNode {
  const fields = record(value, ["id", "kind", "label", "scope"]);
  return { id: graphIdentifier(fields.id), kind: enumeration(fields.kind, graphNodeKinds), label: text(fields.label, 2500), scope: scope(fields.scope) };
}
function edge(value: unknown): GraphEdge {
  const fields = record(value, ["id", "relation_type", "subject_id", "object_id", "scope", "source_revision_ids", "evidence_span_ids", "supporting_claim_ids", "rule_or_model_version", "reason", "status"]);
  return { id: graphIdentifier(fields.id), relation_type: enumeration(fields.relation_type, graphRelationKinds), subject_id: graphIdentifier(fields.subject_id), object_id: graphIdentifier(fields.object_id), scope: scope(fields.scope), source_revision_ids: identifiers(fields.source_revision_ids), evidence_span_ids: identifiers(fields.evidence_span_ids), supporting_claim_ids: identifiers(fields.supporting_claim_ids), rule_or_model_version: ruleVersion(fields.rule_or_model_version), reason: text(fields.reason, 2500), status: enumeration(fields.status, ["supported"]) };
}
function gap(value: unknown): GraphGap {
  const fields = record(value, ["relation_type", "status", "reason"]);
  return { relation_type: enumeration(fields.relation_type, graphRelationKinds), status: enumeration(fields.status, ["unknown"]), reason: enumeration(fields.reason, ["no_current_supported_relation", "truncated"]) };
}

/** 拒绝不匹配协议、悬空或重复标识；不从缺口推断业务否定，也不自行验证内容hash真实性。 */
export function parseGraphSnapshot(value: unknown): GraphSnapshot {
  const fields = record(value, ["schema_version", "event_id", "business_version", "rule_version", "nodes", "edges", "truncated", "gaps", "content_sha256"]);
  if (fields.schema_version !== 1 || typeof fields.business_version !== "number" || !Number.isSafeInteger(fields.business_version) || fields.business_version < 1 || typeof fields.truncated !== "boolean") return invalidGraph();
  const eventId = graphIdentifier(fields.event_id);
  const nodes = list(fields.nodes, node, 1, 200);
  const edges = list(fields.edges, edge, 0, 400);
  const gaps = list(fields.gaps, gap, 0, graphRelationKinds.length);
  const nodesById = new Map(nodes.map((item) => [item.id, item]));
  if (nodesById.size !== nodes.length || new Set(edges.map((item) => item.id)).size !== edges.length || new Set(gaps.map((item) => item.relation_type)).size !== gaps.length) return invalidGraph();
  if (nodesById.get(eventId)?.kind !== "event") return invalidGraph();
  for (const item of edges) {
    const subject = nodesById.get(item.subject_id);
    const object = nodesById.get(item.object_id);
    if (!subject || !object) return invalidGraph();
    for (const endpoint of [subject, object]) {
      if (endpoint.scope.visibility === "tenant" && (item.scope.visibility !== "tenant" || item.scope.tenant_id !== endpoint.scope.tenant_id)) return invalidGraph();
    }
  }
  const hash = text(fields.content_sha256, 64);
  if (!/^[0-9a-f]{64}$/.test(hash)) return invalidGraph();
  return { schema_version: 1, event_id: eventId, business_version: fields.business_version, rule_version: ruleVersion(fields.rule_version), nodes, edges, truncated: fields.truncated, gaps, content_sha256: hash };
}
