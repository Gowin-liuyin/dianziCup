import { randomBytes } from "node:crypto";
import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

const fixtureNonce = randomBytes(32).toString("hex");

const fixtureUser = {
  user_id: "fixture-analyst",
  tenant_id: "fixture-tenant",
  role: "analyst",
  permissions: ["read:public", "read:asset"],
  permission_version: 3,
  data_mode: "fixture",
  csrf_token: fixtureNonce,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function problemResponse(status: number, code: string): Response {
  return jsonResponse({ error: { code, message: "fixture", retryable: false }, trace_id: "fixture-trace" }, status);
}

function mockApi(options: { authenticated?: boolean; dependencyFailure?: boolean; loginRejected?: boolean; logoutFailure?: boolean; expiresOnRefresh?: boolean } = {}) {
  let authenticated = options.authenticated ?? false;
  let meRequests = 0;
  const requests: { path: string; options: RequestInit | undefined }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, requestOptions?: RequestInit) => {
    let path: string;
    if (typeof input === "string") path = input;
    else if (input instanceof URL) path = input.pathname;
    else path = input.url;
    requests.push({ path, options: requestOptions });
    if (path === "/v1/health/live") return jsonResponse({ status: "live" });
    if (path === "/v1/health/ready") return jsonResponse({
      status: options.dependencyFailure ? "degraded" : "ready",
      reason: options.dependencyFailure ? "search unavailable" : "dependencies ready",
      dependencies: {
        database: { state: "ready" },
        cache: { state: "ready" },
        search: { state: options.dependencyFailure ? "unavailable" : "ready", reason: options.dependencyFailure ? "connection failed" : "" },
      },
    }, options.dependencyFailure ? 503 : 200);
    if (path === "/v1/auth/me") {
      meRequests += 1;
      if (options.expiresOnRefresh && meRequests > 1) return problemResponse(401, "session_expired");
      return authenticated ? jsonResponse(fixtureUser) : problemResponse(401, "unauthenticated");
    }
    if (path === "/v1/auth/csrf") return authenticated ? jsonResponse({ csrf_token: fixtureNonce, header_name: "X-CSRF-Token" }) : problemResponse(401, "unauthenticated");
    if (path === "/v1/auth/login") {
      if (options.loginRejected) return problemResponse(401, "invalid_credentials");
      authenticated = true;
      return jsonResponse({ user_id: fixtureUser.user_id, csrf_token: fixtureNonce, expires_at: "2099-01-01T00:00:00+08:00" });
    }
    if (path === "/v1/auth/logout") {
      if (options.logoutFailure) throw new TypeError("fixture offline");
      authenticated = false;
      return jsonResponse({ status: "logged_out" });
    }
    throw new Error(`Unexpected fixture path ${path}`);
  }));
  return requests;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("T40 R01 authenticated workbench — explicit fixture HTTP boundary", () => {
  it("T40-C01 displays server identity, permissions and fixture mode after login", async () => {
    const requests = mockApi();
    render(<App />);
    await screen.findByRole("button", { name: "登录工作台" });
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "fixture-login-name" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "fixture-password" } });
    fireEvent.click(screen.getByRole("button", { name: "登录工作台" }));
    await screen.findByText("fixture-analyst");
    expect(screen.getByText("fixture-tenant")).toBeTruthy();
    expect(screen.getByText("read:asset")).toBeTruthy();
    expect(screen.getByText("权限版本 3")).toBeTruthy();
    expect(screen.getAllByText("合成 / Fixture").length).toBeGreaterThan(0);
    expect(screen.queryByText("fixture-login-name")).toBeNull();
    expect(requests.every((request) => request.options?.credentials === "include")).toBe(true);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("T40-C02 recovers an anonymous route without rendering private context", async () => {
    mockApi();
    render(<App />);
    await screen.findByRole("button", { name: "登录工作台" });
    expect(screen.queryByText("fixture-tenant")).toBeNull();
    expect(screen.queryByText("read:asset")).toBeNull();
    expect(screen.getByText("尚未登录")).toBeTruthy();
  });

  it("T40-C03 reports network failure and provides a working retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fixture offline")));
    render(<App />);
    await screen.findByText("无法连接服务，请检查网络后重试。");
    mockApi({ authenticated: true });
    fireEvent.click(screen.getByRole("button", { name: "重新检查会话" }));
    await screen.findByText("fixture-analyst");
    fireEvent.click(screen.getByRole("button", { name: "刷新状态" }));
    await screen.findByText("全部依赖就绪");
  });

  it("T40-C04 preserves a 503 degraded result and names the failing dependency", async () => {
    mockApi({ authenticated: true, dependencyFailure: true });
    render(<App />);
    await screen.findAllByText("部分不可用");
    expect(screen.getByText("搜索服务")).toBeTruthy();
    expect(screen.getByText("connection failed")).toBeTruthy();
    expect(screen.queryByText("全部依赖就绪")).toBeNull();
  });

  it("T40-C05 restores a session on remount and clears it with memory-only CSRF logout", async () => {
    const requests = mockApi({ authenticated: true });
    const first = render(<App />);
    await screen.findByText("fixture-analyst");
    first.unmount();
    render(<App />);
    await screen.findByText("fixture-analyst");
    fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
    await screen.findByRole("button", { name: "登录工作台" });
    expect(screen.queryByText("fixture-analyst")).toBeNull();
    expect(screen.queryByText("fixture-tenant")).toBeNull();
    await waitFor(() => expect(requests.some((request) => request.path === "/v1/auth/logout")).toBe(true));
    const logout = requests.find((request) => request.path === "/v1/auth/logout");
    expect(new Headers(logout?.options?.headers).get("X-CSRF-Token")).toBe(fixtureNonce);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("T40-C05 does not claim server revocation after a failed logout", async () => {
    mockApi({ authenticated: true, logoutFailure: true });
    render(<App />);
    await screen.findByText("fixture-analyst");
    fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
    await screen.findByText("退出未完成，服务端会话撤销尚未确认。当前页面已清除身份信息。");
    expect(screen.queryByText("fixture-tenant")).toBeNull();
    expect(screen.queryByText("已成功退出")).toBeNull();
    expect(screen.getByRole("button", { name: "重新检查会话" })).toBeTruthy();
  });

  it("T40-C05 clears private context when the server reports an expired restored session", async () => {
    mockApi({ authenticated: true, expiresOnRefresh: true });
    render(<App />);
    await screen.findByText("fixture-analyst");
    fireEvent.click(screen.getByRole("button", { name: "重新验证会话" }));
    await screen.findByText("会话已失效，请重新登录。");
    expect(screen.queryByText("fixture-analyst")).toBeNull();
    expect(screen.queryByText("fixture-tenant")).toBeNull();
    expect(screen.queryByText("read:asset")).toBeNull();
    expect(screen.getByRole("button", { name: "登录工作台" })).toBeTruthy();
  });

  it("T40-C06 exposes labelled native controls and a readable dependency table", async () => {
    mockApi({ authenticated: true });
    render(<App />);
    await screen.findByText("fixture-analyst");
    const refresh = screen.getByRole("button", { name: "刷新状态" });
    refresh.focus();
    expect(document.activeElement).toBe(refresh);
    expect(screen.getByRole("table", { name: "实际依赖探测结果" })).toBeTruthy();
    expect(screen.getAllByText("就绪").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "跳到主要内容" })).toBeTruthy();
  });

  it("rejects invalid credentials without showing a private user", async () => {
    mockApi({ loginRejected: true });
    render(<App />);
    await screen.findByRole("button", { name: "登录工作台" });
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "fixture-user" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "fixture-password" } });
    fireEvent.click(screen.getByRole("button", { name: "登录工作台" }));
    await screen.findByText("用户名或密码不正确。");
    expect(screen.queryByText("fixture-tenant")).toBeNull();
    expect(screen.getByLabelText<HTMLInputElement>("密码").value).toBe("");
  });

  it("does not refill a logged-out identity from an old StrictMode restore request", async () => {
    let releaseOldMe: (response: Response) => void = () => { throw new Error("fixture request was not started"); };
    const oldMe = new Promise<Response>((resolve) => { releaseOldMe = resolve; });
    let meRequests = 0;
    let authenticated = true;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (input === "/v1/auth/me") {
        meRequests += 1;
        if (meRequests === 1) return oldMe;
        return authenticated ? jsonResponse(fixtureUser) : problemResponse(401, "unauthenticated");
      }
      if (input === "/v1/auth/csrf") return authenticated ? jsonResponse({ csrf_token: fixtureNonce, header_name: "X-CSRF-Token" }) : problemResponse(401, "unauthenticated");
      if (input === "/v1/auth/logout") { authenticated = false; return jsonResponse({ status: "logged_out" }); }
      if (input === "/v1/health/live") return jsonResponse({ status: "live" });
      if (input === "/v1/health/ready") return jsonResponse({ status: "ready", reason: "fixture", dependencies: { database: { state: "ready" } } });
      throw new Error("unexpected fixture request");
    }));
    render(<StrictMode><App /></StrictMode>);
    await screen.findByText("fixture-analyst");
    fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
    await screen.findByRole("button", { name: "登录工作台" });
    releaseOldMe(jsonResponse(fixtureUser));
    await waitFor(() => expect(screen.getByRole("button", { name: "登录工作台" }).hasAttribute("disabled")).toBe(false));
    expect(screen.queryByText("fixture-analyst")).toBeNull();
    expect(screen.queryByText("fixture-tenant")).toBeNull();
  });
});
