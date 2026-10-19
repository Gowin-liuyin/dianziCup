const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const { defineConfig } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
module.exports = defineConfig({
  testDir: path.join(root, 'frontend/e2e'), testMatch: 'r17_integrated_sbom_api.spec.ts',
  workers: 1, fullyParallel: false, timeout: 60000, expect: { timeout: 10000 },
  outputDir: path.join(__dirname, process.env.R17_EDGE_LABEL + '_artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(__dirname, process.env.R17_EDGE_LABEL + '.json') }]],
  use: { baseURL: 'http://127.0.0.1:26773', channel: 'msedge', viewport: { width: 1366, height: 900 }, trace: 'off', video: 'off', screenshot: 'off' },
  webServer: { command: 'node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 26773 --strictPort', cwd: path.join(root, 'frontend'), env: { API_PROXY_TARGET: 'http://127.0.0.1:28773' }, url: 'http://127.0.0.1:26773', reuseExistingServer: false, timeout: 30000 }
});
