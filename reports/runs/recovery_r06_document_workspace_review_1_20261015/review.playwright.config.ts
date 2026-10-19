import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";
export default defineConfig({
  testDir: ".", testMatch: /review\.browser\.spec\.ts/, workers: 1, timeout: 30000,
  expect: { timeout: 5000 },
  use: { baseURL: "http://127.0.0.1:25492", browserName: "chromium", channel: "msedge", viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  outputDir: "./independent_browser_artifacts",
  reporter: [["json", { outputFile: "./independent_browser.json" }]],
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 25492 --strictPort", cwd: "D:/wt/r06-doc-review1/frontend", url: "http://127.0.0.1:25492", reuseExistingServer: false, timeout: 30000 },
});
