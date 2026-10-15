import fs from 'node:fs';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire('C:/Users/yinha/.codex/worktrees/recovery-hacker-ui-review/dianzi/frontend/package.json');
const { chromium, expect } = require('@playwright/test');
const output = 'D:/dianzi/reports/runs/recovery_hacker_ui_review_1_20261015';
const report = { start: new Date().toISOString(), mode: 'explicit isolated synthetic HTTP boundaries; no real credentials or business data', cases: [] };
const fixtureUser = { user_id:'fixture-review-user', tenant_id:'fixture-review-tenant', role:'analyst', permissions:['read:asset'], permission_version:1, data_mode:'fixture', csrf_token:'fixture-review-only-not-real-token' };
const browser = await chromium.launch({headless:true});
async function scenario(name, run) {
  const context = await browser.newContext({viewport:{width:1280,height:800}, reducedMotion:'no-preference'});
  const page = await context.newPage();
  const started = new Date().toISOString();
  try {
    await page.route('**/v1/auth/me', route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixtureUser)}));
    await page.route('**/v1/health/live', route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'live'})}));
    await page.route('**/v1/health/ready', route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'ready',reason:'explicit isolated fixture',dependencies:{database:{state:'ready',reason:'explicit isolated fixture'}}})}));
    const observation = await run(page, context);
    report.cases.push({name,start:started,end:new Date().toISOString(),status:'passed',observation});
  } catch (error) {
    report.cases.push({name,start:started,end:new Date().toISOString(),status:'failed',error:String(error.message)});
  } finally { await context.close(); }
}
await scenario('N01 logout network failure clears identity immediately and says revocation unconfirmed', async page => {
  await page.route('**/v1/auth/logout', route => route.abort('failed'));
  await page.goto('http://127.0.0.1:25300/#session');
  await expect(page.getByText('fixture-review-user',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'退出登录',exact:true}).click();
  await expect(page.getByText('fixture-review-user',{exact:true})).toHaveCount(0);
  await expect(page.getByText('已授予权限',{exact:true})).toHaveCount(0);
  await expect(page.getByText('退出未完成，服务端会话撤销尚未确认。当前页面已清除身份信息。',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'登录工作台',exact:true})).toBeEnabled();
  return await page.evaluate(() => ({local_storage:localStorage.length,session_storage:sessionStorage.length,private_identity_present:document.body.innerText.includes('fixture-review-user')}));
});
await scenario('N02 401 session restore removes permission and identity without private cache', async page => {
  await page.goto('http://127.0.0.1:25300/#session');
  await expect(page.getByText('fixture-review-user',{exact:true})).toBeVisible();
  await page.route('**/v1/auth/me', route => route.fulfill({status:401,contentType:'application/problem+json',body:JSON.stringify({error:{code:'session_expired',retryable:false}})}));
  await page.reload();
  await expect(page.getByText('会话已失效，请重新登录。',{exact:true})).toBeVisible();
  await expect(page.getByText('fixture-review-user',{exact:true})).toHaveCount(0);
  await expect(page.getByText('已授予权限',{exact:true})).toHaveCount(0);
  return {identity_cleared:true,expired_message:true};
});
await scenario('N03 unsupported hash cannot route arbitrary tenant or script and no business request occurs', async page => {
  const apiRequests = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/v1/')) apiRequests.push(new URL(request.url()).pathname); });
  for (const hash of ['constructor','__proto__','events?tenant=other','javascript:alert(1)','events/other']) {
    await page.goto('http://127.0.0.1:25300/#' + hash);
    await expect(page.getByRole('heading',{name:'工作区不存在',exact:true})).toBeVisible();
    await expect(page.getByRole('link',{name:'返回运行状态',exact:true})).toHaveAttribute('href','#runtime');
  }
  assert(apiRequests.every(path => ['/v1/auth/me','/v1/health/live','/v1/health/ready'].includes(path)));
  return {hash_cases:5,api_paths:[...new Set(apiRequests)]};
});
await scenario('N04 390px every prepared page keeps full unavailable explanation inside viewport', async page => {
  await page.setViewportSize({width:390,height:844});
  const observations = [];
  for (const hash of ['events','sources','graph','questions','assets','tasks','changes','reports']) {
    await page.goto('http://127.0.0.1:25300/#' + hash);
    await expect(page.getByText('合成 / Fixture',{exact:true})).toBeVisible();
    const bounds = await page.locator('.capability-panel > .empty-state p').evaluate(element => {
      const range=document.createRange(); range.selectNodeContents(element);
      return {page_width:document.documentElement.scrollWidth,viewport:innerWidth,lines:[...range.getClientRects()].map(rect => ({left:rect.left,right:rect.right})),font_size:getComputedStyle(element).fontSize,line_height:getComputedStyle(element).lineHeight};
    });
    assert(bounds.page_width <= bounds.viewport);
    assert(bounds.lines.length > 0 && bounds.lines.every(rect => rect.left >= 0 && rect.right <= bounds.viewport));
    observations.push({hash,...bounds});
  }
  await page.goto('http://127.0.0.1:25300/#events');
  await expect(page.getByText('合成 / Fixture',{exact:true})).toBeVisible();
  await page.screenshot({path:output+'/independent-fixture-events-390.png',fullPage:true});
  return observations;
});
await scenario('N05 health network failure stays error and never becomes ready or empty success', async page => {
  await page.route('**/v1/health/ready', route => route.abort('failed'));
  await page.goto('http://127.0.0.1:25300/#runtime');
  await expect(page.getByText('健康探测未完成，请恢复连接后重新检查。',{exact:true})).toBeVisible();
  await expect(page.getByText('全部依赖就绪',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'重新检查运行状态',exact:true})).toBeEnabled();
  return {error_visible:true,ready_absent:true,retry_enabled:true};
});
await scenario('N06 real browser motion changes visible pixels while reduced motion stops all decorative movement', async page => {
  await page.goto('http://127.0.0.1:25300/#events');
  await expect(page.getByText('合成 / Fixture',{exact:true})).toBeVisible();
  const motion=page.getByTestId('ambient-motion');
  const before=await motion.evaluate(element => getComputedStyle(element).transform);
  const bounds=await page.locator('#main-content').boundingBox();
  const first=await page.screenshot({path:output+'/independent-fixture-motion-a.png'});
  await page.waitForTimeout(1250);
  const second=await page.screenshot({path:output+'/independent-fixture-motion-b.png'});
  const after=await motion.evaluate(element => getComputedStyle(element).transform);
  assert.notEqual(before,after);
  assert(!first.equals(second));
  assert.deepEqual(await page.locator('#main-content').boundingBox(),bounds);
  const style=await page.evaluate(() => ({pointer_events:getComputedStyle(document.querySelector('.ambient-backdrop')).pointerEvents,panel_background:getComputedStyle(document.querySelector('.panel')).backgroundColor,hidden:document.hidden,visibility:document.visibilityState}));
  assert.equal(style.pointer_events,'none');
  assert.equal(style.panel_background,'rgb(16, 25, 28)');
  await page.emulateMedia({reducedMotion:'reduce'});
  await expect.poll(() => motion.evaluate(element => getComputedStyle(element).animationName)).toBe('none');
  const reducedFirst=await page.screenshot({path:output+'/independent-fixture-reduced-a.png'});
  await page.waitForTimeout(1000);
  const reducedSecond=await page.screenshot({path:output+'/independent-fixture-reduced-b.png'});
  assert(reducedFirst.equals(reducedSecond));
  return {transform_before:before,transform_after:after,visible_pixel_buffers_differ:true,main_bounds_unchanged:true,reduced_pixel_buffers_identical:true,...style};
});
await scenario('N07 login followed by a different identity snapshot rejects the mismatched session', async page => {
  let loggedIn=false;
  await page.route('**/v1/auth/me', route => route.fulfill({status:loggedIn?200:401,contentType:'application/json',body:JSON.stringify(loggedIn ? {...fixtureUser,user_id:'fixture-other-user'} : {error:{code:'unauthenticated',retryable:false}})}));
  await page.route('**/v1/auth/login', route => {loggedIn=true; return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user_id:fixtureUser.user_id,csrf_token:fixtureUser.csrf_token,expires_at:'2099-01-01T00:00:00Z'})});});
  await page.goto('http://127.0.0.1:25300/#session');
  await page.getByLabel('用户名',{exact:true}).fill('fixture-review-only');
  await page.getByLabel('密码',{exact:true}).fill('fixture-not-a-real-password');
  await page.getByRole('button',{name:'登录工作台',exact:true}).click();
  await expect(page.getByText('服务返回的数据格式不符合接口约定，请重新检查。',{exact:true})).toBeVisible();
  await expect(page.getByText('已授予权限',{exact:true})).toHaveCount(0);
  await expect(page.getByLabel('密码',{exact:true})).toHaveValue('');
  return {snapshot_identity_mismatch_rejected:true,password_field_cleared:true};
});
await scenario('N08 skip-to-main keeps the selected research page while moving focus', async page => {
  await page.goto('http://127.0.0.1:25300/#events');
  await expect(page.getByText('合成 / Fixture',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'情报工作区',exact:true})).toBeVisible();
  await page.getByRole('link',{name:'跳到主要内容',exact:true}).focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(150);
  const observation=await page.evaluate(() => ({hash:location.hash,heading:document.querySelector('h1').innerText,main_focused:document.activeElement.id==='main-content'}));
  report.skip_link_observation=observation;
  assert.equal(observation.heading,'情报工作区_', 'Skip link should keep the selected research page.');
  return observation;
});
await browser.close();
report.end=new Date().toISOString();
report.passed=report.cases.filter(item=>item.status==='passed').length;
report.failed=report.cases.filter(item=>item.status==='failed').length;
report.skipped=0;
fs.writeFileSync(output+'/independent_negative_report.json',JSON.stringify(report,null,2));
process.stdout.write(JSON.stringify({passed:report.passed,failed:report.failed,skipped:report.skipped})+'\n');
process.exitCode=report.failed?1:0;
