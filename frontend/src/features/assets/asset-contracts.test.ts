import { describe, expect, it } from "vitest";
import { ApiProblem } from "../../api/client";
import { readAssetSelection, readWorkspacePage } from "../../app/workspace-navigation";
import { parseAsset, parseAssetList, parseImportResult, parseSnapshot, parseSnapshotList } from "./asset-contracts";

import { assetFixture, snapshotFixture, fixtureAssetId, fixtureSnapshotId, fixtureTenant } from "./synthetic-fixtures";

describe("R17 asset DTO and routing contract · synthetic only", () => {
  it("keeps nullable versions and configuration distinct from false", () => {
    const snapshot = parseSnapshot(snapshotFixture(), fixtureTenant, fixtureAssetId);
    expect(snapshot.components[0]?.version).toBeNull();
    expect(snapshot.configuration.map((field) => field.value)).toEqual([null, false]);
    expect(snapshot.components[0]?.source_field_locator).toBe("/components/0");
  });
  it("rejects another tenant and mismatched asset or snapshot identities", () => {
    expect(() => parseAsset(assetFixture(), "another-tenant")).toThrow(ApiProblem);
    expect(() => parseAsset({ ...assetFixture(), current_snapshot_id: fixtureAssetId }, fixtureTenant)).toThrow(ApiProblem);
    expect(() => parseSnapshot(snapshotFixture(), fixtureTenant, fixtureSnapshotId)).toThrow(ApiProblem);
  });
  it("rejects changed schemas, invalid timestamps and wrong field types", () => {
    for (const changed of [{ ...snapshotFixture(), schema_version: "invented" }, { ...snapshotFixture(), observed_at: "2026-10-15T10:00:00" }, { ...snapshotFixture(), snapshot_number: 0 }, { ...snapshotFixture(), configuration: [{ name: "secret", value: {}, source_field_locator: "/" }] }]) {
      expect(() => parseSnapshot(changed, fixtureTenant, fixtureAssetId)).toThrow(ApiProblem);
    }
  });
  it("parses current/history cursor pages and rejects duplicated identities", () => {
    expect(parseAssetList({ items: [assetFixture()], next_cursor: "server-cursor" }, fixtureTenant).next_cursor).toBe("server-cursor");
    expect(parseSnapshotList({ items: [snapshotFixture()], next_cursor: null }, fixtureTenant, fixtureAssetId).items).toHaveLength(1);
    expect(() => parseAssetList({ items: [assetFixture(), assetFixture()], next_cursor: null }, fixtureTenant)).toThrow(ApiProblem);
  });
  it("accepts only the synchronous server receipt; no fabricated job result", () => {
    expect(parseImportResult({ asset_id: fixtureAssetId, snapshot: snapshotFixture(), reused: true }, fixtureTenant).reused).toBe(true);
    expect(() => parseImportResult({ job_id: fixtureAssetId, status: "queued" }, fixtureTenant)).toThrow(ApiProblem);
  });
  it("allows canonical UUID deep links and rejects arbitrary hash input", () => {
    expect(readWorkspacePage(`#assets/${fixtureAssetId}`)).toBe("assets");
    expect(readAssetSelection(`#assets/${fixtureAssetId.toUpperCase()}`)).toEqual({ assetId: fixtureAssetId });
    for (const hash of ["#assets/../../secret", "#assets/fixture", `#assets/${fixtureAssetId}?tenant=x`, `#assets/${fixtureAssetId}/extra`]) expect(readWorkspacePage(hash)).toBe("missing");
  });
});
