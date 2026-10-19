// ../reports/runs/recovery_r17_sbom_workbench_review1_fix1_20261016/frontend_profile_probe.ts
var import_node_fs = require("node:fs");
var import_node_assert = require("node:assert");

// src/api/client.ts
var errorMessages = {
  invalid_credentials: "\u7528\u6237\u540D\u6216\u5BC6\u7801\u4E0D\u6B63\u786E\u3002",
  unauthenticated: "\u8BF7\u767B\u5F55\u540E\u7EE7\u7EED\u3002",
  session_expired: "\u4F1A\u8BDD\u5DF2\u5931\u6548\uFF0C\u8BF7\u91CD\u65B0\u767B\u5F55\u3002",
  login_rate_limited: "\u767B\u5F55\u8BF7\u6C42\u8FC7\u4E8E\u9891\u7E41\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5\u3002",
  csrf_rejected: "\u4F1A\u8BDD\u6821\u9A8C\u672A\u901A\u8FC7\uFF0C\u8BF7\u91CD\u65B0\u68C0\u67E5\u4F1A\u8BDD\u3002",
  forbidden: "\u5F53\u524D\u64CD\u4F5C\u6CA1\u6709\u6743\u9650\uFF0C\u8BF7\u8054\u7CFB\u7BA1\u7406\u5458\u3002",
  dependency_unavailable: "\u670D\u52A1\u6682\u4E0D\u53EF\u7528\uFF0C\u8BF7\u68C0\u67E5\u8FD0\u884C\u72B6\u6001\u540E\u91CD\u8BD5\u3002",
  service_unavailable: "\u670D\u52A1\u6682\u4E0D\u53EF\u7528\uFF0C\u8BF7\u68C0\u67E5\u8FD0\u884C\u72B6\u6001\u540E\u91CD\u8BD5\u3002",
  validation_error: "\u8BF7\u6C42\u5185\u5BB9\u672A\u901A\u8FC7\u6821\u9A8C\uFF0C\u8BF7\u68C0\u67E5\u8F93\u5165\u3002",
  network_unavailable: "\u65E0\u6CD5\u8FDE\u63A5\u670D\u52A1\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u8BD5\u3002",
  request_timeout: "\u670D\u52A1\u54CD\u5E94\u8D85\u65F6\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5\u3002",
  request_canceled: "\u8BF7\u6C42\u5DF2\u53D6\u6D88\u3002",
  invalid_response: "\u670D\u52A1\u8FD4\u56DE\u7684\u6570\u636E\u683C\u5F0F\u4E0D\u7B26\u5408\u63A5\u53E3\u7EA6\u5B9A\uFF0C\u8BF7\u91CD\u65B0\u68C0\u67E5\u3002"
};
var ApiProblem = class extends Error {
  constructor(status, code, retryable, traceId) {
    super(Object.hasOwn(errorMessages, code) ? errorMessages[code] : "\u64CD\u4F5C\u672A\u5B8C\u6210\uFF0C\u8BF7\u91CD\u8BD5\u6216\u8054\u7CFB\u7BA1\u7406\u5458\u3002");
    this.status = status;
    this.code = code;
    this.retryable = retryable;
    this.traceId = traceId;
    this.name = "ApiProblem";
  }
};

// src/features/assets/asset-contracts.ts
var AssetResponseScopeMismatch = class extends ApiProblem {
  constructor() {
    super(502, "invalid_response", false);
    this.name = "AssetResponseScopeMismatch";
  }
};
function invalid() {
  throw new ApiProblem(502, "invalid_response", true);
}
function record(value, keys) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid();
  if (Object.keys(value).length !== keys.length || Object.keys(value).some((key) => !keys.includes(key))) return invalid();
  return Object.fromEntries(Object.entries(value));
}
function text(value, maximum = 4096) {
  if (typeof value !== "string" || !value || [...value].length > maximum || /[\u0000-\u001f]/.test(value)) return invalid();
  return value;
}
function nullableText(value) {
  return value === null ? null : text(value);
}
function isAssetIdentifier(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
function identifier(value) {
  const id = text(value, 36);
  return isAssetIdentifier(id) ? id.toLowerCase() : invalid();
}
function timestamp(value) {
  const result = text(value, 64);
  return /T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(result) && Number.isFinite(Date.parse(result)) ? result : invalid();
}
function list(value, parse, maximum) {
  return Array.isArray(value) && value.length <= maximum ? value.map((item) => parse(item)) : invalid();
}
function unique(items, identity) {
  return new Set(items.map(identity)).size === items.length ? items : invalid();
}
function strings(value) {
  return list(value, (item) => text(item), 64);
}
function field(value) {
  const item = record(value, ["name", "value", "source_field_locator"]);
  const declaredValue = item.value === null || typeof item.value === "boolean" ? item.value : text(item.value);
  return { name: text(item.name), value: declaredValue, source_field_locator: text(item.source_field_locator) };
}
function fields(value) {
  return unique(list(value, field, 64), (item) => item.name);
}
function component(value) {
  const item = record(value, ["component_id", "ecosystem", "package_name", "display_name", "purl", "version", "version_scheme", "image_digest", "dependency_path", "source_field_locator"]);
  return { component_id: identifier(item.component_id), ecosystem: text(item.ecosystem), package_name: text(item.package_name), display_name: nullableText(item.display_name), purl: nullableText(item.purl), version: nullableText(item.version), version_scheme: text(item.version_scheme), image_digest: nullableText(item.image_digest), dependency_path: item.dependency_path === null ? null : strings(item.dependency_path), source_field_locator: text(item.source_field_locator) };
}
function isSafeSbomPurl(value) {
  if (!value.startsWith("pkg:") || /[\u0000-\u0020\u007f?#]/.test(value)) return false;
  const match = /^pkg:([a-z][a-z0-9._-]*)\/(.+)$/i.exec(value);
  const type = match?.[1]?.toLowerCase();
  let path = match?.[2];
  if (type === void 0 || path === void 0) return false;
  let namespace = "";
  if (type === "npm" && path.startsWith("@")) {
    const scopeEnd = path.indexOf("/");
    if (scopeEnd < 1) return false;
    namespace = path.slice(0, scopeEnd);
    path = path.slice(scopeEnd + 1);
  }
  const versionPosition = path.lastIndexOf("@");
  const packagePath = versionPosition < 0 ? path : path.slice(0, versionPosition);
  const rawVersion = versionPosition < 0 ? null : path.slice(versionPosition + 1);
  if (!packagePath || packagePath.endsWith("/") || rawVersion === "") return false;
  try {
    const fields2 = [namespace, packagePath, rawVersion ?? ""].map((field2) => decodeURIComponent(field2));
    if (fields2.some((field2) => /[\u0000-\u0020\u007f\\:%?#]/.test(field2))) return false;
    return !/[\/@]/.test(fields2[2] ?? "");
  } catch {
    return false;
  }
}
function parseSnapshot(value, tenant, assetId) {
  const item = record(value, ["schema_version", "snapshot_id", "asset_id", "tenant_id", "snapshot_number", "observed_at", "recorded_at", "source_kind", "inventory_completeness", "declared_scope", "components", "configuration", "tool_permissions", "input_channels", "network_exposure", "snapshot_sha256"]);
  if (item.tenant_id !== tenant || identifier(item.asset_id) !== assetId.toLowerCase()) throw new AssetResponseScopeMismatch();
  if (item.schema_version !== "r11-asset-candidate-1") return invalid();
  const completeness = item.inventory_completeness;
  if (completeness !== "complete_for_declared_scope" && completeness !== "partial" && completeness !== "unknown") return invalid();
  if (typeof item.snapshot_number !== "number" || !Number.isSafeInteger(item.snapshot_number) || item.snapshot_number < 1) return invalid();
  const hash2 = text(item.snapshot_sha256, 64);
  if (!/^[0-9a-f]{64}$/.test(hash2)) return invalid();
  const components = unique(list(item.components, component, 1e4), (entry) => entry.component_id);
  if ((item.source_kind === "cyclonedx_json" || item.source_kind === "spdx_json") && components.some((entry) => entry.purl !== null && !isSafeSbomPurl(entry.purl))) throw new AssetResponseScopeMismatch();
  return { schema_version: item.schema_version, snapshot_id: identifier(item.snapshot_id), asset_id: identifier(item.asset_id), tenant_id: tenant, snapshot_number: item.snapshot_number, observed_at: timestamp(item.observed_at), recorded_at: timestamp(item.recorded_at), source_kind: text(item.source_kind), inventory_completeness: completeness, declared_scope: strings(item.declared_scope), components, configuration: fields(item.configuration), tool_permissions: item.tool_permissions === null ? null : strings(item.tool_permissions), input_channels: item.input_channels === null ? null : fields(item.input_channels), network_exposure: item.network_exposure === null ? null : fields(item.network_exposure), snapshot_sha256: hash2 };
}

// src/features/assets/sbom-contracts.ts
function invalid2() {
  throw new AssetResponseScopeMismatch();
}
function record2(value, keys) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid2();
  if (Object.keys(value).length !== keys.length || Object.keys(value).some((key) => !keys.includes(key))) return invalid2();
  return Object.fromEntries(Object.entries(value));
}
function text2(value) {
  return typeof value === "string" && value.length > 0 && [...value].length <= 4096 && !/[\u0000-\u001f\u007f]/.test(value) ? value : invalid2();
}
function nullableText2(value) {
  return value === null ? null : text2(value);
}
function hash(value) {
  const result = text2(value);
  return /^[0-9a-f]{64}$/.test(result) ? result : invalid2();
}
function token(value) {
  const result = text2(value);
  return /^[A-Za-z][A-Za-z0-9_-]*$/.test(result) ? result : invalid2();
}
function identifier2(value) {
  const result = text2(value);
  return isAssetIdentifier(result) ? result.toLowerCase() : invalid2();
}
function list2(value, parse, maximum = 2e5) {
  return Array.isArray(value) && value.length <= maximum ? value.map((item) => parse(item)) : invalid2();
}
function decoded(value) {
  try {
    for (let round = 0; round < 4; round += 1) {
      if (!value.includes("%")) return value;
      value = decodeURIComponent(value);
    }
    return value.includes("%") ? null : value;
  } catch {
    return null;
  }
}
function isSafeSbomDocumentUri(value) {
  if (/[^\x21-\x7e]|[\\?#]/.test(value) || !/^https?:\/\//i.test(value)) return false;
  const authority = value.slice(value.indexOf("//") + 2).split("/")[0];
  if (!authority || /[%@]/.test(authority)) return false;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase().replace(/\.$/, "");
    if (url.username || url.password || url.search || url.hash) return false;
    if (host.startsWith("[")) {
      const literal = host.slice(1, -1);
      const first = Number.parseInt(literal.split(":")[0] ?? "", 16);
      if (!(first >= 8192 && first <= 16383) || /^2001:(?:db8|0|1[0-9a-f]|2[0-9a-f]):/i.test(literal)) return false;
    } else if (/^[0-9.]+$/.test(host)) {
      const [first = -1, second = -1, third = -1, fourth = -1] = host.split(".").map(Number);
      if (first <= 0 || first === 10 || first === 127 || first >= 224 || first === 100 && second >= 64 && second <= 127 || first === 169 && second === 254 || first === 172 && second >= 16 && second <= 31 || first === 192 && second === 168 || first === 192 && second === 0 && third === 0 && fourth !== 9 && fourth !== 10 || first === 192 && second === 0 && third === 2 || first === 198 && (second === 18 || second === 19 || second === 51 && third === 100) || first === 203 && second === 0 && third === 113) return false;
    } else if (!host.includes(".") || /(?:^|\.)(localhost|localdomain|local|internal|lan|home|intranet)$/.test(host) || host.length > 253 || host.split(".").some((part) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(part))) return false;
    const rawPath = value.slice(value.indexOf("//") + 2 + authority.length);
    const path = decoded(rawPath);
    return path !== null && !/[\u0000-\u0020\u007f\\:@?#%]/.test(path);
  } catch {
    return false;
  }
}
function safeReference(value) {
  if (/^[A-Za-z0-9][A-Za-z0-9._@+-]*$/.test(value)) return true;
  if (/^DocumentRef-[A-Za-z0-9.+-]+:SPDXRef-[A-Za-z0-9.-]+$/.test(value)) return true;
  if (/^urn:uuid:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value)) return true;
  if (/^urn:cdx:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/[1-9][0-9]*#[A-Za-z0-9][A-Za-z0-9._@+-]*$/.test(value)) return true;
  if (value.startsWith("pkg:")) {
    return isSafeSbomPurl(value);
  }
  return isSafeSbomDocumentUri(value);
}
function locator(value) {
  const result = text2(value);
  if (!result.startsWith("/")) return invalid2();
  for (const field2 of result.split("/").slice(1)) {
    if (/^redacted-field:[0-9a-f]{64}$/.test(field2)) continue;
    const original = decoded(field2.replace(/~1/g, "/").replace(/~0/g, "~"));
    if (original === null || /[\u0000-\u001f\u007f]/.test(original) || /^(?:[/\\]|~\/|[A-Za-z][A-Za-z0-9+.-]*:)/.test(original)) return invalid2();
  }
  return result;
}
function checksum(value) {
  const item = record2(value, ["algorithm", "checksum_value", "source_field_locator"]);
  const digest = text2(item.checksum_value);
  if (!/^[0-9a-f]+$/i.test(digest)) return invalid2();
  return { algorithm: token(item.algorithm), checksum_value: digest, source_field_locator: locator(item.source_field_locator) };
}
function parseSnapshotSbom(value, tenant, snapshot) {
  const item = record2(value, ["schema_version", "snapshot_id", "asset_id", "tenant_id", "adapter_version", "source_format", "spec_version", "projection_sha256", "sidecar_sha256", "combined_semantic_sha256", "raw_sha256", "component_sources", "dependency_edges", "completeness_declarations", "external_documents", "unmapped_field_locators", "redactions"]);
  if (item.tenant_id !== tenant || snapshot.tenant_id !== tenant || identifier2(item.asset_id) !== snapshot.asset_id || identifier2(item.snapshot_id) !== snapshot.snapshot_id || item.projection_sha256 !== snapshot.snapshot_sha256) return invalid2();
  if (item.schema_version !== "r11-sbom-sidecar-2" || item.adapter_version !== "r11-sbom-adapter-1" || item.source_format !== snapshot.source_kind) return invalid2();
  const format = item.source_format;
  const version = item.spec_version;
  if (format !== "cyclonedx_json" && format !== "spdx_json") return invalid2();
  if (version !== "1.5" && version !== "1.6" && version !== "1.7" && version !== "SPDX-2.3") return invalid2();
  if (!(format === "cyclonedx_json" ? version === "1.5" || version === "1.6" || version === "1.7" : version === "SPDX-2.3")) return invalid2();
  const redactions = list2(item.redactions, (entry) => {
    const marker = record2(entry, ["source_field_locator", "reason", "replacement_ref"]);
    if (marker.reason !== "unsafe_uri_or_path") return invalid2();
    const replacement = nullableText2(marker.replacement_ref);
    if (replacement !== null && !/^redacted-ref:[0-9a-f]{64}$/.test(replacement)) return invalid2();
    return { source_field_locator: locator(marker.source_field_locator), reason: marker.reason, replacement_ref: replacement };
  });
  const markers = new Map(redactions.map((marker) => [marker.source_field_locator, marker]));
  if (markers.size !== redactions.length) return invalid2();
  const used = /* @__PURE__ */ new Set();
  function reference(value2, position) {
    const result = text2(value2);
    const marker = markers.get(position);
    if (marker !== void 0) {
      if (marker.replacement_ref !== result) return invalid2();
      used.add(position);
    } else if (!safeReference(result)) return invalid2();
    return result;
  }
  const componentIds = new Set(snapshot.components.map((component2) => component2.component_id));
  const components = list2(item.component_sources, (entry) => {
    const source = record2(entry, ["component_id", "source_ref", "component_type", "source_field_locator", "field_sources", "checksums"]);
    const id = identifier2(source.component_id);
    if (!componentIds.has(id)) return invalid2();
    const position = locator(source.source_field_locator);
    return {
      component_id: id,
      source_ref: source.source_ref === null ? null : reference(source.source_ref, position + (format === "cyclonedx_json" ? "/bom-ref" : "/SPDXID")),
      component_type: source.component_type === null ? null : token(source.component_type),
      source_field_locator: position,
      field_sources: list2(source.field_sources, (field2) => {
        const parsed = record2(field2, ["field_name", "source_field_locator"]);
        const fieldName = token(parsed.field_name);
        const fieldLocator = locator(parsed.source_field_locator);
        if (fieldName === "purl" && markers.get(fieldLocator)?.replacement_ref === null) used.add(fieldLocator);
        return { field_name: fieldName, source_field_locator: fieldLocator };
      }, 64),
      checksums: list2(source.checksums, checksum, 64)
    };
  }, 1e4);
  if (new Set(components.map((source) => source.component_id)).size !== components.length) return invalid2();
  const edges = list2(item.dependency_edges, (entry) => {
    const edge = record2(entry, ["source_ref", "target_ref", "relationship", "source_field_locator"]);
    const position = locator(edge.source_field_locator);
    const sourcePosition = format === "cyclonedx_json" ? position.split("/").slice(0, -2).join("/") + "/ref" : position + "/spdxElementId";
    const targetPosition = format === "cyclonedx_json" ? position : position + "/relatedSpdxElement";
    return { source_ref: reference(edge.source_ref, sourcePosition), target_ref: reference(edge.target_ref, targetPosition), relationship: token(edge.relationship), source_field_locator: position };
  });
  const declarations = list2(item.completeness_declarations, (entry) => {
    const declaration = record2(entry, ["aggregate", "assemblies", "dependencies", "vulnerabilities", "source_field_locator"]);
    const position = locator(declaration.source_field_locator);
    const references = (field2) => list2(declaration[field2], (entry2) => entry2, 1e4).map((value2, index) => reference(value2, `${position}/${field2}/${index}`));
    return { aggregate: token(declaration.aggregate), assemblies: references("assemblies"), dependencies: references("dependencies"), vulnerabilities: references("vulnerabilities"), source_field_locator: position };
  }, 1e4);
  const documents = list2(item.external_documents, (entry) => {
    const document = record2(entry, ["document_ref", "document_uri", "checksum", "source_field_locator"]);
    const position = locator(document.source_field_locator);
    const uriPosition = position + "/spdxDocument";
    const uri = nullableText2(document.document_uri);
    if (uri === null) {
      if (markers.get(uriPosition)?.replacement_ref !== null) return invalid2();
      used.add(uriPosition);
    } else if (!isSafeSbomDocumentUri(uri) || markers.has(uriPosition)) return invalid2();
    return { document_ref: reference(document.document_ref, position + "/externalDocumentId"), document_uri: uri, checksum: checksum(document.checksum), source_field_locator: position };
  }, 1e4);
  const unmapped = list2(item.unmapped_field_locators, (entry) => locator(entry));
  for (const position of unmapped) {
    if (position.split("/").some((field2) => /^redacted-field:[0-9a-f]{64}$/.test(field2))) {
      if (markers.get(position)?.replacement_ref !== null) return invalid2();
      used.add(position);
    }
  }
  if (markers.size !== used.size) return invalid2();
  return {
    schema_version: "r11-sbom-sidecar-2",
    snapshot_id: snapshot.snapshot_id,
    asset_id: snapshot.asset_id,
    tenant_id: tenant,
    adapter_version: "r11-sbom-adapter-1",
    source_format: format,
    spec_version: version,
    projection_sha256: hash(item.projection_sha256),
    sidecar_sha256: hash(item.sidecar_sha256),
    combined_semantic_sha256: hash(item.combined_semantic_sha256),
    raw_sha256: hash(item.raw_sha256),
    component_sources: components,
    dependency_edges: edges,
    completeness_declarations: declarations,
    external_documents: documents,
    unmapped_field_locators: unmapped,
    redactions
  };
}

// src/features/assets/synthetic-fixtures.ts
var fixtureAssetId = "a0000000-0000-4000-8000-000000000001";
var fixtureSnapshotId = "b0000000-0000-4000-8000-000000000002";
var fixtureTenant = "synthetic-assets-tenant";
function snapshotFixture(number = 2) {
  return {
    schema_version: "r11-asset-candidate-1",
    snapshot_id: number === 2 ? fixtureSnapshotId : "b0000000-0000-4000-8000-000000000001",
    asset_id: fixtureAssetId,
    tenant_id: fixtureTenant,
    snapshot_number: number,
    observed_at: "2026-10-15T10:00:00+00:00",
    recorded_at: "2026-10-15T10:01:00+00:00",
    source_kind: "json_manifest_v1",
    inventory_completeness: "partial",
    declared_scope: ["Synthetic fixture runtime"],
    components: [{ component_id: "c0000000-0000-4000-8000-000000000001", ecosystem: "PyPI", package_name: "synthetic-demo-package", display_name: "Synthetic fixture component", purl: "pkg:pypi/synthetic-demo-package@1.9.0", version: number === 2 ? null : "1.9.0", version_scheme: "pep440", image_digest: null, dependency_path: ["synthetic-root"], source_field_locator: "/components/0" }],
    configuration: [{ name: "trust_remote_code", value: null, source_field_locator: "/configuration/trust_remote_code" }, { name: "authentication_required", value: false, source_field_locator: "/configuration/authentication_required" }],
    tool_permissions: null,
    input_channels: null,
    network_exposure: [{ name: "public_endpoint", value: false, source_field_locator: "/network_exposure/public_endpoint" }],
    snapshot_sha256: "a".repeat(64)
  };
}

// tests/r17_sbom_fixture.ts
function sbomSnapshot(number = 2, format = "cyclonedx_json") {
  return parseSnapshot({ ...snapshotFixture(number), source_kind: format, inventory_completeness: "unknown", declared_scope: [] }, fixtureTenant, fixtureAssetId);
}
function sbomFixture(number = 2, format = "cyclonedx_json") {
  const snapshot = sbomSnapshot(number, format);
  const component2 = snapshot.components[0];
  if (component2 === void 0) throw new Error("synthetic component missing");
  return {
    schema_version: "r11-sbom-sidecar-2",
    snapshot_id: snapshot.snapshot_id,
    asset_id: snapshot.asset_id,
    tenant_id: snapshot.tenant_id,
    adapter_version: "r11-sbom-adapter-1",
    source_format: format,
    spec_version: format === "cyclonedx_json" ? "1.6" : "SPDX-2.3",
    projection_sha256: snapshot.snapshot_sha256,
    sidecar_sha256: "b".repeat(64),
    combined_semantic_sha256: (number === 2 ? "c" : "d").repeat(64),
    raw_sha256: "e".repeat(64),
    component_sources: [{ component_id: component2.component_id, source_ref: "synthetic-root", component_type: "library", source_field_locator: "/components/0", field_sources: [{ field_name: "package_name", source_field_locator: "/components/0/name" }], checksums: [{ algorithm: "SHA-256", checksum_value: "f".repeat(64), source_field_locator: "/components/0/hashes/0" }] }],
    dependency_edges: [{ source_ref: "synthetic-root", target_ref: "synthetic-child", relationship: format === "cyclonedx_json" ? "dependsOn" : "DEPENDS_ON", source_field_locator: format === "cyclonedx_json" ? "/dependencies/0/dependsOn/0" : "/relationships/0" }],
    completeness_declarations: [{ aggregate: "complete", assemblies: ["synthetic-root"], dependencies: [], vulnerabilities: [], source_field_locator: "/compositions/0" }],
    external_documents: [],
    unmapped_field_locators: ["/metadata/annotations"],
    redactions: []
  };
}

// tests/r17_purl_profile_cases.ts
var purlProfileCases = [
  { name: "original encoded absolute version", purl: "pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env", expected: false },
  { name: "original encoded at in version", purl: "pkg:pypi/synthetic@review-secret%40private", expected: false },
  { name: "original double encoded slash", purl: "pkg:generic/synthetic@%252Fhome%252Freview-private", expected: false },
  { name: "plain version slash", purl: "pkg:generic/synthetic@/home/review-private", expected: false },
  { name: "plain nested version slash", purl: "pkg:generic/synthetic@release/private", expected: false },
  { name: "double encoded at", purl: "pkg:pypi/synthetic@review%2540private", expected: false },
  { name: "lowercase escape slash", purl: "pkg:generic/synthetic@%2fprivate", expected: false },
  { name: "plain space", purl: "pkg:generic/synthetic@review private", expected: false },
  { name: "encoded space", purl: "pkg:generic/synthetic@review%20private", expected: false },
  { name: "plain tab", purl: "pkg:generic/synthetic@review	private", expected: false },
  { name: "encoded tab", purl: "pkg:generic/synthetic@review%09private", expected: false },
  { name: "plain newline", purl: "pkg:generic/synthetic@review\n", expected: false },
  { name: "encoded NUL", purl: "pkg:generic/synthetic@review%00private", expected: false },
  { name: "plain backslash", purl: "pkg:generic/synthetic@review\\private", expected: false },
  { name: "encoded backslash", purl: "pkg:generic/synthetic@review%5Cprivate", expected: false },
  { name: "residual percent", purl: "pkg:generic/synthetic@review%25private", expected: false },
  { name: "encoded fake URI", purl: "pkg:generic/synthetic@https%3A%2F%2Fsynthetic%3Asynthetic%40example.com", expected: false },
  { name: "twice encoded fake URI", purl: "pkg:generic/synthetic@https%253A%252F%252Fexample.com", expected: false },
  { name: "plain fake URI", purl: "pkg:generic/synthetic@file:///review-private", expected: false },
  { name: "qualifier", purl: "pkg:generic/synthetic@1.0?token=synthetic", expected: false },
  { name: "subpath", purl: "pkg:generic/synthetic@1.0#private", expected: false },
  { name: "encoded qualifier", purl: "pkg:generic/synthetic@1.0%3Ftoken=synthetic", expected: false },
  { name: "ordinary package version", purl: "pkg:pypi/synthetic@1.0", expected: true },
  { name: "version omitted", purl: "pkg:generic/synthetic", expected: true },
  { name: "raw npm scope no version", purl: "pkg:npm/@scope/synthetic", expected: true },
  { name: "raw npm scope with version", purl: "pkg:npm/@scope/synthetic@1.2.3", expected: true },
  { name: "encoded npm scope no version", purl: "pkg:npm/%40scope/synthetic", expected: true },
  { name: "encoded npm scope with version", purl: "pkg:npm/%40scope/synthetic@1.2.3", expected: true },
  { name: "Unicode name", purl: "pkg:generic/\u5408\u6210\u7EC4\u4EF6@1.0", expected: true },
  { name: "encoded Unicode name", purl: "pkg:generic/%E5%90%88%E6%88%90%E7%BB%84%E4%BB%B6@1.0", expected: true },
  { name: "Unicode version", purl: "pkg:generic/synthetic@\u7248\u672C\u4E00", expected: true },
  { name: "encoded Unicode version", purl: "pkg:generic/synthetic@%E7%89%88%E6%9C%AC%E4%B8%80", expected: true },
  { name: "encoded at belongs to name", purl: "pkg:generic/synthetic%40package@1.0", expected: true },
  { name: "build version", purl: "pkg:generic/synthetic@1.0+build", expected: true },
  { name: "case folded type", purl: "pkg:PyPI/synthetic@1.0", expected: true },
  { name: "wrong case scheme", purl: "PKG:pypi/synthetic@1.0", expected: false }
];

// ../reports/runs/recovery_r17_sbom_workbench_review1_fix1_20261016/frontend_profile_probe.ts
var originalInputs = ["pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env", "pkg:pypi/synthetic@review-secret%40private", "pkg:generic/synthetic@%252Fhome%252Freview-private"];
var receipts = [];
for (const purl of originalInputs) {
  import_node_assert.strict.equal(isSafeSbomPurl(purl), false);
  const snapshot = sbomSnapshot();
  snapshot.components[0].purl = purl;
  const sidecar = sbomFixture();
  sidecar.dependency_edges[0].target_ref = purl;
  import_node_assert.strict.throws(() => parseSnapshot(snapshot, fixtureTenant, snapshot.asset_id), AssetResponseScopeMismatch);
  import_node_assert.strict.throws(() => parseSnapshotSbom(sidecar, fixtureTenant, sbomSnapshot()), AssetResponseScopeMismatch);
  receipts.push({ purl, helper: false, snapshot: "AssetResponseScopeMismatch", reference: "AssetResponseScopeMismatch" });
}
var cases = purlProfileCases.map((item) => ({ ...item, frontend: isSafeSbomPurl(item.purl) }));
for (const item of cases) import_node_assert.strict.equal(item.frontend, item.expected, item.name);
(0, import_node_fs.writeFileSync)("../reports/runs/recovery_r17_sbom_workbench_review1_fix1_20261016/frontend_profile_probe.json", JSON.stringify({ original: receipts, cases }, null, 2) + "\n");
console.log(JSON.stringify({ original_passed: receipts.length, manual_cases: cases.length, all_manual_match: true }));
