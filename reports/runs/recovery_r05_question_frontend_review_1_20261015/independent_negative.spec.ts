import { randomBytes } from 'node:crypto';
import { test, expect } from 'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/node_modules/@playwright/test/index.mjs';
import { questionAnswerFixture, questionFixtureIds as ids } from 'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/src/features/questions/question.fixture';

async function fixture(page, variant = 'normal') {
 const csrf = randomBytes(32).toString('hex');
 const calls = [];
 await page.route('**/v1/**', async route => {
  const req = route.request(); const path = new URL(req.url()).pathname; calls.push({path, body:req.postData(), key:req.headers()['idempotency-key']});
  const send = (body, status=200) => route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if (path === '/v1/auth/me') return send({user_id:'isolated-independent-reviewer',tenant_id:'isolated-tenant',role:'analyst',permissions:['read:public'],permission_version:1,data_mode:'fixture',csrf_token:csrf});
  if (path === '/v1/auth/csrf') return send({csrf_token:csrf,header_name:'X-CSRF-Token'});
  if (path === '/v1/health/live') return send({status:'live'});
  if (path === '/v1/health/ready') return send({status:'ready',reason:'isolated reviewer fixture',dependencies:{}});
  if (path === '/v1/questions') {
   if (variant === 'late') { await new Promise(resolve=>setTimeout(resolve,12000)); try { return await send(questionAnswerFixture()); } catch { return; } }
   if (variant === 'csrf401') return send({error:{code:'session_expired',retryable:false}},401);
   const answer = questionAnswerFixture();
   if (variant === 'extra') answer.claims[0].tenant_id = 'synthetic-not-allowed';
   if (variant === 'http') answer.citations[0].source_uri = 'http://example.test/legacy';
   if (variant === 'html') { answer.answer_text='<script>window.reviewInjected=true</script>'; answer.claims[0].text='<img src=x onerror="window.reviewInjected=true">'; }
   return send(answer);
  }
  if (path === `/v1/answers/${ids.answer}`) return send({...questionAnswerFixture(),freshness:'unknown'});
  throw new Error(`Unrecognized isolated route: ${path}`);
 });
 await page.goto(`/#questions/${ids.event}`); await expect(page.getByRole('button',{name:'提交问题',exact:true})).toBeVisible();
 return calls;
}
async function ask(page) { await page.getByLabel('你的问题',{exact:true}).fill('独立审查合成问题'); await page.getByRole('button',{name:'提交问题',exact:true}).click(); }

test('NEG01 complete synchronous model answer at 12 seconds must remain observable',async ({page}) => {
 await fixture(page,'late'); await ask(page);
 await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible({timeout:16000});
 await expect(page.getByRole('alert')).toHaveCount(0);
});
test('NEG02 event route change fences late CSRF and old scope',async ({page}) => {
 const calls = await fixture(page); let release; const gate = new Promise(resolve=>release=resolve);
 await page.route('**/v1/auth/csrf', async route=>{ await gate; await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({csrf_token:'isolated-review-csrf',header_name:'X-CSRF-Token'})}); });
 await ask(page); await expect(page.getByText(/正在提交问题并等待完整回答/)).toBeVisible();
 await page.evaluate(other=>{window.location.hash=`#questions/${other}`},ids.other); await expect(page.getByLabel('事件标识',{exact:true})).toHaveValue(ids.other); release();
 await page.waitForTimeout(150); expect(calls.filter(call=>call.path==='/v1/questions')).toHaveLength(0);
 await expect(page.getByRole('article',{name:'完整证据回答'})).toHaveCount(0);
});
test('NEG03 nested DTO extra fields never appear as an answer',async ({page}) => {
 await fixture(page,'extra'); await ask(page); await expect(page.getByRole('alert')).toContainText('提交结果未确认'); await expect(page.getByRole('article',{name:'完整证据回答'})).toHaveCount(0);
});
test('NEG04 HTTP source is text only and saved GET does not borrow event scope',async ({page}) => {
 const calls=await fixture(page,'http'); await ask(page); await expect(page.getByText('来源仅提供HTTP地址，本页不打开该外链')).toBeVisible(); await expect(page.getByRole('link',{name:/打开来源原文/})).toHaveCount(0);
 await page.getByLabel('回答标识',{exact:true}).fill(ids.answer); await page.getByRole('button',{name:'查询 / 刷新回答',exact:true}).click(); await expect(page.getByText(/服务未确认该回答的当前性/)).toBeVisible();
 // This GET is the same answer with a prior confirmed POST binding, so it must retain that exact binding.
 await expect(page.getByRole('link',{name:/检视固定修订证据/})).toHaveAttribute('href',`#events/${ids.event}/evidence/${ids.evidence}/revision/${ids.revision}`); expect(calls.filter(call=>call.path==='/v1/questions')).toHaveLength(1);
 await page.reload(); await page.getByLabel('回答标识',{exact:true}).fill(ids.answer); await page.getByRole('button',{name:'查询 / 刷新回答',exact:true}).click(); await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible(); await expect(page.getByRole('link',{name:/检视固定修订证据/})).toHaveCount(0);
});
test('NEG05 answer and claims render HTML as plain text',async ({page})=>{
 await fixture(page,'html'); await ask(page); await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible(); await expect(page.locator('.question-answer-text')).toContainText('<script>'); await expect(page.locator('.question-claim').first()).toContainText('<img'); await expect(page.locator('.question-answer img, .question-answer script')).toHaveCount(0); expect(await page.evaluate(()=>window.reviewInjected)).toBeUndefined();
});
test('NEG06 source fact and empty structured answer do not invent success facts',async ({page})=>{
 await fixture(page); await page.route('**/v1/questions',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...questionAnswerFixture(),claims:[],citations:[],limitations:[]})})); await ask(page); await expect(page.getByRole('heading',{name:'未提供关键结论',exact:true})).toBeVisible(); await expect(page.getByRole('heading',{name:'没有原文引用',exact:true})).toBeVisible(); await expect(page.getByText(/这不等于已穷尽所有来源/)).toBeVisible();
});
test('NEG07 background moves visibly over time and reduced motion stops transforms',async ({page},testInfo)=>{
 await fixture(page); const moving=page.getByTestId('ambient-motion'); const first=await moving.evaluate(el=>getComputedStyle(el).transform); await page.waitForTimeout(1200); const second=await moving.evaluate(el=>getComputedStyle(el).transform); expect(second).not.toBe(first); await page.screenshot({path:testInfo.outputPath('review-background-normal.png')});
 await page.emulateMedia({reducedMotion:'reduce'}); await expect.poll(()=>moving.evaluate(el=>getComputedStyle(el).animationName)).toBe('none'); const still=await moving.evaluate(el=>getComputedStyle(el).transform); await page.waitForTimeout(350); expect(await moving.evaluate(el=>getComputedStyle(el).transform)).toBe(still);
});
