const { test, expect } = require('../../../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const ASSET = 'a1111111-1111-4111-8111-111111111111';
const CURRENT = 'b1111111-1111-4111-8111-111111111112';
const OLD = 'b1111111-1111-4111-8111-111111111111';
const TENANT = 'independent-synthetic-tenant';
const NAME = '独立合成资产 Alpha';
function snapshot(number = 2, tenant = TENANT) {
  return { schema_version: 'r11-asset-candidate-1', snapshot_id: number === 2 ? CURRENT : OLD, asset_id: ASSET, tenant_id: tenant, snapshot_number: number, observed_at: '2026-10-15T01:00:00Z', recorded_at: '2026-10-15T02:00:00Z', source_kind: 'json_manifest_v1', inventory_completeness: 'partial', declared_scope: ['independent-synthetic-package'], components: [{ component_id: 'c1111111-1111-4111-8111-111111111111', ecosystem: 'PyPI', package_name: 'independent-synthetic-package', display_name: null, purl: null, version: number === 2 ? '2.0.0' : '1.0.0', version_scheme: 'pep440', image_digest: null, dependency_path: null, source_field_locator: '/components/0' }], configuration: [{ name: 'external_inputs', value: null, source_field_locator: '/configuration/external_inputs' }], tool_permissions: null, input_channels: null, network_exposure: null, snapshot_sha256: 'd'.repeat(64) };
}
function asset(tenant = TENANT) { return { asset_id: ASSET, tenant_id: tenant, display_name: NAME, criticality: 'unknown', active: true, current_snapshot_id: CURRENT, created_at: '2026-10-15T01:00:00Z', updated_at: '2026-10-15T02:00:00Z', snapshot: snapshot(2, tenant) }; }
async function click(page, locator) {
  await locator.scrollIntoViewIfNeeded(); const rect = await locator.boundingBox();
  if (!rect) throw new Error('鼠标目标不可见');
  await page.mouse.click(rect.x + rect.width / 2, rect.y + rect.height / 2);
}
async function install(page) {
  const state = { badList: false, badFixed: false, currentHold: false, currentRelease: null, csrfHold: false, csrfRelease: null, history404: false, selectedStatus: 200, imports: [], requests: [], authenticated: true, importHold: false, importRelease: null };
  await page.route('**/v1/**', async (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname;
    state.requests.push(req.method() + ' ' + path); let body; let status = 200;
    if (path === '/v1/auth/me') { status = state.authenticated ? 200 : 401; body = status === 200 ? { user_id: 'independent-synthetic-user', tenant_id: TENANT, role: 'tenant_admin', permissions: ['read:asset', 'write:asset'], permission_version: 1, data_mode: 'fixture', csrf_token: 'independent-synthetic-csrf' } : { error: { code: 'session_expired', retryable: false } }; }
    else if (path === '/v1/auth/csrf') { if (state.csrfHold) await new Promise(resolve => state.csrfRelease = resolve); body = { csrf_token: 'independent-synthetic-csrf', header_name: 'X-CSRF-Token' }; }
    else if (path === '/v1/auth/logout') { state.authenticated = false; body = { status: 'logged_out' }; }
    else if (path === '/v1/health/live') body = { status: 'live' };
    else if (path === '/v1/health/ready') body = { status: 'ready', reason: '独立合成截获，非后端联测', dependencies: {} };
    else if (path === '/v1/assets') body = url.searchParams.has('cursor') ? { items: [asset(state.badList ? 'wrong-synthetic-tenant' : TENANT)], next_cursor: null } : { items: [asset()], next_cursor: 'independent-next' };
    else if (path === `/v1/assets/${ASSET}`) { const frozen = asset(); if (state.currentHold) await new Promise(resolve => state.currentRelease = resolve); body = frozen; }
    else if (path === `/v1/assets/${ASSET}/snapshots`) { status = state.history404 ? 404 : 200; body = status === 200 ? { items: [snapshot(), snapshot(1)], next_cursor: null } : { error: { code: 'not_found', retryable: false } }; }
    else if (path === `/v1/assets/${ASSET}/snapshots/${OLD}`) { status = state.selectedStatus; body = status === 200 ? snapshot(1, state.badFixed ? 'wrong-synthetic-tenant' : TENANT) : { error: { code: 'not_found', retryable: false } }; }
    else if (path === '/v1/asset-imports') {
      state.imports.push({ key: req.headers()['idempotency-key'], bytes: req.postDataBuffer().toString('base64'), headers: { origin: req.headers()['origin'], csrf: req.headers()['x-csrf-token'] }, query: Object.fromEntries(url.searchParams) });
      if (state.importHold) await new Promise(resolve => state.importRelease = resolve);
      status = 503; body = { error: { code: 'inventory_unavailable', retryable: true } };
    } else throw new Error('独立fixture未知路由 ' + path);
    await route.fulfill({ status, json: body });
  }); return state;
}
async function fill(page, raw) {
  await click(page, page.locator('.asset-import-panel summary'));
  await page.getByLabel('选择本地清单', { exact: true }).setInputFiles({ name: 'independent.json', mimeType: 'application/json', buffer: Buffer.from(raw) });
  await page.getByLabel('资产名称', { exact: true }).fill(NAME);
  await page.getByLabel('输入来源版本', { exact: true }).fill('independent-v1');
  await page.getByLabel('实际观察时间（含时区）', { exact: true }).fill('2026-10-15T01:00:00Z');
}
async function record(page, info, state) {
  fs.writeFileSync(info.outputPath('observation.json'), JSON.stringify({ fixture: true, requests: state.requests, imports: state.imports, privateNameCount: await page.getByText(NAME, { exact: true }).count(), localStorage: await page.evaluate(() => localStorage.length + sessionStorage.length) }, null, 2));
  await page.screenshot({ path: info.outputPath('observation.png'), fullPage: true });
}

test('合成连动 F：目录范围违例后释放 current 不得恢复目录或详情', async ({ page }, info) => {
  const state = await install(page); state.currentHold = true;
  await page.goto(`/#assets/${ASSET}`);
  await expect.poll(() => state.currentRelease !== null).toBe(true);
  await expect(page.getByRole('link', { name: new RegExp(NAME) })).toBeVisible();
  state.badList = true; await click(page, page.getByRole('button', { name: '加载更多资产', exact: true }));
  await expect(page.getByRole('alert')).toContainText('会话范围不一致');
  await expect(page.getByText(NAME, { exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '快照历史', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('选择本地清单', { exact: true })).toHaveCount(0);
  state.currentHold = false; state.currentRelease();
  await record(page, info, state);
  await expect(page.getByText(NAME, { exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toHaveCount(0);
});
test('合成连动 G：固定历史范围违例后释放 CSRF 不得实际 POST', async ({ page }, info) => {
  const state = await install(page); await page.goto(`/#assets/${ASSET}`);
  await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible();
  await fill(page, '{"format_version":1,"components":[]}\r\n'); state.csrfHold = true;
  await click(page, page.getByRole('button', { name: '提交授权清单', exact: true }));
  await expect.poll(() => state.csrfRelease !== null).toBe(true);
  state.badFixed = true; await click(page, page.getByRole('button', { name: /查看快照 #1/ }));
  await expect(page.getByRole('alert')).toContainText('会话范围不一致');
  await expect(page.getByText(NAME, { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('选择本地清单', { exact: true })).toHaveCount(0);
  state.csrfHold = false; state.csrfRelease();
  await record(page, info, state); expect(state.imports).toHaveLength(0);
  await expect(page.getByText(NAME, { exact: true })).toHaveCount(0);
  await click(page, page.getByRole('link', { name: '核对会话与权限', exact: true }));
  await expect(page.getByRole('button', { name: '退出登录', exact: true })).toBeVisible();
});
