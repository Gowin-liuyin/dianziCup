/** 服务端认证上下文；客户端不从表单或浏览器存储推断身份。 */
export interface CurrentUser {
  user_id: string;
  tenant_id: string | null;
  role: "viewer" | "analyst" | "tenant_admin" | "system_admin";
  permissions: string[];
  permission_version: number;
  data_mode: "live" | "fixture";
  app_env?: string;
  platform_version?: string;
}

export interface Readiness {
  status: "ready" | "not_ready" | "degraded";
  reason: string;
  dependencies: Record<string, { state: string; reason?: string }>;
}

export interface LoginSession {
  user_id: string;
  csrf_token: string;
  expires_at: string;
}

/** 同一次认证读取取得的身份与会话绑定 CSRF，不暴露到公开用户上下文。 */
export interface SessionSnapshot {
  user: CurrentUser;
  csrfToken: string;
}

const errorMessages: Record<string, string> = {
  invalid_credentials: "用户名或密码不正确。",
  unauthenticated: "请登录后继续。",
  session_expired: "会话已失效，请重新登录。",
  login_rate_limited: "登录请求过于频繁，请稍后重试。",
  csrf_rejected: "会话校验未通过，请重新检查会话。",
  forbidden: "当前操作没有权限，请联系管理员。",
  dependency_unavailable: "服务暂不可用，请检查运行状态后重试。",
  service_unavailable: "服务暂不可用，请检查运行状态后重试。",
  validation_error: "请求内容未通过校验，请检查输入。",
  network_unavailable: "无法连接服务，请检查网络后重试。",
  request_timeout: "服务响应超时，请稍后重试。",
  request_canceled: "请求已取消。",
  invalid_response: "服务返回的数据格式不符合接口约定，请重新检查。",
};

/** 仅保留可公开的错误标识；原始响应与网络异常不会显示到页面。 */
export class ApiProblem extends Error {
  constructor(readonly status: number, readonly code: string, readonly retryable: boolean, readonly traceId?: string) {
    super(Object.hasOwn(errorMessages, code) ? errorMessages[code] : "操作未完成，请重试或联系管理员。");
    this.name = "ApiProblem";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function invalidResponse(): never {
  throw new ApiProblem(502, "invalid_response", true);
}

function parseProblem(value: unknown, status: number): ApiProblem {
  let fallbackCode = "request_failed";
  if (status === 401) fallbackCode = "unauthenticated";
  if (status === 403) fallbackCode = "forbidden";
  if (status === 503) fallbackCode = "service_unavailable";
  if (!isRecord(value) || !isRecord(value.error)) return new ApiProblem(status, fallbackCode, status >= 500);
  const code = isNonEmptyString(value.error.code) ? value.error.code : fallbackCode;
  const traceId = typeof value.trace_id === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(value.trace_id) ? value.trace_id : undefined;
  return new ApiProblem(status, code, value.error.retryable === true, traceId);
}

export async function fetchJson(path: string, options: RequestInit = {}, signal?: AbortSignal, acceptedStatuses: number[] = [], requestTimeoutMilliseconds = 10_000, expectedStatuses?: readonly number[]): Promise<unknown> {
  if (!Number.isInteger(requestTimeoutMilliseconds) || requestTimeoutMilliseconds < 1 || requestTimeoutMilliseconds > 120_000) throw new RangeError("request timeout must be between 1 and 120000 milliseconds");
  const controller = new AbortController();
  const abortRequest = () => controller.abort();
  signal?.addEventListener("abort", abortRequest, { once: true });
  if (signal?.aborted) controller.abort();
  let timedOut = false;
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, requestTimeoutMilliseconds);
  try {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json, application/problem+json");
    const response = await fetch(path, { ...options, headers, credentials: "include", cache: "no-store", signal: controller.signal });
    let body: unknown;
    try { body = await response.json(); } catch {
      if (!response.ok && !acceptedStatuses.includes(response.status)) throw parseProblem(null, response.status);
      return invalidResponse();
    }
    if (!response.ok && !acceptedStatuses.includes(response.status)) throw parseProblem(body, response.status);
    if (expectedStatuses !== undefined && !expectedStatuses.includes(response.status)) return invalidResponse();
    return body;
  } catch (error: unknown) {
    if (error instanceof ApiProblem) throw error;
    if (controller.signal.aborted) throw new ApiProblem(0, timedOut ? "request_timeout" : "request_canceled", timedOut);
    throw new ApiProblem(0, "network_unavailable", true);
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortRequest);
  }
}

function parseCurrentUser(value: unknown): CurrentUser {
  if (!isRecord(value)) return invalidResponse();
  const { user_id, tenant_id, role, permissions, permission_version, data_mode, app_env, platform_version } = value;
  if (!isNonEmptyString(user_id) || !(tenant_id === null || isNonEmptyString(tenant_id))) return invalidResponse();
  if (role !== "viewer" && role !== "analyst" && role !== "tenant_admin" && role !== "system_admin") return invalidResponse();
  if (!Array.isArray(permissions) || !permissions.every(isNonEmptyString)) return invalidResponse();
  if (typeof permission_version !== "number" || !Number.isInteger(permission_version) || permission_version < 1) return invalidResponse();
  if (data_mode !== "live" && data_mode !== "fixture") return invalidResponse();
  if (app_env !== undefined && !isNonEmptyString(app_env)) return invalidResponse();
  if (platform_version !== undefined && !isNonEmptyString(platform_version)) return invalidResponse();
  return { user_id, tenant_id, role, permissions, permission_version, data_mode, app_env, platform_version };
}

export async function getCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
  return parseCurrentUser(await fetchJson("/v1/auth/me", {}, signal));
}

export async function getSessionSnapshot(signal?: AbortSignal): Promise<SessionSnapshot> {
  const value = await fetchJson("/v1/auth/me", {}, signal);
  const user = parseCurrentUser(value);
  if (!isRecord(value) || !isNonEmptyString(value.csrf_token)) return invalidResponse();
  return { user, csrfToken: value.csrf_token };
}

export async function getCsrfToken(signal?: AbortSignal): Promise<string> {
  const value = await fetchJson("/v1/auth/csrf", {}, signal);
  if (!isRecord(value) || !isNonEmptyString(value.csrf_token) || value.header_name !== "X-CSRF-Token") return invalidResponse();
  return value.csrf_token;
}

export async function loginSession(username: string, password: string): Promise<LoginSession> {
  const value = await fetchJson("/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
  if (!isRecord(value) || !isNonEmptyString(value.user_id) || !isNonEmptyString(value.csrf_token) || !isNonEmptyString(value.expires_at)) return invalidResponse();
  if (!Number.isFinite(Date.parse(value.expires_at))) return invalidResponse();
  return { user_id: value.user_id, csrf_token: value.csrf_token, expires_at: value.expires_at };
}

export async function logoutSession(csrfToken: string): Promise<void> {
  const value = await fetchJson("/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
  if (!isRecord(value) || value.status !== "logged_out") return invalidResponse();
}

export async function getLiveness(signal?: AbortSignal): Promise<void> {
  const value = await fetchJson("/v1/health/live", {}, signal);
  if (!isRecord(value) || value.status !== "live") return invalidResponse();
}

export async function getReadiness(signal?: AbortSignal): Promise<Readiness> {
  const value = await fetchJson("/v1/health/ready", {}, signal, [503]);
  if (!isRecord(value) || !isRecord(value.dependencies)) return invalidResponse();
  if (value.status !== "ready" && value.status !== "not_ready" && value.status !== "degraded") return invalidResponse();
  if (typeof value.reason !== "string") return invalidResponse();
  const dependencies: [string, { state: string; reason?: string }][] = [];
  for (const [name, dependency] of Object.entries(value.dependencies)) {
    if (!isRecord(dependency) || !isNonEmptyString(dependency.state)) return invalidResponse();
    if (dependency.reason !== undefined && typeof dependency.reason !== "string") return invalidResponse();
    dependencies.push([name, { state: dependency.state, reason: dependency.reason }]);
  }
  return { status: value.status, reason: value.reason, dependencies: Object.fromEntries(dependencies) };
}

export function publicProblem(error: unknown): ApiProblem {
  return error instanceof ApiProblem ? error : new ApiProblem(0, "network_unavailable", true);
}
