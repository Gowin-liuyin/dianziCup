import { AssetResponseScopeMismatch, isAssetIdentifier, isSafeSbomPurl, type AssetSnapshot } from "./asset-contracts";

export interface SbomFieldSource { field_name: string; source_field_locator: string }
export interface SbomChecksum { algorithm: string; checksum_value: string; source_field_locator: string }
export interface SbomComponentSource { component_id: string; source_ref: string | null; component_type: string | null; source_field_locator: string; field_sources: SbomFieldSource[]; checksums: SbomChecksum[] }
export interface SbomDependencyEdge { source_ref: string; target_ref: string; relationship: string; source_field_locator: string }
export interface SbomCompletenessDeclaration { aggregate: string; assemblies: string[]; dependencies: string[]; vulnerabilities: string[]; source_field_locator: string }
export interface SbomExternalDocument { document_ref: string; document_uri: string | null; checksum: SbomChecksum; source_field_locator: string }
export interface SbomRedaction { source_field_locator: string; reason: "unsafe_uri_or_path"; replacement_ref: string | null }
export interface SnapshotSbom {
  schema_version: "r11-sbom-sidecar-2"; snapshot_id: string; asset_id: string; tenant_id: string;
  adapter_version: "r11-sbom-adapter-1"; source_format: "cyclonedx_json" | "spdx_json";
  spec_version: "1.5" | "1.6" | "1.7" | "SPDX-2.3";
  projection_sha256: string; sidecar_sha256: string; combined_semantic_sha256: string; raw_sha256: string;
  component_sources: SbomComponentSource[]; dependency_edges: SbomDependencyEdge[];
  completeness_declarations: SbomCompletenessDeclaration[]; external_documents: SbomExternalDocument[];
  unmapped_field_locators: string[]; redactions: SbomRedaction[];
}

function invalid(): never { throw new AssetResponseScopeMismatch(); }
function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid();
  if (Object.keys(value).length !== keys.length || Object.keys(value).some((key) => !keys.includes(key))) return invalid();
  return Object.fromEntries(Object.entries(value));
}
function text(value: unknown): string {
  return typeof value === "string" && value.length > 0 && [...value].length <= 4096 && !/[\u0000-\u001f\u007f]/.test(value) ? value : invalid();
}
function nullableText(value: unknown): string | null { return value === null ? null : text(value); }
function hash(value: unknown): string { const result = text(value); return /^[0-9a-f]{64}$/.test(result) ? result : invalid(); }
function token(value: unknown): string { const result = text(value); return /^[A-Za-z][A-Za-z0-9_-]*$/.test(result) ? result : invalid(); }
function identifier(value: unknown): string { const result = text(value); return isAssetIdentifier(result) ? result.toLowerCase() : invalid(); }
function list<T>(value: unknown, parse: (item: unknown) => T, maximum = 200000): T[] {
  return Array.isArray(value) && value.length <= maximum ? value.map((item: unknown) => parse(item)) : invalid();
}
function decoded(value: string): string | null {
  try {
    for (let round = 0; round < 4; round += 1) {
      if (!value.includes("%")) return value;
      value = decodeURIComponent(value);
    }
    return value.includes("%") ? null : value;
  } catch { return null; }
}

/** 可点击 URI 只允许服务器公开的无凭据 HTTP(S)；不执行 DNS、URL 抓取或原值恢复。 */
export function isSafeSbomDocumentUri(value: string): boolean {
  if (/[^\x21-\x7e]|[\\?#]/.test(value) || !/^https?:\/\//i.test(value)) return false;
  const authority = value.slice(value.indexOf("//") + 2).split("/")[0];
  if (!authority || /[%@]/.test(authority)) return false;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase().replace(/\.$/, "");
    if (url.username || url.password || url.search || url.hash) return false;
    if (host.startsWith("[")) {
      const literal = host.slice(1, -1); const first = Number.parseInt(literal.split(":")[0] ?? "", 16);
      if (!(first >= 0x2000 && first <= 0x3fff) || /^2001:(?:db8|0|1[0-9a-f]|2[0-9a-f]):/i.test(literal)) return false;
    } else if (/^[0-9.]+$/.test(host)) {
      const [first = -1, second = -1, third = -1, fourth = -1] = host.split(".").map(Number);
      if (first <= 0 || first === 10 || first === 127 || first >= 224 || (first === 100 && second >= 64 && second <= 127) || (first === 169 && second === 254) || (first === 172 && second >= 16 && second <= 31) || (first === 192 && second === 168) || (first === 192 && second === 0 && third === 0 && fourth !== 9 && fourth !== 10) || (first === 192 && second === 0 && third === 2) || (first === 198 && (second === 18 || second === 19 || (second === 51 && third === 100))) || (first === 203 && second === 0 && third === 113)) return false;
    } else if (!host.includes(".") || /(?:^|\.)(localhost|localdomain|local|internal|lan|home|intranet)$/.test(host) || host.length > 253 || host.split(".").some((part) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(part))) return false;
    const rawPath = value.slice(value.indexOf("//") + 2 + authority.length);
    const path = decoded(rawPath);
    return path !== null && !/[\u0000-\u0020\u007f\\:@?#%]/.test(path);
  } catch { return false; }
}
function safeReference(value: string): boolean {
  if (/^[A-Za-z0-9][A-Za-z0-9._@+-]*$/.test(value)) return true;
  if (/^DocumentRef-[A-Za-z0-9.+-]+:SPDXRef-[A-Za-z0-9.-]+$/.test(value)) return true;
  if (/^urn:uuid:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value)) return true;
  if (/^urn:cdx:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/[1-9][0-9]*#[A-Za-z0-9][A-Za-z0-9._@+-]*$/.test(value)) return true;
  if (value.startsWith("pkg:")) {
    return isSafeSbomPurl(value);
  }
  return isSafeSbomDocumentUri(value);
}
function locator(value: unknown): string {
  const result = text(value);
  if (!result.startsWith("/")) return invalid();
  for (const field of result.split("/").slice(1)) {
    if (/^redacted-field:[0-9a-f]{64}$/.test(field)) continue;
    const original = decoded(field.replace(/~1/g, "/").replace(/~0/g, "~"));
    if (original === null || /[\u0000-\u001f\u007f]/.test(original) || /^(?:[/\\]|~\/|[A-Za-z][A-Za-z0-9+.-]*:)/.test(original)) return invalid();
  }
  return result;
}
function checksum(value: unknown): SbomChecksum {
  const item = record(value, ["algorithm", "checksum_value", "source_field_locator"]);
  const digest = text(item.checksum_value);
  if (!/^[0-9a-f]+$/i.test(digest)) return invalid();
  return { algorithm: token(item.algorithm), checksum_value: digest, source_field_locator: locator(item.source_field_locator) };
}

/** sidecar 只绑定已取得的固定快照；合同/范围/展示安全违例撤销整个私有工作区。 */
export function parseSnapshotSbom(value: unknown, tenant: string, snapshot: AssetSnapshot): SnapshotSbom {
  const item = record(value, ["schema_version", "snapshot_id", "asset_id", "tenant_id", "adapter_version", "source_format", "spec_version", "projection_sha256", "sidecar_sha256", "combined_semantic_sha256", "raw_sha256", "component_sources", "dependency_edges", "completeness_declarations", "external_documents", "unmapped_field_locators", "redactions"]);
  if (item.tenant_id !== tenant || snapshot.tenant_id !== tenant || identifier(item.asset_id) !== snapshot.asset_id || identifier(item.snapshot_id) !== snapshot.snapshot_id || item.projection_sha256 !== snapshot.snapshot_sha256) return invalid();
  if (item.schema_version !== "r11-sbom-sidecar-2" || item.adapter_version !== "r11-sbom-adapter-1" || item.source_format !== snapshot.source_kind) return invalid();
  const format = item.source_format;
  const version = item.spec_version;
  if (format !== "cyclonedx_json" && format !== "spdx_json") return invalid();
  if (version !== "1.5" && version !== "1.6" && version !== "1.7" && version !== "SPDX-2.3") return invalid();
  if (!(format === "cyclonedx_json" ? version === "1.5" || version === "1.6" || version === "1.7" : version === "SPDX-2.3")) return invalid();
  const redactions = list(item.redactions, (entry): SbomRedaction => {
    const marker = record(entry, ["source_field_locator", "reason", "replacement_ref"]);
    if (marker.reason !== "unsafe_uri_or_path") return invalid();
    const replacement = nullableText(marker.replacement_ref);
    if (replacement !== null && !/^redacted-ref:[0-9a-f]{64}$/.test(replacement)) return invalid();
    return { source_field_locator: locator(marker.source_field_locator), reason: marker.reason, replacement_ref: replacement };
  });
  const markers = new Map(redactions.map((marker) => [marker.source_field_locator, marker]));
  if (markers.size !== redactions.length) return invalid();
  const used = new Set<string>();
  function reference(value: unknown, position: string): string {
    const result = text(value);
    const marker = markers.get(position);
    if (marker !== undefined) {
      if (marker.replacement_ref !== result) return invalid();
      used.add(position);
    } else if (!safeReference(result)) return invalid();
    return result;
  }
  const componentIds = new Set(snapshot.components.map((component) => component.component_id));
  const components = list(item.component_sources, (entry): SbomComponentSource => {
    const source = record(entry, ["component_id", "source_ref", "component_type", "source_field_locator", "field_sources", "checksums"]);
    const id = identifier(source.component_id);
    if (!componentIds.has(id)) return invalid();
    const position = locator(source.source_field_locator);
    return { component_id: id, source_ref: source.source_ref === null ? null : reference(source.source_ref, position + (format === "cyclonedx_json" ? "/bom-ref" : "/SPDXID")), component_type: source.component_type === null ? null : token(source.component_type), source_field_locator: position,
      field_sources: list(source.field_sources, (field): SbomFieldSource => {
        const parsed = record(field, ["field_name", "source_field_locator"]);
        const fieldName = token(parsed.field_name); const fieldLocator = locator(parsed.source_field_locator);
        if (fieldName === "purl" && markers.get(fieldLocator)?.replacement_ref === null) used.add(fieldLocator);
        return { field_name: fieldName, source_field_locator: fieldLocator };
      }, 64), checksums: list(source.checksums, checksum, 64) };
  }, 10000);
  if (new Set(components.map((source) => source.component_id)).size !== components.length) return invalid();
  const edges = list(item.dependency_edges, (entry): SbomDependencyEdge => {
    const edge = record(entry, ["source_ref", "target_ref", "relationship", "source_field_locator"]);
    const position = locator(edge.source_field_locator);
    const sourcePosition = format === "cyclonedx_json" ? position.split("/").slice(0, -2).join("/") + "/ref" : position + "/spdxElementId";
    const targetPosition = format === "cyclonedx_json" ? position : position + "/relatedSpdxElement";
    return { source_ref: reference(edge.source_ref, sourcePosition), target_ref: reference(edge.target_ref, targetPosition), relationship: token(edge.relationship), source_field_locator: position };
  });
  const declarations = list(item.completeness_declarations, (entry): SbomCompletenessDeclaration => {
    const declaration = record(entry, ["aggregate", "assemblies", "dependencies", "vulnerabilities", "source_field_locator"]);
    const position = locator(declaration.source_field_locator);
    const references = (field: "assemblies" | "dependencies" | "vulnerabilities") => list(declaration[field], (entry) => entry, 10000).map((value, index) => reference(value, `${position}/${field}/${index}`));
    return { aggregate: token(declaration.aggregate), assemblies: references("assemblies"), dependencies: references("dependencies"), vulnerabilities: references("vulnerabilities"), source_field_locator: position };
  }, 10000);
  const documents = list(item.external_documents, (entry): SbomExternalDocument => {
    const document = record(entry, ["document_ref", "document_uri", "checksum", "source_field_locator"]);
    const position = locator(document.source_field_locator); const uriPosition = position + "/spdxDocument";
    const uri = nullableText(document.document_uri);
    if (uri === null) {
      if (markers.get(uriPosition)?.replacement_ref !== null) return invalid();
      used.add(uriPosition);
    } else if (!isSafeSbomDocumentUri(uri) || markers.has(uriPosition)) return invalid();
    return { document_ref: reference(document.document_ref, position + "/externalDocumentId"), document_uri: uri, checksum: checksum(document.checksum), source_field_locator: position };
  }, 10000);
  const unmapped = list(item.unmapped_field_locators, (entry) => locator(entry));
  for (const position of unmapped) {
    if (position.split("/").some((field) => /^redacted-field:[0-9a-f]{64}$/.test(field))) {
      if (markers.get(position)?.replacement_ref !== null) return invalid();
      used.add(position);
    }
  }
  if (markers.size !== used.size) return invalid();
  return { schema_version: "r11-sbom-sidecar-2", snapshot_id: snapshot.snapshot_id, asset_id: snapshot.asset_id, tenant_id: tenant, adapter_version: "r11-sbom-adapter-1", source_format: format, spec_version: version,
    projection_sha256: hash(item.projection_sha256), sidecar_sha256: hash(item.sidecar_sha256), combined_semantic_sha256: hash(item.combined_semantic_sha256), raw_sha256: hash(item.raw_sha256), component_sources: components, dependency_edges: edges, completeness_declarations: declarations, external_documents: documents, unmapped_field_locators: unmapped, redactions };
}
