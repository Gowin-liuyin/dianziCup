const path = require("node:path");
const root = path.resolve(__dirname, "../../..");
const { defineConfig } = require(path.join(root, "frontend/node_modules/@playwright/test"));
module.exports = defineConfig({
  testDir: path.join(root, "frontend/e2e"),
  testMatch: ["r17_assets_fixture.spec.ts", "r17_graph_app_fixture.spec.ts"],
  fullyParallel: false, workers: 1, timeout: 30000, expect: { timeout: 10000 },
  outputDir: path.join(__dirname, "edge_artifacts"),
  reporter: [["list"], ["json", { outputFile: path.join(__dirname, "edge_report.json") }]],
  use: { baseURL: "http://127.0.0.1:25387", browserName: "chromium", channel: "msedge", viewport: { width: 1280, height: 800 }, trace: "off", video: "off", screenshot: "off" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 25387 --strictPort", cwd: path.join(root, "frontend"), url: "http://127.0.0.1:25387", timeout: 30000, reuseExistingServer: false },
});
