import { useEffect, useRef, useState, type FormEvent } from "react";
import { publicProblem, type ApiProblem } from "../../api/client";
import { importAsset, MAX_ASSET_UPLOAD_BYTES, parseCsvMapping, type AssetImportRequest } from "./asset-client";
import type { Asset, AssetImportResult, ManifestFormat } from "./asset-contracts";
import { AssetError } from "./asset-status";

interface ImportProps { tenant: string; currentAsset: Asset | null; isCurrent: () => boolean; onImported: (result: AssetImportResult) => void; onFailure: (error: ApiProblem) => void }
type Preview = { kind: "none" | "loading" } | { kind: "ready"; format: string; components: string; completeness: string } | { kind: "failed"; message: string };

/** 预览只汇总本地文件结构，最终校验和快照身份由后端产生；原 File 原样上传。 */
export function AssetImport({ tenant, currentAsset, isCurrent, onImported, onFailure }: ImportProps) {
  const [file, setFile] = useState<File | null>(null);
  const [manifestFormat, setManifestFormat] = useState<ManifestFormat>("json_manifest_v1");
  const [displayName, setDisplayName] = useState("");
  const [sourceVersion, setSourceVersion] = useState("");
  const [observedAt, setObservedAt] = useState("");
  const [append, setAppend] = useState(false);
  const [mapping, setMapping] = useState('{"package_name":"package_name","ecosystem":"ecosystem","version":"version"}');
  const [preview, setPreview] = useState<Preview>({ kind: "none" });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiProblem | null>(null);
  const request = useRef<AssetImportRequest | null>(null);
  const controller = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => () => { controller.current?.abort(); request.current = null; }, []);
  useEffect(() => {
    let current = true;
    if (file === null) { setPreview({ kind: "none" }); return; }
    if (file.size < 1 || file.size > MAX_ASSET_UPLOAD_BYTES) { setPreview({ kind: "failed", message: "文件必须非空且不超过 1 MiB。" }); return; }
    if (manifestFormat === "csv_components_v1") { setPreview({ kind: "ready", format: "CSV 组件清单", components: "待服务端解析", completeness: "CSV 清单完整性未知" }); return; }
    setPreview({ kind: "loading" });
    void file.text().then((text) => {
      if (!current) return;
      let parsed: unknown;
      try { parsed = JSON.parse(text); } catch { setPreview({ kind: "failed", message: "JSON 语法无效，请核对原文件。" }); return; }
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) { setPreview({ kind: "failed", message: "JSON v1 清单必须是对象。" }); return; }
      const fields = Object.fromEntries(Object.entries(parsed));
      if (manifestFormat === "cyclonedx_json") {
        setPreview({ kind: "ready", format: fields.bomFormat === "CycloneDX" && ["1.5", "1.6", "1.7"].includes(String(fields.specVersion)) ? `CycloneDX JSON ${String(fields.specVersion)}` : "CycloneDX 标记或版本待服务端校验", components: Array.isArray(fields.components) ? `${fields.components.length} 个顶层组件声明（嵌套数量待服务端解析）` : "components 字段待校验", completeness: "安装范围完整性未知 · composition 仅为文档声明" });
        return;
      }
      if (manifestFormat === "spdx_json") {
        setPreview({ kind: "ready", format: fields.spdxVersion === "SPDX-2.3" ? "SPDX JSON 2.3" : "SPDX 版本待服务端校验", components: Array.isArray(fields.packages) ? `${fields.packages.length} 个 package 声明` : "packages 字段待校验", completeness: "安装范围完整性未知 · 文件和关系不证明已安装" });
        return;
      }
      let completeness = "完整性未知";
      if (fields.inventory_completeness === "complete_for_declared_scope") completeness = "文件声明：范围内完整";
      if (fields.inventory_completeness === "partial") completeness = "文件声明：部分清单";
      setPreview({ kind: "ready", format: fields.format_version === 1 ? "JSON manifest v1" : "格式版本未识别", components: Array.isArray(fields.components) ? `${fields.components.length} 个组件声明` : "components 字段待校验", completeness });
    }).catch(() => { if (current) setPreview({ kind: "failed", message: "浏览器无法读取所选文件，请重新选择。" }); });
    return () => { current = false; };
  }, [file, manifestFormat]);

  function changed() { request.current = null; setError(null); }
  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (pending || file === null || !isCurrent()) return;
    setError(null);
    try {
      if (request.current === null) {
        request.current = { file, displayName: append && currentAsset !== null ? currentAsset.display_name : displayName, sourceVersion, observedAt, manifestFormat, idempotencyKey: crypto.randomUUID(), ...(append && currentAsset !== null ? { assetId: currentAsset.asset_id } : {}), ...(manifestFormat === "csv_components_v1" ? { csvColumnMapping: parseCsvMapping(mapping) } : {}) };
      }
      setPending(true);
      controller.current = new AbortController();
      const result = await importAsset(tenant, request.current, controller.current.signal, isCurrent);
      if (!isCurrent() || controller.current.signal.aborted) return;
      request.current = null; setFile(null);
      if (fileInput.current !== null) fileInput.current.value = "";
      onImported(result);
    } catch (failure: unknown) {
      if (!isCurrent() || controller.current?.signal.aborted) return;
      const problem = publicProblem(failure); setError(problem); onFailure(problem);
    } finally { if (isCurrent()) setPending(false); }
  }
  let submitLabel = "提交授权清单";
  if (request.current !== null && error?.retryable) submitLabel = "重试相同导入";
  if (pending) submitLabel = "正在提交实际导入…";
  return <details className="panel asset-import-panel">
    <summary>导入授权清单 <span className="small-note">JSON / CSV / CycloneDX / SPDX · 最大 1 MiB</span></summary>
    <div className="asset-import-body">
      <p className="asset-boundary">仅导入已获授权的资产。原文件保留在浏览器与私有后端，页面不展示原文件内容。完整性属于输入声明，不代表独立核验。</p>
      <form onSubmit={(event) => void submit(event)}>
        <fieldset disabled={pending} className="asset-import-fields">
          <div><label htmlFor="asset-manifest-format">清单格式</label><select id="asset-manifest-format" value={manifestFormat} onChange={(event) => { const value = event.target.value; if (value === "json_manifest_v1" || value === "csv_components_v1" || value === "cyclonedx_json" || value === "spdx_json") { changed(); setManifestFormat(value); } }}><option value="json_manifest_v1">JSON manifest v1</option><option value="csv_components_v1">CSV 组件清单</option><option value="cyclonedx_json">CycloneDX JSON 1.5 / 1.6 / 1.7</option><option value="spdx_json">SPDX JSON 2.3</option></select></div>
          <div><label htmlFor="asset-manifest-file">选择本地清单</label><input ref={fileInput} id="asset-manifest-file" type="file" accept={manifestFormat === "csv_components_v1" ? ".csv,text/csv" : ".json,application/json"} required onChange={(event) => { changed(); setFile(event.target.files?.[0] ?? null); }} /></div>
          {currentAsset !== null && <label className="asset-checkbox"><input type="checkbox" checked={append} onChange={(event) => { changed(); setAppend(event.target.checked); }} />追加到当前所选资产（名称保持一致）</label>}
          <div><label htmlFor="asset-display-name">资产名称</label><input id="asset-display-name" value={append && currentAsset !== null ? currentAsset.display_name : displayName} disabled={append && currentAsset !== null} required maxLength={200} onChange={(event) => { changed(); setDisplayName(event.target.value); }} /></div>
          <div><label htmlFor="asset-source-version">输入来源版本</label><input id="asset-source-version" value={sourceVersion} required maxLength={200} placeholder="填写实际清单版本" onChange={(event) => { changed(); setSourceVersion(event.target.value); }} /></div>
          <div className="asset-form-wide"><label htmlFor="asset-observed-at">实际观察时间（含时区）</label><input id="asset-observed-at" value={observedAt} required maxLength={64} placeholder="2026-10-15T18:00:00+08:00" aria-describedby="asset-time-help" onChange={(event) => { changed(); setObservedAt(event.target.value); }} /><p id="asset-time-help" className="small-note">不要用上传时间代替观察时间；时间未知时，本接口暂不支持提交。</p></div>
          {manifestFormat === "csv_components_v1" && <div className="asset-form-wide"><label htmlFor="asset-csv-mapping">CSV 字段 → 列名映射（JSON）</label><textarea id="asset-csv-mapping" value={mapping} required maxLength={8192} onChange={(event) => { changed(); setMapping(event.target.value); }} /><p className="small-note">支持 package_name、ecosystem、display_name、purl、version、version_scheme、image_digest；映射必须覆盖文件全部列，package_name 必填。</p></div>}
        </fieldset>
        {preview.kind === "loading" && <p role="status">正在读取本地文件结构…</p>}
        {preview.kind === "failed" && <p role="alert" className="asset-warning">{preview.message}</p>}
        {preview.kind === "ready" && <dl className="asset-preview"><dt>本地结构预览</dt><dd>{preview.format}</dd><dt>组件声明</dt><dd>{preview.components}</dd><dt>完整性</dt><dd>{preview.completeness}</dd><dt>文件大小</dt><dd>{file?.size} 字节</dd></dl>}
        <p className="small-note">本地预览只读取结构，不校验完整规范、重复键或真实性。服务端决定支持范围、字段错误及最多 10000 个组件；原文件原样提交。SBOM 的完整声明不等于安装范围已核验。</p>
        <button className="button" type="submit" disabled={pending || file === null || preview.kind !== "ready"}>{submitLabel}</button>
      </form>
      {error !== null && <AssetError error={error} />}
      {pending && <p className="small-note" role="status">等待服务端提交。页面不模拟解析进度；网络中断后请用同一请求重试或核对资产列表。</p>}
    </div>
  </details>;
}
