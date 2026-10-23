import { useEffect, useRef, useState } from "react";
import { enqueueEventEnrichment, type EnrichmentReceipt } from "../../api/enrichment-client";
import { ApiProblem, publicProblem } from "../../api/client";
import { ErrorPanel } from "../../components/status";

/** Acceptance is scheduling only. Dimension badges still come from the saved event. */
export function EventEnrichmentAction({ eventId, businessVersion, onReload }: { eventId: string; businessVersion: number; onReload: () => void }) {
  const [receipt, setReceipt] = useState<EnrichmentReceipt | null>(null);
  const [failure, setFailure] = useState<ApiProblem | null>(null);
  const [pending, setPending] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(() => `enrich-ui-${crypto.randomUUID()}`);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    setIdempotencyKey(`enrich-ui-${crypto.randomUUID()}`);
    setReceipt(null);
    setFailure(null);
  }, [eventId, businessVersion]);

  async function submit() {
    if (pending || receipt !== null) return;
    setPending(true);
    setFailure(null);
    controller.current?.abort();
    const next = new AbortController();
    controller.current = next;
    try {
      const accepted = await enqueueEventEnrichment(eventId, businessVersion, idempotencyKey, next.signal);
      if (!next.signal.aborted) setReceipt(accepted);
    } catch (error: unknown) {
      if (!next.signal.aborted) setFailure(publicProblem(error));
    } finally {
      if (!next.signal.aborted) setPending(false);
    }
  }

  return <div className="panel-actions">
    <button className="button secondary" type="button" disabled={pending || receipt !== null} onClick={() => void submit()}>{pending ? "正在提交富化…" : "提交富化"}</button>
    <button className="button secondary" type="button" onClick={onReload}>重新读取事件</button>
    {receipt !== null && <p className="small-note" role="status">已受理工作流 <code>{receipt.workflow_id}</code>。受理不是完成；受阻、失败和未发现都不能显示成已取得。</p>}
    {failure !== null && <ErrorPanel error={failure} message="富化没有完成。请核对权限和事件版本后重试，不能把提交失败当成无风险。" />}
  </div>;
}
