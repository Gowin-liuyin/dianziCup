import { fileURLToPath } from "node:url";
import base from "./browser-probes.config.mjs";

export default {
  ...base,
  testDir: fileURLToPath(new URL("../../../frontend/e2e", import.meta.url)),
  testMatch: ["r17_event_detail_fixture.spec.ts", "r04_fixture_contract.spec.ts"],
  grep: undefined,
  outputDir: fileURLToPath(new URL("./browser_artifacts", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./browser.json", import.meta.url)) }]],
};
