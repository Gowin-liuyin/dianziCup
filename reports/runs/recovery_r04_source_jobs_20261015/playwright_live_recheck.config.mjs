import { defineConfig } from "file:///D:/dianzi/frontend/node_modules/@playwright/test/index.mjs";

export default defineConfig({
  testDir: "D:/dianzi/frontend/e2e",
  testMatch: "r17_real_source_workspace.spec.ts",
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  outputDir: "D:/dianzi/reports/runs/recovery_r04_source_jobs_20261015/real_browser_segment6_recheck_artifacts",
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:25300", browserName: "chromium", trace: "off", video: "off", screenshot: "off" },
});
