import { fileURLToPath } from "node:url";
import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";

const frontendPath = fileURLToPath(new URL("../../../frontend", import.meta.url));
export default defineConfig({
  testDir: fileURLToPath(new URL(".", import.meta.url)),
  testMatch: "review-fixture-probes.spec.ts",
  grep: /independent (loading|revision|narrow)/,
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  outputDir: fileURLToPath(new URL("./browser_probe_artifacts", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./browser-probes.json", import.meta.url)) }]],
  use: { baseURL: "http://127.0.0.1:25317", browserName: "chromium", trace: "off", video: "off", screenshot: "off" },
  webServer: { command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 25317 --strictPort", cwd: frontendPath, url: "http://127.0.0.1:25317", timeout: 30_000, reuseExistingServer: false },
});
