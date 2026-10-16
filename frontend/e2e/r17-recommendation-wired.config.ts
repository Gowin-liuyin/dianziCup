import { defineConfig } from "@playwright/test";
import base from "../playwright.config";

/** 使用专用端口与已安装 Edge，输出仅写本有界切片，不复用共享服务。 */
export default defineConfig({ ...base, testDir: ".", testMatch: "r17_recommendation_wire.spec.ts", outputDir: "../../reports/runs/recovery_r17_recommendation_wired_20261016/browser_artifacts", reporter: "json", use: { ...base.use, channel: "msedge", viewport: { width: 1366, height: 900 } } });
