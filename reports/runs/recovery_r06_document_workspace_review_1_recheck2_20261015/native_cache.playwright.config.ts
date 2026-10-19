import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";
export default defineConfig({
  testDir: ".", testMatch: /native_cache\.browser\.spec\.ts/, workers: 1, timeout: 30000,
  use: { baseURL: "http://127.0.0.1:25494", browserName: "chromium", channel: "msedge", trace: "off", video: "off", screenshot: "off" },
  outputDir: "./native_cache_browser_artifacts", reporter: [["list"]],
  webServer: [
    { command: "node D:/wt/r06-doc-recheck2/reports/runs/recovery_r06_document_workspace_review_1_recheck2_20261015/native_cache_fixture.mjs", url: "http://127.0.0.1:25493/v1/health/live", reuseExistingServer: false },
    { command: "npm run dev -- --host 127.0.0.1 --port 25494 --strictPort", cwd: "D:/wt/r06-doc-recheck2/frontend", url: "http://127.0.0.1:25494", env: { API_PROXY_TARGET: "http://127.0.0.1:25493" }, reuseExistingServer: false },
  ],
});
