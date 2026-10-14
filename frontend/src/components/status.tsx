import type { ApiProblem } from "../api/client";

const statusLabels: Record<string, string> = { ready: "就绪", live: "可响应", not_ready: "未就绪", degraded: "部分不可用", unavailable: "不可用", not_configured: "未配置", not_observed_or_stale: "待观测 / 已过期", unknown: "未知", stale: "已过期", partial: "部分完成", loading: "检查中" };

/** 文本标识与颜色共同表达状态，未知状态不解释为成功。 */
export function StatusBadge({ state }: { state: string }) {
  const confirmed = state === "ready" || state === "live";
  const label = Object.hasOwn(statusLabels, state) ? statusLabels[state] : `未知状态：${state}`;
  return <span className={`status-badge ${confirmed ? "confirmed" : "attention"}`}><span aria-hidden="true" className="status-mark" />{label}</span>;
}

export function ErrorPanel({ error, message, onRetry, retryLabel = "重试" }: { error: ApiProblem; message?: string; onRetry?: () => void; retryLabel?: string }) {
  return <div className="error-panel" role="alert"><p>{message ?? error.message}</p>{error.traceId && <p className="trace-id">追踪标识 <code>{error.traceId}</code></p>}{onRetry && <button className="button secondary" onClick={onRetry}>{retryLabel}</button>}</div>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><h3>{title}</h3><p>{description}</p></div>;
}
