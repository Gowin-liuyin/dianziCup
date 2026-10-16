import { useState, type FormEvent } from "react";
import { ApiProblem } from "../../api/client";
import { RecommendationError } from "./workspace-state";

/** 本地表单草稿；网络 DTO 由冻结接口适配，不包含认证身份或内部收据。 */
export interface SubscriptionDraft {
  productKeys: string[];
  assetIds: string[];
  riskTopics: string[];
  maximumPriorityBucket: 0 | 1 | 2 | 3;
  enabled: boolean;
}

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const priorityValues = { "0": 0, "1": 1, "2": 2, "3": 3 } as const;
const emptyDraft: SubscriptionDraft = { productKeys: [], assetIds: [], riskTopics: [], maximumPriorityBucket: 3, enabled: true };

function parseInterestLines(value: string, identifiers = false): string[] {
  const lines = value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length > 100 || lines.some((line) => [...line].length > 200 || /[\u0000-\u001f]/.test(line) || (identifiers && !uuidPattern.test(line)))) throw new Error(identifiers ? "资产标识须为 UUID，每行一个，最多100项。" : "每行一个明确兴趣，最多100项，每项最多200字符。" );
  const normalized = identifiers ? lines.map((line) => line.toLowerCase()) : lines;
  if (new Set(normalized).size !== normalized.length) throw new Error("同一过滤条件不能重复，请核对输入。" );
  return normalized;
}

export function SubscriptionEditor({ initialDraft = emptyDraft, currentVersion = null, pending, canSubmit, allowAssetSelectors = true, error, onSubmit, onRefresh, onCancel }: { initialDraft?: SubscriptionDraft; currentVersion?: number | null; pending: boolean; canSubmit: boolean; allowAssetSelectors?: boolean; error: ApiProblem | null; onSubmit: (draft: SubscriptionDraft, expectedVersion: number | null) => void; onRefresh?: () => void; onCancel?: () => void }) {
  const [products, setProducts] = useState(initialDraft.productKeys.join("\n"));
  const [assets, setAssets] = useState(initialDraft.assetIds.join("\n"));
  const [topics, setTopics] = useState(initialDraft.riskTopics.join("\n"));
  const [priority, setPriority] = useState(initialDraft.maximumPriorityBucket);
  const [enabled, setEnabled] = useState(initialDraft.enabled);
  const [expectedVersion, setExpectedVersion] = useState(currentVersion);
  const [validationError, setValidationError] = useState<string | null>(null);
  const versionChanged = currentVersion !== expectedVersion;
  const conflictUnresolved = error?.status === 409;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || pending || versionChanged || conflictUnresolved) return;
    try {
      const draft = { productKeys: parseInterestLines(products), assetIds: parseInterestLines(assets, true), riskTopics: parseInterestLines(topics), maximumPriorityBucket: priority, enabled };
      if (!allowAssetSelectors && draft.assetIds.length > 0) throw new Error("资产关注需要当前会话明确授予 read:asset，请先核对授权。" );
      if (!draft.productKeys.length && !draft.assetIds.length && !draft.riskTopics.length) throw new Error("至少填写一个产品、授权资产或风险主题。" );
      setValidationError(null); onSubmit(draft, expectedVersion);
    } catch (failure: unknown) { setValidationError(failure instanceof Error ? failure.message : "输入未通过校验。" ); }
  }
  return <form className="subscription-form" onSubmit={submit} aria-label={currentVersion === null ? "创建本人订阅" : "编辑本人订阅"}>
    <h3>{currentVersion === null ? "创建订阅范围" : "编辑订阅范围"}</h3>
    {currentVersion !== null && <p className="small-note">服务端当前版本 <strong>{currentVersion}</strong> · 本次编辑依据 <strong>{expectedVersion}</strong></p>}
    <label>产品关注（每行一个）<textarea value={products} onChange={(event) => setProducts(event.target.value)} maxLength={20100} disabled={pending} aria-describedby="subscription-selector-help" /></label>
    <label>授权资产 UUID（每行一个）<textarea value={assets} onChange={(event) => setAssets(event.target.value)} maxLength={3800} disabled={pending || !allowAssetSelectors} /></label>
    {!allowAssetSelectors && <p className="small-note">当前会话未授予 read:asset，只能按产品与主题关注。</p>}
    <label>风险主题（每行一个）<textarea value={topics} onChange={(event) => setTopics(event.target.value)} maxLength={20100} disabled={pending} /></label>
    <p id="subscription-selector-help" className="small-note">至少一个明确兴趣。不同条件的支持依据由服务端核对；未知主题可能返回证据缺口。</p>
    <label>接收优先级范围<select value={priority} onChange={(event) => { const value = event.target.value; if (value === "0" || value === "1" || value === "2" || value === "3") setPriority(priorityValues[value]); }} disabled={pending}><option value="0">仅 P0（最高）</option><option value="1">P0 至 P1</option><option value="2">P0 至 P2</option><option value="3">P0 至 P3</option></select></label>
    <label>订阅状态<select value={enabled ? "enabled" : "disabled"} onChange={(event) => setEnabled(event.target.value === "enabled")} disabled={pending}><option value="enabled">启用提醒</option><option value="disabled">退订（保留历史）</option></select></label>
    {!enabled && <p className="small-note">退订后停止新提醒，已保存的推荐与报告仍保留。</p>}
    {versionChanged && <div className="recommendation-boundary" role="alert"><p>服务端版本已变化。你的输入保持原样，请核对当前范围后确认新的编辑依据。</p><button className="button secondary" type="button" disabled={pending} onClick={() => setExpectedVersion(currentVersion)}>保留输入，采用版本 {currentVersion}</button></div>}
    {validationError && <p className="recommendation-boundary" role="alert">{validationError}</p>}
    {error && <RecommendationError error={error} onRetry={onRefresh} />}
    <div className="subscription-actions"><button className="button" type="submit" disabled={!canSubmit || pending || versionChanged || conflictUnresolved}>{pending ? "提交中…" : currentVersion === null ? "创建本人订阅" : "保存订阅修改"}</button>{onCancel && <button className="button secondary" type="button" disabled={pending} onClick={onCancel}>取消编辑</button>}</div>
  </form>;
}
