import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ApiProblem, publicProblem } from "../../api/client";
import { useAuthSession } from "../../app/auth-session";
import { EmptyState, ErrorPanel } from "../../components/status";
import { getEventGraph } from "./graph-client";
import { graphNodeKinds, type GraphNodeKind, type GraphRelationKind, type GraphSnapshot } from "./graph-contracts";
import { graphLaneKinds, layoutGraph } from "./graph-layout";
import "./graph.css";

const nodeLabels: Record<GraphNodeKind, string> = { event: "事件", source_revision: "来源修订", component_version: "组件版本", atlas: "ATLAS", paper: "论文", remediation: "修复" };
const relationLabels: Record<GraphRelationKind, string> = { same_event: "归于同一事件", affects_component_version: "影响组件版本", mapped_atlas: "映射 ATLAS", related_paper: "关联论文", remediated_by: "修复依据", component_version_vulnerability: "组件版本关联事件" };
type GraphSelection = { kind: "node"; id: string } | { kind: "edge"; id: string };
type GraphResource = { kind: "loading" } | { kind: "loaded"; value: GraphSnapshot } | { kind: "failed"; error: ApiProblem };
export interface GraphExplorerProps { eventId: string; onNavigateBack?: () => void; dataMode?: "fixture" | "live" | "unknown" }

function selectWithKeyboard(event: KeyboardEvent<SVGGElement>, select: () => void) {
  if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); }
}
function GraphNodeShape({ kind }: { kind: GraphNodeKind }) {
  if (kind === "event") return <path d="M0 -34 L42 0 L0 34 L-42 0 Z" />;
  if (kind === "component_version") return <path d="M-26 -32 L26 -32 L45 0 L26 32 L-26 32 L-45 0 Z" />;
  if (kind === "atlas") return <path d="M0 -34 L40 0 L0 34 L-40 0 Z M0 -23 L27 0 L0 23 L-27 0 Z" />;
  if (kind === "paper") return <ellipse rx="42" ry="34" />;
  if (kind === "remediation") return <path d="M-42 -30 H42 V30 H-42 Z M-24 0 L-7 13 L25 -15" />;
  return <rect x="-43" y="-32" width="86" height="64" rx="3" />;
}
function GraphError({ error, retry }: { error: ApiProblem; retry: () => void }) {
  let title = "图查询未完成";
  let message = error.message;
  if (error.status === 401) { title = "需要重新登录"; message = "会话已失效。旧图已清除，请重新登录后查询。"; }
  if (error.status === 403) { title = "没有查看权限"; message = "当前授权不允许查看证据图。没有保留旧图内容。"; }
  if (error.status === 404) { title = "事件不可访问"; message = "事件不存在，或当前会话没有查看权限。"; }
  if (error.status === 409) { title = "图快照已过期"; message = "业务版本已经变化，本次图不能作为当前依据。请重新取得快照。"; }
  if (error.status === 503) { title = "图服务暂不可用"; message = "查询失败，不能解释为没有关联或没有风险。"; }
  if (error.code === "invalid_response") { title = "图协议不匹配"; message = "返回数据未通过冻结合同校验。请核对接口版本后重试。"; }
  return <div className="graph-error"><h3>{title}</h3><ErrorPanel error={error} message={message} onRetry={error.status === 401 || error.status === 403 ? undefined : retry} retryLabel="重新取得图" /></div>;
}
function IdentifierList({ title, identifiers }: { title: string; identifiers: string[] }) {
  return <details className="graph-provenance"><summary>{title} · {identifiers.length}</summary><ul>{identifiers.map((id) => <li key={id}><code>{id}</code></li>)}</ul></details>;
}
function GraphInspector({ snapshot, selection, select }: { snapshot: GraphSnapshot; selection: GraphSelection; select: (selection: GraphSelection) => void }) {
  const edge = selection.kind === "edge" ? snapshot.edges.find((item) => item.id === selection.id) : undefined;
  const node = selection.kind === "node" ? snapshot.nodes.find((item) => item.id === selection.id) : undefined;
  const subject = edge ? snapshot.nodes.find((item) => item.id === edge.subject_id) : undefined;
  const object = edge ? snapshot.nodes.find((item) => item.id === edge.object_id) : undefined;
  return <aside className="graph-inspector" aria-labelledby="graph-inspector-title">
    <div className="graph-section-heading"><p className="graph-kicker">INSPECT / 可追溯依据</p><h3 id="graph-inspector-title">{edge ? "关系检视" : "节点检视"}</h3></div>
    {edge && <>
      <span className="graph-supported">有证据支持 · 当前快照</span><h4>{relationLabels[edge.relation_type]}</h4><code className="graph-code">{edge.relation_type}</code>
      <div className="graph-endpoints"><button onClick={() => select({ kind: "node", id: edge.subject_id })}>{subject?.label}</button><span aria-hidden="true">↓</span><button onClick={() => select({ kind: "node", id: edge.object_id })}>{object?.label}</button></div>
      <p className="graph-reason">{edge.reason}</p>
      <dl className="graph-metadata"><dt>规则 / 模型版本</dt><dd>{edge.rule_or_model_version}</dd><dt>可见范围</dt><dd>{edge.scope.visibility === "public" ? "公开" : "当前授权租户"}</dd><dt>业务版本</dt><dd>{snapshot.business_version}</dd></dl>
      <div className="graph-evidence-links"><h4>原文证据 · {edge.evidence_span_ids.length}</h4><p>打开保存片段后核查其原文修订与位置。</p>{edge.evidence_span_ids.map((id, index) => <a key={id} href={`#events/${snapshot.event_id}/evidence/${id}`}>原文片段 [{index + 1}]<code>{id}</code></a>)}</div>
      <IdentifierList title="支持断言" identifiers={edge.supporting_claim_ids} /><IdentifierList title="来源修订" identifiers={edge.source_revision_ids} />
      <details className="graph-provenance"><summary>关系标识</summary><code className="graph-code">{edge.id}</code></details>
    </>}
    {node && <>
      <span className={`graph-kind-tag graph-kind-${node.kind}`}>{nodeLabels[node.kind]}</span><h4 className="graph-full-label">{node.label}</h4><code className="graph-code">{node.id}</code>
      <p className="graph-muted">{node.scope.visibility === "public" ? "公开范围" : "当前授权租户范围"} · 节点本身不是资产影响结论。</p>
      <h4>关联关系</h4><div className="graph-node-relations">{snapshot.edges.filter((item) => item.subject_id === node.id || item.object_id === node.id).map((item) => <button key={item.id} onClick={() => select({ kind: "edge", id: item.id })}>{relationLabels[item.relation_type]}<span aria-hidden="true"> ↗</span></button>)}</div>
      {!snapshot.edges.some((item) => item.subject_id === node.id || item.object_id === node.id) && <p className="graph-muted">本快照未提供该节点的支持关系。</p>}
    </>}
    <p className="graph-boundary">引文存在不等于内容支持。候选与待审关系未包含在此 supported 快照中；接口未提供人工审核进度。</p>
  </aside>;
}

function LoadedGraph({ snapshot, refresh }: { snapshot: GraphSnapshot; refresh: () => void }) {
  const [selection, setSelection] = useState<GraphSelection>({ kind: "node", id: snapshot.event_id });
  const [visibleKinds, setVisibleKinds] = useState<readonly GraphNodeKind[]>(graphNodeKinds);
  const [zoom, setZoom] = useState(1);
  const canvas = useRef<HTMLDivElement>(null);
  const layout = useMemo(() => layoutGraph(snapshot), [snapshot]);
  const positions = useMemo(() => new Map(layout.nodes.map((item) => [item.node.id, item])), [layout]);
  const visibleNodes = layout.nodes.filter((item) => visibleKinds.includes(item.node.kind));
  const visibleIds = new Set(visibleNodes.map((item) => item.node.id));
  const visibleEdges = snapshot.edges.filter((edge) => visibleIds.has(edge.subject_id) && visibleIds.has(edge.object_id));
  const selectedEdge = selection.kind === "edge" ? snapshot.edges.find((item) => item.id === selection.id) : undefined;
  function select(item: GraphSelection) { setSelection(item); }
  function reset() { setZoom(1); canvas.current?.scrollTo?.({ left: 0, top: 0, behavior: "instant" }); }
  function pan(left: number, top: number) { canvas.current?.scrollBy?.({ left, top, behavior: "instant" }); }
  function toggleKind(kind: GraphNodeKind) {
    const next = visibleKinds.includes(kind) ? visibleKinds.filter((item) => item !== kind) : [...visibleKinds, kind];
    setVisibleKinds(next);
    setSelection({ kind: "node", id: snapshot.event_id });
  }
  return <>
    <div className="graph-snapshot-bar"><span>快照 <strong>v{snapshot.business_version}</strong></span><span>{snapshot.nodes.length} 节点 / {snapshot.edges.length} 支持关系</span><span>上限 200 / 400</span><button onClick={refresh}>重新读取</button></div>
    {snapshot.truncated && <p className="graph-warning" role="status">结果已截断：只展示有界子图，隐藏部分不能解释为不存在关联。</p>}
    {snapshot.gaps.length > 0 && <details className="graph-gaps" open><summary>关系缺口 · {snapshot.gaps.length} 项未知</summary><ul>{snapshot.gaps.map((gap) => <li key={gap.relation_type}><strong>{relationLabels[gap.relation_type]}</strong><span>未知 · {gap.reason === "truncated" ? "结果限额，未完整展示" : "尚无当前受支持关系"}</span></li>)}</ul></details>}
    {snapshot.edges.length === 0 && <EmptyState title="目前只有事件上下文" description="本次查询尚无受支持关系。未知不等于否定，也不能据此判断没有风险。" />}
    <div className="graph-workspace-grid"><div className="graph-primary">
      <fieldset className="graph-types"><legend>节点类型 / 视图筛选</legend>{graphLaneKinds.map((kind) => <label key={kind}><input type="checkbox" checked={visibleKinds.includes(kind)} disabled={kind === "event"} onChange={() => toggleKind(kind)} /><span className={`graph-kind-dot graph-kind-${kind}`} aria-hidden="true" />{nodeLabels[kind]}</label>)}</fieldset>
      <div className="graph-canvas-toolbar" role="group" aria-label="图画布控制"><button disabled={zoom <= 0.8} onClick={() => setZoom((value) => Math.max(0.8, value - 0.2))} aria-label="缩小图">−</button><output aria-label="图缩放比例">{Math.round(zoom * 100)}%</output><button disabled={zoom >= 1.8} onClick={() => setZoom((value) => Math.min(1.8, value + 0.2))} aria-label="放大图">+</button><button onClick={reset}>重置视图</button><button onClick={() => pan(-240, 0)} aria-label="向左平移">←</button><button onClick={() => pan(240, 0)} aria-label="向右平移">→</button><button onClick={() => pan(0, -180)} aria-label="向上平移">↑</button><button onClick={() => pan(0, 180)} aria-label="向下平移">↓</button></div>
      <p id="graph-canvas-help" className="graph-canvas-help">图区域可滚动。Tab 选择节点或边，Enter / 空格检视；方向键滚动，缩放与重置在上方。</p>
      <div ref={canvas} className="graph-canvas" tabIndex={0} role="region" aria-label="证据关系图画布" aria-describedby="graph-canvas-help">
        <svg className="graph-scene" width={layout.width * zoom} height={layout.height * zoom} viewBox={`0 0 ${layout.width} ${layout.height}`} role="group" aria-label="事件与证据关系">
          {graphLaneKinds.map((kind, index) => <g key={kind} className="graph-lane" aria-hidden="true"><path d={`M${105 + index * 190} 85 V${layout.height - 35}`} /><text x={105 + index * 190} y="46" textAnchor="middle">{nodeLabels[kind]}</text></g>)}
          {visibleEdges.map((edge, index) => {
            const subject = positions.get(edge.subject_id); const object = positions.get(edge.object_id);
            if (!subject || !object) return null;
            const path = `M${subject.x} ${subject.y} C${subject.x + 70} ${subject.y + 50 + index % 4 * 18},${object.x - 70} ${object.y + 50 + index % 4 * 18},${object.x} ${object.y}`;
            const active = selection.kind === "edge" && selection.id === edge.id;
            return <g key={edge.id} role="button" tabIndex={0} aria-label={`图关系 ${index + 1}：${relationLabels[edge.relation_type]}`} aria-pressed={active} className={`graph-edge${active ? " graph-edge-selected" : ""}`} onClick={() => select({ kind: "edge", id: edge.id })} onKeyDown={(event) => selectWithKeyboard(event, () => select({ kind: "edge", id: edge.id }))}><title>{`${subject.node.label} → ${object.node.label}：${relationLabels[edge.relation_type]}`}</title><path className="graph-edge-hit" d={path} /><path className="graph-edge-line" d={path} /><circle className="graph-edge-direction" cx={object.x} cy={object.y + 32} r="4" /></g>;
          })}
          {visibleNodes.map(({ node, x, y }) => {
            const active = selection.kind === "node" && selection.id === node.id;
            const endpoint = selectedEdge?.subject_id === node.id || selectedEdge?.object_id === node.id;
            const label = [...node.label].slice(0, 16).join("");
            return <g key={node.id} transform={`translate(${x} ${y})`} className={`graph-node graph-kind-${node.kind}${active || endpoint ? " graph-node-selected" : ""}`} role="button" tabIndex={0} aria-label={`${nodeLabels[node.kind]}节点：${node.label}`} aria-pressed={active} onClick={() => select({ kind: "node", id: node.id })} onKeyDown={(event) => selectWithKeyboard(event, () => select({ kind: "node", id: node.id }))}><title>{node.label}</title><rect className="graph-node-hit" x="-70" y="-38" width="140" height="95" /><GraphNodeShape kind={node.kind} /><text y="5" textAnchor="middle" className="graph-node-type">{nodeLabels[node.kind]}</text><text y="61" textAnchor="middle" className="graph-node-label">{label}{[...node.label].length > 16 ? "…" : ""}</text></g>;
          })}
        </svg>
      </div>
      <section className="graph-relations" aria-labelledby="graph-relations-title"><div className="graph-section-heading"><h3 id="graph-relations-title">关系列表</h3><span>当前视图 {visibleEdges.length} / 快照 {snapshot.edges.length}</span></div><div className="graph-relation-list">{visibleEdges.map((edge, index) => <button key={edge.id} aria-pressed={selection.kind === "edge" && selection.id === edge.id} onClick={() => select({ kind: "edge", id: edge.id })}><span className="graph-relation-number">{String(index + 1).padStart(2, "0")}</span><span>{relationLabels[edge.relation_type]}<small>{positions.get(edge.subject_id)?.node.label} → {positions.get(edge.object_id)?.node.label}</small></span><span className="graph-relation-state">支持</span></button>)}</div>{visibleEdges.length === 0 && snapshot.edges.length > 0 && <p className="graph-muted">当前视图筛选隐藏了关系；快照内容未改变。</p>}</section>
    </div><GraphInspector snapshot={snapshot} selection={selection} select={select} /></div>
    <details className="graph-provenance graph-snapshot-provenance"><summary>快照版本与内容标识</summary><dl className="graph-metadata"><dt>事件标识</dt><dd><code>{snapshot.event_id}</code></dd><dt>schema / 规则版本</dt><dd>{snapshot.schema_version} / {snapshot.rule_version}</dd><dt>内容 SHA256</dt><dd><code>{snapshot.content_sha256}</code></dd></dl><p className="graph-muted">内容标识由服务返回，用于追溯；它不单独证明来源真实性。</p></details>
  </>;
}

function GraphRequest({ eventId, dataMode, onNavigateBack }: GraphExplorerProps) {
  const { sessionGeneration, expireSession, isSessionCurrent } = useAuthSession();
  const [resource, setResource] = useState<GraphResource>({ kind: "loading" });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setResource({ kind: "loading" });
    void getEventGraph(eventId, controller.signal).then((value) => {
      if (!controller.signal.aborted && isSessionCurrent(sessionGeneration)) setResource({ kind: "loaded", value });
    }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isSessionCurrent(sessionGeneration)) return;
      const error = publicProblem(failure); setResource({ kind: "failed", error });
      if (error.status === 401) expireSession(sessionGeneration);
    });
    return () => controller.abort();
  }, [eventId, retry, sessionGeneration, isSessionCurrent, expireSession]);
  function refresh() { setResource({ kind: "loading" }); setRetry((value) => value + 1); }
  return <section className="graph-explorer" aria-labelledby="graph-explorer-title"><header className="graph-page-heading"><div><p className="graph-kicker">EVIDENCE GRAPH / 关系与原文</p><h2 id="graph-explorer-title">证据关系图</h2><p>从事件到关联依据，核查每条关系的版本与证据。</p></div><div className="graph-heading-actions"><span className={`graph-mode graph-mode-${dataMode ?? "unknown"}`}>{dataMode === "fixture" ? "合成 / Fixture" : dataMode === "live" ? "真实 / Live" : "数据模式未确认"}</span>{onNavigateBack ? <button onClick={onNavigateBack}>返回事件</button> : <a href={`#events/${eventId}`}>返回事件</a>}</div></header>
    {resource.kind === "loading" && <div className="graph-loading" role="status" aria-busy="true">正在取得授权范围内的图快照…</div>}
    {resource.kind === "failed" && <GraphError error={resource.error} retry={refresh} />}
    {resource.kind === "loaded" && <LoadedGraph snapshot={resource.value} refresh={refresh} />}
  </section>;
}

/** 调用者沿用AuthProvider；换事件/会话/权限即重建读取上下文，撤权和失败不会继续展示旧图。 */
export function GraphExplorerView(props: GraphExplorerProps) {
  const { state, actionPending, sessionGeneration, error } = useAuthSession();
  if (state.kind !== "authenticated" || actionPending) return <section className="graph-explorer">{error?.status === 401 && <ErrorPanel error={error} message="会话已失效。旧图已清除，请重新登录。" />}<EmptyState title="登录后查看证据图" description="当前没有可用认证上下文。请先恢复团队会话。" /></section>;
  return <GraphRequest key={`${sessionGeneration}-${state.user.user_id}-${state.user.permission_version}-${props.eventId}`} {...props} />;
}
