import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

/** 独立浏览器夹具与输出目录；不复用产品服务、真实账号或旧验收产物。 */
export default defineConfig({ ...base, use: { ...base.use, channel: "msedge" }, testMatch: /r06_document_workspace_fixture\.spec\.ts/, outputDir: "../reports/runs/recovery_r06_document_workspace_20261015/e2e_artifacts", reporter: [["list"], ["json", { outputFile: "../reports/runs/recovery_r06_document_workspace_20261015/e2e_report.json" }]] });
