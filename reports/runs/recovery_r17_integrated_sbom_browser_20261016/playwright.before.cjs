const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const { defineConfig } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
module.exports = defineConfig({
  testDir: path.join(root, 'frontend/e2e'), testMatch: 'r17_sbom_fixture.spec.ts',
  workers: 1, fullyParallel: false, timeout: 30000,
  outputDir: path.join(__dirname, 'before_fixture_artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(__dirname, 'before_fixture.json') }]],
  use: { baseURL: 'http://127.0.0.1:26773', channel: 'msedge', viewport: { width: 1366, height: 900 }, trace: 'off', video: 'off', screenshot: 'off' },
  webServer: { command: 'node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 26773 --strictPort', cwd: path.join(root, 'frontend'), url: 'http://127.0.0.1:26773', reuseExistingServer: false, timeout: 30000 }
});
