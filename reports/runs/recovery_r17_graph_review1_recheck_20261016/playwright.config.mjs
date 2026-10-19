import { fileURLToPath } from "node:url";
import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";

const frontendPath = fileURLToPath(new URL("../../../frontend", import.meta.url));
export default defineConfig({
  testDir: `${frontendPath}/e2e`, testMatch: ["r17_graph_edge_pointer_fixture.spec.ts", "r17_evidence_graph_fixture.spec.ts"], workers: 1, fullyParallel: false, timeout: 60000, globalTimeout: 150000, retries: 0,
  expect: { timeout: 5000 }, outputDir: fileURLToPath(new URL("./author_e2e_artifacts", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./author-e2e.json", import.meta.url)) }]],
  use: { baseURL: "http://127.0.0.1:25502", browserName: "chromium", channel: "msedge", headless: true, viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  webServer: { command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 25502 --strictPort", cwd: frontendPath, url: "http://127.0.0.1:25502/e2e/graph-fixture/index.html", timeout: 30000, reuseExistingServer: false },
});
