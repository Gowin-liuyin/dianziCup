import { defineConfig } from 'C:/Users/yinha/.codex/worktrees/source-jobs-review/dianzi/frontend/node_modules/@playwright/test/index.mjs';
export default defineConfig({
 testDir:'C:/Users/yinha/.codex/worktrees/source-jobs-review/dianzi/frontend/e2e',
 testMatch:'r17_source_jobs_fixture.spec.ts',
 workers:1,fullyParallel:false,timeout:30000,
 reporter:[['list'],['json',{outputFile:'D:/dianzi/reports/runs/recovery_r17_source_jobs_review_1_20261015/browser-report.json'}]],
 outputDir:'D:/dianzi/reports/runs/recovery_r17_source_jobs_review_1_20261015/browser-artifacts',
 use:{baseURL:'http://127.0.0.1:25304',browserName:'chromium',viewport:{width:1280,height:800},trace:'off',video:'off',screenshot:'off'},
 webServer:{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 25304 --strictPort',cwd:'C:/Users/yinha/.codex/worktrees/source-jobs-review/dianzi/frontend',url:'http://127.0.0.1:25304',timeout:30000,reuseExistingServer:false,env:{API_PROXY_TARGET:'http://127.0.0.1:25306',NODE_OPTIONS:'--max-old-space-size=384'}}
});
