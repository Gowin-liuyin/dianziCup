import { randomBytes } from 'node:crypto';
import { test, expect } from 'C:/Users/yinha/.codex/worktrees/source-jobs-review/dianzi/frontend/node_modules/@playwright/test/index.mjs';
const token=randomBytes(32).toString('hex');
const first='00000000-0000-4000-8000-000000000010', second='00000000-0000-4000-8000-000000000020';
const job=(id=first,status='queued')=>({job_id:id,status,attempt_count:0,error_code:null,result_ref:null,created_at:'2026-10-15T06:00:00Z',finished_at:null});
const user={user_id:'independent-isolated-fixture-reviewer',tenant_id:null,role:'system_admin',permissions:['read:public'],permission_version:1,data_mode:'fixture',csrf_token:token};
function barrier(){let release=()=>{};const promise=new Promise(resolve=>release=resolve);return {promise,release};}
async function routes(page,extra){
 const requests=[];
 await page.route('**/*',async route=>{
  const request=route.request(); const url=new URL(request.url());
  if(url.origin!=='http://127.0.0.1:25304'){await route.abort();throw new Error('fixture attempted non-review origin');}
  if(!url.pathname.startsWith('/v1/')){await route.continue();return;}
  requests.push({path:url.pathname,method:request.method(),body:request.postData(),key:request.headers()['idempotency-key']});
  if(await extra(route,url.pathname,request))return;
  if(url.pathname==='/v1/auth/me')return route.fulfill({json:user});
  if(url.pathname==='/v1/auth/csrf')return route.fulfill({json:{csrf_token:token,header_name:'X-CSRF-Token'}});
  if(url.pathname==='/v1/health/live')return route.fulfill({json:{status:'live'}});
  if(url.pathname==='/v1/health/ready')return route.fulfill({json:{status:'ready',reason:'isolated fixture',dependencies:{}}});
  if(url.pathname==='/v1/auth/logout')return route.fulfill({json:{status:'logged_out'}});
  await route.abort();throw new Error('unexpected fixture route '+url.pathname);
 });return requests;
}
test('independent fixture: late CSRF after actual logout cannot POST',async({page})=>{
 const delayed=barrier(), observed=barrier();
 const requests=await routes(page,async(route,path)=>{if(path!=='/v1/auth/csrf')return false;observed.release();await delayed.promise;await route.fulfill({json:{csrf_token:token,header_name:'X-CSRF-Token'}}).catch(()=>{});return true;});
 await page.goto('/#sources');await page.getByRole('button',{name:'提交本轮采集',exact:true}).click();await observed.promise;
 await page.goto('/#session');await page.getByRole('button',{name:'退出登录',exact:true}).click();await expect(page.getByRole('button',{name:'登录工作台',exact:true})).toBeVisible();
 delayed.release();await page.getByRole('link',{name:'来源监测',exact:true}).click();await expect(page.getByRole('heading',{name:'没有来源调度权限',exact:true})).toBeVisible();
 expect(requests.filter(r=>r.path.startsWith('/v1/sources/'))).toHaveLength(0);expect(requests.filter(r=>r.path==='/v1/auth/logout')).toHaveLength(1);
});
test('independent fixture: old lookup after navigation cannot replace another source job',async({page})=>{
 const delayed=barrier(),observed=barrier();
 const requests=await routes(page,async(route,path)=>{if(path===`/v1/jobs/${first}`){observed.release();await delayed.promise;await route.fulfill({json:job(first,'succeeded')}).catch(()=>{});return true;}if(path===`/v1/jobs/${second}`){await route.fulfill({json:job(second,'blocked')});return true;}return false;});
 await page.goto('/#sources');await page.getByLabel('任务标识',{exact:true}).fill(first);await page.getByRole('button',{name:'查询 / 刷新任务',exact:true}).click();await observed.promise;
 await page.getByRole('link',{name:'运行状态',exact:true}).click();await page.getByRole('link',{name:'来源监测',exact:true}).click();await page.getByRole('combobox',{name:'固定来源',exact:true}).selectOption('vllm_vendor');
 await page.getByLabel('任务标识',{exact:true}).fill(second);await page.getByRole('button',{name:'查询 / 刷新任务',exact:true}).click();await expect(page.getByRole('heading',{name:'任务已阻塞',exact:true})).toBeVisible();delayed.release();
 await expect(page.getByRole('heading',{name:'本页处理完成',exact:true})).toHaveCount(0);await expect(page.getByLabel('任务标识',{exact:true})).toHaveValue(second);
 const prior=requests.length;await page.getByRole('button',{name:'刷新状态',exact:true}).click();await expect(page.getByRole('button',{name:'刷新状态',exact:true})).toBeEnabled();expect(requests.slice(prior).every(r=>r.path.startsWith('/v1/health/'))).toBe(true);
});
test('independent fixture: malformed acceptance stays frozen and raw 403 never leaks',async({page})=>{
 let write=0;const requests=await routes(page,async(route,path)=>{if(!path.startsWith('/v1/sources/'))return false;write++;if(write===1)await route.fulfill({status:202,json:{...job(),status:'all_sources_complete'}});else if(write===2)await route.fulfill({status:403,json:{error:{code:'<img src=x onerror=fixture_secret>',message:'fixture_secret',retryable:true}}});else await route.fulfill({status:202,json:job()});return true;});
 await page.goto('/#sources');await expect(page.getByRole('button',{name:'提交本轮采集',exact:true})).toBeVisible();await page.getByLabel('观察窗口截止（含时区）',{exact:true}).fill('2099-10-15T00:00:00+08:00');await page.getByRole('button',{name:'提交本轮采集',exact:true}).click();await expect(page.getByRole('alert')).toBeVisible();expect(requests.filter(r=>r.path==='/v1/auth/csrf'||r.path.startsWith('/v1/sources/'))).toHaveLength(0);
 await page.getByLabel('观察窗口截止（含时区）',{exact:true}).fill('2026-10-15T06:00:00+08:00');await page.getByRole('button',{name:'提交本轮采集',exact:true}).click();await expect(page.getByText(/提交结果未确认/)).toBeVisible();await page.getByRole('button',{name:'原样重试本轮',exact:true}).click();await expect(page.getByText(/当前会话没有来源管理权限/)).toBeVisible();await expect(page.getByText(/fixture_secret/)).toHaveCount(0);await expect(page.locator('img')).toHaveCount(0);
 await page.getByRole('button',{name:'原样重试本轮',exact:true}).click();await expect(page.getByRole('heading',{name:'本轮已受理',exact:true})).toBeVisible();const writes=requests.filter(r=>r.path.startsWith('/v1/sources/'));expect(writes).toHaveLength(3);expect(writes.every(r=>r.body===writes[0].body&&r.key===writes[0].key)).toBe(true);
 await page.emulateMedia({reducedMotion:'no-preference'});expect(await page.getByTestId('ambient-motion').evaluate(e=>getComputedStyle(e).animationName)).not.toBe('none');await page.emulateMedia({reducedMotion:'reduce'});expect(await page.getByTestId('ambient-motion').evaluate(e=>getComputedStyle(e).animationName)).toBe('none');
});
