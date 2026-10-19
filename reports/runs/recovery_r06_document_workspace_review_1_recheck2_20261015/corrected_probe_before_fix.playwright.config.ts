import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";
export default defineConfig({
  testDir: ".", testMatch: /catalog_privacy\.corrected\.browser\.spec\.ts/, workers: 1, timeout: 30000, expect: { timeout: 5000 },
  use: { baseURL: "http://127.0.0.1:25505", browserName: "chromium", channel: "msedge", viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  outputDir: "./corrected_probe_before_fix_artifacts", reporter: [["list"]],
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 25505 --strictPort", cwd: "D:/wt/r06-doc-recheck1/frontend", url: "http://127.0.0.1:25505", reuseExistingServer: false, timeout: 30000 },
});
