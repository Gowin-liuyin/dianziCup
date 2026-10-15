import { mergeConfig } from "../../../frontend/node_modules/vitest/dist/config.js";
import base from "../../../frontend/vite.config";

export default mergeConfig(base, { test: { include: ["../reports/runs/recovery_r06_document_workspace_20261015/review_fix_1.test.ts"], exclude: [], environment: "jsdom", maxWorkers: 1, fileParallelism: false } });
