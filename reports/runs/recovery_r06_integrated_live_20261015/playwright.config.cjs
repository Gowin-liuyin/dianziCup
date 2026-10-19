const { defineConfig } = require("D:/wt/r06-integrated-live-1156/frontend/node_modules/@playwright/test");
const path = require("node:path");

/** Actual services and inherited Windows Job limits; never save credential traces. */
module.exports = defineConfig({
  testDir: __dirname,
  testMatch: "integrated-live.spec.cjs",
  fullyParallel: false,
  workers: 1,
  timeout: 100000,
  expect: { timeout: 15000 },
  outputDir: path.join(__dirname, "browser_artifacts"),
  reporter: [["list"], ["json", { outputFile: path.join(__dirname, "browser_report.json") }]],
  use: { baseURL: "http://127.0.0.1:25175", browserName: "chromium", channel: "msedge", headless: true, trace: "off", video: "off", screenshot: "off" },
});
