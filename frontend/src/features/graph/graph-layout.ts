import type { GraphNode, GraphNodeKind, GraphSnapshot } from "./graph-contracts";

export const graphLaneKinds: readonly GraphNodeKind[] = ["source_revision", "event", "component_version", "atlas", "paper", "remediation"];
export interface PositionedGraphNode { node: GraphNode; x: number; y: number }

/** 有界确定布局：每类一列，完整标签在检视区展示；节点不因选择或渲染而随机移动。 */
export function layoutGraph(snapshot: GraphSnapshot): { nodes: PositionedGraphNode[]; width: number; height: number } {
  const nodes: PositionedGraphNode[] = [];
  let largestLane = 1;
  graphLaneKinds.forEach((kind, lane) => {
    const group = snapshot.nodes.filter((node) => node.kind === kind).sort((left, right) => left.id.localeCompare(right.id));
    largestLane = Math.max(largestLane, group.length);
    group.forEach((node, row) => nodes.push({ node, x: 105 + lane * 190, y: 145 + row * 112 }));
  });
  return { nodes, width: 1160, height: Math.max(490, largestLane * 112 + 160) };
}
