import { defineConfig } from "../../../frontend/node_modules/@playwright/test/index.mjs";

export default defineConfig({
  testDir: "../../../frontend/e2e",
  testMatch: "r17_event_detail_fixture.spec.ts",
  fullyParallel: false,
  workers: 1,
  globalTimeout: 90_000,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  outputDir: "./event_fixture_artifacts",
  reporter: [["list"], ["json", { outputFile: "./event_fixture.json" }], ["junit", { outputFile: "./event_fixture.xml" }]],
  use: {
    baseURL: "http://127.0.0.1:25486",
    browserName: "chromium",
    channel: "msedge",
    viewport: { width: 1366, height: 900 },
    trace: "off",
    video: "off",
    screenshot: "off",
  },
  webServer: {
    command: '"C:/Program Files/nodejs/node.exe" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 25486 --strictPort',
    cwd: "D:/wt/gc-8a-validation/frontend",
    url: "http://127.0.0.1:25486",
    timeout: 20_000,
    reuseExistingServer: false,
  },
});
