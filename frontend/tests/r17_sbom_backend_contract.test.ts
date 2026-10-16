import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parseSnapshot } from "../src/features/assets/asset-contracts";
import { parseSnapshotSbom } from "../src/features/assets/sbom-contracts";

const samples: unknown = JSON.parse(readFileSync(resolve(process.cwd(), "../reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"), "utf8"));
if (!Array.isArray(samples) || samples.length !== 8) throw new Error("eight synthetic sample cases required");
const cases = samples.map((value: unknown) => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("synthetic sample object missing");
  return Object.fromEntries(Object.entries(value));
});
describe("R17 frozen actual backend DTO serializer → frontend · synthetic contract", () => {
  it.each(cases)("accepts actual serialized $case DTO", (sample) => {
      expect(sample.data_mode).toBe("synthetic_contract");
      expect(sample.backend_material_sha).toBe("5be873ec38a41955b5a58e9762df4b866a7a9d63");
      const snapshot = parseSnapshot(sample.snapshot, "synthetic-assets-tenant", "a0000000-0000-4000-8000-000000000001");
      const sidecar = parseSnapshotSbom(sample.sidecar, snapshot.tenant_id, snapshot);
      expect(sidecar.snapshot_id).toBe(snapshot.snapshot_id);
      expect(sidecar.projection_sha256).toBe(snapshot.snapshot_sha256);
  });
});
