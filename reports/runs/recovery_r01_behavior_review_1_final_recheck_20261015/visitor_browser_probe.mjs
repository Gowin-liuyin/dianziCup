import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { writeFile } from 'node:fs/promises';

const root = 'C:/Users/yinha/.codex/worktrees/recovery-r01-recheck-final/dianzi';
const require = createRequire(root + '/frontend/package.json');
const { chromium, expect } = require('@playwright/test');
const artifact = 'D:/dianzi/reports/runs/recovery_r01_behavior_review_1_final_recheck_20261015';
const server = spawn(process.execPath, [root + '/frontend/node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '25179', '--strictPort'], { cwd: root + '/frontend', windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let serverOutput = '';
let browser;
const startedAt = new Date().toISOString();
const results = [];
try {
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('isolated Vite startup timeout')), 15_000);
    server.once('error', reject);
    server.once('exit', (code) => { clearTimeout(timeout); reject(new Error('isolated Vite exited before readiness: ' + code)); });
    server.stdout.on('data', (value) => { serverOutput += value.toString(); if (serverOutput.includes('http://127.0.0.1:25179/')) { clearTimeout(timeout); resolve(); } });
    server.stderr.on('data', (value) => { serverOutput += value.toString(); });
  });
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  let releaseReady;
  let readyStarted;
  const readyHeld = new Promise((resolve) => { releaseReady = resolve; });
  const readyEntered = new Promise((resolve) => { readyStarted = resolve; });
  await page.route('**/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/v1/auth/me') return route.fulfill({ status: 401, contentType: 'application/problem+json', body: JSON.stringify({ error: { code: 'unauthenticated', retryable: false } }) });
    if (path === '/v1/health/live') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'live' }) });
    if (path === '/v1/health/ready') {
      readyStarted();
      await readyHeld;
      return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ status: 'not_ready', reason: 'controlled slow health boundary', dependencies: { database: { state: 'ready' }, worker: { state: 'not_observed_or_stale' }, scheduler: { state: 'unavailable' } } }) });
    }
    throw new Error('unexpected visitor API path');
  });
  await page.goto('http://127.0.0.1:25179/');
  await readyEntered;
  await expect(page.getByRole('button', { name: '登录工作台', exact: true })).toBeVisible();
  const refresh = page.getByRole('button', { name: '刷新状态', exact: true });
  await expect(refresh).toBeDisabled();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: '跳到主要内容', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('用户名', { exact: true })).toBeFocused();
  releaseReady();
  await expect(refresh).toBeEnabled();
  await page.getByRole('link', { name: '跳到主要内容', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(refresh).toBeFocused();
  results.push({ case: 'visitor-native-keyboard-slow-ready', passed: true, disabledRefreshSkipped: true, enabledRefreshFocused: true });
  await expect(page.getByRole('row', { name: /任务进程/ })).toContainText('待观测 / 已过期');
  await expect(page.getByRole('row', { name: /调度进程/ })).toContainText('不可用');
  await expect(page.getByText('全部依赖就绪', { exact: true })).toHaveCount(0);
  await expect(page.getByText('已授予权限', { exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: '登录工作台', exact: true })).toBeVisible();
  if (!(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))) throw new Error('visitor layout overflows at 390px');
  const stores = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }));
  if (stores.local !== 0 || stores.session !== 0) throw new Error('unexpected visitor browser storage');
  results.push({ case: 'visitor-stale-worker-and-unavailable-scheduler', passed: true, visitorOnly: true, viewportWidth: 390 });
  const receipt = { mode: 'real headless browser + this frozen frontend with controlled HTTP route delay; no authenticated API/credentials', startedAt, finishedAt: new Date().toISOString(), browserVersion: browser.version(), candidateSha: 'd30eeab1d723080decea5f64a992b909a0d834c2', serverPort: 25179, trace: 'off', video: 'off', screenshots: 'off', tests: results.length, results };
  await writeFile(artifact + '/visitor_browser_receipt.json', JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify(receipt));
  await context.close();
} finally {
  if (browser) await browser.close();
  server.kill();
}
