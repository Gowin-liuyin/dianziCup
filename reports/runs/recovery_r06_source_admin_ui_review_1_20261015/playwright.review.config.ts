import base from "../../../frontend/playwright.config";

/** 独立Edge审查；自有Vite端口，拒绝复用服务，所有业务API均为隔离fixture。 */
export default {
  ...base,
  testDir: "../../..",
  testMatch: [
    "**/frontend/e2e/r06_source_admin_fixture.spec.ts",
    "**/frontend/e2e/r17_source_jobs_fixture.spec.ts",
    "**/reports/runs/recovery_r06_source_admin_ui_review_1_20261015/review_negative.spec.ts",
  ],
  outputDir: "./edge_artifacts",
  reporter: [["list"], ["json", { outputFile: "D:/wt/r06-source-admin-ui-review-1/reports/runs/recovery_r06_source_admin_ui_review_1_20261015/edge_report.json" }]],
  use: { ...base.use, channel: "msedge" },
  webServer: {
    ...base.webServer,
    cwd: "D:/wt/r06-source-admin-ui-review-1/frontend",
    env: { API_PROXY_TARGET: "http://127.0.0.1:9" },
  },
};
