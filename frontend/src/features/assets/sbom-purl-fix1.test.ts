import { describe, expect, it } from "vitest";
import { ApiProblem } from "../../api/client";
import { AssetResponseScopeMismatch, isSafeSbomPurl, parseSnapshot } from "./asset-contracts";
import { parseSnapshotSbom } from "./sbom-contracts";
import { sbomFixture, sbomSnapshot } from "../../../tests/r17_sbom_fixture";
import { fixtureTenant } from "./synthetic-fixtures";
import { purlProfileCases } from "../../../tests/r17_purl_profile_cases";

export const originalPurlMustInputs = [
  "pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env",
  "pkg:pypi/synthetic@review-secret%40private",
  "pkg:generic/synthetic@%252Fhome%252Freview-private",
];

describe("R17 independent Must1 exact PURL inputs · synthetic", () => {
  it.each(originalPurlMustInputs)("rejects %s in both snapshot and unredacted sidecar before DOM", (purl) => {
    expect(isSafeSbomPurl(purl)).toBe(false);
    const snapshot = sbomSnapshot();
    expect(() => parseSnapshot({ ...snapshot, components: snapshot.components.map((component) => ({ ...component, purl })) }, fixtureTenant, snapshot.asset_id)).toThrow(AssetResponseScopeMismatch);
    const sbom = sbomFixture();
    const edge = sbom.dependency_edges[0]; if (edge === undefined) throw new Error("synthetic edge missing");
    edge.target_ref = purl;
    expect(() => parseSnapshotSbom(sbom, fixtureTenant, snapshot)).toThrow(AssetResponseScopeMismatch);
  });
});

describe("R17 frozen PURL safe display subset · explicit positive and negative examples", () => {
  it.each(purlProfileCases)("$name", ({ purl, expected }) => {
    expect(isSafeSbomPurl(purl)).toBe(expected);
    const snapshot = sbomSnapshot();
    const snapshotPayload = { ...snapshot, components: snapshot.components.map((component) => ({ ...component, purl })) };
    const sbom = sbomFixture(); const edge = sbom.dependency_edges[0];
    if (edge === undefined) throw new Error("synthetic edge missing");
    edge.target_ref = purl;
    if (expected) {
      expect(parseSnapshot(snapshotPayload, fixtureTenant, snapshot.asset_id).components[0]?.purl).toBe(purl);
      expect(parseSnapshotSbom(sbom, fixtureTenant, snapshot).dependency_edges[0]?.target_ref).toBe(purl);
    } else {
      expect(() => parseSnapshot(snapshotPayload, fixtureTenant, snapshot.asset_id)).toThrow(ApiProblem);
      expect(() => parseSnapshotSbom(sbom, fixtureTenant, snapshot)).toThrow(ApiProblem);
    }
  });
});
