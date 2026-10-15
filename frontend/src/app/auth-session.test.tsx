import { randomBytes } from "node:crypto";
import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuthSession } from "./auth-session";

const fixtureUser = { user_id: "fixture-user-a", tenant_id: "fixture-tenant-a", role: "analyst", permissions: ["read:asset"], permission_version: 1, data_mode: "fixture" };

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function SessionProbe() {
  const { state, error, actionPending, logout, login } = useAuthSession();
  return <><output data-testid="session">{JSON.stringify(state)}</output><output data-testid="error">{error?.code}</output><output data-testid="pending">{String(actionPending)}</output><button onClick={() => void logout()}>退出</button><button onClick={() => void login("fixture-user-a", "fixture-password")}>登录A</button></>;
}

function SessionFenceProbe() {
  const { state, error, actionPending, logoutUnconfirmed, sessionGeneration, expireSession, login, logout } = useAuthSession();
  const [readGeneration, setReadGeneration] = useState<number | null>(null);
  return <><output data-testid="session">{JSON.stringify(state)}</output><output data-testid="error">{error?.code}</output><output data-testid="pending">{String(actionPending)}</output><output data-testid="unconfirmed">{String(logoutUnconfirmed)}</output><button onClick={() => setReadGeneration(sessionGeneration)}>开始读取</button><button onClick={() => { if (readGeneration !== null) expireSession(readGeneration); }}>读取返回401</button><button onClick={() => void login("fixture-user-b", "fixture-password")}>登录B</button><button onClick={() => void logout()}>退出</button></>;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("atomic authentication snapshot — isolated cross-tab HTTP boundary", () => {
  it("never combines A identity with B CSRF after another tab replaces the cookie", async () => {
    const csrfA = randomBytes(32).toString("hex");
    const csrfB = randomBytes(32).toString("hex");
    let cookieUser = "fixture-user-a";
    let csrfRequests = 0;
    let logoutSubject: string | null = null;
    let outgoingToken: string | null = null;
    vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
      if (path === "/v1/auth/me") {
        const snapshot = { ...fixtureUser, csrf_token: csrfA };
        cookieUser = "fixture-user-b";
        return response(snapshot);
      }
      if (path === "/v1/auth/csrf") { csrfRequests += 1; return response({ csrf_token: csrfB, header_name: "X-CSRF-Token" }); }
      if (path === "/v1/auth/logout") {
        outgoingToken = new Headers(options?.headers).get("X-CSRF-Token");
        if (cookieUser === "fixture-user-b" && outgoingToken === csrfB) {
          logoutSubject = cookieUser;
          return response({ status: "logged_out" });
        }
        return response({ error: { code: "csrf_rejected", retryable: false } }, 403);
      }
      throw new Error("unexpected synthetic HTTP path");
    }));
    render(<AuthProvider><SessionProbe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain('"kind":"authenticated"'));
    expect(screen.getByTestId("session").textContent).toContain("fixture-tenant-a");
    fireEvent.click(screen.getByRole("button", { name: "退出" }));
    await waitFor(() => expect(screen.getByTestId("pending").textContent).toBe("false"));
    expect(outgoingToken).toBe(csrfA);
    expect(logoutSubject).toBeNull();
    expect(csrfRequests).toBe(0);
    expect(screen.getByTestId("error").textContent).toBe("csrf_rejected");
    expect(screen.getByTestId("session").textContent).not.toContain("fixture-tenant-a");
  });

  it("uses me snapshot nonce after login when another session for the same user replaces its cookie", async () => {
    const loginCsrf = randomBytes(32).toString("hex");
    const currentCsrf = randomBytes(32).toString("hex");
    let loggedIn = false;
    let csrfRequests = 0;
    let outgoingToken: string | null = null;
    vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
      if (path === "/v1/auth/me") return loggedIn ? response({ ...fixtureUser, csrf_token: currentCsrf }) : response({ error: { code: "unauthenticated", retryable: false } }, 401);
      if (path === "/v1/auth/login") { loggedIn = true; return response({ user_id: fixtureUser.user_id, csrf_token: loginCsrf, expires_at: "2099-01-01T00:00:00+08:00" }); }
      if (path === "/v1/auth/csrf") { csrfRequests += 1; return response({ csrf_token: currentCsrf, header_name: "X-CSRF-Token" }); }
      if (path === "/v1/auth/logout") {
        outgoingToken = new Headers(options?.headers).get("X-CSRF-Token");
        if (outgoingToken !== currentCsrf) return response({ error: { code: "csrf_rejected", retryable: false } }, 403);
        return response({ status: "logged_out" });
      }
      throw new Error("unexpected synthetic HTTP path");
    }));
    render(<AuthProvider><SessionProbe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain('"kind":"anonymous"'));
    fireEvent.click(screen.getByRole("button", { name: "登录A" }));
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain('"kind":"authenticated"'));
    fireEvent.click(screen.getByRole("button", { name: "退出" }));
    await waitFor(() => expect(screen.getByTestId("pending").textContent).toBe("false"));
    expect(outgoingToken).toBe(currentCsrf);
    expect(csrfRequests).toBe(0);
    expect(screen.getByTestId("error").textContent).toBe("");
  });

  it("rejects an incomplete me snapshot instead of falling back to a second csrf request", async () => {
    const nonce = randomBytes(32).toString("hex");
    let csrfRequests = 0;
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      if (path === "/v1/auth/me") return response(fixtureUser);
      if (path === "/v1/auth/csrf") { csrfRequests += 1; return response({ csrf_token: nonce, header_name: "X-CSRF-Token" }); }
      throw new Error("unexpected synthetic HTTP path");
    }));
    render(<AuthProvider><SessionProbe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("session").textContent).not.toContain('"kind":"loading"'));
    expect(screen.getByTestId("session").textContent).toContain('"kind":"anonymous"');
    expect(screen.getByTestId("error").textContent).toBe("invalid_response");
    expect(csrfRequests).toBe(0);
  });
});

describe("read response session generation fence — isolated HTTP boundary", () => {
  function installFixtureApi(logoutResult?: Promise<Response>) {
    let cookieUser = "fixture-user-a";
    const nonceA = randomBytes(32).toString("hex");
    const nonceB = randomBytes(32).toString("hex");
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      if (path === "/v1/auth/me") return response({ ...fixtureUser, user_id: cookieUser, tenant_id: cookieUser === "fixture-user-a" ? "fixture-tenant-a" : "fixture-tenant-b", csrf_token: cookieUser === "fixture-user-a" ? nonceA : nonceB });
      if (path === "/v1/auth/login") { cookieUser = "fixture-user-b"; return response({ user_id: cookieUser, csrf_token: nonceB, expires_at: "2099-01-01T00:00:00Z" }); }
      if (path === "/v1/auth/logout") return logoutResult ?? response({ status: "logged_out" });
      throw new Error("unexpected isolated generation route");
    }));
  }
  it("does not let a former identity's delayed 401 expire the newly logged-in identity", async () => {
    installFixtureApi();
    render(<AuthProvider><SessionFenceProbe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain("fixture-user-a"));
    fireEvent.click(screen.getByRole("button", { name: "开始读取" }));
    fireEvent.click(screen.getByRole("button", { name: "登录B" }));
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain("fixture-user-b"));
    fireEvent.click(screen.getByRole("button", { name: "读取返回401" }));
    expect(screen.getByTestId("session").textContent).toContain("fixture-tenant-b");
    expect(screen.getByTestId("error").textContent).toBe("");
  });
  it("does not let a former logout completion clear the newly logged-in identity", async () => {
    let finishLogout: (value: Response) => void = () => { throw new Error("isolated logout was not initialized"); };
    const logoutResult = new Promise<Response>((resolve) => { finishLogout = resolve; });
    installFixtureApi(logoutResult);
    render(<AuthProvider><SessionFenceProbe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain("fixture-user-a"));
    fireEvent.click(screen.getByRole("button", { name: "退出" }));
    fireEvent.click(screen.getByRole("button", { name: "登录B" }));
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain("fixture-user-b"));
    finishLogout(response({ status: "logged_out" }));
    await waitFor(() => expect(screen.getByTestId("pending").textContent).toBe("false"));
    expect(screen.getByTestId("session").textContent).toContain("fixture-tenant-b");
    expect(screen.getByTestId("error").textContent).toBe("");
  });
  it("preserves unconfirmed server revocation when an old read 401 arrives during logout", async () => {
    let rejectLogout: (failure: Error) => void = () => { throw new Error("isolated logout was not initialized"); };
    const logoutResult = new Promise<Response>((_resolve, reject) => { rejectLogout = reject; });
    installFixtureApi(logoutResult);
    render(<AuthProvider><SessionFenceProbe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("session").textContent).toContain("fixture-user-a"));
    fireEvent.click(screen.getByRole("button", { name: "开始读取" }));
    fireEvent.click(screen.getByRole("button", { name: "退出" }));
    fireEvent.click(screen.getByRole("button", { name: "读取返回401" }));
    expect(screen.getByTestId("pending").textContent).toBe("true");
    rejectLogout(new TypeError("isolated offline logout"));
    await waitFor(() => expect(screen.getByTestId("pending").textContent).toBe("false"));
    expect(screen.getByTestId("unconfirmed").textContent).toBe("true");
    expect(screen.getByTestId("error").textContent).toBe("network_unavailable");
    expect(screen.getByTestId("session").textContent).not.toContain("fixture-tenant-a");
  });
});
