import { test, expect, type Page } from '../../../frontend/node_modules/@playwright/test/index.mjs';
import { randomBytes } from 'node:crypto';
import { sbomAsset, sbomSnapshot, sbomFixture } from '../../../frontend/tests/r17_sbom_fixture.ts';
import { fixtureAssetId, fixtureTenant } from '../../../frontend/src/features/assets/synthetic-fixtures.ts';

type Fault = 'none' | '401' | '403' | 'tenant' | 'asset' | 'snapshot' | 'projection' | 'locator' | 'type' | 'hash' | 'alias' | 'key';
async function fixture(page: Page) {
  const state = { fault: 'none' as Fault, uri: null as string | null, snapshotPurl: null as string | null, referencePurl: null as string | null, status: 200, hold: '' as 'sbom' | 'parent' | 'fixed' | '', entered: false, release: () => {}, paths: [] as string[], foreign: [] as string[] };
  const csrf = randomBytes(32).toString('hex');
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:26373') { state.foreign.push(url.href); await route.abort(); return; }
    if (!url.pathname.startsWith('/v1/')) { await route.continue(); return; }
    const path = url.pathname; state.paths.push(path);
    let body: unknown; let status = 200;
    const current = sbomSnapshot(); const old = sbomSnapshot(1); const asset = sbomAsset();
    if (state.snapshotPurl !== null) for (const component of current.components) component.purl = state.snapshotPurl;
    asset.snapshot = current;
    if (path === '/v1/auth/me') body = { user_id: 'independent-synthetic-review', tenant_id: fixtureTenant, role: 'tenant_admin', permissions: ['read:asset', 'write:asset'], permission_version: 1, data_mode: 'fixture', csrf_token: csrf };
    else if (path === '/v1/health/live') body = { status: 'live' };
    else if (path === '/v1/health/ready') body = { status: 'ready', reason: 'independent explicit fixture', dependencies: {} };
    else if (path === '/v1/assets') body = { items: [asset], next_cursor: null };
    else if (path === `/v1/assets/${fixtureAssetId}/snapshots`) body = { items: [current,old], next_cursor: null };
    else if (path === `/v1/assets/${fixtureAssetId}`) {
      if (state.hold === 'parent') { state.entered = true; await new Promise<void>(resolve => { state.release = resolve; }); }
      body = asset;
      if (state.fault === 'tenant') body = { ...asset, tenant_id: 'independent-wrong-tenant' };
      if (state.fault === '401' || state.fault === '403') { status = Number(state.fault); body = { error: { code: 'permission_denied', retryable: false } }; }
    } else if (path === `/v1/assets/${fixtureAssetId}/snapshots/${old.snapshot_id}`) {
      if (state.hold === 'fixed') { state.entered = true; await new Promise<void>(resolve => { state.release = resolve; }); }
      body = state.fault === 'tenant' ? { ...old, tenant_id: 'independent-wrong-tenant' } : old;
      if (state.fault === '401' || state.fault === '403') { status = Number(state.fault); body = { error: { code: 'permission_denied', retryable: false } }; }
    } else if (path.endsWith('/sbom')) {
      const historical = path.includes(old.snapshot_id); const sbom = sbomFixture(historical ? 1 : 2);
      if (state.hold === 'sbom' && !historical) { state.entered = true; await new Promise<void>(resolve => { state.release = resolve; }); }
      if (state.uri !== null) sbom.external_documents = [{ document_ref: 'DocumentRef-Independent', document_uri: state.uri, checksum: { algorithm:'SHA256', checksum_value:'1'.repeat(64), source_field_locator:'/externalDocumentRefs/0/checksum' }, source_field_locator:'/externalDocumentRefs/0' }];
      if (state.referencePurl !== null) sbom.dependency_edges[0].target_ref=state.referencePurl;
      if (state.fault === 'tenant') sbom.tenant_id = 'independent-wrong-tenant';
      if (state.fault === 'asset') sbom.asset_id = 'a0000000-0000-4000-8000-000000000099';
      if (state.fault === 'snapshot') sbom.snapshot_id = old.snapshot_id;
      if (state.fault === 'projection') sbom.projection_sha256 = '9'.repeat(64);
      if (state.fault === 'locator') sbom.unmapped_field_locators = ['/metadata/file:~1~1~1independent-private'];
      if (state.fault === 'hash') sbom.raw_sha256 = 'G'.repeat(64);
      if (state.fault === 'type') sbom.dependency_edges[0].relationship = 'file:///independent-private';
      if (state.fault === 'alias') { sbom.dependency_edges[0].target_ref = `redacted-ref:${'1'.repeat(64)}`; sbom.redactions = [{ source_field_locator:'/dependencies/0/ref', reason:'unsafe_uri_or_path', replacement_ref:`redacted-ref:${'1'.repeat(64)}` }]; }
      body = state.fault === 'key' ? { ...sbom, raw_input:'independent-private-do-not-display' } : sbom;
      status = state.fault === '401' || state.fault === '403' ? Number(state.fault) : state.status;
      if (status !== 200) body = { error: { code: status === 503 ? 'inventory_unavailable' : 'permission_denied', retryable: status === 503 } };
    } else throw new Error(`unexpected independent route ${path}`);
    await route.fulfill({ status, json:body });
  });
  return state;
}
async function clearAssertion(page: Page) {
  await expect(page.getByRole('heading', { name:'快照 #2', exact:true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name:'当前授权资产', exact:true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name:'快照历史', exact:true })).toHaveCount(0);
  await expect(page.getByLabel('选择本地清单', { exact:true })).toHaveCount(0);
  await expect(page.getByText(sbomFixture().combined_semantic_sha256,{ exact:true })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
}

const unsafeUris = [
  'https://example.com/%25252525253A', 'https://example.com/c:/../public',
  'https://127.1/private', 'https://2130706433/private', 'https://0x7f000001/private',
  'https://[::ffff:127.0.0.1]/private', 'https://[fc00::1]/private', 'https://[2001:db8::1]/private',
  'https://192.168.4.2/private', 'https://169.254.169.254/private', 'https://user:secret@example.com/document',
  'https://example.com/%2566%2569%256c%2565%253A/private', 'https://example.com/%252f%252fprivate',
  'https://example.com/%2540private', 'https://example.com/a?token=synthetic', 'https://localdomain/private',
];
for (const [index,uri] of unsafeUris.entries()) test(`independent URI ${index+1}: ${index===12 ? 'encoded public path stays on allowed host' : 'dangerous URI removes private DOM'}`, async ({page}) => {
  const api = await fixture(page); api.uri = uri;
  await page.goto(`/#assets/${fixtureAssetId}`);
  if (index===12) {
    const link=page.getByRole('link',{name:'打开服务器提供的公开文档 ↗'});
    await expect(link).toHaveAttribute('href',uri);
    expect(await link.evaluate(element=>new URL((element as HTMLAnchorElement).href).hostname)).toBe('example.com');
    expect(api.foreign).toEqual([]); return;
  }
  await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible(); await clearAssertion(page);
  expect(await page.locator('a').evaluateAll(links => links.map(link=>link.getAttribute('href')))).not.toContain(uri);
  expect(api.foreign).toEqual([]);
});
for (const fault of ['asset','snapshot','projection','locator','hash','type','alias','key'] as const) test(`independent malformed ${fault}: fence clears private DOM`, async ({page}) => {
  const api = await fixture(page); api.hold = 'sbom';
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByRole('heading',{name:'快照 #2',exact:true})).toBeVisible();
  await expect.poll(()=>api.entered).toBe(true); api.fault=fault; api.release();
  await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible(); await clearAssertion(page);
});
for (const target of ['parent','fixed','sbom'] as const) for (const fault of ['401','403','tenant'] as const) test(`independent delayed ${target} ${fault}: revoke whole private workspace`, async ({page}) => {
  const api=await fixture(page); api.hold=target;
  await page.goto(`/#assets/${fixtureAssetId}`);
  if (target==='fixed') { await expect(page.getByRole('heading',{name:'快照 #2',exact:true})).toBeVisible(); await page.getByRole('button',{name:/查看快照 #1 · 历史/}).click(); }
  await expect.poll(()=>api.entered).toBe(true); api.fault=fault; api.release();
  if (fault==='401') await expect(page.getByText('会话已失效，私有资产已清除',{exact:true})).toBeVisible();
  else await expect(page.getByText(/已清除私有资产工作区|当前会话没有此项资产权限/)).toBeVisible();
  await clearAssertion(page);
});
test('independent snapshot PURL cannot enter DOM before sidecar GET',async ({page})=>{
  const api=await fixture(page); api.snapshotPurl='pkg:generic/independent@https%253A%252F%252Fsecret%253Asecret%2540example.com';
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
  await clearAssertion(page); expect(api.paths.some(path=>path.endsWith('/sbom'))).toBe(false);
});
test('independent 503 retry preserves authorized data and fixture label',async ({page})=>{
  const api=await fixture(page); api.status=503;
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText('合成 Fixture · 非真实资产',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'快照 #2',exact:true})).toBeVisible();
  await expect(page.getByText(/当前有效性尚未重新验证/)).toBeVisible();
  api.status=200; await page.getByRole('button',{name:'重试固定 SBOM 声明',exact:true}).click();
  await expect(page.getByText(sbomFixture().combined_semantic_sha256,{exact:true})).toBeVisible();
  expect(api.foreign).toEqual([]);
});
test('independent late current SBOM cannot replace selected history',async ({page})=>{
  const api=await fixture(page); api.hold='sbom'; await page.goto(`/#assets/${fixtureAssetId}`);
  await expect.poll(()=>api.entered).toBe(true); await page.getByRole('button',{name:/查看快照 #1 · 历史/}).click();
  await expect(page.getByText(sbomFixture(1).combined_semantic_sha256,{exact:true})).toBeVisible();
  api.release(); await expect(page.getByText(sbomFixture().combined_semantic_sha256,{exact:true})).toHaveCount(0);
  await expect(page.getByText(sbomFixture(1).combined_semantic_sha256,{exact:true})).toBeVisible();
});
test('independent 390px keyboard and dynamic backdrop both modes',async ({page},info)=>{
  await fixture(page); await page.setViewportSize({width:390,height:844});
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(sbomFixture().combined_semantic_sha256,{exact:true})).toBeVisible();
  expect(await page.locator('.ambient-topology').evaluate(element=>getComputedStyle(element).animationName)).not.toBe('none');
  await page.emulateMedia({reducedMotion:'reduce'});
  expect(await page.locator('.ambient-topology').evaluate(element=>getComputedStyle(element).animationName)).toBe('none');
  const history=page.getByRole('button',{name:/查看快照 #1 · 历史/}); await history.focus(); await page.keyboard.press('Enter');
  await expect(page.getByText(sbomFixture(1).combined_semantic_sha256,{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('independent-390-history.png'),fullPage:true});
});
test('independent normalized safe public URL renders with no-referrer and no fetch',async ({page},info)=>{
  const api=await fixture(page); api.uri='https://Example.COM:443/a/../synthetic.spdx.json';
  await page.goto(`/#assets/${fixtureAssetId}`); const link=page.getByRole('link',{name:'打开服务器提供的公开文档 ↗'});
  await expect(link).toHaveAttribute('referrerpolicy','no-referrer'); await expect(link).toHaveAttribute('rel','noopener noreferrer');
  expect(await link.evaluate(element=>(element as HTMLAnchorElement).href)).toBe('https://example.com/synthetic.spdx.json');
  expect(api.foreign).toEqual([]); await page.screenshot({path:info.outputPath('independent-desktop.png'),fullPage:true});
});
for (const target of ['snapshot','reference'] as const) test(`independent MUST PURL encoded private version in ${target} must be revoked`,async ({page},info)=>{
  const api=await fixture(page); const purl='pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env';
  if (target==='snapshot') api.snapshotPurl=purl; else api.referencePurl=purl;
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(purl,{exact:true})).toBeVisible();
  await page.getByText(purl,{exact:true}).scrollIntoViewIfNeeded();
  await page.screenshot({path:info.outputPath(`must-purl-${target}-disclosed.png`),fullPage:true});
  await page.screenshot({path:info.outputPath(`must-purl-${target}-viewport.png`)});
  await info.attach('observed-private-version',{body:JSON.stringify({target,purl,displayed:true,expected:'scope fence must reject this unsafe PURL before DOM',sidecarRequested:api.paths.some(path=>path.endsWith('/sbom'))}),contentType:'application/json'});
  await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
});
