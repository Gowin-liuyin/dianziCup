import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";
export default defineConfig({
  testDir: ".", testMatch: /catalog_privacy\.browser\.spec\.ts/, workers: 1, timeout: 12000, expect: { timeout: 3000 },
  use: { baseURL: "http://127.0.0.1:25502", browserName: "chromium", channel: "msedge", viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  outputDir: "./legacy_probe_artifacts", reporter: [["list"]],
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 25502 --strictPort", cwd: "D:/wt/r06-doc-recheck2/frontend", url: "http://127.0.0.1:25502", reuseExistingServer: false, timeout: 30000 },
});
