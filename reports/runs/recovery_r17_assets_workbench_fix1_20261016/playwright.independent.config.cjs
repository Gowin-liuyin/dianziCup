const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const { defineConfig } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
const phase = process.env.DIANZI_ASSET_SCOPE_PHASE === 'red' ? 'red' : 'green';
module.exports = defineConfig({
  testDir: __dirname, testMatch: 'independent.spec.cjs', fullyParallel: false, workers: 1,
  timeout: 30000, expect: { timeout: 2000 }, outputDir: path.join(__dirname, `independent_${phase}_artifacts`),
  reporter: [['list'], ['json', { outputFile: path.join(__dirname, `independent_${phase}_report.json`) }]],
  use: { baseURL: 'http://127.0.0.1:25719', browserName: 'chromium', channel: 'msedge', headless: true, viewport: { width: 1280, height: 800 }, trace: 'off', video: 'off', screenshot: 'off' },
  webServer: { command: 'npm run preview -- --host 127.0.0.1 --port 25719 --strictPort', cwd: path.join(root, 'frontend'), url: 'http://127.0.0.1:25719', timeout: 30000, reuseExistingServer: false }
});
