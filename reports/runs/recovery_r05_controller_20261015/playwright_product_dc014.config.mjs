import { defineConfig } from "file:///D:/dianzi/frontend/node_modules/@playwright/test/index.mjs";

export default defineConfig({
  testDir: "D:/dianzi/frontend/e2e",
  testMatch: "r05_real_question.spec.ts",
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  outputDir: "D:/dianzi/reports/runs/recovery_r05_controller_20261015/product_live_dc014c9/browser_artifacts",
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:25300", browserName: "chromium", trace: "off", video: "off", screenshot: "off" },
});
