import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";
export default defineConfig({
  testDir: ".", testMatch: /catalog_privacy\.browser\.spec\.ts/, workers: 1, timeout: 30000, expect: { timeout: 5000 },
  use: { baseURL: "http://127.0.0.1:25497", browserName: "chromium", channel: "msedge", viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  outputDir: "./catalog_privacy_browser_artifacts", reporter: [["list"]],
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 25497 --strictPort", cwd: "D:/wt/r06-doc-recheck1/frontend", url: "http://127.0.0.1:25497", reuseExistingServer: false, timeout: 30000 },
});
