const { defineConfig } = require('D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/node_modules/@playwright/test');
module.exports = defineConfig({
 testDir: 'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/e2e',
 fullyParallel: false, workers: 1, timeout: 30000, expect: { timeout: 10000 },
 outputDir: 'D:/dianzi/reports/runs/recovery_r05_question_frontend_review_1_20261015/e2e_original_artifacts',
 reporter: [['list'], ['json',{outputFile:'D:/dianzi/reports/runs/recovery_r05_question_frontend_review_1_20261015/e2e_original.json'}]],
 use: {baseURL:'http://127.0.0.1:25317', browserName:'chromium', viewport:{width:1280,height:800},trace:'off',video:'off',screenshot:'off'},
 webServer: { command:'npm run dev -- --host 127.0.0.1 --port 25317 --strictPort', cwd:'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend',url:'http://127.0.0.1:25317',timeout:30000,reuseExistingServer:false}
});
