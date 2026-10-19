import { fileURLToPath } from "node:url";
import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";

export default defineConfig({
  testDir: fileURLToPath(new URL("../../../frontend/e2e", import.meta.url)),
  testMatch: ["r17_event_detail_fixture.spec.ts", "r04_fixture_contract.spec.ts"],
  fullyParallel: false, workers: 1, timeout: 30_000, expect: { timeout: 10_000 },
  outputDir: fileURLToPath(new URL("./browser_artifacts", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./browser.json", import.meta.url)) }]],
  use: { baseURL: "http://127.0.0.1:25321", browserName: "chromium", trace: "off", video: "off", screenshot: "off" },
});
