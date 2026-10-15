# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: independent_negative.spec.ts >> NEG01 complete synchronous model answer at 12 seconds must remain observable
- Location: ..\..\dianzi\reports\runs\recovery_r05_question_frontend_review_1_20261015\independent_negative.spec.ts:32:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('article', { name: '完整证据回答' })
Expected: visible
Timeout: 16000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('article', { name: '完整证据回答' }) with timeout 16000ms
  - waiting for getByRole('article', { name: '完整证据回答' })

```

```yaml
- link "跳到主要内容":
  - /url: "#main-content"
- complementary:
  - link "安全情报 DEFENSE INTELLIGENCE":
    - /url: "#runtime"
  - navigation "工作台导航":
    - paragraph: 研究
    - link "情报列表":
      - /url: "#events"
    - link "来源监测":
      - /url: "#sources"
    - link "知识图谱":
      - /url: "#graph"
    - link "引用问答":
      - /url: "#questions"
    - link "资产自查":
      - /url: "#assets"
    - paragraph: 协作
    - link "任务轨迹":
      - /url: "#tasks"
    - link "变化与推荐":
      - /url: "#changes"
    - link "证据报告":
      - /url: "#reports"
    - paragraph: 系统
    - link "运行状态":
      - /url: "#runtime"
    - link "会话与权限":
      - /url: "#session"
  - paragraph: 可追溯的事实 清晰的判断边界
  - text: AI 安全知识情报系统
  - code: READ · VERIFY · CONNECT
- banner:
  - text: 工作台 引用问答 数据模式
  - strong: 合成 / Fixture
- main:
  - paragraph: RESEARCH / QUESTIONS
  - heading "证据问答" [level=1]
  - paragraph: 跨文档研究，让每条关键结论都有依据。
  - button "刷新状态"
  - paragraph: LIBRARY / 单事件证据研究
  - paragraph: 基于当前有权查看的事件资料提问。此次只支持资料库单事件，不支持资产研判、历史时间或自动调查。
  - text: 当前会话：合成 / Fixture · 隔离数据
  - region "提出问题":
    - paragraph: ASK / 从证据开始
    - heading "提出问题" [level=2]
    - text: library
    - form "单事件问答":
      - text: 事件标识
      - textbox "事件标识" [disabled]:
        - /placeholder: 一个完整事件UUID
        - text: 00000000-0000-4000-8000-000000000001
      - text: 你的问题
      - textbox "你的问题" [disabled]:
        - /placeholder: 描述你需要核对的事实、机制或修复依据
        - text: 独立审查合成问题
      - paragraph: 8 / 4096 字符。未知与缺失会明确显示，页面不会补造答案。
      - button "提交问题" [disabled]
    - heading "本轮请求已冻结" [level=3]
    - term: 事件
    - definition:
      - code: 00000000-0000-4000-8000-000000000001
    - term: 请求键
    - definition:
      - code: question-ui-2b1a5781-a3c3-41d6-9ab0-fee893089297
    - paragraph: 结果未知时保留相同问题、事件和请求键。原样重试沿用同一业务请求；开始新问题后首次提交才生成新键。
    - button "原样重试本轮"
    - button "开始新问题"
    - form "查询已保存回答":
      - heading "读取已保存回答" [level=3]
      - text: 回答标识
      - textbox "回答标识":
        - /placeholder: 保存的answer UUID
      - button "查询 / 刷新回答" [disabled]
      - paragraph: 服务端重新检查所有权与当前性。问题与回答正文只在本页内存中保留；返回后可凭回答标识查询。
  - region "回答与证据":
    - paragraph: ANSWER / 结论与依据
    - heading "回答与证据" [level=2]
    - text: 完整完成后显示
    - alert:
      - paragraph: 提交结果未确认，请保留本轮问题与请求键原样重试；网络或格式错误不能解释为未提交。
  - text: 环境未由服务端标明 版本未由服务端标明
```

# Test source

```ts
  1  | import { randomBytes } from 'node:crypto';
  2  | import { test, expect } from 'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/node_modules/@playwright/test/index.mjs';
  3  | import { questionAnswerFixture, questionFixtureIds as ids } from 'D:/dianzi-wt-r05-question-frontend-independent-review-1/frontend/src/features/questions/question.fixture';
  4  | 
  5  | async function fixture(page, variant = 'normal') {
  6  |  const csrf = randomBytes(32).toString('hex');
  7  |  const calls = [];
  8  |  await page.route('**/v1/**', async route => {
  9  |   const req = route.request(); const path = new URL(req.url()).pathname; calls.push({path, body:req.postData(), key:req.headers()['idempotency-key']});
  10 |   const send = (body, status=200) => route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  11 |   if (path === '/v1/auth/me') return send({user_id:'isolated-independent-reviewer',tenant_id:'isolated-tenant',role:'analyst',permissions:['read:public'],permission_version:1,data_mode:'fixture',csrf_token:csrf});
  12 |   if (path === '/v1/auth/csrf') return send({csrf_token:csrf,header_name:'X-CSRF-Token'});
  13 |   if (path === '/v1/health/live') return send({status:'live'});
  14 |   if (path === '/v1/health/ready') return send({status:'ready',reason:'isolated reviewer fixture',dependencies:{}});
  15 |   if (path === '/v1/questions') {
  16 |    if (variant === 'late') { await new Promise(resolve=>setTimeout(resolve,12000)); try { return await send(questionAnswerFixture()); } catch { return; } }
  17 |    if (variant === 'csrf401') return send({error:{code:'session_expired',retryable:false}},401);
  18 |    const answer = questionAnswerFixture();
  19 |    if (variant === 'extra') answer.claims[0].tenant_id = 'synthetic-not-allowed';
  20 |    if (variant === 'http') answer.citations[0].source_uri = 'http://example.test/legacy';
  21 |    if (variant === 'html') { answer.answer_text='<script>window.reviewInjected=true</script>'; answer.claims[0].text='<img src=x onerror="window.reviewInjected=true">'; }
  22 |    return send(answer);
  23 |   }
  24 |   if (path === `/v1/answers/${ids.answer}`) return send({...questionAnswerFixture(),freshness:'unknown'});
  25 |   throw new Error(`Unrecognized isolated route: ${path}`);
  26 |  });
  27 |  await page.goto(`/#questions/${ids.event}`); await expect(page.getByRole('button',{name:'提交问题',exact:true})).toBeVisible();
  28 |  return calls;
  29 | }
  30 | async function ask(page) { await page.getByLabel('你的问题',{exact:true}).fill('独立审查合成问题'); await page.getByRole('button',{name:'提交问题',exact:true}).click(); }
  31 | 
  32 | test('NEG01 complete synchronous model answer at 12 seconds must remain observable',async ({page}) => {
  33 |  await fixture(page,'late'); await ask(page);
> 34 |  await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible({timeout:16000});
     |                                                          ^ Error: expect(locator).toBeVisible() failed
  35 |  await expect(page.getByRole('alert')).toHaveCount(0);
  36 | });
  37 | test('NEG02 event route change fences late CSRF and old scope',async ({page}) => {
  38 |  const calls = await fixture(page); let release; const gate = new Promise(resolve=>release=resolve);
  39 |  await page.route('**/v1/auth/csrf', async route=>{ await gate; await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({csrf_token:'isolated-review-csrf',header_name:'X-CSRF-Token'})}); });
  40 |  await ask(page); await expect(page.getByText(/正在提交问题并等待完整回答/)).toBeVisible();
  41 |  await page.evaluate(other=>{window.location.hash=`#questions/${other}`},ids.other); await expect(page.getByLabel('事件标识',{exact:true})).toHaveValue(ids.other); release();
  42 |  await page.waitForTimeout(150); expect(calls.filter(call=>call.path==='/v1/questions')).toHaveLength(0);
  43 |  await expect(page.getByRole('article',{name:'完整证据回答'})).toHaveCount(0);
  44 | });
  45 | test('NEG03 nested DTO extra fields never appear as an answer',async ({page}) => {
  46 |  await fixture(page,'extra'); await ask(page); await expect(page.getByRole('alert')).toContainText('提交结果未确认'); await expect(page.getByRole('article',{name:'完整证据回答'})).toHaveCount(0);
  47 | });
  48 | test('NEG04 HTTP source is text only and saved GET does not borrow event scope',async ({page}) => {
  49 |  const calls=await fixture(page,'http'); await ask(page); await expect(page.getByText('来源仅提供HTTP地址，本页不打开该外链')).toBeVisible(); await expect(page.getByRole('link',{name:/打开来源原文/})).toHaveCount(0);
  50 |  await page.getByLabel('回答标识',{exact:true}).fill(ids.answer); await page.getByRole('button',{name:'查询 / 刷新回答',exact:true}).click(); await expect(page.getByText(/服务未确认该回答的当前性/)).toBeVisible();
  51 |  // This GET is the same answer with a prior confirmed POST binding, so it must retain that exact binding.
  52 |  await expect(page.getByRole('link',{name:/检视固定修订证据/})).toHaveAttribute('href',`#events/${ids.event}/evidence/${ids.evidence}/revision/${ids.revision}`); expect(calls.filter(call=>call.path==='/v1/questions')).toHaveLength(1);
  53 |  await page.reload(); await page.getByLabel('回答标识',{exact:true}).fill(ids.answer); await page.getByRole('button',{name:'查询 / 刷新回答',exact:true}).click(); await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible(); await expect(page.getByRole('link',{name:/检视固定修订证据/})).toHaveCount(0);
  54 | });
  55 | test('NEG05 answer and claims render HTML as plain text',async ({page})=>{
  56 |  await fixture(page,'html'); await ask(page); await expect(page.getByRole('article',{name:'完整证据回答'})).toBeVisible(); await expect(page.locator('.question-answer-text')).toContainText('<script>'); await expect(page.locator('.question-claim').first()).toContainText('<img'); await expect(page.locator('.question-answer img, .question-answer script')).toHaveCount(0); expect(await page.evaluate(()=>window.reviewInjected)).toBeUndefined();
  57 | });
  58 | test('NEG06 source fact and empty structured answer do not invent success facts',async ({page})=>{
  59 |  await fixture(page); await page.route('**/v1/questions',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...questionAnswerFixture(),claims:[],citations:[],limitations:[]})})); await ask(page); await expect(page.getByRole('heading',{name:'未提供关键结论',exact:true})).toBeVisible(); await expect(page.getByRole('heading',{name:'没有原文引用',exact:true})).toBeVisible(); await expect(page.getByText(/这不等于已穷尽所有来源/)).toBeVisible();
  60 | });
  61 | test('NEG07 background moves visibly over time and reduced motion stops transforms',async ({page},testInfo)=>{
  62 |  await fixture(page); const moving=page.getByTestId('ambient-motion'); const first=await moving.evaluate(el=>getComputedStyle(el).transform); await page.waitForTimeout(1200); const second=await moving.evaluate(el=>getComputedStyle(el).transform); expect(second).not.toBe(first); await page.screenshot({path:testInfo.outputPath('review-background-normal.png')});
  63 |  await page.emulateMedia({reducedMotion:'reduce'}); await expect.poll(()=>moving.evaluate(el=>getComputedStyle(el).animationName)).toBe('none'); const still=await moving.evaluate(el=>getComputedStyle(el).transform); await page.waitForTimeout(350); expect(await moving.evaluate(el=>getComputedStyle(el).transform)).toBe(still);
  64 | });
  65 | 
```