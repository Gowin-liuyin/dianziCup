import { mergeConfig } from "../../../frontend/node_modules/vitest/dist/config.js";
import base from "../../../frontend/vite.config";
export default mergeConfig(base, { test: { include: ["../reports/runs/recovery_r06_document_workspace_review_1_recheck2_20261015/review.test.ts", "../reports/runs/recovery_r06_document_workspace_review_1_recheck2_20261015/recheck.race.test.ts", "../reports/runs/recovery_r06_document_workspace_review_1_recheck2_20261015/catalog_privacy.test.ts"], exclude: [], environment: "jsdom", maxWorkers: 1, fileParallelism: false } });
