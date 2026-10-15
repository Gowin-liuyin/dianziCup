import { ApiProblem, fetchJson } from "../../api/client";
import { graphIdentifier, parseGraphSnapshot, type GraphSnapshot } from "./graph-contracts";

/** 同源有界读路径，认证Cookie/Problem/超时沿用原HTTP客户端，不接受租户、SQL或任意URL。 */
export async function getEventGraph(eventId: string, signal?: AbortSignal, limits: { maxNodes?: number; maxEdges?: number } = {}): Promise<GraphSnapshot> {
  let id: string;
  try { id = graphIdentifier(eventId); } catch { throw new ApiProblem(422, "validation_error", false); }
  const maxNodes = limits.maxNodes ?? 200;
  const maxEdges = limits.maxEdges ?? 400;
  if (!Number.isInteger(maxNodes) || maxNodes < 1 || maxNodes > 200 || !Number.isInteger(maxEdges) || maxEdges < 1 || maxEdges > 400) throw new ApiProblem(422, "validation_error", false);
  const query = new URLSearchParams({ max_nodes: String(maxNodes), max_edges: String(maxEdges) });
  const snapshot = parseGraphSnapshot(await fetchJson(`/v1/events/${id}/graph?${query}`, {}, signal));
  if (snapshot.event_id !== id || snapshot.nodes.length > maxNodes || snapshot.edges.length > maxEdges) throw new ApiProblem(502, "invalid_response", true);
  return snapshot;
}
