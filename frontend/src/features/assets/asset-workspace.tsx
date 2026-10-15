import { useCallback, useEffect, useState, type FormEvent } from "react";
import { publicProblem, type ApiProblem, type CurrentUser } from "../../api/client";
import { useAuthSession } from "../../app/auth-session";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { EmptyState } from "../../components/status";
import { getAssetList } from "./asset-client";
import type { Asset, AssetImportResult, AssetPage } from "./asset-contracts";
import { AssetDetail } from "./asset-detail";
import { AssetImport } from "./asset-import";
import { AssetError, completenessLabels } from "./asset-status";
import "./assets.css";

function AuthorizedAssets({ user, assetId }: { user: CurrentUser & { tenant_id: string }; assetId?: string }) {
  const { sessionGeneration, isSessionCurrent, expireSession } = useAuthSession();
  const [list, setList] = useState<AssetPage | null>(null);
  const [listError, setListError] = useState<ApiProblem | null>(null);
  const [pending, setPending] = useState(false);
  const [productInput, setProductInput] = useState("");
  const [product, setProduct] = useState("");
  const [request, setRequest] = useState<{ cursor: string | null; retry: number }>({ cursor: null, retry: 0 });
  const [refresh, setRefresh] = useState(0);
  const [denied, setDenied] = useState<ApiProblem | null>(null);
  const [currentAsset, setCurrentAsset] = useState<Asset | null>(null);
  const [receipt, setReceipt] = useState<AssetImportResult | null>(null);
  const isCurrent = useCallback(() => isSessionCurrent(sessionGeneration), [isSessionCurrent, sessionGeneration]);
  const failed = useCallback((error: ApiProblem) => {
    if (!isCurrent()) return;
    if (error.status === 401) expireSession(sessionGeneration);
    if (error.status === 403 && error.code !== "csrf_rejected") { setList(null); setCurrentAsset(null); setReceipt(null); setDenied(error); }
  }, [isCurrent, expireSession, sessionGeneration]);
  useEffect(() => {
    const controller = new AbortController();
    if (denied !== null) return () => controller.abort();
    setPending(true); setListError(null);
    if (request.cursor === null) setList(null);
    void getAssetList(user.tenant_id, product, request.cursor, controller.signal).then((result) => {
      if (!controller.signal.aborted && isCurrent()) setList((previous) => ({ items: request.cursor === null ? result.items : [...(previous?.items ?? []), ...result.items], next_cursor: result.next_cursor }));
    }).catch((failure: unknown) => { if (controller.signal.aborted || !isCurrent()) return; const problem = publicProblem(failure); setListError(problem); failed(problem); }).finally(() => { if (!controller.signal.aborted && isCurrent()) setPending(false); });
    return () => controller.abort();
  }, [user.tenant_id, product, request, isCurrent, failed, denied]);
  function refreshAssets() { setRequest({ cursor: null, retry: request.retry + 1 }); setRefresh(refresh + 1); }
  function filter(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setProduct(productInput.trim()); setRequest({ cursor: null, retry: request.retry + 1 }); }
  function imported(result: AssetImportResult) { if (!isCurrent()) return; setReceipt(result); refreshAssets(); window.location.hash = `assets/${result.asset_id}`; }
  if (denied !== null) return <section className="panel"><AssetError error={denied} /><a className="button secondary asset-access-link" href="#session">核对会话与权限</a></section>;
  return <div className="asset-workspace">
    <div className="asset-scope-banner"><p><span className="eyebrow">PRIVATE INVENTORY / 授权清单</span>仅显示当前认证租户的资产声明</p><span className="asset-tag">{user.data_mode === "fixture" ? "合成 Fixture · 非真实资产" : "真实会话 · 服务端资产"}</span><button className="button secondary" disabled={pending} onClick={refreshAssets}>刷新资产与快照</button></div>
    {receipt !== null && <div className="asset-receipt" role="status"><strong>{receipt.reused ? "已复用服务端快照" : "导入成功 · 服务端已保存快照"}</strong><p>快照 #{receipt.snapshot.snapshot_number} · <code>{receipt.snapshot.snapshot_id}</code>。当前内容请以重新读取的资产详情为准。</p></div>}
    {user.permissions.includes("write:asset") ? <AssetImport key={assetId ?? "new-asset"} tenant={user.tenant_id} currentAsset={currentAsset?.asset_id === assetId ? currentAsset : null} isCurrent={isCurrent} onImported={imported} onFailure={failed} /> : <div className="asset-permission-note"><strong>只读资产权限</strong><p>导入需要当前会话明确授予 write:asset。分析员当前只有读取权限；本页不会按角色名称补授权限。</p></div>}
    <div className={`asset-catalog-layout ${assetId ? "has-selection" : ""}`}>
      <section className="panel asset-list-panel" aria-labelledby="asset-list-title"><div className="panel-heading"><div><p className="eyebrow">INVENTORY / 资产目录</p><h2 id="asset-list-title">当前授权资产</h2></div><span className="small-note">{list === null ? "等待读取" : `已读 ${list.items.length} 项`}</span></div>
        <form className="asset-filter" onSubmit={filter}><label htmlFor="asset-product-filter">按组件包名精确筛选</label><div><input id="asset-product-filter" value={productInput} maxLength={200} placeholder="package_name" onChange={(event) => setProductInput(event.target.value)} /><button className="button secondary" type="submit" disabled={pending}>筛选资产</button></div>{product && <p className="small-note">当前筛选：<code>{product}</code></p>}</form>
        {pending && <p className="loading-state" role="status">正在读取资产页…</p>}
        {listError !== null && <AssetError error={listError} onRetry={() => setRequest({ ...request, retry: request.retry + 1 })} retryLabel="重试资产页" />}
        {list !== null && list.items.length === 0 && !pending && <EmptyState title={product ? "当前筛选未匹配资产" : "尚无可见资产清单"} description="空查询不等于零影响或安全。可调整筛选，或由有写权限的管理员导入授权清单。" />}
        <ul className="asset-catalog">{list?.items.map((asset) => <li key={asset.asset_id}><a className={`asset-catalog-link ${assetId === asset.asset_id ? "selected" : ""}`} href={`#assets/${asset.asset_id}`} aria-current={assetId === asset.asset_id ? "page" : undefined}><div><strong>{asset.display_name}</strong><span aria-hidden="true">↗</span></div><span className="asset-tag">{completenessLabels[asset.snapshot.inventory_completeness]}</span><p>快照 #{asset.snapshot.snapshot_number} · {asset.snapshot.components.length} 个组件声明</p><span className="small-note">实际观察 <time dateTime={asset.snapshot.observed_at}>{formatShanghaiTimestamp(asset.snapshot.observed_at)}</time></span><code className="asset-locator">{asset.asset_id}</code></a></li>)}</ul>
        {list !== null && list.items.length > 0 && <p className="asset-page-note small-note">{list.next_cursor === null ? "当前查询已到末页；不是所有资产的完整性证明。" : "尚有后续页；以上仅为已读取记录。"}</p>}
        {list?.next_cursor !== null && list?.next_cursor !== undefined && <div className="asset-pagination"><button className="button secondary" disabled={pending} onClick={() => { const cursor = list.next_cursor; if (cursor !== null) setRequest({ cursor, retry: 0 }); }}>加载更多资产</button></div>}
      </section>
      {assetId ? <AssetDetail key={`${assetId}:${refresh}`} tenant={user.tenant_id} assetId={assetId} refresh={refresh} isCurrent={isCurrent} onAsset={setCurrentAsset} onFailure={failed} /> : <section className="asset-selection-guide"><p className="eyebrow">READ / VERIFY / COMPARE</p><h2>固定快照<br />保留判断边界</h2><p>选择资产，核对当前清单、历史快照、组件版本与字段位置。版本、配置或范围缺失时保留未知。</p><div><span>内部声明</span><strong>来源与完整性分别核对</strong></div><div><span>外部观察</span><strong>独立入口尚未接通</strong></div><div><span>影响研判</span><strong>等待条件与证据接口</strong></div></section>}
    </div>
  </div>;
}

/** 会话代次变化时由 App 重新挂载，私有结果与上传 File 不进入持久缓存。 */
export function AssetWorkspace({ assetId }: { assetId?: string }) {
  const { state, error } = useAuthSession();
  if (state.kind === "loading") return <section className="panel"><p role="status" className="loading-state">正在确认资产访问会话…</p></section>;
  if (state.kind !== "authenticated") return <section className="panel"><EmptyState title={error?.code === "session_expired" ? "会话已失效，私有资产已清除" : "登录后查看授权资产"} description="私有资产只从当前服务端认证会话读取。" /><a className="button secondary asset-access-link" href="#session">进入团队会话</a></section>;
  if (!state.user.permissions.includes("read:asset") || state.user.tenant_id === null) return <section className="panel"><EmptyState title="当前会话无资产读取权限" description="需要 read:asset 与明确租户范围；系统管理员也必须关联租户，才能操作私有清单。" /><a className="button secondary asset-access-link" href="#session">核对会话与权限</a></section>;
  return <AuthorizedAssets user={{ ...state.user, tenant_id: state.user.tenant_id }} assetId={assetId} />;
}
