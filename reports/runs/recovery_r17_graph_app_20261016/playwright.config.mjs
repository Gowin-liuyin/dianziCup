import { fileURLToPath } from "node:url";
import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";

const frontendPath = fileURLToPath(new URL("../../../frontend", import.meta.url));
export default defineConfig({
  testDir: `${frontendPath}/e2e`, testMatch: ["r17_graph_app_fixture.spec.ts"], workers: 1, fullyParallel: false, timeout: 30000, globalTimeout: 180000, retries: 0,
  expect: { timeout: 5000 }, outputDir: fileURLToPath(new URL("./browser_artifacts", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./browser.json", import.meta.url)) }]],
  use: { baseURL: "http://127.0.0.1:25517", browserName: "chromium", channel: "msedge", headless: true, viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  webServer: { command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 25517 --strictPort", cwd: frontendPath, url: "http://127.0.0.1:25517", timeout: 30000, reuseExistingServer: false },
});
