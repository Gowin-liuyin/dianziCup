import { ApiProblem, fetchJson, getCsrfToken } from "../../api/client";
import { isRecommendationIdentifier, normalizeDefinition } from "./schema-validation";
import { parseGeneration, parseRecommendation, parseRecommendationPage, parseReport, parseReportPage, parseSubscription, parseSubscriptionPage, type RecommendationScope } from "./recommendation-contracts";
import { isCreateReport, type CreateReport, type CreateSubscription, type ReplaceSubscription, type SetSubscriptionEnabled } from "./recommendation-wire-types";

const prefix = "/api/v1";
export interface RecommendationMutation { idempotencyKey: string; signal?: AbortSignal; isCurrent: () => boolean }
function invalidInput(): never { throw new ApiProblem(400, "validation_error", false); }
function identifier(value: string): string { return isRecommendationIdentifier(value) ? encodeURIComponent(value.toLowerCase()) : invalidInput(); }
function pageQuery(cursor: string | null): URLSearchParams {
  const query = new URLSearchParams({ limit: "20" }); if (cursor !== null) query.set("cursor", identifier(cursor)); return query;
}
function input(value: unknown, name: string): unknown {
  try { return normalizeDefinition(value, name); } catch (failure: unknown) { if (failure instanceof ApiProblem) return invalidInput(); throw failure; }
}
async function write(path: string, method: "POST" | "PATCH", body: unknown, definition: string | null, mutation: RecommendationMutation): Promise<unknown> {
  if (!/^[A-Za-z0-9_-]{1,200}$/.test(mutation.idempotencyKey)) return invalidInput();
  const payload = definition === null ? body : input(body, definition);
  if (mutation.signal?.aborted || !mutation.isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  const csrf = await getCsrfToken(mutation.signal);
  if (mutation.signal?.aborted || !mutation.isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  const expectedStatuses = definition === "CreateSubscription" || definition === "CreateReport" ? [200, 201] : [200];
  return fetchJson(path, { method, headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": mutation.idempotencyKey }, body: JSON.stringify(payload) }, mutation.signal, [], 10_000, expectedStatuses);
}
export async function getSubscriptions(scope: RecommendationScope, cursor: string | null = null, signal?: AbortSignal) { return parseSubscriptionPage(await fetchJson(`${prefix}/subscriptions?${pageQuery(cursor)}`, {}, signal, [], 10_000, [200]), scope, cursor); }
export async function getSubscription(scope: RecommendationScope, subscriptionId: string, signal?: AbortSignal) { return parseSubscription(await fetchJson(`${prefix}/subscriptions/${identifier(subscriptionId)}`, {}, signal, [], 10_000, [200]), scope, subscriptionId); }
export async function createSubscription(scope: RecommendationScope, body: CreateSubscription, mutation: RecommendationMutation) { return parseSubscription(await write(`${prefix}/subscriptions`, "POST", body, "CreateSubscription", mutation), scope); }
export async function replaceSubscription(scope: RecommendationScope, subscriptionId: string, body: ReplaceSubscription, mutation: RecommendationMutation) { return parseSubscription(await write(`${prefix}/subscriptions/${identifier(subscriptionId)}`, "PATCH", body, "ReplaceSubscription", mutation), scope, subscriptionId); }
export async function setSubscriptionEnabled(scope: RecommendationScope, subscriptionId: string, body: SetSubscriptionEnabled, mutation: RecommendationMutation) { return parseSubscription(await write(`${prefix}/subscriptions/${identifier(subscriptionId)}`, "PATCH", body, "SetSubscriptionEnabled", mutation), scope, subscriptionId); }
export async function generateRecommendations(scope: RecommendationScope, subscriptionId: string, maxCandidates: number, mutation: RecommendationMutation) { return parseGeneration(await write(`${prefix}/subscriptions/${identifier(subscriptionId)}/generate`, "POST", { max_candidates: maxCandidates }, "GenerateRecommendations", mutation), scope); }
export async function getRecommendations(scope: RecommendationScope, subscriptionId: string, cursor: string | null = null, signal?: AbortSignal) { return parseRecommendationPage(await fetchJson(`${prefix}/subscriptions/${identifier(subscriptionId)}/recommendations?${pageQuery(cursor)}`, {}, signal, [], 10_000, [200]), scope, subscriptionId, cursor); }
export async function markRecommendationRead(scope: RecommendationScope, subscriptionId: string, recommendationId: string, mutation: RecommendationMutation) { return parseRecommendation(await write(`${prefix}/recommendations/${identifier(recommendationId)}/read?subscription_id=${identifier(subscriptionId)}`, "POST", {}, null, mutation), scope, subscriptionId, recommendationId); }
export async function getReports(scope: RecommendationScope, subscriptionId: string, cursor: string | null = null, signal?: AbortSignal) { return parseReportPage(await fetchJson(`${prefix}/subscriptions/${identifier(subscriptionId)}/reports?${pageQuery(cursor)}`, {}, signal, [], 10_000, [200]), scope, subscriptionId, cursor); }
export async function createReport(scope: RecommendationScope, body: CreateReport, mutation: RecommendationMutation) {
  const request = input(body, "CreateReport"); if (!isCreateReport(request)) return invalidInput();
  const receipt = parseReport(await write(`${prefix}/reports`, "POST", request, "CreateReport", mutation), scope, request.subscription_id);
  if (receipt.content.generation_id !== request.generation_id || receipt.content.report.frequency !== request.frequency || receipt.content.max_items !== request.max_items) throw new ApiProblem(502, "invalid_response", false);
  return receipt;
}
export async function getReport(scope: RecommendationScope, subscriptionId: string, reportId: string, signal?: AbortSignal) { return parseReport(await fetchJson(`${prefix}/reports/${identifier(reportId)}?subscription_id=${identifier(subscriptionId)}`, {}, signal, [], 10_000, [200]), scope, subscriptionId, reportId); }
export async function exportReport(scope: RecommendationScope, subscriptionId: string, reportId: string, signal?: AbortSignal) { return parseReport(await fetchJson(`${prefix}/reports/${identifier(reportId)}/export?subscription_id=${identifier(subscriptionId)}`, {}, signal, [], 10_000, [200]), scope, subscriptionId, reportId); }

/** 仅从新授权 export 响应下载，不从历史页面缓存制作授权报告。 */
export function downloadAuthorizedReport(report: Awaited<ReturnType<typeof exportReport>>): void {
  const objectUrl = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a"); anchor.href = objectUrl; anchor.download = `${identifier(report.report_id)}.json`; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}
