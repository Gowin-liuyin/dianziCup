const path = require("node:path");
const root = path.resolve(__dirname, "../../..");
const { defineConfig } = require(path.join(root, "frontend/node_modules/@playwright/test"));
module.exports = defineConfig({
  testDir: root,
  testMatch: [/frontend[\\/]e2e[\\/]r17_(sbom_fixture|assets_fixture|graph_app_fixture)\.spec\.ts$/, /recovery_r17_sbom_workbench_fix1_20261016[\\/](reviewer_resource_adapter|purl_acceptance)\.spec\.ts$/],
  fullyParallel: false, workers: 1, timeout: 30000, expect: { timeout: 7000 },
  outputDir: path.join(__dirname, process.env.R17_PURL_EDGE_OUTPUT || "edge_red_artifacts"),
  reporter: [["list"], ["json", { outputFile: path.join(__dirname, process.env.R17_PURL_EDGE_REPORT || "edge_red_report.json") }]],
  use: { baseURL: "http://127.0.0.1:26373", browserName: "chromium", channel: "msedge", viewport: { width: 1366, height: 900 }, trace: "off", video: "off", screenshot: "off" },
  webServer: { command: "node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 26373 --strictPort", cwd: path.join(root, "frontend"), url: "http://127.0.0.1:26373", timeout: 30000, reuseExistingServer: false },
});
