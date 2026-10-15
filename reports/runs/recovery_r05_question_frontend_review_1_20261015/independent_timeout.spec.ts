import { randomBytes } from 'node:crypto';
import { test, expect } from 'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/node_modules/@playwright/test/index.mjs';
import { questionAnswerFixture, questionFixtureIds as ids } from 'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/src/features/questions/question.fixture';

async function setup(page, heldPath) {
 const csrf=randomBytes(32).toString('hex'); const calls=[]; let release; const held=new Promise(resolve=>release=resolve); let holdOnce=true;
 await page.route('**/v1/**',async route=>{
  const req=route.request(); const path=new URL(req.url()).pathname; calls.push({path,body:req.postData(),key:req.headers()['idempotency-key']});
  if(path===heldPath && holdOnce) { holdOnce=false; await held; }
  const send=async(body,status=200)=>{try{return await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});}catch{return;}};
  if(path==='/v1/auth/me')return send({user_id:'independent-budget-user',tenant_id:'budget-tenant',role:'analyst',permissions:['read:public'],permission_version:1,data_mode:'fixture',csrf_token:csrf});
  if(path==='/v1/auth/csrf')return send({csrf_token:csrf,header_name:'X-CSRF-Token'});
  if(path==='/v1/health/live')return send({status:'live'});
  if(path==='/v1/health/ready')return send({status:'ready',reason:'review fixture',dependencies:{}});
  if(path==='/v1/questions'||path.startsWith('/v1/answers/'))return send(questionAnswerFixture());
  throw new Error(`Unexpected route: ${path}`);
 });
 await page.goto(`/#questions/${ids.event}`); await expect(page.getByRole('button',{name:'提交问题',exact:true})).toBeVisible();
 return {calls,release:()=>release()};
}
async function ask(page){await page.getByLabel('你的问题',{exact:true}).fill('独立预算边界');await page.getByRole('button',{name:'提交问题',exact:true}).click();}

test('TIME01 POST stays pending at 10s, expires at 90s, retries identical body and key',async({page})=>{
 const flow=await setup(page,'/v1/questions'); await page.clock.install(); await ask(page); await expect.poll(()=>flow.calls.filter(c=>c.path==='/v1/questions').length).toBe(1);
 await page.clock.fastForward(10001); await expect(page.getByText(/正在提交问题并等待完整回答/)).toBeVisible(); await expect(page.getByRole('alert')).toHaveCount(0);
 await page.clock.fastForward(79999); await expect(page.getByRole('alert')).toContainText('提交结果未确认'); await expect(page.getByRole('article',{name:'完整证据回答'})).toHaveCount(0); flow.release();
 await page.getByRole('button',{name:'原样重试本轮',exact:true}).click(); await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible(); const writes=flow.calls.filter(c=>c.path==='/v1/questions');expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0]);
});
test('TIME02 CSRF still expires at default 10s and performs zero paid POST',async({page})=>{
 const flow=await setup(page,'/v1/auth/csrf'); await page.clock.install(); await ask(page); await expect.poll(()=>flow.calls.filter(c=>c.path==='/v1/auth/csrf').length).toBe(1);
 await page.clock.fastForward(10001); await expect(page.getByRole('alert')).toContainText('提交结果未确认'); expect(flow.calls.filter(c=>c.path==='/v1/questions')).toHaveLength(0); flow.release();
 await page.getByRole('button',{name:'原样重试本轮',exact:true}).click(); await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible(); expect(flow.calls.filter(c=>c.path==='/v1/questions')).toHaveLength(1);
});
test('TIME03 answer GET still expires at default 10s without generating POST',async({page})=>{
 const flow=await setup(page,`/v1/answers/${ids.answer}`); await page.clock.install();await page.getByLabel('回答标识',{exact:true}).fill(ids.answer);await page.getByRole('button',{name:'查询 / 刷新回答',exact:true}).click();await expect.poll(()=>flow.calls.filter(c=>c.path.startsWith('/v1/answers/')).length).toBe(1);
 await page.clock.fastForward(10001);await expect(page.getByRole('alert')).toContainText('本次未取得回答');expect(flow.calls.filter(c=>c.path==='/v1/questions'||c.path==='/v1/auth/csrf')).toHaveLength(0);flow.release();await expect(page.getByRole('article',{name:'完整证据回答'})).toHaveCount(0);
});
test('TIME04 external page abort clears pending POST and ignores late answer',async({page})=>{
 const flow=await setup(page,'/v1/questions');await ask(page);await expect.poll(()=>flow.calls.filter(c=>c.path==='/v1/questions').length).toBe(1);await page.getByRole('link',{name:'会话与权限',exact:true}).click();await expect(page.getByRole('button',{name:'重新验证会话',exact:true})).toBeVisible();flow.release();await page.waitForTimeout(150);await page.getByRole('link',{name:'引用问答',exact:true}).click();await expect(page.getByRole('heading',{name:'尚未提出问题',exact:true})).toBeVisible();await expect(page.getByRole('article',{name:'完整证据回答'})).toHaveCount(0);expect(flow.calls.filter(c=>c.path==='/v1/questions')).toHaveLength(1);
});
