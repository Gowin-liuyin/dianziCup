import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AuthProvider, useAuthSession } from 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/src/app/auth-session';
import { getCurrentUser, getReadiness } from 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/src/api/client';

const userA = { user_id: 'review-user-a', tenant_id: 'review-tenant-a', role: 'analyst', permissions: ['read:asset'], permission_version: 1, data_mode: 'fixture' };
const userB = { user_id: 'review-user-b', tenant_id: 'review-tenant-b', role: 'viewer', permissions: ['read:public'], permission_version: 1, data_mode: 'fixture' };
const jsonResponse = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const errorResponse = (status: number, code: string) => jsonResponse({ error: { code, message: 'SYNTHETIC-PRIVATE-DETAIL', retryable: true } }, status);

function SessionHarness() {
  const session = useAuthSession();
  return <><output data-testid="state">{JSON.stringify(session.state)}</output><output data-testid="error">{session.error?.message ?? ''}</output><output data-testid="unconfirmed">{String(session.logoutUnconfirmed)}</output><button onClick={() => void session.refreshSession()}>refresh</button><button onClick={() => void session.logout()}>logout</button></>;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('independent R01 current session boundary probes', () => {
  it('clears the private identity immediately while logout is still pending', async () => {
    let releaseLogout: (value: Response) => void = () => { throw new Error('not started'); };
    const logoutResponse = new Promise<Response>((resolve) => { releaseLogout = resolve; });
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      if (path.endsWith('/me')) return jsonResponse(userA);
      if (path.endsWith('/csrf')) return jsonResponse({ csrf_token: 'synthetic-csrf-a', header_name: 'X-CSRF-Token' });
      return logoutResponse;
    }));
    render(<AuthProvider><SessionHarness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-tenant-a'));
    fireEvent.click(screen.getByText('logout'));
    expect(screen.getByTestId('state').textContent).not.toContain('review-tenant-a');
    releaseLogout(jsonResponse({ status: 'logged_out' }));
    await waitFor(() => expect(screen.getByTestId('unconfirmed').textContent).toBe('false'));
  });

  it('does not restore an identity from a CSRF response that arrives after logout', async () => {
    let releaseCsrf: (value: Response) => void = () => { throw new Error('not started'); };
    const csrfResponse = new Promise<Response>((resolve) => { releaseCsrf = resolve; });
    let csrfRequests = 0;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      if (path.endsWith('/me')) return jsonResponse(userA);
      if (path.endsWith('/csrf')) { csrfRequests += 1; return csrfRequests === 1 ? jsonResponse({ csrf_token: 'synthetic-csrf-a', header_name: 'X-CSRF-Token' }) : csrfResponse; }
      return jsonResponse({ status: 'logged_out' });
    }));
    render(<AuthProvider><SessionHarness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-tenant-a'));
    fireEvent.click(screen.getByText('refresh'));
    await waitFor(() => expect(csrfRequests).toBe(2));
    fireEvent.click(screen.getByText('logout'));
    releaseCsrf(jsonResponse({ csrf_token: 'synthetic-csrf-a', header_name: 'X-CSRF-Token' }));
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('{"kind":"anonymous"}'));
  });

  it('reports a failed logout while keeping the private identity cleared', async () => {
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      if (path.endsWith('/me')) return jsonResponse(userA);
      if (path.endsWith('/csrf')) return jsonResponse({ csrf_token: 'synthetic-csrf-a', header_name: 'X-CSRF-Token' });
      throw new TypeError('SYNTHETIC-PRIVATE-DETAIL');
    }));
    render(<AuthProvider><SessionHarness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-tenant-a'));
    fireEvent.click(screen.getByText('logout'));
    await waitFor(() => expect(screen.getByTestId('unconfirmed').textContent).toBe('true'));
    expect(screen.getByTestId('state').textContent).not.toContain('review-tenant-a');
    expect(screen.getByTestId('error').textContent).not.toContain('SYNTHETIC-PRIVATE-DETAIL');
  });

  it('clears restored private state for an expired session', async () => {
    let expired = false;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      if (path.endsWith('/me')) return expired ? errorResponse(401, 'session_expired') : jsonResponse(userA);
      return jsonResponse({ csrf_token: 'synthetic-csrf-a', header_name: 'X-CSRF-Token' });
    }));
    render(<AuthProvider><SessionHarness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-tenant-a'));
    expired = true;
    fireEvent.click(screen.getByText('refresh'));
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('{"kind":"anonymous"}'));
    expect(screen.getByTestId('error').textContent).toContain('会话已失效');
  });

  it('keeps an unknown dependency state instead of inventing ready', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ status: 'not_ready', reason: 'not observed', dependencies: { database: { state: 'future-unknown-state' } } }, 503)));
    const readiness = await getReadiness();
    expect(readiness.status).toBe('not_ready');
    expect(readiness.dependencies.database.state).toBe('future-unknown-state');
  });

  it('sanitizes an unknown backend error without echoing private details', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => errorResponse(503, 'future_backend_code')));
    await expect(getCurrentUser()).rejects.toMatchObject({ status: 503, code: 'future_backend_code', message: '操作未完成，请重试或联系管理员。' });
  });

  it('distinguishes a real request timeout from a normal empty result', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn((_path: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))));
    const request = getCurrentUser();
    const assertion = expect(request).rejects.toMatchObject({ code: 'request_timeout', retryable: true });
    await vi.advanceTimersByTimeAsync(10_001);
    await assertion;
  });

  it('rejects a restore assembled from different users when another tab replaces the cookie between me and csrf', async () => {
    let currentUser = userA;
    let logoutFor = '';
    vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
      if (path.endsWith('/me')) { const sampled = currentUser; currentUser = userB; return jsonResponse(sampled); }
      if (path.endsWith('/csrf')) return jsonResponse({ csrf_token: 'synthetic-csrf-b', header_name: 'X-CSRF-Token' });
      logoutFor = currentUser.user_id;
      expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe('synthetic-csrf-b');
      return jsonResponse({ status: 'logged_out' });
    }));
    render(<AuthProvider><SessionHarness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-user-a'));
    const restored = screen.getByTestId('state').textContent;
    fireEvent.click(screen.getByText('logout'));
    await waitFor(() => expect(logoutFor).toBe('review-user-b'));
    console.log(JSON.stringify({ probe: 'cross-tab-cookie-switch', displayedUser: 'review-user-a', actionUser: logoutFor, privateTenantRetainedDuringRestore: restored?.includes('review-tenant-a') }));
    expect(restored).not.toContain('review-tenant-a');
  });
});
