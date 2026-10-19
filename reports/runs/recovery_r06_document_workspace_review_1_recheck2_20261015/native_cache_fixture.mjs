import http from "node:http";
import fs from "node:fs";
const runPath = new URL(".", import.meta.url);
const documentId = "00000000-0000-4000-8000-000000000101";
let activeUser = 1;
let documentReads = 0;
const requests = [];
function send(response, body, status = 200, cacheControl = "no-store") {
  response.writeHead(status, { "Content-Type": "application/json", "Cache-Control": cacheControl });
  response.end(JSON.stringify(body));
}
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:25493");
  const log = { path: url.pathname, method: request.method, cacheControl: request.headers["cache-control"] ?? null, pragma: request.headers.pragma ?? null };
  requests.push(log); fs.appendFileSync(new URL("native_cache_http_requests.jsonl", runPath), JSON.stringify(log) + "\n");
  if (url.pathname === "/v1/health/live") return send(response, { status: "live" });
  if (url.pathname === "/v1/health/ready") return send(response, { status: "ready", reason: "isolated native HTTP fixture", dependencies: {} });
  if (url.pathname === "/v1/auth/me") return activeUser === null ? send(response, { error: { code: "unauthenticated" } }, 401) : send(response, { user_id: `native-cache-fixture-user-${activeUser}`, tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: activeUser, data_mode: "fixture", csrf_token: "f".repeat(64) });
  if (url.pathname === "/v1/auth/logout" && request.method === "POST") { activeUser = null; return send(response, { status: "logged_out" }); }
  if (url.pathname === "/v1/auth/login" && request.method === "POST") { for await (const ignored of request) void ignored; activeUser = 2; return send(response, { user_id: "native-cache-fixture-user-2", csrf_token: "f".repeat(64), expires_at: "2026-10-16T00:00:00Z" }); }
  if (url.pathname === "/v1/fixture-probe") return send(response, { documentReads, requests });
  if (url.pathname === "/v1/documents") {
    if (activeUser === null) return send(response, { error: { code: "unauthenticated" } }, 401);
    documentReads += 1;
    const summary = { document_id: documentId, source_id: "00000000-0000-4000-8000-000000000105", revision_id: "00000000-0000-4000-8000-000000000102", source_name: "隔离HTTP缓存夹具", source_category: "academic_paper", document_kind: "paper", title: `隔离测试：会话${activeUser}授权资料`, canonical_uri: null, revision_number: 1, is_current: true, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, parse_status: "partial", content_coverage: "metadata", published_at_raw: null, published_precision: "unknown" };
    return send(response, { schema_version: 2, items: [summary], next_cursor: null, data_mode: "fixture" }, 200, "private, max-age=600");
  }
  return send(response, { error: { code: "isolated_fixture_unknown_route" } }, 404);
});
server.listen(25493, "127.0.0.1");
