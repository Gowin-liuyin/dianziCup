import { fileURLToPath } from "node:url";
import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";

const frontendPath = fileURLToPath(new URL("../../../frontend", import.meta.url));
export default defineConfig({
  testDir: `${frontendPath}/e2e`, testMatch: "r17_evidence_graph_fixture.spec.ts", fullyParallel: false, workers: 1,
  timeout: 20000, globalTimeout: 120000, expect: { timeout: 7000 }, retries: 0,
  outputDir: fileURLToPath(new URL("./browser_artifacts_v1_1", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./browser-v1_1.json", import.meta.url)) }]],
  use: { baseURL: "http://127.0.0.1:25488", browserName: "chromium", channel: "msedge", headless: true, viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  webServer: { command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 25488 --strictPort", cwd: frontendPath, url: "http://127.0.0.1:25488/e2e/graph-fixture/index.html", timeout: 30000, reuseExistingServer: false },
});
