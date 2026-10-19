const { defineConfig } = require("D:/wt/r06-document-live-0a45185/frontend/node_modules/@playwright/test");
const path = require("node:path");

/** Real loopback services; no route interception, credential traces, or automatic login screenshots. */
module.exports = defineConfig({
  testDir: __dirname,
  testMatch: "document-live.spec.cjs",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 15000 },
  outputDir: path.join(__dirname, "browser_artifacts"),
  reporter: [["list"], ["json", { outputFile: path.join(__dirname, "browser_report.json") }]],
  use: { baseURL: "http://127.0.0.1:25174", browserName: "chromium", channel: "msedge", headless: true, trace: "off", video: "off", screenshot: "off" },
});
