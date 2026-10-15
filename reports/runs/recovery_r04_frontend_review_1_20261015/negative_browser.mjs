import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';

const run = path.dirname(fileURLToPath(import.meta.url));
const frontend = 'C:/Users/yinha/.codex/worktrees/recovery-r04-frontend-review/dianzi/frontend';
process.env.PLAYWRIGHT_BROWSERS_PATH = 'C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248';
const require = createRequire(`${frontend}/package.json`);
const { chromium } = require('playwright');
const now = () => new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }).replace(' ', 'T') + '+08:00';
const startedAt = now();
const receipt = { started_at: startedAt, candidate: '0b983349e0468a4c75a1adf9f050ac3e7dd00686', credential_input: 'none', viewport: { width: 390, height: 844 }, browser_cache: 'C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248', fixture_scope: 'all /v1 requests intercepted in each isolated context', tests: [] };
const eventId = '10000000-0000-4000-8000-000000000001';
const revisionA = '10000000-0000-4000-8000-000000000002';
const evidenceId = '10000000-0000-4000-8000-000000000003';
const revisionB = '10000000-0000-4000-8000-000000000004';
const claimId = '10000000-0000-4000-8000-000000000005';
const event = { event_id: eventId, event_type: 'advisory', title: '独立 Fixture：旧授权详情', external_ids: ['REVIEW-FIXTURE'], primary_product_ids: [], first_seen_at: '2026-10-15T02:00:00Z', status: 'active', source_count: 1, latest_revision_id: revisionA, freshness: 'unknown' };
const detail = { schema_version: 2, event, dimensions: [{ dimension: 'versions', status: 'available', claim_ids: [claimId], citations: [{ evidence_id: evidenceId, revision_id: revisionA, quote: '版本A原文', locator: 'revision A', source_uri: 'https://example.test/fixture/a' }], freshness: 'unknown', observed_at: null, source_version: null, error_code: null }], revisions: [], claims: [{ claim_id: claimId, predicate: 'review_fixture_statement', display_value: '独立 Fixture：历史A断言', origin: 'source_explicit', status: 'superseded', source_revision_id: revisionA, evidence_ids: [evidenceId] }], data_mode: 'fixture' };
const evidence = { schema_version: 2, span_id: evidenceId, revision_id: revisionA, block_id: null, start_offset: 10, end_offset: 15, quote_text: '独立 Fixture：中😀证据X', quote_sha256: 'a'.repeat(64), locator_kind: 'legacy_unverified', page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: 'fixture' };
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '25304', '--strictPort'], { cwd: frontend, env: { ...process.env, NO_COLOR: '1', FORCE_COLOR: '0' }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let serverOutput = '';
server.stdout.on('data', (chunk) => { serverOutput += chunk; });
server.stderr.on('data', (chunk) => { serverOutput += chunk; });
let browser;

async function createPage(options = {}) {
  const context = await browser.newContext({ viewport: receipt.viewport, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const requests = [];
  let releaseEvidence;
  const evidenceBarrier = new Promise((resolve) => { releaseEvidence = resolve; });
  await page.route('**/v1/**', async (route) => {
    const url = new URL(route.request().url());
    requests.push(url.pathname + url.search);
    let body;
    let status = 200;
    if (url.pathname === '/v1/auth/me') body = { user_id: 'independent-review-fixture', tenant_id: 'independent-review-fixture-tenant', role: 'analyst', permissions: ['read:public'], permission_version: 1, data_mode: 'fixture', csrf_token: randomBytes(32).toString('hex') };
    else if (url.pathname === '/v1/health/live') body = { status: 'live' };
    else if (url.pathname === '/v1/health/ready') body = { status: 'ready', reason: 'independent fixture', dependencies: {} };
    else if (url.pathname === '/v1/events') {
      status = url.searchParams.has('q') ? options.queryStatus ?? 200 : 200;
      body = status === 200 ? { schema_version: 2, items: [event], next_cursor: null, data_mode: 'fixture' } : { error: { code: status === 403 ? 'permission_denied' : 'dependency_unavailable', retryable: status === 503 } };
    } else if (url.pathname === `/v1/events/${eventId}`) body = detail;
    else if (url.pathname === `/v1/evidence/${evidenceId}`) {
      if (options.delayEvidence) await evidenceBarrier;
      status = options.evidenceStatus ?? 200;
      body = status === 200 ? { ...evidence, ...(options.mismatch ? { revision_id: revisionB, quote_text: '独立 Fixture：错误版本B原文' } : {}) } : { error: { code: 'dependency_unavailable', retryable: true } };
    } else throw new Error(`Unexpected isolated request: ${url.pathname}`);
    await route.fulfill({ status, json: body });
  });
  await page.goto('http://127.0.0.1:25304/#events');
  await page.getByRole('link', { name: event.title, exact: true }).waitFor();
  await page.getByRole('link', { name: event.title, exact: true }).click();
  await page.getByText('独立 Fixture：历史A断言', { exact: true }).waitFor();
  return { context, page, requests, releaseEvidence };
}

async function runCase(id, task) {
  const started = now();
  try {
    const observed = await task();
    receipt.tests.push({ id, started_at: started, ended_at: now(), ...observed });
  } catch (error) {
    receipt.tests.push({ id, started_at: started, ended_at: now(), passed: false, harness_error: String(error) });
  }
}

try {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode !== null) throw new Error('dedicated Vite server exited before ready');
    try { if ((await fetch('http://127.0.0.1:25304/')).ok) break; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  await mkdir(path.join(run, 'negative-artifacts'), { recursive: true });
  browser = await chromium.launch({ headless: true });
  await runCase('claim-reference-rejects-mismatched-known-revision', async () => {
    const { context, page, requests } = await createPage({ mismatch: true });
    const href = await page.getByRole('link', { name: '原文片段 [1]', exact: true }).getAttribute('href');
    await page.getByRole('link', { name: '原文片段 [1]', exact: true }).click();
    await page.getByRole('complementary', { name: '证据检视', exact: true }).locator('blockquote').waitFor();
    const wrongVersionDisplayed = (await page.locator('blockquote').textContent()) === '独立 Fixture：错误版本B原文';
    await page.screenshot({ path: path.join(run, 'negative-artifacts', 'claim-mismatched-revision-390.png'), fullPage: true });
    await context.close();
    return { passed: !wrongVersionDisplayed, expected_revision: revisionA, returned_revision: revisionB, href, wrong_version_displayed: wrongVersionDisplayed, requests };
  });
  await runCase('dimension-reference-rejects-mismatched-revision', async () => {
    const { context, page, requests } = await createPage({ mismatch: true });
    await page.getByRole('link', { name: '查看引用：revision A', exact: true }).click();
    await page.getByText('服务返回的数据格式不符合接口约定，请重新检查。', { exact: true }).waitFor();
    const quoteCount = await page.locator('blockquote').count();
    await context.close();
    return { passed: quoteCount === 0, quote_count: quoteCount, requests };
  });
  for (const status of [403, 503]) {
    await runCase(`filter-${status}-clears-selected-detail-and-evidence`, async () => {
      const { context, page, requests } = await createPage({ queryStatus: status });
      await page.getByRole('link', { name: '查看引用：revision A', exact: true }).click();
      await page.locator('blockquote').waitFor();
      await page.getByLabel('检索关键词', { exact: true }).fill('new-filter');
      await page.getByRole('button', { name: '检索情报', exact: true }).click();
      await page.getByRole('heading', { name: status === 403 ? '没有查看权限' : '依赖暂不可用', exact: true }).waitFor();
      const detailTitleCount = await page.locator('.event-detail h3').filter({ hasText: event.title }).count();
      const quoteCount = await page.locator('blockquote').count();
      const oldClaimCount = await page.getByText('独立 Fixture：历史A断言', { exact: true }).count();
      const screenshot = `filter-${status}-retained-detail-390.png`;
      await page.screenshot({ path: path.join(run, 'negative-artifacts', screenshot), fullPage: true });
      await context.close();
      return { passed: detailTitleCount === 0 && quoteCount === 0 && oldClaimCount === 0, detail_title_count: detailTitleCount, evidence_quote_count: quoteCount, old_claim_count: oldClaimCount, requests, screenshot };
    });
  }
  await runCase('evidence-loading-and-error-do-not-steal-focus', async () => {
    const { context, page, releaseEvidence, requests } = await createPage({ evidenceStatus: 503, delayEvidence: true });
    const citation = page.getByRole('link', { name: '查看引用：revision A', exact: true });
    await citation.focus();
    await page.keyboard.press('Enter');
    await page.getByText('正在取得指定版本证据…', { exact: true }).waitFor();
    const loadingFocus = await citation.evaluate((element) => element === document.activeElement);
    releaseEvidence();
    await page.getByRole('heading', { name: '依赖暂不可用', exact: true }).waitFor();
    const failedFocus = await citation.evaluate((element) => element === document.activeElement);
    const quoteCount = await page.locator('blockquote').count();
    await context.close();
    return { passed: loadingFocus && failedFocus && quoteCount === 0, loading_focus_retained: loadingFocus, error_focus_retained: failedFocus, quote_count: quoteCount, requests };
  });
} finally {
  await browser?.close();
  server.kill();
  await writeFile(path.join(run, 'negative-vite.log'), serverOutput);
  receipt.ended_at = now();
  receipt.summary = { passed: receipt.tests.filter((test) => test.passed).length, failed: receipt.tests.filter((test) => !test.passed).length, skipped: 0 };
  await writeFile(path.join(run, 'negative-browser.json'), JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify(receipt));
}
process.exitCode = receipt.summary.failed ? 1 : 0;
