import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { publicProblem, type ApiProblem } from "../../api/client";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { EmptyState } from "../../components/status";
import { getAsset, getAssetHistory, getAssetSnapshot } from "./asset-client";
import type { Asset, AssetSnapshot, DeclaredField, SnapshotPage } from "./asset-contracts";
import { AssetError, completenessLabels } from "./asset-status";
import { SbomDetail } from "./sbom-detail";

interface DetailProps { tenant: string; assetId: string; refresh: number; isCurrent: () => boolean; onAsset: (asset: Asset | null) => void; onFailure: (error: ApiProblem) => void }
function savedTime(value: string) { return <time dateTime={value}>{formatShanghaiTimestamp(value)}</time>; }
function declaredValue(value: DeclaredField["value"]): string { if (value === null) return "未知 · 未声明"; if (typeof value === "boolean") return value ? "声明为 true" : "声明为 false"; return value; }
function DeclaredFields({ title, fields }: { title: string; fields: DeclaredField[] | null }) {
  return <section className="asset-field-section"><h4>{title}</h4>{fields === null || fields.length === 0 ? <p className="asset-unknown">未知 · 未提供声明，不能解释为 false。</p> : <dl className="asset-declared-fields">{fields.map((field) => <div key={field.name}><dt><code>{field.name}</code></dt><dd>{declaredValue(field.value)}<code className="asset-locator">{field.source_field_locator}</code></dd></div>)}</dl>}</section>;
}
type SnapshotPosition = "current" | "history" | "unverified";
const positionLabels: Record<SnapshotPosition, string> = { current: "CURRENT SNAPSHOT / 当前快照", history: "SAVED HISTORY / 保存历史", unverified: "REVALIDATE / 当前指针待复核" };
function SnapshotView({ snapshot, position, isCurrent, onFailure }: { snapshot: AssetSnapshot; position: SnapshotPosition; isCurrent: () => boolean; onFailure: (error: ApiProblem) => void }) {
  const [componentPage, setComponentPage] = useState(0);
  const components = snapshot.components.slice(componentPage * 20, (componentPage + 1) * 20);
  let toolPermissionsLabel = "未知 · 未提供声明";
  if (snapshot.tool_permissions !== null) toolPermissionsLabel = snapshot.tool_permissions.length ? snapshot.tool_permissions.join(" · ") : "显式空权限清单（输入声明）";
  return <div className="asset-snapshot-view">
    <div className="asset-snapshot-heading"><div><p className="eyebrow">{positionLabels[position]}</p><h3>快照 #{snapshot.snapshot_number}</h3></div><span className="asset-tag">{completenessLabels[snapshot.inventory_completeness]}</span></div>
    {position === "history" && <p className="asset-warning">正在查看历史快照。此版本保留原始声明，不代表当前状态；研判新鲜度尚未提供。</p>}
    {position === "unverified" && <p className="asset-warning">历史页包含较新快照，当前指针需要复核。请刷新资产与快照；这些分别读取的版本不能视为已确认的当前状态。</p>}
    <dl className="asset-metadata"><dt>快照标识</dt><dd><code>{snapshot.snapshot_id}</code></dd><dt>实际观察时间</dt><dd>{savedTime(snapshot.observed_at)}</dd><dt>系统记录时间</dt><dd>{savedTime(snapshot.recorded_at)}</dd><dt>输入类型</dt><dd><code>{snapshot.source_kind}</code></dd><dt>输入来源版本</dt><dd className="asset-unknown">未知 · 当前响应未提供</dd><dt>声明范围</dt><dd>{snapshot.declared_scope.length ? snapshot.declared_scope.join(" · ") : "未知 · 未声明"}</dd><dt>快照内容摘要</dt><dd><code>{snapshot.snapshot_sha256}</code><span className="small-note">内容 SHA-256；摘要不证明清单真实性。</span></dd></dl>
    <section className="asset-components"><div className="asset-section-heading"><h4>组件声明</h4><span className="small-note">共 {snapshot.components.length} 项 · 每页 20 项</span></div>
      {snapshot.components.length === 0 ? <EmptyState title="该快照没有组件声明" description="缺组件不等于不存在，也不能据此判断无影响或安全。" /> : <div className="table-scroll"><table aria-label="资产组件声明"><thead><tr><th scope="col">组件 / 生态</th><th scope="col">版本 / 比较方案</th><th scope="col">身份与字段定位</th></tr></thead><tbody>{components.map((component) => <tr key={component.component_id}><th scope="row">{component.display_name ?? component.package_name}<code className="asset-locator">{component.package_name}</code><span className="asset-tag">{component.ecosystem === "unknown" ? "生态未知" : component.ecosystem}</span></th><td><strong className={component.version === null ? "asset-unknown" : ""}>{component.version ?? "版本未知"}</strong><code className="asset-locator">{component.version_scheme === "unknown" ? "比较方案未知" : component.version_scheme}</code></td><td><dl className="asset-component-identities"><dt>purl</dt><dd><code>{component.purl ?? "未知 · 未声明"}</code></dd><dt>镜像摘要</dt><dd><code>{component.image_digest ?? "未知 · 未声明"}</code></dd><dt>依赖路径</dt><dd>{component.dependency_path?.join(" → ") ?? "未知 · 未声明"}</dd><dt>字段位置</dt><dd><code>{component.source_field_locator}</code></dd><dt>组件标识</dt><dd><code>{component.component_id}</code></dd></dl></td></tr>)}</tbody></table></div>}
      {snapshot.components.length > 20 && <div className="asset-pagination"><button className="button secondary" disabled={componentPage === 0} onClick={() => setComponentPage(componentPage - 1)}>上一页组件</button><span className="small-note">组件页 {componentPage + 1} / {Math.ceil(snapshot.components.length / 20)}</span><button className="button secondary" disabled={(componentPage + 1) * 20 >= snapshot.components.length} onClick={() => setComponentPage(componentPage + 1)}>下一页组件</button></div>}
    </section>
    <DeclaredFields title="内部配置声明" fields={snapshot.configuration} />
    <DeclaredFields title="输入通道声明" fields={snapshot.input_channels} />
    <DeclaredFields title="网络配置声明（不是外部观测）" fields={snapshot.network_exposure} />
    <section className="asset-field-section"><h4>工具权限声明</h4><p>{toolPermissionsLabel}</p></section>
    <SbomDetail tenant={snapshot.tenant_id} snapshot={snapshot} isCurrent={isCurrent} onFailure={onFailure} />
  </div>;
}

export function AssetDetail({ tenant, assetId, refresh, isCurrent, onAsset, onFailure }: DetailProps) {
  const [asset, setAsset] = useState<Asset | null>(null);
  const [assetError, setAssetError] = useState<ApiProblem | null>(null);
  const [detailRetry, setDetailRetry] = useState(0);
  const [history, setHistory] = useState<SnapshotPage | null>(null);
  const [historyError, setHistoryError] = useState<ApiProblem | null>(null);
  const [historyPending, setHistoryPending] = useState(false);
  const [historyRequest, setHistoryRequest] = useState<{ cursor: string | null; retry: number }>({ cursor: null, retry: 0 });
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<AssetSnapshot | null>(null);
  const [snapshotError, setSnapshotError] = useState<ApiProblem | null>(null);
  const [snapshotRetry, setSnapshotRetry] = useState(0);
  const unreadable = useRef(false);
  const failed = useCallback((problem: ApiProblem) => {
    if (problem.status === 404) { unreadable.current = true; setAsset(null); setAssetError(problem); onAsset(null); setHistory(null); setSelectedSnapshot(null); }
    onFailure(problem);
  }, [onAsset, onFailure]);

  useEffect(() => {
    const controller = new AbortController();
    unreadable.current = false;
    setAsset(null); setAssetError(null); onAsset(null); setSelectedSnapshotId(null); setSelectedSnapshot(null);
    void getAsset(tenant, assetId, controller.signal).then((result) => { if (!controller.signal.aborted && isCurrent() && !unreadable.current) { setAsset(result); onAsset(result); } }).catch((failure: unknown) => { if (controller.signal.aborted || !isCurrent()) return; const problem = publicProblem(failure); setAssetError(problem); failed(problem); });
    return () => controller.abort();
  }, [tenant, assetId, refresh, detailRetry, isCurrent, onAsset, failed]);

  useEffect(() => {
    const controller = new AbortController();
    setHistoryPending(true); setHistoryError(null);
    if (historyRequest.cursor === null) setHistory(null);
    void getAssetHistory(tenant, assetId, historyRequest.cursor, controller.signal).then((result) => {
      if (controller.signal.aborted || !isCurrent() || unreadable.current) return;
      setHistory((previous) => ({ items: historyRequest.cursor === null ? result.items : [...(previous?.items ?? []), ...result.items], next_cursor: result.next_cursor }));
    }).catch((failure: unknown) => { if (controller.signal.aborted || !isCurrent()) return; const problem = publicProblem(failure); setHistoryError(problem); if ([401, 403, 404].includes(problem.status)) setHistory(null); failed(problem); }).finally(() => { if (!controller.signal.aborted && isCurrent()) setHistoryPending(false); });
    return () => controller.abort();
  }, [tenant, assetId, refresh, historyRequest, isCurrent, failed]);

  useEffect(() => {
    const controller = new AbortController(); setSelectedSnapshot(null); setSnapshotError(null);
    if (selectedSnapshotId === null) return () => controller.abort();
    void getAssetSnapshot(tenant, assetId, selectedSnapshotId, controller.signal).then((result) => { if (!controller.signal.aborted && isCurrent() && !unreadable.current) setSelectedSnapshot(result); }).catch((failure: unknown) => { if (controller.signal.aborted || !isCurrent()) return; const problem = publicProblem(failure); setSnapshotError(problem); failed(problem); });
    return () => controller.abort();
  }, [tenant, assetId, selectedSnapshotId, snapshotRetry, isCurrent, failed]);

  let snapshotContent: ReactNode = null;
  if (asset !== null) {
    const newerHistory = history?.items.some((snapshot) => snapshot.snapshot_number > asset.snapshot.snapshot_number) === true;
    if (selectedSnapshotId === null) snapshotContent = <SnapshotView key={asset.snapshot.snapshot_id} snapshot={asset.snapshot} position={newerHistory ? "unverified" : "current"} isCurrent={isCurrent} onFailure={onFailure} />;
    else if (snapshotError !== null) snapshotContent = <AssetError error={snapshotError} onRetry={() => setSnapshotRetry(snapshotRetry + 1)} retryLabel="重试固定快照" />;
    else if (selectedSnapshot === null || selectedSnapshot.snapshot_id !== selectedSnapshotId) snapshotContent = <p className="loading-state" role="status">正在读取所选历史快照…</p>;
    else snapshotContent = <><button className="button secondary asset-return-current" onClick={() => setSelectedSnapshotId(null)}>查看当前快照</button><SnapshotView key={selectedSnapshot.snapshot_id} snapshot={selectedSnapshot} position={selectedSnapshot.snapshot_number < asset.snapshot.snapshot_number ? "history" : "unverified"} isCurrent={isCurrent} onFailure={onFailure} /></>;
  }

  return <section className="panel asset-detail-panel" aria-labelledby="asset-detail-title">
    <div className="panel-heading"><div><p className="eyebrow">ASSET / 私有资产检视</p><h2 id="asset-detail-title">{asset?.display_name ?? "资产详情"}</h2></div><a className="button secondary" href="#assets">返回资产列表</a></div>
    {asset === null && assetError === null && <p role="status" className="loading-state">正在读取当前资产快照…</p>}
    {assetError !== null && <AssetError error={assetError} onRetry={() => { setDetailRetry(detailRetry + 1); setHistoryRequest({ cursor: null, retry: historyRequest.retry + 1 }); }} retryLabel="重新读取资产" />}
    {asset !== null && <>
      <div className="asset-detail-identity"><code>{asset.asset_id}</code><span className="asset-tag">{asset.active ? "服务端标记：活跃" : "服务端标记：非活跃"}</span><p className="small-note">业务重要性：{asset.criticality === "unknown" ? "未知" : asset.criticality} · 资产声明不等于已核查影响。</p></div>
      <div className="asset-history"><div className="asset-section-heading"><h3>快照历史</h3><button className="button secondary" disabled={historyPending} onClick={() => { setHistoryRequest({ cursor: null, retry: historyRequest.retry + 1 }); }}>刷新历史</button></div><p className="small-note">按服务端快照顺序读取；点击版本后重新获取该固定快照。</p>
        {historyPending && <p role="status">正在读取历史页…</p>}
        {history?.items.length === 0 && !historyPending && <p className="asset-unknown">历史查询为空；不能据此解释当前快照已失效。</p>}
        <div className="asset-history-list">{history?.items.map((snapshot) => <button className={`asset-history-button ${selectedSnapshotId === snapshot.snapshot_id || (selectedSnapshotId === null && snapshot.snapshot_id === asset.current_snapshot_id) ? "selected" : ""}`} key={snapshot.snapshot_id} onClick={() => setSelectedSnapshotId(snapshot.snapshot_id === asset.current_snapshot_id ? null : snapshot.snapshot_id)}><span>查看快照 #{snapshot.snapshot_number}{snapshot.snapshot_id === asset.current_snapshot_id ? " · 当前" : " · 历史"}</span>{savedTime(snapshot.observed_at)}</button>)}</div>
        {historyError !== null && <AssetError error={historyError} onRetry={() => setHistoryRequest({ ...historyRequest, retry: historyRequest.retry + 1 })} retryLabel="重试历史页" />}
        {history?.next_cursor !== null && history?.next_cursor !== undefined && <button className="button secondary" disabled={historyPending} onClick={() => { const cursor = history.next_cursor; if (cursor !== null) setHistoryRequest({ cursor, retry: 0 }); }}>加载更多历史</button>}
      </div>
      {snapshotContent}
      <section className="asset-unavailable"><p className="eyebrow">OBSERVATION / 外部观察</p><h3>外部观察入口尚未接通</h3><p>本页仅展示内部清单声明。外部不可达不能证明软件已修复；不会从导入动作发起第三方扫描。</p><button className="button secondary" disabled>查询授权外部观察 · 未就绪</button></section>
      <section className="asset-unavailable"><p className="eyebrow">ASSESSMENT / 条件与证据</p><h3>研判与导出入口尚未接通</h3><p>条件树、四态结果、缺口、冲突和 freshness 需由已验证业务接口返回。当前快照不显示预设判定；旧结果须重新验证。</p><div className="asset-actions"><button className="button secondary" disabled>提交研判 · 未就绪</button><button className="button secondary" disabled>导出证据包 / OpenVEX · 未就绪</button></div></section>
    </>}
  </section>;
}
