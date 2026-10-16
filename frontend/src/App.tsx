import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { getLiveness, getReadiness, publicProblem, type ApiProblem, type CurrentUser, type Readiness } from "./api/client";
import { AuthProvider, useAuthSession } from "./app/auth-session";
import { formatShanghaiTimestamp } from "./app/date-time";
import { readAssetSelection, readGraphSelection, readWorkspacePage, workspacePages, type WorkspacePage } from "./app/workspace-navigation";
import { EmptyState, ErrorPanel, StatusBadge } from "./components/status";
import { AmbientBackdrop } from "./components/ambient-backdrop";
import { CapabilityWorkspace } from "./features/preparation/capability-workspace";
import { EventWorkspace } from "./features/events/event-workspace";
import { SourceWorkspace } from "./features/sources/source-workspace";
import { QuestionWorkspace } from "./features/questions/question-workspace";
import { DocumentWorkspace } from "./features/documents/document-workspace";
import { GraphExplorerView } from "./features/graph/graph-explorer-view";
import { AssetWorkspace } from "./features/assets/asset-workspace";
import { AssessmentWorkspace } from "./features/assessments/AssessmentWorkspace";
import { InvestigationWorkspace } from "./features/investigations/InvestigationWorkspace";
import { readInvestigationRoute } from "./features/investigations/investigation-contracts";
import { RecommendationWorkspace, ReportWorkspace } from "./features/recommendations/recommendation-workspace";
import { readQuestionRoute } from "./api/question-contracts";
import "./styles.css";

type HealthState = { kind: "loading" } | { kind: "checked"; live: boolean; readiness: Readiness | null; errors: ApiProblem[]; checkedAt: string };

const dependencyNames: Record<string, string> = { database: "数据库", cache: "缓存服务", search: "搜索服务", redis: "缓存服务", opensearch: "搜索服务", worker: "任务进程", scheduler: "调度进程" };
const roleNames: Record<CurrentUser["role"], string> = { viewer: "查看者", analyst: "分析员", tenant_admin: "租户管理员", system_admin: "系统管理员" };

function modeLabel(user: CurrentUser | undefined): string {
  if (user === undefined) return "登录后确认";
  return user.data_mode === "live" ? "真实 / Live" : "合成 / Fixture";
}

function readinessLabel(health: HealthState): string {
  if (health.kind === "loading") return "正在检查";
  if (health.readiness?.status === "ready") return "全部依赖就绪";
  if (health.readiness?.status === "degraded") return "部分不可用";
  if (health.readiness?.status === "not_ready") return "尚未就绪";
  return "状态未知";
}

function SessionPanel() {
  const { state, error, actionPending, logoutUnconfirmed, login, logout, refreshSession } = useAuthSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  let sessionLabel = "尚未登录";
  if (state.kind === "authenticated") sessionLabel = "已认证";
  if (state.kind === "loading") sessionLabel = "恢复中";

  function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedPassword = password;
    setPassword("");
    setUsername("");
    void login(username, submittedPassword);
  }

  return (
    <section className="panel session-panel" id="session" aria-labelledby="session-title">
      <div className="panel-heading">
        <div><p className="eyebrow">ACCESS / 访问</p><h2 id="session-title">团队会话</h2></div>
        <span className="small-note">{sessionLabel}</span>
      </div>
      {state.kind === "loading" && <p className="loading-state" role="status">正在检查当前会话…</p>}
      {state.kind === "authenticated" && (
        <div className="account-content">
          <p className="account-role">{roleNames[state.user.role]}</p>
          <dl className="identity-list">
            <dt>当前用户</dt><dd><code>{state.user.user_id}</code></dd>
            <dt>所属租户</dt><dd><code>{state.user.tenant_id ?? "未关联租户"}</code></dd>
          </dl>
          <h3>已授予权限</h3>
          {state.user.permissions.length === 0 ? (
            <EmptyState title="未授予业务权限" description="请联系团队管理员核对账号授权。" />
          ) : (
            <ul className="permission-list">{state.user.permissions.map((permission) => <li key={permission}><code>{permission}</code></li>)}</ul>
          )}
          <p className="small-note">权限版本 {state.user.permission_version}</p>
          <div className="session-actions">
            <button className="button secondary" disabled={actionPending} onClick={() => void refreshSession()}>重新验证会话</button>
            <button className="button" disabled={actionPending} onClick={() => void logout()}>退出登录</button>
          </div>
        </div>
      )}
      {state.kind === "anonymous" && (
        <div className="login-content">
          <p>使用管理员为你创建的团队账号。</p>
          <form onSubmit={submitLogin}>
            <label htmlFor="username">用户名</label>
            <input id="username" name="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} disabled={actionPending} required maxLength={256} />
            <label htmlFor="password">密码</label>
            <input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={actionPending} required maxLength={1024} />
            <button className="button login-button" type="submit" disabled={actionPending}>{actionPending ? "提交中…" : "登录工作台"}<span aria-hidden="true">→</span></button>
          </form>
        </div>
      )}
      {error && <ErrorPanel error={error} message={logoutUnconfirmed ? "退出未完成，服务端会话撤销尚未确认。当前页面已清除身份信息。" : undefined} onRetry={actionPending ? undefined : () => void refreshSession()} retryLabel="重新检查会话" />}
    </section>
  );
}

function DependencyDetails({ health }: { health: HealthState }) {
  if (health.kind === "loading") return <p className="loading-state" role="status">正在获取实际依赖状态…</p>;
  const readiness = health.readiness;
  if (readiness === null) return <EmptyState title="依赖状态尚未取得" description="检查未完成，不能判断服务已经就绪。" />;
  return (
    <>
      <div className="table-scroll">
        <table aria-label="实际依赖探测结果">
          <thead><tr><th scope="col">依赖</th><th scope="col">状态</th><th scope="col">探测说明</th></tr></thead>
          <tbody>{Object.entries(readiness.dependencies).map(([name, dependency]) => (
            <tr key={name}>
              <th scope="row">{Object.hasOwn(dependencyNames, name) ? dependencyNames[name] : name}<span className="dependency-key">{name}</span></th>
              <td><StatusBadge state={dependency.state} /></td>
              <td className="dependency-reason">{dependency.reason || "服务端未提供附加说明"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {Object.keys(readiness.dependencies).length === 0 && <EmptyState title="没有依赖探测项" description="服务没有提供逐项结果，不能据此确认基础设施正常。" />}
      {readiness.status !== "ready" && <p className="readiness-note">服务尚未全部就绪。可查看逐项说明，恢复依赖后重新检查。</p>}
    </>
  );
}

function Workbench() {
  const { state, sessionGeneration, expireSession, isSessionCurrent } = useAuthSession();
  const [hash, setHash] = useState(() => window.location.hash);
  const questionRoute = readQuestionRoute(hash);
  const graphRoute = readGraphSelection(hash);
  const assetRoute = readAssetSelection(hash);
  const investigationRoute = readInvestigationRoute(hash);
  let page: WorkspacePage | "missing" = readWorkspacePage(hash);
  if (questionRoute !== null) page = "questions";
  if (investigationRoute !== null) page = "investigations";
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });
  const healthGeneration = useRef(0);

  const refreshHealth = useCallback(async (signal?: AbortSignal) => {
    const generation = ++healthGeneration.current;
    setHealth({ kind: "loading" });
    const [liveness, readiness] = await Promise.allSettled([getLiveness(signal), getReadiness(signal)]);
    if (generation !== healthGeneration.current || signal?.aborted) return;
    const errors: ApiProblem[] = [];
    if (liveness.status === "rejected") errors.push(publicProblem(liveness.reason));
    if (readiness.status === "rejected") errors.push(publicProblem(readiness.reason));
    setHealth({ kind: "checked", live: liveness.status === "fulfilled", readiness: readiness.status === "fulfilled" ? readiness.value : null, errors, checkedAt: new Date().toISOString() });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refreshHealth(controller.signal);
    return () => { healthGeneration.current += 1; controller.abort(); };
  }, [refreshHealth]);

  useEffect(() => {
    const navigate = () => setHash(window.location.hash);
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);

  const readiness = health.kind === "checked" ? health.readiness : null;
  const dataMode = modeLabel(state.kind === "authenticated" ? state.user : undefined);
  const currentPage = page === "missing" ? null : workspacePages[page];
  const sessionScopeKey = state.kind === "authenticated" ? JSON.stringify([state.user.user_id, state.user.tenant_id, state.user.permission_version, state.user.data_mode, sessionGeneration]) : state.kind;
  const isAssessmentSessionCurrent = useCallback(() => isSessionCurrent(sessionGeneration), [isSessionCurrent, sessionGeneration]);
  const handleAssessmentFailure = useCallback((error: ApiProblem) => {
    if (error.status === 401) expireSession(sessionGeneration);
  }, [expireSession, sessionGeneration]);
  let processLabel = "无法确认";
  if (health.kind === "loading") processLabel = "检查中";
  if (health.kind === "checked" && health.live) processLabel = "可响应";

  return (
    <div className="workbench-shell">
      <AmbientBackdrop />
      <a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById("main-content")?.focus(); }}>跳到主要内容</a>
      <aside className="sidebar">
        <a className="brand" href="#runtime"><span className="brand-mark" aria-hidden="true">DI<span /></span><span>安全情报<span className="brand-caption">DEFENSE INTELLIGENCE</span></span></a>
        <nav aria-label="工作台导航">
          {(["研究", "协作", "系统"] as const).map((group) => <div className="nav-group" key={group}><p className="nav-group-label">{group}</p>{Object.entries(workspacePages).filter(([, definition]) => definition.group === group).map(([key, definition]) => <a key={key} className={`nav-link ${page === key ? "active" : ""}`} href={`#${key}`} aria-current={page === key ? "page" : undefined}><span aria-hidden="true">{definition.symbol}</span>{definition.label}</a>)}</div>)}
        </nav>
        <div className="sidebar-note"><p>可追溯的事实<br />清晰的判断边界</p><span className="small-note">AI 安全知识情报系统</span><code>READ · VERIFY · CONNECT</code></div>
      </aside>
      <div className="workspace">
        <header className="topbar"><span className="workspace-crumb"><span aria-hidden="true" className="terminal-prompt">&gt;</span>工作台 <span aria-hidden="true">/</span> {currentPage?.label ?? "页面未找到"}</span><span className="mode-label">数据模式 <strong>{dataMode}</strong></span></header>
        <main id="main-content" tabIndex={-1}>
          <div className="page-heading">
            <div><p className="eyebrow">{currentPage?.code ?? "WORKSPACE / UNKNOWN"}</p><h1>{currentPage?.title ?? "页面未找到"}<span className="heading-point" aria-hidden="true">_</span></h1><p>{currentPage?.description ?? "当前地址没有对应工作区，可返回运行状态继续。"}</p></div>
            <button className="button secondary refresh-button" disabled={health.kind === "loading"} onClick={() => void refreshHealth()}><span aria-hidden="true">↻</span>刷新状态</button>
          </div>
          {page === "runtime" && <>
          <section className="status-strip" aria-label="当前运行摘要">
            <div><span className="eyebrow">PROCESS / API 进程</span><strong><span className={`summary-mark ${health.kind === "checked" && health.live ? "is-live" : ""}`} aria-hidden="true" />{processLabel}</strong><span className="small-note">存活不代表依赖已就绪</span></div>
            <div><span className="eyebrow">DEPENDENCIES / 依赖就绪</span><strong>{readinessLabel(health)}</strong><span className="small-note">基于服务端实际探测结果</span></div>
            <div><span className="eyebrow">DATA / 数据模式</span><strong>{dataMode}</strong><span className="small-note">模式与业务验证状态分别呈现</span></div>
          </section>
          <div className="content-grid">
            <section className="panel runtime-panel" id="runtime" aria-labelledby="runtime-title">
              <div className="panel-heading"><div><p className="eyebrow">RUNTIME / 运行</p><h2 id="runtime-title">服务与依赖</h2></div><StatusBadge state={health.kind === "loading" ? "loading" : readiness?.status ?? "unknown"} /></div>
              <DependencyDetails health={health} />
              {health.kind === "checked" && health.errors.length > 0 && <ErrorPanel error={health.errors[0] ?? publicProblem(null)} message="健康探测未完成，请恢复连接后重新检查。" onRetry={() => void refreshHealth()} retryLabel="重新检查运行状态" />}
              {health.kind === "checked" && <p className="checked-time">本页检查于 <time dateTime={health.checkedAt}>{formatShanghaiTimestamp(health.checkedAt)}</time></p>}
            </section>
            <SessionPanel />
          </div>
          <section className="research-entry" aria-labelledby="research-entry-title"><div><p className="eyebrow">RESEARCH WORKSPACE</p><h2 id="research-entry-title">从线索到证据</h2><p>事件、原文版本与判断依据，在同一工作区核查。</p></div><a className="button secondary" href="#events">进入情报工作区<span aria-hidden="true">↗</span></a></section>
          </>}
          {page === "session" && <div className="session-workspace"><SessionPanel /><div className="access-guidance"><p className="eyebrow">TRUST BOUNDARY / 授权边界</p><h2>按权限查看<br />按证据判断</h2><p>登录后，身份与权限由服务端确认。会话失效或退出时，页面立即清除身份信息。</p><a href="#runtime" className="text-link">返回运行概览 →</a></div></div>}
          {page === "events" && <EventWorkspace key={sessionScopeKey} />}
          {page === "sources" && <SourceWorkspace key={sessionScopeKey} />}
          {page === "documents" && <DocumentWorkspace key={sessionScopeKey} />}
          {page === "questions" && <QuestionWorkspace key={`${sessionScopeKey}:${hash}`} eventId={questionRoute?.eventId} />}
          {page === "assets" && <AssetWorkspace key={sessionScopeKey} assetId={assetRoute?.assetId} />}
          {page === "assessments" && (state.kind === "authenticated" ? <AssessmentWorkspace key={sessionScopeKey} user={state.user} authScope={sessionScopeKey} isCurrent={isAssessmentSessionCurrent} onFailure={handleAssessmentFailure} onOpenEvent={(eventId, evidenceId) => { window.location.hash = evidenceId === undefined ? `#events/${eventId}` : `#events/${eventId}/evidence/${evidenceId}`; }} /> : <section className="panel"><EmptyState title={state.kind === "loading" ? "正在确认研判会话" : "登录后进行资产研判"} description="固定资产快照与规则的判断从当前授权范围读取。" /><a className="button secondary" href="#session">核对会话与权限</a></section>)}
          {page === "investigations" && <InvestigationWorkspace key={sessionScopeKey} user={state.kind === "authenticated" ? state.user : null} authScope={sessionScopeKey} isCurrent={isAssessmentSessionCurrent} onFailure={handleAssessmentFailure} initialJobId={investigationRoute?.jobId} onOpenEvent={(eventId, evidenceId) => { window.location.hash = evidenceId === undefined ? `#events/${eventId}` : `#events/${eventId}/evidence/${evidenceId}`; }} onOpenEvidence={(eventId, evidenceId, revisionId) => { window.location.hash = `#events/${eventId}/evidence/${evidenceId}/revision/${revisionId}`; }} />}
          {page === "changes" && <RecommendationWorkspace key={sessionScopeKey} />}
          {page === "reports" && <ReportWorkspace key={sessionScopeKey} />}
          {page === "graph" && (graphRoute === null ? <section className="panel"><EmptyState title="先选择一个事件" description="从情报详情进入证据关系图，核查该事件的关联理由与原文。" /><a className="button secondary" href="#events">进入情报列表</a></section> : <GraphExplorerView key={`${sessionScopeKey}:${graphRoute.eventId}`} eventId={graphRoute.eventId} dataMode={state.kind === "authenticated" ? state.user.data_mode : "unknown"} />)}
          {page !== "runtime" && page !== "session" && page !== "events" && page !== "sources" && page !== "documents" && page !== "questions" && page !== "assets" && page !== "assessments" && page !== "investigations" && page !== "graph" && page !== "changes" && page !== "reports" && page !== "missing" && <CapabilityWorkspace page={page} authenticated={state.kind === "authenticated"} />}
          {page === "missing" && <section className="panel missing-page"><EmptyState title="工作区不存在" description="请通过导航选择已登记页面。该地址没有触发业务请求。" /><a className="button secondary" href="#runtime">返回运行状态</a></section>}
          {state.kind === "authenticated" && <footer className="workspace-footer"><span>{state.user.app_env ? `环境 ${state.user.app_env}` : "环境未由服务端标明"}</span><span>{state.user.platform_version ? `版本 ${state.user.platform_version}` : "版本未由服务端标明"}</span></footer>}
        </main>
      </div>
    </div>
  );
}

/** 从真实认证与健康接口构建当前可用的工作台，不注入业务演示数据。 */
export function App() {
  return <AuthProvider><Workbench /></AuthProvider>;
}
