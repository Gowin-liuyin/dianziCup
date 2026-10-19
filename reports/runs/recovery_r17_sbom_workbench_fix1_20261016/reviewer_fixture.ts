import { test, expect, type Page } from '../../../frontend/node_modules/@playwright/test/index.mjs';
import { randomBytes } from 'node:crypto';
import { sbomAsset, sbomSnapshot, sbomFixture } from '../../../frontend/tests/r17_sbom_fixture.ts';
import { fixtureAssetId, fixtureTenant } from '../../../frontend/src/features/assets/synthetic-fixtures.ts';

type Fault = 'none' | '401' | '403' | 'tenant' | 'asset' | 'snapshot' | 'projection' | 'locator' | 'type' | 'hash' | 'alias' | 'key';
export async function fixture(page: Page) {
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
export async function clearAssertion(page: Page) {
  await expect(page.getByRole('heading', { name:'快照 #2', exact:true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name:'当前授权资产', exact:true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name:'快照历史', exact:true })).toHaveCount(0);
  await expect(page.getByLabel('选择本地清单', { exact:true })).toHaveCount(0);
  await expect(page.getByText(sbomFixture().combined_semantic_sha256,{ exact:true })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
}
