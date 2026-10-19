const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const { defineConfig } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
module.exports = defineConfig({
  testDir: __dirname, testMatch: 'motion.spec.cjs', workers: 1, timeout: 30000,
  outputDir: path.join(__dirname, 'motion_artifacts'), reporter: 'json',
  use: { baseURL: 'http://127.0.0.1:25719', browserName: 'chromium', channel: 'msedge', headless: true, viewport: { width: 1280, height: 800 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: { command: 'npm run preview -- --host 127.0.0.1 --port 25719 --strictPort', cwd: path.join(root, 'frontend'), url: 'http://127.0.0.1:25719', reuseExistingServer: false }
});
