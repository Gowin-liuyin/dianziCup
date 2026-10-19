# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: reports\runs\recovery_r17_sbom_workbench_review1_fix1_20261016\reviewer_resource_adapter.spec.ts >> independent MUST PURL encoded private version in reference must be revoked
- Location: ..\reports\runs\recovery_r17_sbom_workbench_review1_fix1_20261016\reviewer_resource_adapter.spec.ts:138:57

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env', { exact: true })
Expected: visible
Timeout: 7000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env', { exact: true }) with timeout 7000ms
  - waiting for getByText('pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env', { exact: true })

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
    - link "资料库":
      - /url: "#documents"
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
  - text: 工作台 资产自查 数据模式
  - strong: 合成 / Fixture
- main:
  - paragraph: ASSESSMENT / ASSETS
  - heading "版本与资产" [level=1]
  - paragraph: 在固定资产快照上核查版本、条件与影响。
  - button "刷新状态"
  - alert:
    - paragraph: 资产响应与当前会话范围不一致，已清除私有资产工作区。请重新核对会话与权限。
  - link "核对会话与权限":
    - /url: "#session"
  - text: 环境未由服务端标明 版本未由服务端标明
```

# Test source

```ts
  41  |       if (state.fault === 'projection') sbom.projection_sha256 = '9'.repeat(64);
  42  |       if (state.fault === 'locator') sbom.unmapped_field_locators = ['/metadata/file:~1~1~1independent-private'];
  43  |       if (state.fault === 'hash') sbom.raw_sha256 = 'G'.repeat(64);
  44  |       if (state.fault === 'type') sbom.dependency_edges[0].relationship = 'file:///independent-private';
  45  |       if (state.fault === 'alias') { sbom.dependency_edges[0].target_ref = `redacted-ref:${'1'.repeat(64)}`; sbom.redactions = [{ source_field_locator:'/dependencies/0/ref', reason:'unsafe_uri_or_path', replacement_ref:`redacted-ref:${'1'.repeat(64)}` }]; }
  46  |       body = state.fault === 'key' ? { ...sbom, raw_input:'independent-private-do-not-display' } : sbom;
  47  |       status = state.fault === '401' || state.fault === '403' ? Number(state.fault) : state.status;
  48  |       if (status !== 200) body = { error: { code: status === 503 ? 'inventory_unavailable' : 'permission_denied', retryable: status === 503 } };
  49  |     } else throw new Error(`unexpected independent route ${path}`);
  50  |     await route.fulfill({ status, json:body });
  51  |   });
  52  |   return state;
  53  | }
  54  | async function clearAssertion(page: Page) {
  55  |   await expect(page.getByRole('heading', { name:'快照 #2', exact:true })).toHaveCount(0);
  56  |   await expect(page.getByRole('heading', { name:'当前授权资产', exact:true })).toHaveCount(0);
  57  |   await expect(page.getByRole('heading', { name:'快照历史', exact:true })).toHaveCount(0);
  58  |   await expect(page.getByLabel('选择本地清单', { exact:true })).toHaveCount(0);
  59  |   await expect(page.getByText(sbomFixture().combined_semantic_sha256,{ exact:true })).toHaveCount(0);
  60  |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  61  | }
  62  | 
  63  | const unsafeUris = [
  64  |   'https://example.com/%25252525253A', 'https://example.com/c:/../public',
  65  |   'https://127.1/private', 'https://2130706433/private', 'https://0x7f000001/private',
  66  |   'https://[::ffff:127.0.0.1]/private', 'https://[fc00::1]/private', 'https://[2001:db8::1]/private',
  67  |   'https://192.168.4.2/private', 'https://169.254.169.254/private', 'https://user:secret@example.com/document',
  68  |   'https://example.com/%2566%2569%256c%2565%253A/private', 'https://example.com/%252f%252fprivate',
  69  |   'https://example.com/%2540private', 'https://example.com/a?token=synthetic', 'https://localdomain/private',
  70  | ];
  71  | for (const [index,uri] of unsafeUris.entries()) test(`independent URI ${index+1}: ${index===12 ? 'encoded public path stays on allowed host' : 'dangerous URI removes private DOM'}`, async ({page}) => {
  72  |   const api = await fixture(page); api.uri = uri;
  73  |   await page.goto(`/#assets/${fixtureAssetId}`);
  74  |   if (index===12) {
  75  |     const link=page.getByRole('link',{name:'打开服务器提供的公开文档 ↗'});
  76  |     await expect(link).toHaveAttribute('href',uri);
  77  |     expect(await link.evaluate(element=>new URL((element as HTMLAnchorElement).href).hostname)).toBe('example.com');
  78  |     expect(api.foreign).toEqual([]); return;
  79  |   }
  80  |   await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible(); await clearAssertion(page);
  81  |   expect(await page.locator('a').evaluateAll(links => links.map(link=>link.getAttribute('href')))).not.toContain(uri);
  82  |   expect(api.foreign).toEqual([]);
  83  | });
  84  | for (const fault of ['asset','snapshot','projection','locator','hash','type','alias','key'] as const) test(`independent malformed ${fault}: fence clears private DOM`, async ({page}) => {
  85  |   const api = await fixture(page); api.hold = 'sbom';
  86  |   await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByRole('heading',{name:'快照 #2',exact:true})).toBeVisible();
  87  |   await expect.poll(()=>api.entered).toBe(true); api.fault=fault; api.release();
  88  |   await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible(); await clearAssertion(page);
  89  | });
  90  | for (const target of ['parent','fixed','sbom'] as const) for (const fault of ['401','403','tenant'] as const) test(`independent delayed ${target} ${fault}: revoke whole private workspace`, async ({page}) => {
  91  |   const api=await fixture(page); api.hold=target;
  92  |   await page.goto(`/#assets/${fixtureAssetId}`);
  93  |   if (target==='fixed') { await expect(page.getByRole('heading',{name:'快照 #2',exact:true})).toBeVisible(); await page.getByRole('button',{name:/查看快照 #1 · 历史/}).click(); }
  94  |   await expect.poll(()=>api.entered).toBe(true); api.fault=fault; api.release();
  95  |   if (fault==='401') await expect(page.getByText('会话已失效，私有资产已清除',{exact:true})).toBeVisible();
  96  |   else await expect(page.getByText(/已清除私有资产工作区|当前会话没有此项资产权限/)).toBeVisible();
  97  |   await clearAssertion(page);
  98  | });
  99  | test('independent snapshot PURL cannot enter DOM before sidecar GET',async ({page})=>{
  100 |   const api=await fixture(page); api.snapshotPurl='pkg:generic/independent@https%253A%252F%252Fsecret%253Asecret%2540example.com';
  101 |   await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
  102 |   await clearAssertion(page); expect(api.paths.some(path=>path.endsWith('/sbom'))).toBe(false);
  103 | });
  104 | test('independent 503 retry preserves authorized data and fixture label',async ({page})=>{
  105 |   const api=await fixture(page); api.status=503;
  106 |   await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText('合成 Fixture · 非真实资产',{exact:true})).toBeVisible();
  107 |   await expect(page.getByRole('heading',{name:'快照 #2',exact:true})).toBeVisible();
  108 |   await expect(page.getByText(/当前有效性尚未重新验证/)).toBeVisible();
  109 |   api.status=200; await page.getByRole('button',{name:'重试固定 SBOM 声明',exact:true}).click();
  110 |   await expect(page.getByText(sbomFixture().combined_semantic_sha256,{exact:true})).toBeVisible();
  111 |   expect(api.foreign).toEqual([]);
  112 | });
  113 | test('independent late current SBOM cannot replace selected history',async ({page})=>{
  114 |   const api=await fixture(page); api.hold='sbom'; await page.goto(`/#assets/${fixtureAssetId}`);
  115 |   await expect.poll(()=>api.entered).toBe(true); await page.getByRole('button',{name:/查看快照 #1 · 历史/}).click();
  116 |   await expect(page.getByText(sbomFixture(1).combined_semantic_sha256,{exact:true})).toBeVisible();
  117 |   api.release(); await expect(page.getByText(sbomFixture().combined_semantic_sha256,{exact:true})).toHaveCount(0);
  118 |   await expect(page.getByText(sbomFixture(1).combined_semantic_sha256,{exact:true})).toBeVisible();
  119 | });
  120 | test('independent 390px keyboard and dynamic backdrop both modes',async ({page},info)=>{
  121 |   await fixture(page); await page.setViewportSize({width:390,height:844});
  122 |   await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(sbomFixture().combined_semantic_sha256,{exact:true})).toBeVisible();
  123 |   expect(await page.locator('.ambient-topology').evaluate(element=>getComputedStyle(element).animationName)).not.toBe('none');
  124 |   await page.emulateMedia({reducedMotion:'reduce'});
  125 |   expect(await page.locator('.ambient-topology').evaluate(element=>getComputedStyle(element).animationName)).toBe('none');
  126 |   const history=page.getByRole('button',{name:/查看快照 #1 · 历史/}); await history.focus(); await page.keyboard.press('Enter');
  127 |   await expect(page.getByText(sbomFixture(1).combined_semantic_sha256,{exact:true})).toBeVisible();
  128 |   expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  129 |   await page.screenshot({path:info.outputPath('independent-390-history.png'),fullPage:true});
  130 | });
  131 | test('independent normalized safe public URL renders with no-referrer and no fetch',async ({page},info)=>{
  132 |   const api=await fixture(page); api.uri='https://Example.COM:443/a/../synthetic.spdx.json';
  133 |   await page.goto(`/#assets/${fixtureAssetId}`); const link=page.getByRole('link',{name:'打开服务器提供的公开文档 ↗'});
  134 |   await expect(link).toHaveAttribute('referrerpolicy','no-referrer'); await expect(link).toHaveAttribute('rel','noopener noreferrer');
  135 |   expect(await link.evaluate(element=>(element as HTMLAnchorElement).href)).toBe('https://example.com/synthetic.spdx.json');
  136 |   expect(api.foreign).toEqual([]); await page.screenshot({path:info.outputPath('independent-desktop.png'),fullPage:true});
  137 | });
  138 | for (const target of ['snapshot','reference'] as const) test(`independent MUST PURL encoded private version in ${target} must be revoked`,async ({page},info)=>{
  139 |   const api=await fixture(page); const purl='pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env';
  140 |   if (target==='snapshot') api.snapshotPurl=purl; else api.referencePurl=purl;
> 141 |   await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(purl,{exact:true})).toBeVisible();
      |                                                                                                  ^ Error: expect(locator).toBeVisible() failed
  142 |   await page.getByText(purl,{exact:true}).scrollIntoViewIfNeeded();
  143 |   await page.screenshot({path:info.outputPath(`must-purl-${target}-disclosed.png`),fullPage:true});
  144 |   await page.screenshot({path:info.outputPath(`must-purl-${target}-viewport.png`)});
  145 |   await info.attach('observed-private-version',{body:JSON.stringify({target,purl,displayed:true,expected:'scope fence must reject this unsafe PURL before DOM',sidecarRequested:api.paths.some(path=>path.endsWith('/sbom'))}),contentType:'application/json'});
  146 |   await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
  147 | });
  148 | 
```