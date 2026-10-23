import { ApiProblem, fetchJson, getCsrfToken } from "./client";

export interface EnrichmentReceipt {
  workflow_id: string;
  parent_job_id: string;
  reused: boolean;
}

function identifier(value: unknown): string {
  if (typeof value !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)) {
    throw new ApiProblem(502, "invalid_response", true);
  }
  return value.toLowerCase();
}

function parseReceipt(value: unknown): EnrichmentReceipt {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ApiProblem(502, "invalid_response", true);
  }
  const fields = value as Record<string, unknown>;
  const keys = ["workflow_id", "parent_job_id", "reused"];
  if (Object.keys(fields).length !== keys.length || keys.some((key) => !(key in fields))) {
    throw new ApiProblem(502, "invalid_response", true);
  }
  if (typeof fields.reused !== "boolean") throw new ApiProblem(502, "invalid_response", true);
  return {
    workflow_id: identifier(fields.workflow_id),
    parent_job_id: identifier(fields.parent_job_id),
    reused: fields.reused,
  };
}

/** 202 only means the workflow was stored. It is not a completed enrichment result. */
export async function enqueueEventEnrichment(eventId: string, expectedEventVersion: number, idempotencyKey: string, signal?: AbortSignal): Promise<EnrichmentReceipt> {
  if (!Number.isInteger(expectedEventVersion) || expectedEventVersion < 1) throw new ApiProblem(422, "invalid_event_version", false);
  const token = await getCsrfToken(signal);
  const value = await fetchJson(
    `/v1/events/${eventId}/enrichment-jobs`,
    { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token, "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ expected_event_version: expectedEventVersion }) },
    signal,
    [],
    30_000,
    [202],
  );
  return parseReceipt(value);
}
