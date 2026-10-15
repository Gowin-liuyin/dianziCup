import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { ApiProblem, getSessionSnapshot, loginSession, logoutSession, publicProblem, type CurrentUser } from "../api/client";

type SessionState = { kind: "loading" } | { kind: "anonymous" } | { kind: "authenticated"; user: CurrentUser };

interface SessionContext {
  state: SessionState;
  actionPending: boolean;
  error: ApiProblem | null;
  logoutUnconfirmed: boolean;
  sessionGeneration: number;
  refreshSession: (signal?: AbortSignal) => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  expireSession: (expectedGeneration: number) => void;
  isSessionCurrent: (expectedGeneration: number) => boolean;
}

const AuthContext = createContext<SessionContext | null>(null);

/** 会话令牌仅由 HttpOnly Cookie 传递；CSRF 保存在内存，代次阻止旧请求恢复已清除身份。 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ kind: "loading" });
  const [error, setError] = useState<ApiProblem | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const [logoutUnconfirmed, setLogoutUnconfirmed] = useState(false);
  const csrfToken = useRef<string | null>(null);
  const requestGeneration = useRef(0);

  const refreshSession = useCallback(async (signal?: AbortSignal) => {
    const generation = ++requestGeneration.current;
    csrfToken.current = null;
    setState({ kind: "loading" });
    setError(null);
    setLogoutUnconfirmed(false);
    try {
      const snapshot = await getSessionSnapshot(signal);
      if (generation !== requestGeneration.current || signal?.aborted) return;
      csrfToken.current = snapshot.csrfToken;
      setState({ kind: "authenticated", user: snapshot.user });
    } catch (failure: unknown) {
      if (generation !== requestGeneration.current || signal?.aborted) return;
      const problem = publicProblem(failure);
      setState({ kind: "anonymous" });
      if (problem.status !== 401 || problem.code === "session_expired") setError(problem);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refreshSession(controller.signal);
    return () => { requestGeneration.current += 1; controller.abort(); };
  }, [refreshSession]);

  const login = useCallback(async (username: string, password: string) => {
    const generation = ++requestGeneration.current;
    csrfToken.current = null;
    setActionPending(true);
    setError(null);
    setLogoutUnconfirmed(false);
    try {
      const session = await loginSession(username, password);
      const snapshot = await getSessionSnapshot();
      if (session.user_id !== snapshot.user.user_id) throw new ApiProblem(502, "invalid_response", true);
      if (generation !== requestGeneration.current) return;
      csrfToken.current = snapshot.csrfToken;
      setState({ kind: "authenticated", user: snapshot.user });
    } catch (failure: unknown) {
      if (generation !== requestGeneration.current) return;
      setState({ kind: "anonymous" });
      setError(publicProblem(failure));
    } finally {
      if (generation === requestGeneration.current) setActionPending(false);
    }
  }, []);

  const logout = useCallback(async () => {
    const generation = ++requestGeneration.current;
    const token = csrfToken.current;
    csrfToken.current = null;
    setState({ kind: "anonymous" });
    setActionPending(true);
    setError(null);
    setLogoutUnconfirmed(false);
    try {
      if (token === null) throw new ApiProblem(401, "session_expired", false);
      await logoutSession(token);
    } catch (failure: unknown) {
      if (generation !== requestGeneration.current) return;
      setLogoutUnconfirmed(true);
      setError(publicProblem(failure));
    } finally {
      if (generation === requestGeneration.current) setActionPending(false);
    }
  }, []);

  const isSessionCurrent = useCallback((expectedGeneration: number) => requestGeneration.current === expectedGeneration && csrfToken.current !== null, []);

  const expireSession = useCallback((expectedGeneration: number) => {
    if (!isSessionCurrent(expectedGeneration)) return;
    requestGeneration.current += 1;
    csrfToken.current = null;
    setState({ kind: "anonymous" });
    setError(new ApiProblem(401, "session_expired", false));
    setActionPending(false);
    setLogoutUnconfirmed(false);
  }, [isSessionCurrent]);

  return <AuthContext.Provider value={{ state, error, actionPending, logoutUnconfirmed, sessionGeneration: requestGeneration.current, refreshSession, login, logout, expireSession, isSessionCurrent }}>{children}</AuthContext.Provider>;
}

export function useAuthSession(): SessionContext {
  const context = useContext(AuthContext);
  if (context === null) throw new Error("AuthProvider is required");
  return context;
}
