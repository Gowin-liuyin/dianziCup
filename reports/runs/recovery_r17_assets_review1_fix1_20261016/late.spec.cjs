const { test, expect } = require('../../../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const ASSET = 'a1111111-1111-4111-8111-111111111111';
const OTHER = 'a1111111-1111-4111-8111-111111111119';
const CURRENT = 'b1111111-1111-4111-8111-111111111112';
const OLD = 'b1111111-1111-4111-8111-111111111111';
const TENANT = 'independent-synthetic-tenant';
const NAME = '独立合成资产 Alpha';
const RAW = ' {"format_version":1,"components":[]}\r\n';
function snapshot(number = 2, tenant = TENANT, assetId = ASSET) {
  return { schema_version: 'r11-asset-candidate-1', snapshot_id: number === 2 ? CURRENT : OLD, asset_id: assetId, tenant_id: tenant, snapshot_number: number, observed_at: '2026-10-15T01:00:00Z', recorded_at: '2026-10-15T02:00:00Z', source_kind: 'json_manifest_v1', inventory_completeness: 'partial', declared_scope: [], components: [], configuration: [], tool_permissions: null, input_channels: null, network_exposure: null, snapshot_sha256: 'd'.repeat(64) };
}
function asset(assetId = ASSET, tenant = TENANT) { return { asset_id: assetId, tenant_id: tenant, display_name: NAME, criticality: 'unknown', active: true, current_snapshot_id: CURRENT, created_at: '2026-10-15T01:00:00Z', updated_at: '2026-10-15T02:00:00Z', snapshot: snapshot(2, tenant, assetId) }; }
async function click(page, locator) { await locator.scrollIntoViewIfNeeded(); const rect = await locator.boundingBox(); if (!rect) throw new Error('鼠标目标不可见'); await page.mouse.click(rect.x + rect.width / 2, rect.y + rect.height / 2); }
async function install(page) {
  const state = { listFault: 'none', fixedFault: 'none', wrongCurrent: false, wrongImport: false, initialListHold: false, listRelease: null, currentHold: false, currentRelease: null, csrfHold: false, csrfRelease: null, importHold: false, importRelease: null, imports: [], requests: [] };
  await page.route('**/v1/**', async route => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname; state.requests.push(request.method() + ' ' + path);
    let status = 200; let body;
    if (path === '/v1/auth/me') body = { user_id: 'independent-synthetic-user', tenant_id: TENANT, role: 'tenant_admin', permissions: ['read:asset', 'write:asset'], permission_version: 1, data_mode: 'fixture', csrf_token: 'synthetic-scope-csrf' };
    else if (path === '/v1/auth/csrf') { if (state.csrfHold) await new Promise(resolve => state.csrfRelease = resolve); body = { csrf_token: 'synthetic-scope-csrf', header_name: 'X-CSRF-Token' }; }
    else if (path === '/v1/health/live') body = { status: 'live' };
    else if (path === '/v1/health/ready') body = { status: 'ready', reason: 'synthetic intercept only', dependencies: {} };
    else if (path === '/v1/assets') {
      if (url.searchParams.has('cursor')) { status = state.listFault === '503' ? 503 : 200; body = status === 503 ? { error: { code: 'inventory_unavailable', retryable: true } } : { items: state.listFault === 'scope' ? [asset(ASSET, 'wrong-synthetic-tenant')] : [], next_cursor: null }; }
      else { body = { items: [asset()], next_cursor: 'independent-next' }; if (state.initialListHold) await new Promise(resolve => state.listRelease = resolve); }
    } else if (path === `/v1/assets/${ASSET}`) { body = asset(state.wrongCurrent ? OTHER : ASSET); if (state.currentHold) await new Promise(resolve => state.currentRelease = resolve); }
    else if (path === `/v1/assets/${ASSET}/snapshots`) body = { items: [snapshot(), snapshot(1)], next_cursor: null };
    else if (path === `/v1/assets/${ASSET}/snapshots/${OLD}`) { body = snapshot(1, state.fixedFault === 'scope' ? 'wrong-synthetic-tenant' : TENANT); if (state.fixedFault === 'wrong_snapshot') body.snapshot_id = CURRENT; if (state.fixedFault === 'schema') body.schema_version = 'unsupported-synthetic'; }
    else if (path === '/v1/asset-imports') {
      state.imports.push({ bytes: request.postDataBuffer().toString('base64'), key: request.headers()['idempotency-key'], origin: request.headers()['origin'], csrf: request.headers()['x-csrf-token'], query: Object.fromEntries(url.searchParams) });
      body = { asset_id: state.wrongImport ? OTHER : ASSET, snapshot: snapshot(2, TENANT, state.wrongImport ? OTHER : ASSET), reused: false }; status = 201;
      if (state.importHold) await new Promise(resolve => state.importRelease = resolve);
    } else throw new Error('未预期的独立scope路由 ' + path);
    await route.fulfill({ status, json: body });
  }); return state;
}
async function fill(page, append = false) {
  await click(page, page.locator('.asset-import-panel summary'));
  if (append) await click(page, page.getByLabel('追加到当前所选资产（名称保持一致）', { exact: true }));
  await page.getByLabel('选择本地清单', { exact: true }).setInputFiles({ name: 'independent-private.json', mimeType: 'application/json', buffer: Buffer.from(RAW) });
  if (!append) await page.getByLabel('资产名称', { exact: true }).fill(NAME);
  await page.getByLabel('输入来源版本', { exact: true }).fill('independent-scope-v1');
  await page.getByLabel('实际观察时间（含时区）', { exact: true }).fill('2026-10-15T01:00:00Z');
}
async function cleared(page) {
  await expect(page.getByRole('alert')).toContainText('已清除私有资产工作区');
  await expect(page.getByText(NAME, { exact: true })).toHaveCount(0);
  for (const name of ['当前授权资产', '快照历史', '快照 #2']) await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0);
  await expect(page.getByLabel('选择本地清单', { exact: true })).toHaveCount(0);
  await expect(page.getByText('导入成功 · 服务端已保存快照', { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
}
async function record(page, info, state) { fs.writeFileSync(info.outputPath('observation.json'), JSON.stringify({ fixture: true, requests: state.requests, imports: state.imports, hash: await page.evaluate(() => location.hash), privateNameCount: await page.getByText(NAME, { exact: true }).count() }, null, 2)); await page.screenshot({ path: info.outputPath('observation.png'), fullPage: true }); }
test('L1：目录scope失败后迟到current不得恢复', async ({ page }, info) => {
  const state = await install(page); state.currentHold = true; await page.goto(`/#assets/${ASSET}`); await expect.poll(() => state.currentRelease !== null).toBe(true);
  state.listFault = 'scope'; await click(page, page.getByRole('button', { name: '加载更多资产', exact: true })); await cleared(page);
  state.currentHold = false; state.currentRelease(); await cleared(page); await record(page, info, state);
});
test('L2：历史scope失败后迟到catalog不得恢复', async ({ page }, info) => {
  const state = await install(page); state.initialListHold = true; await page.goto(`/#assets/${ASSET}`); await expect.poll(() => state.listRelease !== null).toBe(true);
  await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible(); state.fixedFault = 'scope';
  await click(page, page.getByRole('button', { name: /查看快照 #1/ })); await cleared(page); state.initialListHold = false; state.listRelease(); await cleared(page); await record(page, info, state);
});
test('L3：历史scope失败清File，迟到CSRF不得POST', async ({ page }, info) => {
  const state = await install(page); await page.goto(`/#assets/${ASSET}`); await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible(); await fill(page); state.csrfHold = true;
  await click(page, page.getByRole('button', { name: '提交授权清单', exact: true })); await expect.poll(() => state.csrfRelease !== null).toBe(true); state.fixedFault = 'scope';
  await click(page, page.getByRole('button', { name: /查看快照 #1/ })); await cleared(page); state.csrfHold = false; state.csrfRelease(); await cleared(page); await record(page, info, state); expect(state.imports).toHaveLength(0);
  await click(page, page.getByRole('link', { name: '核对会话与权限', exact: true })); await expect(page.getByRole('button', { name: '退出登录', exact: true })).toBeVisible();
});
test('L4：已POST导入迟到201不得恢复receipt或跳新asset', async ({ page }, info) => {
  const state = await install(page); await page.goto(`/#assets/${ASSET}`); await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible(); await fill(page); state.wrongImport = true; state.importHold = true;
  await click(page, page.getByRole('button', { name: '提交授权清单', exact: true })); await expect.poll(() => state.importRelease !== null).toBe(true); expect(state.imports).toHaveLength(1); state.fixedFault = 'scope';
  await click(page, page.getByRole('button', { name: /查看快照 #1/ })); await cleared(page); state.importHold = false; state.importRelease(); await cleared(page); await record(page, info, state);
  await expect(page).toHaveURL(new RegExp(`#assets/${ASSET}$`)); expect(state.imports[0].bytes).toBe(Buffer.from(RAW).toString('base64'));
});
test('L5：普通503保留可读目录和File，会话有效，真实retry恢复', async ({ page }, info) => {
  const state = await install(page); await page.goto('/#assets'); await expect(page.getByRole('link', { name: new RegExp(NAME) })).toBeVisible(); await fill(page); state.listFault = '503';
  await click(page, page.getByRole('button', { name: '加载更多资产', exact: true })); await expect(page.getByRole('alert')).toContainText('暂不可用'); await expect(page.getByRole('link', { name: new RegExp(NAME) })).toBeVisible();
  expect(await page.getByLabel('选择本地清单', { exact: true }).evaluate(el => el.files[0].name)).toBe('independent-private.json');
  state.listFault = 'none'; await click(page, page.getByRole('button', { name: '重试资产页', exact: true })); await expect(page.getByRole('alert')).toHaveCount(0); await record(page, info, state);
  await click(page, page.getByRole('link', { name: '会话与权限', exact: true })); await expect(page.getByRole('button', { name: '退出登录', exact: true })).toBeVisible(); expect(state.requests.some(v => v.startsWith('POST'))).toBe(false);
});
test('L6：current返回不同请求asset UUID清目录', async ({ page }, info) => {
  const state = await install(page); state.wrongCurrent = true; await page.goto(`/#assets/${ASSET}`); await cleared(page); await record(page, info, state);
});
test('L7：fixed返回不同请求snapshot UUID清详情历史', async ({ page }, info) => {
  const state = await install(page); await page.goto(`/#assets/${ASSET}`); await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible(); state.fixedFault = 'wrong_snapshot';
  await click(page, page.getByRole('button', { name: /查看快照 #1/ })); await cleared(page); await record(page, info, state);
});
test('L8：追加receipt不同asset UUID清File且不导航', async ({ page }, info) => {
  const state = await install(page); await page.goto(`/#assets/${ASSET}`); await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible(); await fill(page, true); state.wrongImport = true;
  await click(page, page.getByRole('button', { name: '提交授权清单', exact: true })); await cleared(page); await record(page, info, state); expect(state.imports).toHaveLength(1); expect(state.imports[0].query.asset_id).toBe(ASSET);
  await expect(page).toHaveURL(new RegExp(`#assets/${ASSET}$`));
});
test('L9：普通schema invalid保留授权目录和局部重试', async ({ page }, info) => {
  const state = await install(page); await page.goto(`/#assets/${ASSET}`); await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible(); state.fixedFault = 'schema';
  await click(page, page.getByRole('button', { name: /查看快照 #1/ })); await expect(page.getByRole('alert')).toContainText('合同或会话范围不一致'); await expect(page.getByRole('link', { name: new RegExp(NAME) })).toBeVisible(); await expect(page.getByRole('button', { name: '重试固定快照', exact: true })).toBeVisible(); await record(page, info, state);
});
