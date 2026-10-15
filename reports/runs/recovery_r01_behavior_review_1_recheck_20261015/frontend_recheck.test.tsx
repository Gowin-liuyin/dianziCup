import React from 'react';
import { randomBytes } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuthSession } from 'C:/Users/yinha/.codex/worktrees/recovery-r01-recheck/dianzi/frontend/src/app/auth-session';

const userA = { user_id: 'review-user-a', tenant_id: 'review-tenant-a', role: 'analyst', permissions: ['read:asset'], permission_version: 1, data_mode: 'fixture' };
const userB = { ...userA, user_id: 'review-user-b', tenant_id: 'review-tenant-b', role: 'viewer', permissions: ['read:public'] };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
function Harness() { const session = useAuthSession(); return <><output data-testid="state">{JSON.stringify(session.state)}</output><output data-testid="error">{session.error?.code}</output><output data-testid="unconfirmed">{String(session.logoutUnconfirmed)}</output><button onClick={() => void session.logout()}>logout</button><button onClick={() => void session.refreshSession()}>refresh</button><button onClick={() => void session.login('fixture-a', 'fixture-password')}>login</button></>; }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('independent atomic auth snapshot recheck', () => {
  it('never acquires B nonce to revoke B after sampling A', async () => {
    const nonceA = randomBytes(32).toString('hex');
    const nonceB = randomBytes(32).toString('hex');
    let changedCookie = false;
    let csrfReads = 0;
    let revokedB = false;
    let sentNonce = '';
    vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
      if (path.endsWith('/me')) { changedCookie = true; return response({ ...userA, csrf_token: nonceA }); }
      if (path.endsWith('/csrf')) { csrfReads += 1; return response({ csrf_token: nonceB, header_name: 'X-CSRF-Token' }); }
      sentNonce = new Headers(options?.headers).get('X-CSRF-Token') ?? '';
      if (changedCookie && sentNonce === nonceB) { revokedB = true; return response({ status: 'logged_out' }); }
      return response({ error: { code: 'csrf_rejected', retryable: false } }, 403);
    }));
    render(<AuthProvider><Harness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-user-a'));
    fireEvent.click(screen.getByText('logout'));
    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('csrf_rejected'));
    expect(sentNonce).toBe(nonceA);
    expect(revokedB).toBe(false);
    expect(csrfReads).toBe(0);
    expect(screen.getByTestId('state').textContent).not.toContain('review-tenant-a');
    expect(screen.getByTestId('unconfirmed').textContent).toBe('true');
    console.log(JSON.stringify({ probe: 'A-snapshot-cookie-B', csrfReads, revokedB, oldNonceWasSent: sentNonce === nonceA }));
  });

  it('does not refill a logout from a delayed older me snapshot', async () => {
    const nonce = randomBytes(32).toString('hex');
    let releaseOld: (value: Response) => void = () => { throw new Error('not started'); };
    const old = new Promise<Response>((resolve) => { releaseOld = resolve; });
    let meReads = 0;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      if (path.endsWith('/me')) { meReads += 1; return meReads === 1 ? old : response({ ...userA, csrf_token: nonce }); }
      if (path.endsWith('/csrf')) throw new Error('separate csrf request forbidden in snapshot flow');
      return response({ status: 'logged_out' });
    }));
    render(<AuthProvider><Harness /></AuthProvider>);
    await waitFor(() => expect(meReads).toBe(1));
    fireEvent.click(screen.getByText('refresh'));
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-user-a'));
    fireEvent.click(screen.getByText('logout'));
    releaseOld(response({ ...userA, csrf_token: nonce }));
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('{"kind":"anonymous"}'));
  });

  it('rejects missing snapshot nonce without falling back to another request', async () => {
    let csrfReads = 0;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => { if (path.endsWith('/csrf')) csrfReads += 1; return response(userA); }));
    render(<AuthProvider><Harness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('invalid_response'));
    expect(screen.getByTestId('state').textContent).toBe('{"kind":"anonymous"}');
    expect(csrfReads).toBe(0);
  });

  it('rejects an account switch between login and its snapshot', async () => {
    const nonce = randomBytes(32).toString('hex');
    let loggedIn = false;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      if (path.endsWith('/login')) { loggedIn = true; return response({ user_id: userA.user_id, csrf_token: nonce, expires_at: '2099-01-01T00:00:00+08:00' }); }
      return loggedIn ? response({ ...userB, csrf_token: nonce }) : response({ error: { code: 'unauthenticated' } }, 401);
    }));
    render(<AuthProvider><Harness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('{"kind":"anonymous"}'));
    fireEvent.click(screen.getByText('login'));
    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('invalid_response'));
    expect(screen.getByTestId('state').textContent).not.toContain('review-tenant-b');
  });

  it('takes the replacement nonce from a same-user snapshot and keeps it out of public user state', async () => {
    const original = randomBytes(32).toString('hex');
    const replacement = randomBytes(32).toString('hex');
    let loggedIn = false;
    let sentNonce = '';
    vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
      if (path.endsWith('/login')) { loggedIn = true; return response({ user_id: userA.user_id, csrf_token: original, expires_at: '2099-01-01T00:00:00+08:00' }); }
      if (path.endsWith('/me')) return loggedIn ? response({ ...userA, csrf_token: replacement }) : response({ error: { code: 'unauthenticated' } }, 401);
      sentNonce = new Headers(options?.headers).get('X-CSRF-Token') ?? '';
      return response({ status: 'logged_out' });
    }));
    render(<AuthProvider><Harness /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('{"kind":"anonymous"}'));
    fireEvent.click(screen.getByText('login'));
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('review-user-a'));
    expect(screen.getByTestId('state').textContent).not.toContain(replacement);
    fireEvent.click(screen.getByText('logout'));
    await waitFor(() => expect(sentNonce).toBe(replacement));
  });
});
