import base from "../../../frontend/playwright.config";

/** 固定依赖、隔离loopback与Edge；所有API仅使用标明fixture的浏览器拦截。 */
export default {
  ...base,
  testDir: "../../../frontend/e2e",
  testMatch: /(?:r06_source_admin_fixture|r17_source_jobs_fixture)\.spec\.ts/,
  outputDir: "./e2e_accessibility_artifacts",
  reporter: [["list"], ["json", { outputFile: "D:/wt/r06-source-admin-ui/reports/runs/recovery_r06_source_admin_ui_20261015/e2e_accessibility_report.json" }]],
  use: { ...base.use, channel: "msedge" },
  webServer: { ...base.webServer, cwd: "D:/wt/r06-source-admin-ui/frontend" },
};
