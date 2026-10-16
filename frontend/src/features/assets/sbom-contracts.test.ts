import { describe, expect, it } from "vitest";
import { sbomFixture, sbomSnapshot } from "../../../tests/r17_sbom_fixture";
import { fixtureTenant } from "./synthetic-fixtures";
import { AssetResponseScopeMismatch, parseSnapshot } from "./asset-contracts";
import { isSafeSbomDocumentUri, parseSnapshotSbom, type SnapshotSbom } from "./sbom-contracts";

describe("R17 SBOM sidecar runtime contract · explicitly synthetic", () => {
  it.each(["1.5", "1.6", "1.7"] as const)("accepts CycloneDX %s without converting complete into verified inventory", (version) => {
    const snapshot = sbomSnapshot();
    const result = parseSnapshotSbom({ ...sbomFixture(), spec_version: version }, fixtureTenant, snapshot);
    expect(result.completeness_declarations[0]?.aggregate).toBe("complete");
    expect(snapshot.inventory_completeness).toBe("unknown");
  });
  it("accepts SPDX standard edges and a public external document", () => {
    const sbom = sbomFixture(1, "spdx_json");
    sbom.external_documents = [{ document_ref: "DocumentRef-Synthetic", document_uri: "https://example.com/synthetic.spdx.json", checksum: { algorithm: "SHA256", checksum_value: "a".repeat(64), source_field_locator: "/externalDocumentRefs/0/checksum" }, source_field_locator: "/externalDocumentRefs/0" }];
    expect(parseSnapshotSbom(sbom, fixtureTenant, sbomSnapshot(1, "spdx_json")).dependency_edges[0]?.relationship).toBe("DEPENDS_ON");
  });
  it.each(["tenant_id", "asset_id", "snapshot_id", "projection_sha256"])("rejects a different %s and exposes no received identifier", (field) => {
    expect(() => parseSnapshotSbom({ ...sbomFixture(), [field]: "wrong-synthetic-scope" }, fixtureTenant, sbomSnapshot())).toThrow(AssetResponseScopeMismatch);
  });
  it.each(["schema_version", "adapter_version", "source_format", "spec_version"])("rejects incompatible %s rather than manufacturing unknown successful data", (field) => {
    expect(() => parseSnapshotSbom({ ...sbomFixture(), [field]: "unsupported" }, fixtureTenant, sbomSnapshot())).toThrow(AssetResponseScopeMismatch);
  });
  it("rejects extra raw fields, bad hashes, shapes, excessive and duplicate component IDs", () => {
    const original = sbomFixture();
    for (const value of [{ ...original, raw_input: "synthetic-private-bytes" }, { ...original, raw_sha256: "g".repeat(64) }, { ...original, dependency_edges: {} }, { ...original, component_sources: [...original.component_sources, ...original.component_sources] }, { ...original, component_sources: Array.from({ length: 10001 }, () => original.component_sources[0]) }]) expect(() => parseSnapshotSbom(value, fixtureTenant, sbomSnapshot())).toThrow(AssetResponseScopeMismatch);
  });
  it("requires precise redaction markers for each hidden ref and preserves only aliases", () => {
    const sbom = sbomFixture(); const alias = `redacted-ref:${"1".repeat(64)}`;
    const component = sbom.component_sources[0]; const edge = sbom.dependency_edges[0];
    if (component === undefined || edge === undefined) throw new Error("synthetic ref absent");
    component.source_ref = alias; edge.source_ref = alias;
    sbom.redactions = [{ source_field_locator: "/components/0/bom-ref", reason: "unsafe_uri_or_path", replacement_ref: alias }, { source_field_locator: "/dependencies/0/ref", reason: "unsafe_uri_or_path", replacement_ref: alias }];
    expect(parseSnapshotSbom(sbom, fixtureTenant, sbomSnapshot()).dependency_edges[0]?.source_ref).toBe(alias);
    expect(() => parseSnapshotSbom({ ...sbom, redactions: sbom.redactions.slice(0, 1) }, fixtureTenant, sbomSnapshot())).toThrow(AssetResponseScopeMismatch);
    expect(() => parseSnapshotSbom({ ...sbom, redactions: [...sbom.redactions, { ...sbom.redactions[0] }] }, fixtureTenant, sbomSnapshot())).toThrow(AssetResponseScopeMismatch);
  });
  it("hidden document URI needs a bound null marker, never a missing-marker success", () => {
    const sbom = sbomFixture(2, "spdx_json");
    sbom.external_documents = [{ document_ref: "DocumentRef-Synthetic", document_uri: null, checksum: { algorithm: "SHA256", checksum_value: "a".repeat(64), source_field_locator: "/externalDocumentRefs/0/checksum" }, source_field_locator: "/externalDocumentRefs/0" }];
    expect(() => parseSnapshotSbom(sbom, fixtureTenant, sbomSnapshot(2, "spdx_json"))).toThrow(AssetResponseScopeMismatch);
    sbom.redactions = [{ source_field_locator: "/externalDocumentRefs/0/spdxDocument", reason: "unsafe_uri_or_path", replacement_ref: null }];
    expect(parseSnapshotSbom(sbom, fixtureTenant, sbomSnapshot(2, "spdx_json")).external_documents[0]?.document_uri).toBeNull();
  });
  it.each(["file:///private/synthetic", "postgresql://synthetic:synthetic@localhost/test", "https://synthetic:synthetic@example.com/a", "https://localhost/a", "https://10.0.0.1/a", "https://example.com/a?token=synthetic", "https://example.com/a#synthetic", "https://example.com/%252525253A", "https://example.com/c:/../visible"])("rejects unsafe document URI %s", (uri) => {
    expect(isSafeSbomDocumentUri(uri)).toBe(false);
  });
  it.each(["https://example.com/a", "https://8.8.8.8/public", "https://[2606:4700:4700::1111]/public"])("keeps a server permitted public URI %s", (uri) => expect(isSafeSbomDocumentUri(uri)).toBe(true));
  it("rejects injected field values and URI-like unknown keys without displaying them", () => {
    for (const mutate of [
      (sbom: SnapshotSbom) => { sbom.unmapped_field_locators = ["/file:~1~1~1private"]; },
      (sbom: SnapshotSbom) => { sbom.unmapped_field_locators = ["/%25252525253A"]; },
      (sbom: SnapshotSbom) => { const source = sbom.component_sources[0]; if (source !== undefined) source.component_type = "file:///private/synthetic"; },
      (sbom: SnapshotSbom) => { const edge = sbom.dependency_edges[0]; if (edge !== undefined) edge.relationship = "https://synthetic:synthetic@example.com"; },
    ]) { const sbom = sbomFixture(); mutate(sbom); expect(() => parseSnapshotSbom(sbom, fixtureTenant, sbomSnapshot())).toThrow(AssetResponseScopeMismatch); }
  });
  it("accepts a redacted unknown key only with a bound locator marker", () => {
    const sbom = sbomFixture(); const position = `/metadata/redacted-field:${"1".repeat(64)}`;
    sbom.unmapped_field_locators = [position];
    expect(() => parseSnapshotSbom(sbom, fixtureTenant, sbomSnapshot())).toThrow(AssetResponseScopeMismatch);
    sbom.redactions = [{ source_field_locator: position, reason: "unsafe_uri_or_path", replacement_ref: null }];
    expect(parseSnapshotSbom(sbom, fixtureTenant, sbomSnapshot()).unmapped_field_locators).toEqual([position]);
  });
  it("rejects unsafe SBOM snapshot PURL before sidecar loading or private DOM display", () => {
    for (const purl of ["pkg:generic/synthetic@https%3A%2F%2Fsynthetic%3Asynthetic%40example.com", "pkg:pypi/synthetic@file%3A%2F%2F%2Fprivate", "pkg:pypi/synthetic@1.0?token=synthetic"]) {
      const snapshot = sbomSnapshot();
      expect(() => parseSnapshot({ ...snapshot, components: snapshot.components.map((component) => ({ ...component, purl })) }, fixtureTenant, snapshot.asset_id)).toThrow(AssetResponseScopeMismatch);
    }
  });
});
