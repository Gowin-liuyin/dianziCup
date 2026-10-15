import { ApiProblem, fetchJson } from "./client";
import { parseEventDetailResponse, parseEventListResponse, parseEvidenceResponse, type EventDetailResponse, type EventListResponse, type EvidenceResponse } from "./knowledge-contracts";

export interface EventFilters {
  q?: string; product?: string; risk_type?: string; updated_after?: string; cursor?: string; limit?: number;
}

function eventPath(id: string, kind: "events" | "evidence"): string {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) throw new ApiProblem(422, "validation_error", false);
  return `/v1/${kind}/${id}`;
}

/** 固定过滤字段构建同源只读请求；错误响应始终保留为错误，不解释成空列表。 */
export async function getEventList(filters: EventFilters = {}, signal?: AbortSignal): Promise<EventListResponse> {
  const query = new URLSearchParams();
  for (const key of ["q", "product", "risk_type", "updated_after", "cursor"] as const) {
    const value = filters[key];
    if (value !== undefined && value !== "") query.set(key, value);
  }
  const limit = filters.limit ?? 20;
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new ApiProblem(422, "validation_error", false);
  query.set("limit", String(limit));
  return parseEventListResponse(await fetchJson(`/v1/events?${query}`, {}, signal));
}

export async function getEventDetail(id: string, signal?: AbortSignal): Promise<EventDetailResponse> {
  const result = parseEventDetailResponse(await fetchJson(eventPath(id, "events"), {}, signal));
  if (result.event.event_id.toLowerCase() !== id.toLowerCase()) throw new ApiProblem(502, "invalid_response", true);
  return result;
}

export async function getEvidence(id: string, expectedRevisionId: string | null = null, signal?: AbortSignal): Promise<EvidenceResponse> {
  const result = parseEvidenceResponse(await fetchJson(eventPath(id, "evidence"), {}, signal));
  if (result.span_id.toLowerCase() !== id.toLowerCase()) throw new ApiProblem(502, "invalid_response", true);
  if (expectedRevisionId !== null && result.revision_id.toLowerCase() !== expectedRevisionId.toLowerCase()) throw new ApiProblem(502, "invalid_response", true);
  return result;
}
