import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiProblem, publicProblem, type CurrentUser } from "../../api/client";
import { useAuthSession } from "../../app/auth-session";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { EmptyState } from "../../components/status";
import { createReport, createSubscription, downloadAuthorizedReport, exportReport, generateRecommendations, getRecommendations, getReport, getReports, getSubscription, getSubscriptions, markRecommendationRead, replaceSubscription, setSubscriptionEnabled, type RecommendationMutation } from "./recommendation-client";
import { RecommendationScopeMismatch, type RecommendationScope } from "./recommendation-contracts";
import { CurrentValidity, RecommendationContentView, currentValidityLabels } from "./recommendation-content";
import { ReportContentView } from "./report-content";
import { SubscriptionEditor, type SubscriptionDraft } from "./subscription-editor";
import { PrivateWorkspaceAccess, RecommendationError, RecommendationLoading } from "./workspace-state";
import type { GenerationResponse, PublicSubscriptionSpec, RecommendationPage, ReportPage, ReportReceipt, SubscriptionPage, SubscriptionRecord } from "./recommendation-wire-types";
import "./recommendations.css";

type Resource<T> = { kind: "loading" } | { kind: "loaded"; value: T } | { kind: "failed"; error: ApiProblem };
interface PrivateContext { scope: RecommendationScope; allowAssets: boolean; isCurrent: () => boolean; onFailure: (error: ApiProblem) => void }
function AuthorizedBoundary({ user, children }: { user: CurrentUser & { tenant_id: string }; children: (context: PrivateContext) => ReactNode }) {
  const { sessionGeneration, isSessionCurrent, expireSession } = useAuthSession();
  const invalidated = useRef(false);
  const [denied, setDenied] = useState<ApiProblem | null>(null);
  const isCurrent = useCallback(() => !invalidated.current && isSessionCurrent(sessionGeneration), [isSessionCurrent, sessionGeneration]);
  const onFailure = useCallback((error: ApiProblem) => {
    if (!isCurrent()) return;
    if (error.status === 401) expireSession(sessionGeneration);
    if (error instanceof RecommendationScopeMismatch || (error.status === 403 && error.code !== "csrf_rejected")) { invalidated.current = true; setDenied(error); }
  }, [isCurrent, expireSession, sessionGeneration]);
  const context = useMemo<PrivateContext>(() => ({ scope: { userId: user.user_id, tenantId: user.tenant_id, dataMode: user.data_mode }, allowAssets: user.permissions.includes("read:asset"), isCurrent, onFailure }), [user, isCurrent, onFailure]);
  if (denied !== null) return <section className="panel"><RecommendationError error={denied} /><div className="panel-actions"><a className="button secondary" href="#session">核对会话与权限</a></div></section>;
  return children(context);
}
function SessionBoundary({ children }: { children: (context: PrivateContext) => ReactNode }) {
  const { state, error, sessionGeneration } = useAuthSession();
  if (state.kind !== "authenticated") return <PrivateWorkspaceAccess loading={state.kind === "loading"} expired={error?.code === "session_expired"} title="登录后查看本人订阅与报告" />;
  if (state.user.tenant_id === null || !state.user.permissions.includes("read:public")) return <PrivateWorkspaceAccess loading={false} expired={false} title="当前会话需要 read:public 和明确租户范围" />;
  const user = { ...state.user, tenant_id: state.user.tenant_id };
  return <AuthorizedBoundary key={JSON.stringify([user.user_id, user.tenant_id, user.role, user.permission_version, user.data_mode, sessionGeneration])} user={user}>{children}</AuthorizedBoundary>;
}
function specFromDraft(draft: SubscriptionDraft): PublicSubscriptionSpec { return { product_keys: draft.productKeys, asset_ids: draft.assetIds, risk_topics: draft.riskTopics, minimum_priority: draft.maximumPriorityBucket, enabled: draft.enabled }; }
function draftFromRecord(record: SubscriptionRecord): SubscriptionDraft { return { productKeys: record.spec.product_keys, assetIds: record.spec.asset_ids, riskTopics: record.spec.risk_topics, maximumPriorityBucket: record.spec.maximum_priority_bucket, enabled: record.spec.enabled }; }
function PageActions({ cursor, pending, onNext, onFirst }: { cursor: string | null; pending: boolean; onNext: () => void; onFirst: () => void }) { return <div className="panel-actions"><button className="button secondary" disabled={pending} onClick={onFirst}>返回首页</button>{cursor !== null && <button className="button secondary" disabled={pending} onClick={onNext}>读取下一页</button>}</div>; }

function AuthorizedWorkspace({ context, mode }: { context: PrivateContext; mode: "recommendations" | "reports" }) {
  const { scope, isCurrent, onFailure, allowAssets } = context;
  const [subscriptions, setSubscriptions] = useState<Resource<SubscriptionPage>>({ kind: "loading" });
  const [subscriptionRequest, setSubscriptionRequest] = useState<{ cursor: string | null; retry: number }>({ cursor: null, retry: 0 });
  const [selected, setSelected] = useState<SubscriptionRecord | null>(null);
  const [editor, setEditor] = useState<"closed" | "create" | "edit">("closed");
  const [recommendations, setRecommendations] = useState<Resource<RecommendationPage>>({ kind: "loading" });
  const [hasUnavailableRecommendation, setHasUnavailableRecommendation] = useState(false);
  const [reports, setReports] = useState<Resource<ReportPage>>({ kind: "loading" });
  const [resultRequest, setResultRequest] = useState<{ cursor: string | null; retry: number }>({ cursor: null, retry: 0 });
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [reportDetail, setReportDetail] = useState<Resource<ReportReceipt> | null>(null);
  const [detailRetry, setDetailRetry] = useState(0);
  const [generation, setGeneration] = useState<GenerationResponse | null>(null);
  const [generationInput, setGenerationInput] = useState("");
  const [frequency, setFrequency] = useState<"day" | "week">("day");
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<{ operation: string; error: ApiProblem } | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);
  const controllers = useRef(new Set<AbortController>());
  const reportSection = useRef<HTMLDivElement>(null);
  const mutationKeys = useRef(new Map<string, { fingerprint: string; key: string }>());
  const subscriptionRecords = useRef(new Map<string, SubscriptionRecord>());
  const subscriptionReadEpoch = useRef(0);
  const subscriptionCatalogController = useRef<AbortController | null>(null);
  const recommendationReadEpoch = useRef(0);
  const recommendationController = useRef<AbortController | null>(null);
  useEffect(() => { const active = controllers.current; return () => { active.forEach((controller) => controller.abort()); active.clear(); }; }, []);
  const selectedId = selected?.subscription_id ?? null;
  const failed = useCallback((failure: unknown): ApiProblem => { const problem = publicProblem(failure); onFailure(problem); return problem; }, [onFailure]);
  const receiveSubscriptionRecord = useCallback((record: SubscriptionRecord, selectRecord = false) => {
    const previous = subscriptionRecords.current.get(record.subscription_id);
    const latest = previous !== undefined && previous.version >= record.version ? previous : record;
    subscriptionRecords.current.set(latest.subscription_id, latest);
    setSelected((current) => {
      if (selectRecord || current === null || current.subscription_id === latest.subscription_id) return latest;
      return current;
    });
    setSubscriptions((current) => {
      if (current.kind !== "loaded") return current;
      return { kind: "loaded", value: { ...current.value, items: current.value.items.map((item) => item.subscription_id === latest.subscription_id ? latest : item) } };
    });
    return latest;
  }, []);
  function markSubscriptionUnavailable(subscriptionId: string, error: ApiProblem) {
    subscriptionReadEpoch.current += 1;
    subscriptionCatalogController.current?.abort();
    subscriptionRecords.current.delete(subscriptionId);
    setSelected((current) => current?.subscription_id === subscriptionId ? null : current);
    setSubscriptions({ kind: "failed", error });
    setActionError(null);
    setHasUnavailableRecommendation(false);
  }
  function markRecommendationUnavailable(recommendationId: string, error: ApiProblem) {
    recommendationReadEpoch.current += 1;
    recommendationController.current?.abort();
    setHasUnavailableRecommendation(true);
    setRecommendations((current) => current.kind === "loaded" ? { kind: "loaded", value: { ...current.value, items: current.value.items.filter((item) => item.recommendation_id !== recommendationId) } } : { kind: "failed", error });
  }
  useEffect(() => {
    const controller = new AbortController(); const readEpoch = subscriptionReadEpoch.current;
    subscriptionCatalogController.current = controller; setSubscriptions({ kind: "loading" });
    void getSubscriptions(scope, subscriptionRequest.cursor, controller.signal).then((page) => {
      if (!controller.signal.aborted && readEpoch === subscriptionReadEpoch.current && isCurrent()) {
        const items = page.items.map((record) => receiveSubscriptionRecord(record));
        setSubscriptions({ kind: "loaded", value: { ...page, items } });
      }
    }).catch((failure: unknown) => { if (!controller.signal.aborted && readEpoch === subscriptionReadEpoch.current && isCurrent()) setSubscriptions({ kind: "failed", error: failed(failure) }); });
    return () => { controller.abort(); if (subscriptionCatalogController.current === controller) subscriptionCatalogController.current = null; };
  }, [scope, subscriptionRequest, isCurrent, failed, receiveSubscriptionRecord]);
  useEffect(() => {
    const controller = new AbortController();
    if (selectedId === null) return () => controller.abort();
    if (mode === "recommendations") {
      const readEpoch = recommendationReadEpoch.current; recommendationController.current = controller;
      setRecommendations({ kind: "loading" });
      void getRecommendations(scope, selectedId, resultRequest.cursor, controller.signal).then((value) => {
        if (!controller.signal.aborted && readEpoch === recommendationReadEpoch.current && isCurrent()) { setRecommendations({ kind: "loaded", value }); setHasUnavailableRecommendation(false); setActionError((current) => current?.operation.startsWith("read:") ? null : current); }
      }).catch((failure: unknown) => { if (!controller.signal.aborted && readEpoch === recommendationReadEpoch.current && isCurrent()) setRecommendations({ kind: "failed", error: failed(failure) }); });
    }
    else { setReports({ kind: "loading" }); void getReports(scope, selectedId, resultRequest.cursor, controller.signal).then((value) => { if (!controller.signal.aborted && isCurrent()) setReports({ kind: "loaded", value }); }).catch((failure: unknown) => { if (!controller.signal.aborted && isCurrent()) setReports({ kind: "failed", error: failed(failure) }); }); }
    return () => { controller.abort(); if (recommendationController.current === controller) recommendationController.current = null; };
  }, [scope, selectedId, mode, resultRequest, isCurrent, failed]);
  useEffect(() => {
    const controller = new AbortController();
    if (selectedId === null || selectedReportId === null) return () => controller.abort();
    setReportDetail({ kind: "loading" });
    void getReport(scope, selectedId, selectedReportId, controller.signal).then((value) => { if (!controller.signal.aborted && isCurrent()) setReportDetail({ kind: "loaded", value }); }).catch((failure: unknown) => { if (!controller.signal.aborted && isCurrent()) setReportDetail({ kind: "failed", error: failed(failure) }); });
    return () => controller.abort();
  }, [scope, selectedId, selectedReportId, detailRetry, isCurrent, failed]);
  useEffect(() => { if (reportDetail?.kind === "loaded") { reportSection.current?.focus({ preventScroll: true }); reportSection.current?.scrollIntoView?.({ block: "start", behavior: "instant" }); } }, [selectedReportId, reportDetail?.kind]);
  function refreshResults() { setResultRequest((value) => ({ cursor: null, retry: value.retry + 1 })); setDetailRetry((value) => value + 1); }
  function selectSubscription(record: SubscriptionRecord) { if (selected?.subscription_id !== record.subscription_id) setHasUnavailableRecommendation(false); receiveSubscriptionRecord(record, true); setRecommendations({ kind: "loading" }); setReports({ kind: "loading" }); setResultRequest({ cursor: null, retry: 0 }); setSelectedReportId(null); setReportDetail(null); setGeneration(null); setGenerationInput(""); setEditor("closed"); setActionError(null); setReceipt(null); }
  async function mutate<T>(operation: string, payload: unknown, send: (mutation: RecommendationMutation) => Promise<T>, succeeded: (value: T) => void) {
    if (pending || !isCurrent()) return;
    const fingerprint = JSON.stringify(payload); const existing = mutationKeys.current.get(operation);
    const key = existing?.fingerprint === fingerprint ? existing.key : crypto.randomUUID(); mutationKeys.current.set(operation, { fingerprint, key });
    const controller = new AbortController(); controllers.current.add(controller); setPending(true); setActionError(null); setReceipt(null);
    try { const value = await send({ idempotencyKey: key, signal: controller.signal, isCurrent }); if (!controller.signal.aborted && isCurrent()) { mutationKeys.current.delete(operation); succeeded(value); } }
    catch (failure: unknown) { if (!controller.signal.aborted && isCurrent()) { const error = failed(failure); setActionError({ operation, error }); if (error.status === 404 && operation.startsWith("read:")) markRecommendationUnavailable(operation.slice("read:".length), error); } }
    finally { controllers.current.delete(controller); if (!controller.signal.aborted && isCurrent()) setPending(false); }
  }
  function saveDraft(draft: SubscriptionDraft, expectedVersion: number | null) {
    const spec = specFromDraft(draft); const record = selected;
    if (editor === "create") void mutate("create", { spec }, (mutation) => createSubscription(scope, { spec }, mutation), (result) => { selectSubscription(result); setReceipt(`服务端已创建订阅，版本 ${result.version}。`); setSubscriptionRequest((value) => ({ cursor: null, retry: value.retry + 1 })); });
    else if (record !== null && expectedVersion !== null) { const body = { expected_version: expectedVersion, spec }; void mutate(`save:${record.subscription_id}`, body, (mutation) => replaceSubscription(scope, record.subscription_id, body, mutation), (result) => { receiveSubscriptionRecord(result); setEditor("closed"); setReceipt(`服务端已保存订阅版本 ${result.version}。`); setSubscriptionRequest((value) => ({ cursor: null, retry: value.retry + 1 })); refreshResults(); }); }
  }
  function refreshSubscription() {
    if (selected === null || pending) return;
    const controller = new AbortController(); const readEpoch = subscriptionReadEpoch.current; const subscriptionId = selected.subscription_id;
    controllers.current.add(controller); setPending(true);
    void getSubscription(scope, subscriptionId, controller.signal).then((record) => { if (!controller.signal.aborted && readEpoch === subscriptionReadEpoch.current && isCurrent()) { receiveSubscriptionRecord(record); setActionError(null); } }).catch((failure: unknown) => { if (!controller.signal.aborted && readEpoch === subscriptionReadEpoch.current && isCurrent()) { const error = failed(failure); if (error.status === 404) markSubscriptionUnavailable(subscriptionId, error); else setActionError({ operation: "refresh", error }); } }).finally(() => { controllers.current.delete(controller); if (!controller.signal.aborted && isCurrent()) setPending(false); });
  }
  function generate() { if (selected === null) return; const subscriptionId = selected.subscription_id; void mutate(`generate:${subscriptionId}`, { max_candidates: 200 }, (mutation) => generateRecommendations(scope, subscriptionId, 200, mutation), (result) => { setGeneration(result); setGenerationInput(result.generation_id); setReceipt(result.reused ? "已复用服务端生成批次。" : "服务端已完成本次推荐生成。"); refreshResults(); }); }
  function toggle() { if (selected === null) return; const record = selected; const body = { expected_version: record.version, enabled: !record.spec.enabled }; void mutate(`toggle:${record.subscription_id}`, body, (mutation) => setSubscriptionEnabled(scope, record.subscription_id, body, mutation), (result) => { receiveSubscriptionRecord(result); setReceipt(result.spec.enabled ? "服务端已启用订阅。" : "服务端已退订，保存的历史仍保留。"); setSubscriptionRequest((value) => ({ cursor: null, retry: value.retry + 1 })); refreshResults(); }); }
  function createSavedReport() { if (selected === null) return; const body = { subscription_id: selected.subscription_id, generation_id: generationInput, frequency, max_items: 20 }; void mutate(`report:${selected.subscription_id}`, body, (mutation) => createReport(scope, body, mutation), (result) => { setSelectedReportId(result.report_id); setReportDetail({ kind: "loaded", value: result }); setReceipt(result.reused ? "已复用服务端保存的报告。" : "服务端已保存报告。"); refreshResults(); }); }
  function download() { if (selected === null || selectedReportId === null || pending) return; const controller = new AbortController(); controllers.current.add(controller); setPending(true); setActionError(null); void exportReport(scope, selected.subscription_id, selectedReportId, controller.signal).then((result) => { if (!controller.signal.aborted && isCurrent()) { setReportDetail({ kind: "loaded", value: result }); downloadAuthorizedReport(result); setReceipt("已从本次授权核对响应导出 JSON。"); } }).catch((failure: unknown) => { if (!controller.signal.aborted && isCurrent()) { const error = failed(failure); setActionError({ operation: "export", error }); if (error.status === 404) setReportDetail(null); } }).finally(() => { controllers.current.delete(controller); if (!controller.signal.aborted && isCurrent()) setPending(false); }); }
  return <div className="recommendation-workspace">
    <div className="recommendation-banner"><p><span className="eyebrow">PERSONAL WATCH / 本人范围</span>{mode === "recommendations" ? "推荐由当前本人订阅与支持依据生成" : "冻结报告与本次有效性分别核对"}</p><span className="recommendation-tag">{scope.dataMode === "fixture" ? "合成 Fixture · 非真实情报" : "真实会话 · 服务端记录"}</span><button className="button secondary" disabled={pending} onClick={() => { refreshSubscription(); setSubscriptionRequest((value) => ({ cursor: null, retry: value.retry + 1 })); refreshResults(); }}>刷新本人记录</button></div>
    {receipt !== null && <p className="recommendation-receipt" role="status">{receipt}</p>}
    {actionError !== null && !(editor !== "closed" && (actionError.operation === "create" || actionError.operation.startsWith("save:"))) && <RecommendationError error={actionError.error} onRetry={actionError.error.status === 409 ? refreshSubscription : undefined} />}
    <div className="recommendation-layout"><section className="panel" aria-labelledby="personal-results-title"><div className="panel-heading"><div><p className="eyebrow">{mode === "recommendations" ? "RECOMMENDATIONS / 理由与依据" : "REPORTS / 历史目录"}</p><h2 id="personal-results-title">{mode === "recommendations" ? "本人推荐" : "日周报告历史"}</h2></div>{selected !== null && <code>{selected.subscription_id}</code>}</div>
      {selected === null ? <EmptyState title="选择或创建本人订阅" description="推荐与报告按明确的订阅范围读取。没有查询结果不能解释为无风险。" /> : <>
        <div className="recommendation-toolbar"><p className="small-note">订阅版本 {selected.version} · {selected.spec.enabled ? "已启用" : "已退订，历史保留"} · 优先级 P0 至 P{selected.spec.maximum_priority_bucket}</p><div className="filter-actions"><button className="button" disabled={pending || !selected.spec.enabled} onClick={generate}>生成当前推荐</button><a className="button secondary" href={mode === "recommendations" ? "#reports" : "#changes"}>{mode === "recommendations" ? "查看证据报告" : "查看本人推荐"}</a></div></div>
        {generation !== null && <div className="recommendation-generation"><p>生成批次 <code>{generation.generation_id}</code> · 保存 {generation.recommendation_ids.length} 项{generation.reused ? " · 已复用" : ""}</p>{generation.partial && <p className="recommendation-boundary">输入或候选范围为部分结果，不能视为完整覆盖。</p>}{generation.gaps.length > 0 && <details><summary>服务端证据缺口 {generation.gaps.length} 项</summary><ul>{generation.gaps.map((gap, index) => <li key={`${gap.code}:${index}`}><code>{gap.code}</code>{gap.event_id !== null && <> · 事件 <code>{gap.event_id}</code></>}</li>)}</ul></details>}</div>}
        {mode === "recommendations" && <>{hasUnavailableRecommendation && <p className="recommendation-boundary" role="status">部分推荐当前不可读取，已隐藏其内容；这不表示没有风险。</p>}{recommendations.kind === "loading" && <RecommendationLoading description="正在读取本人推荐与当前有效性…" />}{recommendations.kind === "failed" && <RecommendationError error={recommendations.error} collection onRetry={refreshResults} />}{recommendations.kind === "loaded" && <>{recommendations.value.items.length === 0 && <EmptyState title={hasUnavailableRecommendation ? "当前页推荐暂不可读取" : "本页未返回推荐"} description={hasUnavailableRecommendation ? "当前页的部分记录未通过可访问性核对。可重新查询；这不能解释为无风险。" : "这是当前订阅的成功空查询，不能解释为无风险。可核对订阅范围，或生成当前推荐。"} />}<ul className="recommendation-list">{recommendations.value.items.map((record) => <li key={record.recommendation_id}><CurrentValidity status={record.current_status} reason={record.current_reason} checkedAt={record.current_checked_at} /><RecommendationContentView content={record.content} /><div className="subscription-actions"><span className="small-note">{record.read_at === null ? "未读" : `已读 · ${formatShanghaiTimestamp(record.read_at)}`}</span><button className="button secondary" disabled={pending || record.read_at !== null} onClick={() => void mutate(`read:${record.recommendation_id}`, { subscription_id: selected.subscription_id }, (mutation) => markRecommendationRead(scope, selected.subscription_id, record.recommendation_id, mutation), (result) => { setRecommendations((current) => current.kind === "loaded" ? { kind: "loaded", value: { ...current.value, items: current.value.items.map((item) => item.recommendation_id === result.recommendation_id ? result : item) } } : current); setReceipt("服务端已确认推荐已读。"); })}>标记已读</button></div></li>)}</ul><p className="recommendation-page-note small-note">本页 {recommendations.value.items.length} 项{recommendations.value.next_cursor === null ? " · 当前查询已到末页" : " · 尚有后续页"}，不是全部范围的风险统计。</p><PageActions cursor={recommendations.value.next_cursor} pending={pending} onFirst={refreshResults} onNext={() => setResultRequest((value) => ({ cursor: recommendations.value.next_cursor, retry: value.retry + 1 }))} /></>}</>}
        {mode === "reports" && <><form className="recommendation-toolbar" onSubmit={(event) => { event.preventDefault(); createSavedReport(); }} aria-label="生成日周报告"><label>既有生成批次 UUID<input value={generationInput} onChange={(event) => setGenerationInput(event.target.value)} maxLength={36} disabled={pending} required /></label><label>报告周期<select value={frequency} onChange={(event) => { if (event.target.value === "day" || event.target.value === "week") setFrequency(event.target.value); }} disabled={pending}><option value="day">日报</option><option value="week">周报</option></select></label><p className="small-note">先生成当前推荐取得批次；报告截止时刻来自该批次，表单不能改写历史截止时间。</p><button className="button" type="submit" disabled={pending}>保存日周报告</button></form>
          {reports.kind === "loading" && <RecommendationLoading description="正在读取本人报告历史…" />}{reports.kind === "failed" && <RecommendationError error={reports.error} collection onRetry={refreshResults} />}{reports.kind === "loaded" && <>{reports.value.items.length === 0 && <EmptyState title="本页未返回保存的报告" description="可从本人生成批次保存日报或周报。空报告目录不证明没有风险。" />}<ul className="report-list">{reports.value.items.map((record) => <li key={record.report_id}><button className="report-selection" disabled={pending} aria-pressed={selectedReportId === record.report_id} onClick={() => setSelectedReportId(record.report_id)}><strong>{record.content.report.frequency === "day" ? "日报" : "周报"} · {formatShanghaiTimestamp(record.content.report.cutoff_at)}</strong><code className="report-id">{record.report_id}</code></button><span className={`recommendation-tag is-${record.current_status}`}>{currentValidityLabels[record.current_status]}</span></li>)}</ul><p className="recommendation-page-note small-note">本页 {reports.value.items.length} 份保存记录，服务端顺序保留。</p><PageActions cursor={reports.value.next_cursor} pending={pending} onFirst={refreshResults} onNext={() => setResultRequest((value) => ({ cursor: reports.value.next_cursor, retry: value.retry + 1 }))} /></>}
          {reportDetail?.kind === "loading" && <RecommendationLoading description="正在重新核对所选报告…" />}{reportDetail?.kind === "failed" && <RecommendationError error={reportDetail.error} onRetry={() => setDetailRetry((value) => value + 1)} />}{reportDetail?.kind === "loaded" && <div ref={reportSection} className="report-detail" tabIndex={-1}><div className="panel-heading"><h2>报告内容与当前状态</h2><button className="button" disabled={pending} onClick={download}>授权核对并导出 JSON</button></div><div className="report-content"><CurrentValidity status={reportDetail.value.current_status} reason={reportDetail.value.current_reason} checkedAt={reportDetail.value.current_checked_at} /><p className="small-note">不可变内容校验 <code>{reportDetail.value.content_sha256}</code></p>{reportDetail.value.content.gaps.length > 0 && <p className="recommendation-boundary">该报告保存了 {reportDetail.value.content.gaps.length} 项证据缺口，历史内容仍需结合限制阅读。</p>}</div><ReportContentView report={reportDetail.value.content.report} /></div>}
        </>}
      </>}
    </section><aside className="panel" aria-labelledby="subscription-catalog-title"><div className="panel-heading"><div><p className="eyebrow">SUBSCRIPTIONS / 明确兴趣</p><h2 id="subscription-catalog-title">本人订阅</h2></div><button className="button secondary" disabled={pending} onClick={() => { setEditor("create"); setActionError(null); }}>新建订阅</button></div>
      {subscriptions.kind === "loading" && <RecommendationLoading description="正在读取本人订阅…" />}{subscriptions.kind === "failed" && <RecommendationError error={subscriptions.error} collection onRetry={() => setSubscriptionRequest((value) => ({ ...value, retry: value.retry + 1 }))} />}{subscriptions.kind === "loaded" && <>{subscriptions.value.items.length === 0 && <EmptyState title="本页未返回本人订阅" description="创建产品、主题或授权资产关注后，才有明确的推荐范围。" />}<ul className="subscription-list">{subscriptions.value.items.map((record) => <li key={record.subscription_id}><button className="report-selection" disabled={pending} aria-pressed={selected?.subscription_id === record.subscription_id} onClick={() => selectSubscription(record)}><strong>{record.spec.product_keys.join("、") || record.spec.risk_topics.join("、") || "授权资产关注"}</strong><code className="report-id">{record.subscription_id}</code></button><p className="small-note">版本 {record.version} · {record.spec.enabled ? "已启用" : "已退订"} · P0 至 P{record.spec.maximum_priority_bucket}</p></li>)}</ul><PageActions cursor={subscriptions.value.next_cursor} pending={pending} onFirst={() => setSubscriptionRequest((value) => ({ cursor: null, retry: value.retry + 1 }))} onNext={() => setSubscriptionRequest((value) => ({ cursor: subscriptions.value.next_cursor, retry: value.retry + 1 }))} /></>}
      {selected !== null && editor === "closed" && <div className="panel-actions"><button className="button secondary" disabled={pending} onClick={() => { setEditor("edit"); setActionError(null); }}>编辑当前订阅</button><button className="button secondary" disabled={pending} onClick={toggle}>{selected.spec.enabled ? "退订并保留历史" : "重新启用订阅"}</button></div>}
      {editor !== "closed" && (editor === "create" || selected !== null) && <SubscriptionEditor key={editor === "create" ? "new" : selected?.subscription_id} initialDraft={editor === "create" || selected === null ? undefined : draftFromRecord(selected)} currentVersion={editor === "create" ? null : selected?.version} pending={pending} canSubmit allowAssetSelectors={allowAssets} error={actionError?.operation.startsWith("save:") || actionError?.operation === "create" ? actionError.error : null} onSubmit={saveDraft} onRefresh={editor === "edit" ? refreshSubscription : undefined} onCancel={() => { setEditor("closed"); setActionError(null); }} />}
    </aside></div>
  </div>;
}

export function RecommendationWorkspace() { return <SessionBoundary>{(context) => <AuthorizedWorkspace context={context} mode="recommendations" />}</SessionBoundary>; }
export function ReportWorkspace() { return <SessionBoundary>{(context) => <AuthorizedWorkspace context={context} mode="reports" />}</SessionBoundary>; }
