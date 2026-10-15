export default {
  testDir: 'C:/Users/yinha/.codex/worktrees/recovery-hacker-ui-review/dianzi/frontend/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  expect: { timeout: 10000 },
  outputDir: 'D:/dianzi/reports/runs/recovery_hacker_ui_review_1_20261015/real_browser_artifacts',
  reporter: [['D:/dianzi/reports/runs/recovery_hacker_ui_review_1_20261015/safe-reporter.mjs']],
  use: {
    baseURL: 'http://127.0.0.1:25300',
    browserName: 'chromium',
    viewport: { width: 1280, height: 800 },
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
};
