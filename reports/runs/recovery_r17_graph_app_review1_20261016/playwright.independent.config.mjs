import { fileURLToPath } from "node:url";
import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";

const frontendPath = fileURLToPath(new URL("../../../frontend", import.meta.url));
export default defineConfig({
  testDir: fileURLToPath(new URL(".", import.meta.url)), testMatch: ["independent-default-app.spec.ts"],
  workers: 1, fullyParallel: false, timeout: 30000, globalTimeout: 120000, retries: 0,
  expect: { timeout: 5000 }, outputDir: fileURLToPath(new URL("./browser-independent", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./browser-independent.json", import.meta.url)) }]],
  use: { baseURL: "http://127.0.0.1:25620", browserName: "chromium", channel: "msedge", headless: true,
    viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "only-on-failure" },
  webServer: { command: "node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 25620 --strictPort",
    cwd: frontendPath, url: "http://127.0.0.1:25620", timeout: 30000, reuseExistingServer: false },
});
