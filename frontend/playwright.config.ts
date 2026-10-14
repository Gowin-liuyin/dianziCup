import process from "node:process";
import { defineConfig } from "@playwright/test";

const frontendUrl = new URL(process.env.DIANZI_E2E_FRONTEND_URL ?? "http://127.0.0.1:25173");
if (frontendUrl.hostname !== "127.0.0.1" || frontendUrl.protocol !== "http:" || !frontendUrl.port || frontendUrl.username || frontendUrl.password) {
  throw new Error("E2E requires a dedicated loopback HTTP frontend port");
}

/** 使用隔离真实 API；不保留可能包含密码输入的 trace、video 或失败自动截图。 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  outputDir: "../reports/runs/recovery_r01_frontend_20261014/e2e_artifacts",
  reporter: [["list"], ["json", { outputFile: "../reports/runs/recovery_r01_frontend_20261014/e2e_report.json" }]],
  use: {
    baseURL: frontendUrl.origin,
    browserName: "chromium",
    viewport: { width: 1280, height: 800 },
    trace: "off",
    video: "off",
    screenshot: "off",
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${frontendUrl.port} --strictPort`,
    url: frontendUrl.origin,
    timeout: 30_000,
    reuseExistingServer: false,
  },
});
