import { useCallback, useEffect, useRef, useState } from "react";
import { ApiProblem, publicProblem, type CurrentUser } from "../../api/client";
import { EmptyState } from "../../components/status";
import { getAsset, getAssetHistory, getAssetList, getAssetSnapshot } from "../assets/asset-client";
import { AssetResponseScopeMismatch, type Asset, type AssetPage, type AssetSnapshot, type SnapshotPage } from "../assets/asset-contracts";
import { AssetError } from "../assets/asset-status";
import { AssessmentPanel } from "./AssessmentPanel";
import { AssessmentResponseScopeMismatch } from "./assessment-contracts";

export interface AssessmentWorkspaceProps {
  user: CurrentUser; authScope: string; isCurrent: () => boolean;
  onFailure?: (error: ApiProblem) => void; onOpenEvent?: (eventId: string, evidenceId?: string) => void;
}
function AuthorizedAssessmentWorkspace({ user, authScope, isCurrent, onFailure, onOpenEvent }: AssessmentWorkspaceProps & { user: CurrentUser & { tenant_id: string } }) {
  const [list, setList] = useState<AssetPage | null>(null);
  const [listError, setListError] = useState<ApiProblem | null>(null);
  const [listPending, setListPending] = useState(false);
  const [listRequest, setListRequest] = useState<{ cursor: string | null; retry: number }>({ cursor: null, retry: 0 });
  const [assetId, setAssetId] = useState("");
  const [asset, setAsset] = useState<Asset | null>(null);
  const [history, setHistory] = useState<SnapshotPage | null>(null);
  const [selectionError, setSelectionError] = useState<ApiProblem | null>(null);
  const [selectionPending, setSelectionPending] = useState(false);
  const [historyError, setHistoryError] = useState<ApiProblem | null>(null);
  const [historyPending, setHistoryPending] = useState(false);
  const [historyRequest, setHistoryRequest] = useState<{ cursor: string | null; retry: number }>({ cursor: null, retry: 0 });
  const [selectedSnapshotId, setSelectedSnapshotId] = useState("");
  const [savedSnapshot, setSavedSnapshot] = useState<AssetSnapshot | null>(null);
  const [snapshotError, setSnapshotError] = useState<ApiProblem | null>(null);
  const [snapshotPending, setSnapshotPending] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [denied, setDenied] = useState<ApiProblem | null>(null);
  const invalidated = useRef(false);
  const current = useCallback(() => !invalidated.current && isCurrent(), [isCurrent]);
  const failed = useCallback((error: ApiProblem) => {
    if (error.status === 401 || error.status === 403 || error instanceof AssetResponseScopeMismatch || error instanceof AssessmentResponseScopeMismatch) {
      invalidated.current = true; setDenied(error); setList(null); setAsset(null); setHistory(null); setSavedSnapshot(null);
    }
    onFailure?.(error);
  }, [onFailure]);

  useEffect(() => {
    const controller = new AbortController();
    setListPending(true); setListError(null);
    if (listRequest.cursor === null) setList(null);
    void getAssetList(user.tenant_id, "", listRequest.cursor, controller.signal).then((page) => {
      if (!controller.signal.aborted && current()) setList((previous) => ({ items: listRequest.cursor === null ? page.items : [...(previous?.items ?? []), ...page.items.filter((item) => !previous?.items.some((saved) => saved.asset_id === item.asset_id))], next_cursor: page.next_cursor }));
    }).catch((failure: unknown) => { if (controller.signal.aborted || !current()) return; const error = publicProblem(failure); setListError(error); failed(error); }).finally(() => { if (!controller.signal.aborted && current()) setListPending(false); });
    return () => controller.abort();
  }, [user.tenant_id, listRequest, current, failed]);

  useEffect(() => {
    const controller = new AbortController();
    setAsset(null); setSelectionError(null); setSavedSnapshot(null); setSelectedSnapshotId("");
    if (assetId === "") { setSelectionPending(false); return () => controller.abort(); }
    setSelectionPending(true);
    void getAsset(user.tenant_id, assetId, controller.signal).then((result) => { if (!controller.signal.aborted && current()) setAsset(result); }).catch((failure: unknown) => { if (controller.signal.aborted || !current()) return; const error = publicProblem(failure); setSelectionError(error); failed(error); }).finally(() => { if (!controller.signal.aborted && current()) setSelectionPending(false); });
    return () => controller.abort();
  }, [assetId, user.tenant_id, refresh, current, failed]);

  useEffect(() => {
    const controller = new AbortController();
    setHistoryError(null);
    if (historyRequest.cursor === null) setHistory(null);
    if (assetId === "") { setHistoryPending(false); return () => controller.abort(); }
    setHistoryPending(true);
    void getAssetHistory(user.tenant_id, assetId, historyRequest.cursor, controller.signal).then((page) => { if (!controller.signal.aborted && current()) setHistory((previous) => ({ items: historyRequest.cursor === null ? page.items : [...(previous?.items ?? []), ...page.items.filter((item) => !previous?.items.some((saved) => saved.snapshot_id === item.snapshot_id))], next_cursor: page.next_cursor })); }).catch((failure: unknown) => { if (controller.signal.aborted || !current()) return; const error = publicProblem(failure); setHistoryError(error); failed(error); }).finally(() => { if (!controller.signal.aborted && current()) setHistoryPending(false); });
    return () => controller.abort();
  }, [assetId, user.tenant_id, historyRequest, refresh, current, failed]);

  useEffect(() => {
    const controller = new AbortController();
    setSavedSnapshot(null); setSnapshotError(null);
    if (assetId === "" || selectedSnapshotId === "") { setSnapshotPending(false); return () => controller.abort(); }
    setSnapshotPending(true);
    void getAssetSnapshot(user.tenant_id, assetId, selectedSnapshotId, controller.signal).then((result) => { if (!controller.signal.aborted && current()) setSavedSnapshot(result); }).catch((failure: unknown) => { if (controller.signal.aborted || !current()) return; const error = publicProblem(failure); setSnapshotError(error); failed(error); }).finally(() => { if (!controller.signal.aborted && current()) setSnapshotPending(false); });
    return () => controller.abort();
  }, [assetId, user.tenant_id, selectedSnapshotId, refresh, current, failed]);

  if (denied !== null) return <section className="panel"><AssetError error={denied} /></section>;
  const selectedAsset = asset?.asset_id === assetId ? asset : null;
  let snapshot: AssetSnapshot | null = null;
  if (selectedSnapshotId === "") snapshot = selectedAsset?.snapshot ?? null;
  else if (savedSnapshot?.snapshot_id === selectedSnapshotId && savedSnapshot.asset_id === assetId) snapshot = savedSnapshot;
  const newerHistory = selectedAsset !== null && history?.items.some((item) => item.snapshot_number > selectedAsset.snapshot.snapshot_number) === true;
  function refreshSelection() { setHistoryRequest({ cursor: null, retry: 0 }); setRefresh(refresh + 1); }
  return <div className="assessment-workspace">
    <div className="assessment-workspace-intro"><p className="small-note">在当前授权清单内固定一份输入，指定已知规则。结果保留四态、时效、范围与证据引用。</p><span className="assessment-mode">{user.data_mode === "fixture" ? "显式 Fixture · 非 live" : "当前认证 API"}</span></div>
    <section className="panel" aria-labelledby="assessment-selector-title"><div className="panel-heading"><div><p className="eyebrow">SELECT / 授权输入</p><h2 id="assessment-selector-title">选择资产与快照</h2></div><span className="small-note">{list?.items.length ?? 0} 个已读资产</span></div>
      <div className="assessment-selector"><div className="assessment-selector-fields"><label>授权资产<select value={assetId} onChange={(event) => { setAssetId(event.target.value); setAsset(null); setHistory(null); setSavedSnapshot(null); setSelectedSnapshotId(""); setHistoryRequest({ cursor: null, retry: 0 }); }}><option value="">请选择授权资产</option>{list?.items.map((item) => <option key={item.asset_id} value={item.asset_id}>{item.display_name} · #{item.snapshot.snapshot_number}</option>)}</select></label><label>固定快照<select value={selectedSnapshotId} disabled={selectedAsset === null} onChange={(event) => { setSavedSnapshot(null); setSelectedSnapshotId(event.target.value); }}><option value="">{selectedAsset === null ? "先选择资产" : `当前快照 #${selectedAsset.snapshot.snapshot_number}`}</option>{history?.items.map((item) => <option key={item.snapshot_id} value={item.snapshot_id}>保存快照 #{item.snapshot_number} · {item.snapshot_id}</option>)}</select></label></div>
        <div className="assessment-selector-actions"><button className="button secondary" disabled={listPending} onClick={() => setListRequest({ cursor: null, retry: listRequest.retry + 1 })}>刷新授权资产</button>{list?.next_cursor !== null && list?.next_cursor !== undefined && <button className="button secondary" disabled={listPending} onClick={() => setListRequest({ cursor: list.next_cursor, retry: 0 })}>加载更多资产</button>}{assetId !== "" && <button className="button secondary" disabled={selectionPending || historyPending} onClick={refreshSelection}>复核当前指针与历史</button>}{history?.next_cursor !== null && history?.next_cursor !== undefined && <button className="button secondary" disabled={historyPending} onClick={() => setHistoryRequest({ cursor: history.next_cursor, retry: 0 })}>加载更多快照</button>}</div>
        {(listPending || selectionPending || historyPending || snapshotPending) && <p className="small-note" role="status">正在读取授权输入…</p>}
        {listError !== null && <AssetError error={listError} onRetry={() => setListRequest({ ...listRequest, retry: listRequest.retry + 1 })} />}
        {list !== null && list.items.length === 0 && !listPending && <EmptyState title="没有已读的授权资产" description="空目录不证明没有资产或没有影响。请核对权限，或先由授权人员导入清单。" />}
        {selectionError !== null && <AssetError error={selectionError} onRetry={refreshSelection} />}{historyError !== null && <><p className="assessment-warning">历史快照页读取失败，当前指针与历史关联待复核。已读快照不当作当前有效结论。</p><AssetError error={historyError} onRetry={() => setHistoryRequest({ ...historyRequest, retry: historyRequest.retry + 1 })} /></>}{snapshotError !== null && <AssetError error={snapshotError} onRetry={() => setRefresh(refresh + 1)} />}
        {list !== null && <p className="small-note">{list.next_cursor === null ? "当前资产查询已到末页，目录数量不是完整性或安全证明。" : "尚有后续资产页，可继续加载。"}</p>}
      </div></section>
    <AssessmentPanel user={user} snapshot={snapshot} currentSnapshotId={newerHistory || historyError !== null ? null : selectedAsset?.current_snapshot_id ?? null} authScope={authScope} isCurrent={current} onFailure={failed} onOpenEvent={onOpenEvent} />
  </div>;
}

/** Uses only the authenticated user's tenant for reads; the assessment body contains fixed asset and rule inputs. */
export function AssessmentWorkspace(props: AssessmentWorkspaceProps) {
  const { user } = props;
  if (user.tenant_id === null || !user.permissions.includes("read:asset")) return <section className="panel"><EmptyState title="当前会话无资产研判权限" description="需要 read:asset 与明确租户。请在团队会话中核对授权范围。" /></section>;
  return <AuthorizedAssessmentWorkspace key={`${props.authScope}:${user.user_id}:${user.tenant_id}:${user.permission_version}`} {...props} user={{ ...user, tenant_id: user.tenant_id }} />;
}
