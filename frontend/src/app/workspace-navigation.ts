export const workspacePages = {
  runtime: { label: "运行状态", title: "运行概览", code: "SYSTEM / RUNTIME", description: "查看服务状态，管理你的团队会话。", group: "系统", symbol: "◫" },
  events: { label: "情报列表", title: "情报工作区", code: "INTELLIGENCE / FEED", description: "从事件线索进入事实、版本与原文证据。", group: "研究", symbol: "≡" },
  sources: { label: "来源监测", title: "来源与采集", code: "COLLECTION / SOURCES", description: "区分来源覆盖、实际接通与采集时效。", group: "研究", symbol: "◉" },
  documents: { label: "资料库", title: "资料与原文", code: "RESEARCH / DOCUMENTS", description: "核查论文、标准、政策与研究资料的原文版本和覆盖范围。", group: "研究", symbol: "▤" },
  graph: { label: "知识图谱", title: "关联研究", code: "KNOWLEDGE / RELATIONS", description: "查看关系理由、证据与历史状态。", group: "研究", symbol: "◇" },
  questions: { label: "引用问答", title: "证据问答", code: "RESEARCH / QUESTIONS", description: "跨文档研究，让每条关键结论都有依据。", group: "研究", symbol: ">_" },
  assets: { label: "资产自查", title: "版本与资产", code: "ASSESSMENT / ASSETS", description: "在固定资产快照上核查版本、条件与影响。", group: "研究", symbol: "⬡" },
  assessments: { label: "影响研判", title: "资产影响研判", code: "ASSESSMENT / EVIDENCE", description: "固定授权资产快照与规则，核查四态结果、时效和证据。", group: "研究", symbol: "⊞" },
  tasks: { label: "任务轨迹", title: "调查与任务", code: "OPERATIONS / RUNS", description: "核对实际工具调用、停止原因与结果。", group: "协作", symbol: "⌘" },
  changes: { label: "变化与推荐", title: "变化与关注", code: "UPDATES / WATCH", description: "追踪结论修订、新增命中与订阅变化。", group: "协作", symbol: "↗" },
  reports: { label: "证据报告", title: "报告与交付", code: "EVIDENCE / REPORTS", description: "查看有版本与范围说明的可核查报告。", group: "协作", symbol: "▤" },
  session: { label: "会话与权限", title: "访问控制", code: "ACCESS / SESSION", description: "核对当前团队身份、授权与会话状态。", group: "系统", symbol: "◎" },
} as const;

export type WorkspacePage = keyof typeof workspacePages;

function isWorkspacePage(page: string): page is WorkspacePage {
  return Object.hasOwn(workspacePages, page);
}

export function readEventSelection(hash: string): { eventId: string; evidenceId: string | null; revisionId: string | null } | null {
  const uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
  const match = new RegExp(`^#events/(${uuid})(?:/evidence/(${uuid})(?:/revision/(${uuid}))?)?$`, "i").exec(hash);
  const eventId = match?.[1];
  return eventId === undefined ? null : { eventId: eventId.toLowerCase(), evidenceId: match?.[2]?.toLowerCase() ?? null, revisionId: match?.[3]?.toLowerCase() ?? null };
}

export function readDocumentSelection(hash: string): { documentId: string; revisionId: string | null } | null {
  const uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
  const match = new RegExp(`^#documents/(${uuid})(?:/revision/(${uuid}))?$`, "i").exec(hash);
  const documentId = match?.[1];
  return documentId === undefined ? null : { documentId: documentId.toLowerCase(), revisionId: match?.[2]?.toLowerCase() ?? null };
}

/** 图谱只接受一个事件UUID；租户与可见范围仍由服务端会话确定。 */
export function readGraphSelection(hash: string): { eventId: string } | null {
  const match = /^#graph\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(hash);
  const eventId = match?.[1];
  return eventId === undefined ? null : { eventId: eventId.toLowerCase() };
}

/** 资产导航使用后端 UUID；租户与权限不从 hash 读取。 */
export function readAssetSelection(hash: string): { assetId: string } | null {
  const match = /^#assets\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(hash);
  const assetId = match?.[1];
  return assetId === undefined ? null : { assetId: assetId.toLowerCase() };
}

/** Hash 导航仅表示页面，不持久化私有数据；未知页面保留可解释的返回路径。 */
export function readWorkspacePage(hash: string): WorkspacePage | "missing" {
  const page = hash.replace(/^#/, "");
  if (!page || page === "main-content") return "runtime";
  if (readEventSelection(hash) !== null) return "events";
  if (readDocumentSelection(hash) !== null) return "documents";
  if (readGraphSelection(hash) !== null) return "graph";
  if (readAssetSelection(hash) !== null) return "assets";
  return isWorkspacePage(page) ? page : "missing";
}
