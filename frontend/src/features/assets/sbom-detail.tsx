import { useEffect, useState, type ReactNode } from "react";
import { publicProblem, type ApiProblem } from "../../api/client";
import { getAssetSnapshotSbom } from "./asset-client";
import { AssetResponseScopeMismatch, type AssetSnapshot } from "./asset-contracts";
import { AssetError } from "./asset-status";
import type { SnapshotSbom } from "./sbom-contracts";

function Ref({ value }: { value: string }) {
  return <code>{value.startsWith("redacted-ref:") ? <>隐藏引用 · <span className="small-note">{value.slice(13, 25)}…（仅拓扑别名）</span></> : value}</code>;
}
function ReferenceList({ title, values }: { title: string; values: string[] }) {
  const [page, setPage] = useState(0);
  return <div className="sbom-composition-refs"><p>{title}: {values.length} 个引用</p><div>{values.slice(page * 20, (page + 1) * 20).map((reference, index) => <span className="sbom-ref" key={page * 20 + index}><Ref value={reference} /></span>)}</div>
    {values.length > 20 && <div className="asset-pagination"><button className="button secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页 {title} 引用</button><span className="small-note">引用页 {page + 1} / {Math.ceil(values.length / 20)}</span><button className="button secondary" disabled={(page + 1) * 20 >= values.length} onClick={() => setPage(page + 1)}>下一页 {title} 引用</button></div>}
  </div>;
}
function DeclarationRows({ items, title, sectionId, children }: { items: number; title: string; sectionId: string; children: (start: number, end: number) => ReactNode }) {
  const [page, setPage] = useState(0);
  return <section id={sectionId} tabIndex={-1} className="sbom-declaration-section"><div className="asset-section-heading"><h4>{title}</h4><span className="small-note">{items} 项 · 每页 20 项</span></div>
    {items === 0 ? <p className="asset-unknown">该文档未提供这类声明；不能据此排除依赖或风险。</p> : children(page * 20, (page + 1) * 20)}
    {items > 20 && <div className="asset-pagination"><button className="button secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页{title}</button><span className="small-note">页 {page + 1} / {Math.ceil(items / 20)}</span><button className="button secondary" disabled={(page + 1) * 20 >= items} onClick={() => setPage(page + 1)}>下一页{title}</button></div>}
  </section>;
}
function SbomView({ sbom, snapshot }: { sbom: SnapshotSbom; snapshot: AssetSnapshot }) {
  const componentNames = new Map(snapshot.components.map((component) => [component.component_id, component.display_name ?? component.package_name]));
  const sections = [
    { key: "components", title: "组件来源", items: sbom.component_sources.length },
    { key: "relationships", title: "依赖与标准关系", items: sbom.dependency_edges.length },
    { key: "completeness", title: "文档完整性声明", items: sbom.completeness_declarations.length },
    { key: "documents", title: "外部文档声明", items: sbom.external_documents.length },
    { key: "unmapped", title: "未映射字段位置", items: sbom.unmapped_field_locators.length },
    { key: "redactions", title: "隐藏位置说明", items: sbom.redactions.length },
  ];
  const sectionId = (key: string) => `sbom-${sbom.snapshot_id}-${key}`;
  function openSection(key: string) {
    const section = document.getElementById(sectionId(key));
    section?.focus({ preventScroll: true });
    section?.scrollIntoView({ behavior: "instant", block: "start" });
  }
  return <>
    <nav className="sbom-section-nav" aria-label="当前固定 SBOM 的声明导航">{sections.map((section) => <button type="button" key={section.key} aria-controls={sectionId(section.key)} onClick={() => openSection(section.key)}><span>{section.title}</span><span className="sbom-declaration-count">{section.items}</span></button>)}</nav>
    <dl className="asset-metadata"><dt>来源格式 / 规范版本</dt><dd><code>{sbom.source_format} / {sbom.spec_version}</code></dd><dt>适配器版本</dt><dd><code>{sbom.adapter_version}</code></dd><dt>原文摘要</dt><dd><code>{sbom.raw_sha256}</code></dd><dt>组合声明摘要</dt><dd><code>{sbom.combined_semantic_sha256}</code></dd><dt>展示限制</dt><dd>{sbom.redactions.length} 个位置已隐藏；未恢复原 URI、路径或凭据。</dd></dl>
    <DeclarationRows items={sbom.component_sources.length} title="组件来源" sectionId={sectionId("components")}>{(start, end) => <ul className="sbom-row-list">{sbom.component_sources.slice(start, end).map((source) => <li key={source.component_id}><div className="sbom-source-heading"><strong>{componentNames.get(source.component_id) ?? "组件名称未知"}</strong><span className="asset-tag">{source.component_type ?? "组件类型未知"}</span></div><Ref value={source.source_ref ?? "来源引用未声明"} /><code className="asset-locator">{source.component_id} · {source.source_field_locator}</code><details><summary>字段来源与校验摘要</summary><dl className="asset-component-identities">{source.field_sources.map((field, index) => <div key={index}><dt>{field.field_name}</dt><dd><code>{field.source_field_locator}</code></dd></div>)}</dl>{source.checksums.map((checksum, index) => <p key={index}><code>{checksum.algorithm}: {checksum.checksum_value}</code></p>)}<p className="small-note">checksum 是文档声明；没有对外部文件执行下载或核验。</p></details></li>)}</ul>}</DeclarationRows>
    <DeclarationRows items={sbom.dependency_edges.length} title="依赖与标准关系" sectionId={sectionId("relationships")}>{(start, end) => <div className="table-scroll"><table aria-label="SBOM 原始关系声明"><thead><tr><th scope="col">来源引用</th><th scope="col">声明关系</th><th scope="col">目标引用 / 字段位置</th></tr></thead><tbody>{sbom.dependency_edges.slice(start, end).map((edge, index) => <tr key={start + index}><td><Ref value={edge.source_ref} /></td><td><code>{edge.relationship}</code></td><td><Ref value={edge.target_ref} /><code className="asset-locator">{edge.source_field_locator}</code></td></tr>)}</tbody></table></div>}</DeclarationRows>
    <DeclarationRows items={sbom.completeness_declarations.length} title="文档完整性声明" sectionId={sectionId("completeness")}>{(start, end) => <ul className="sbom-row-list">{sbom.completeness_declarations.slice(start, end).map((declaration, index) => <li key={start + index}><strong><code>{declaration.aggregate}</code> · 输入声明</strong><code className="asset-locator">{declaration.source_field_locator}</code>{(["assemblies", "dependencies", "vulnerabilities"] as const).map((field) => <ReferenceList key={field} title={field} values={declaration[field]} />)}<p className="asset-unknown">此声明不证明授权资产安装范围完整，也不改变影响状态。</p></li>)}</ul>}</DeclarationRows>
    <DeclarationRows items={sbom.external_documents.length} title="外部文档声明" sectionId={sectionId("documents")}>{(start, end) => <ul className="sbom-row-list">{sbom.external_documents.slice(start, end).map((document, index) => <li key={start + index}><Ref value={document.document_ref} />{document.document_uri === null ? <p className="asset-warning">原 URI 已隐藏 · 不恢复或点击不安全定位</p> : <a href={document.document_uri} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">打开服务器提供的公开文档 ↗</a>}<code className="asset-locator">{document.source_field_locator}</code><p className="small-note">{document.checksum.algorithm}: <code>{document.checksum.checksum_value}</code> · 仅声明，未下载核验</p></li>)}</ul>}</DeclarationRows>
    <DeclarationRows items={sbom.unmapped_field_locators.length} title="未映射字段位置" sectionId={sectionId("unmapped")}>{(start, end) => <ul className="sbom-row-list">{sbom.unmapped_field_locators.slice(start, end).map((position, index) => <li key={start + index}><code>{position}</code></li>)}</ul>}</DeclarationRows>
    <DeclarationRows items={sbom.redactions.length} title="隐藏位置说明" sectionId={sectionId("redactions")}>{(start, end) => <ul className="sbom-row-list">{sbom.redactions.slice(start, end).map((marker) => <li key={marker.source_field_locator}><code>{marker.source_field_locator}</code><span className="asset-tag">URI / 路径展示限制</span>{marker.replacement_ref !== null && <Ref value={marker.replacement_ref} />}</li>)}</ul>}</DeclarationRows>
  </>;
}

/** 仅请求当前展示的固定 snapshot；授权代次撤销后所有迟到结果均不能重新显示。 */
export function SbomDetail({ tenant, snapshot, isCurrent, onFailure }: { tenant: string; snapshot: AssetSnapshot; isCurrent: () => boolean; onFailure: (error: ApiProblem) => void }) {
  const [result, setResult] = useState<SnapshotSbom | null>(null);
  const [error, setError] = useState<ApiProblem | null>(null);
  const [retry, setRetry] = useState(0);
  const supported = snapshot.source_kind === "cyclonedx_json" || snapshot.source_kind === "spdx_json";
  useEffect(() => {
    const controller = new AbortController(); setResult(null); setError(null);
    if (!supported) return () => controller.abort();
    void getAssetSnapshotSbom(tenant, snapshot, controller.signal).then((value) => {
      if (!controller.signal.aborted && isCurrent()) setResult(value);
    }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isCurrent()) return;
      const problem = publicProblem(failure); setError(problem);
      if (problem instanceof AssetResponseScopeMismatch || problem.status === 401 || problem.status === 403) onFailure(problem);
    });
    return () => controller.abort();
  }, [tenant, snapshot, supported, retry, isCurrent, onFailure]);
  return <section className="sbom-panel" aria-label="固定快照 SBOM 声明"><p className="eyebrow">SBOM / FROZEN DECLARATIONS</p><h4>SBOM 历史声明</h4><p className="small-note">绑定正在查看的快照，不随当前版本覆盖。来源版本未知；适配器与规范版本单列。以下关系与完整性属于输入声明，核验状态未知。</p>
    {!supported ? <p className="asset-unknown">此快照为 {snapshot.source_kind}，没有 SBOM 声明接口；不能据此判断资产安全。</p> : <>
      {result === null && error === null && <p role="status">正在读取固定快照 SBOM 声明…</p>}
      {error?.status === 404 ? <p className="asset-warning">该快照的 SBOM 声明不可用或无权读取。当前清单仍可查看，声明与核验状态保持未知。</p> : error !== null && <AssetError error={error} onRetry={() => setRetry(retry + 1)} retryLabel="重试固定 SBOM 声明" />}
      {result !== null && <SbomView key={result.snapshot_id} sbom={result} snapshot={snapshot} />}
    </>}
  </section>;
}
