import { defineConfig } from '../../../frontend/node_modules/@playwright/test/index.mjs';

export default defineConfig({
  testDir: '../../../frontend/e2e',
  testMatch: ['r04_fixture_contract.spec.ts','r05_question_workspace.spec.ts','r17_source_jobs_fixture.spec.ts'],
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  expect: { timeout: 10000 },
  outputDir: 'D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/browser_final_artifacts',
  reporter: [['list'],['json',{outputFile:'D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/browser_final.json'}]],
  use: {baseURL:'http://127.0.0.1:28173',browserName:'chromium',trace:'off',video:'off',screenshot:'off'},
  webServer: {command:'npm run dev -- --host 127.0.0.1 --port 28173 --strictPort',cwd:'D:/wt/gb-stage-review/frontend',url:'http://127.0.0.1:28173',reuseExistingServer:false,timeout:30000},
});
