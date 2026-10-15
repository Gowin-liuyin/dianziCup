import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";
export default defineConfig({
  testDir: ".", testMatch: /review_fix_1\.browser\.spec\.ts/, workers: 1, timeout: 30000,
  expect: { timeout: 5000 },
  use: { baseURL: "http://127.0.0.1:25377", browserName: "chromium", channel: "msedge", viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  outputDir: "./review_fix_1_browser_artifacts",
  reporter: [["json", { outputFile: "./review_fix_1_browser.json" }]],
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 25377 --strictPort", cwd: "D:/dianzi-worktrees/r06-document-workspace/frontend", url: "http://127.0.0.1:25377", reuseExistingServer: false, timeout: 30000 },
});
