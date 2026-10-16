import type { Page } from "@playwright/test";
import { syntheticGeneration, syntheticIds, syntheticRecommendation, syntheticReport, syntheticScope, syntheticSubscription } from "../src/features/recommendations/synthetic-wire-fixtures";

export async function installRecommendationWireFixture(page: Page) {
  const state = { subscription: syntheticSubscription(), recommendation: syntheticRecommendation(), reports: [syntheticReport()], authenticated: true, catalogStatus: 200, emptyCatalog: false, casConflict: false, recommendationStatus: 200, generationStatus: 200, exportStatus: 200, partial: false, writes: [] as { path: string; body: unknown; method: string; key: string | undefined }[], paths: [] as string[] };
  state.recommendation.content.key.material_version = "synthetic-material-version-long-unbroken-".repeat(4);
  state.recommendation.content.reasons[0]!.citations[0]!.quote += "\n" + "长文本边界核查".repeat(60);
  await page.route(/\/(?:api\/v1|v1)\//, async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname; const method = request.method(); state.paths.push(`${method} ${path}`);
    let status = 200; let body: unknown;
    if (method === "POST" || method === "PATCH") state.writes.push({ path, body: request.postDataJSON(), method, key: request.headers()["idempotency-key"] });
    if (path === "/v1/auth/me") { status = state.authenticated ? 200 : 401; body = state.authenticated ? { user_id: syntheticScope.userId, tenant_id: syntheticScope.tenantId, role: "viewer", permissions: ["read:public", "read:asset"], permission_version: 1, data_mode: "fixture", csrf_token: "synthetic-browser-memory" } : { error: { code: "session_expired", retryable: false } }; }
    else if (path === "/v1/auth/csrf") body = { csrf_token: "synthetic-browser-memory", header_name: "X-CSRF-Token" };
    else if (path === "/api/v1/subscriptions" && method === "GET") { status = state.catalogStatus; body = status === 200 ? { items: state.emptyCatalog ? [] : [state.subscription], next_cursor: null } : { error: { code: "recommendations_not_configured", retryable: true } }; }
    else if (path === "/api/v1/subscriptions" && method === "POST") { status = 201; body = state.subscription; }
    else if (path === `/api/v1/subscriptions/${syntheticIds.subscription}`) {
      if (method === "PATCH") {
        if (state.casConflict) { state.subscription = syntheticSubscription(2); status = 409; body = { error: { code: "subscription_version_conflict", retryable: false } }; }
        else { const input: unknown = request.postDataJSON(); state.subscription = { ...state.subscription, version: state.subscription.version + 1 }; if (typeof input === "object" && input !== null && "enabled" in input && typeof input.enabled === "boolean") state.subscription.spec.enabled = input.enabled; body = state.subscription; }
      } else body = state.subscription;
    }
    else if (path.endsWith("/generate")) { status = state.generationStatus; body = { ...syntheticGeneration(), partial: state.partial, gaps: state.partial ? [{ code: "input_scope_partial", event_id: null, asset_id: null }] : [] }; }
    else if (path.endsWith("/recommendations")) { status = state.recommendationStatus; body = status === 200 ? { items: [state.recommendation], next_cursor: null } : { error: { code: status === 401 ? "session_expired" : "forbidden", retryable: false } }; }
    else if (path.endsWith("/read")) { state.recommendation.read_at = "2026-10-16T10:00:00Z"; body = state.recommendation; }
    else if (path === "/api/v1/reports" && method === "POST") {
      const input: unknown = request.postDataJSON(); const report = syntheticReport(); if (typeof input === "object" && input !== null && "frequency" in input && (input.frequency === "day" || input.frequency === "week")) report.content.report.frequency = input.frequency;
      report.report_id = "10000000-0000-4000-8000-000000000002"; state.reports.push(report); body = report; status = 201;
    }
    else if (path === `/api/v1/subscriptions/${syntheticIds.subscription}/reports`) body = { items: state.reports, next_cursor: null };
    else if (path.startsWith("/api/v1/reports/")) {
      const id = path.split("/")[4]; const report = state.reports.find((item) => item.report_id === id);
      if (url.searchParams.get("subscription_id") !== syntheticIds.subscription) throw new Error("synthetic report query lacks owner subscription binding");
      status = path.endsWith("/export") ? state.exportStatus : 200; body = status === 200 ? (path.endsWith("/export") ? { ...report, current_reason: "synthetic-export-new-authorized-check" } : report) : { error: { code: "forbidden", retryable: false } };
    }
    else throw new Error(`unexpected isolated fixture route ${method} ${path}`);
    await route.fulfill({ status, json: body });
  });
  return state;
}
