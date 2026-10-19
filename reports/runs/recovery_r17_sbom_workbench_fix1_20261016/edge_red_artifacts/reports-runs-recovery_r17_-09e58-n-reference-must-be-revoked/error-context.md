# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: reports\runs\recovery_r17_sbom_workbench_fix1_20261016\reviewer_resource_adapter.spec.ts >> independent MUST PURL encoded private version in reference must be revoked
- Location: ..\reports\runs\recovery_r17_sbom_workbench_fix1_20261016\reviewer_resource_adapter.spec.ts:138:57

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText(/已清除私有资产工作区/)
Expected: visible
Timeout: 7000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText(/已清除私有资产工作区/) with timeout 7000ms
  - waiting for getByText(/已清除私有资产工作区/)

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
  - paragraph: PRIVATE INVENTORY / 授权清单 仅显示当前认证租户的资产声明
  - text: 合成 Fixture · 非真实资产
  - button "刷新资产与快照"
  - group: + 导入授权清单 JSON / CSV / CycloneDX / SPDX · 最大 1 MiB
  - region "当前授权资产":
    - paragraph: INVENTORY / 资产目录
    - heading "当前授权资产" [level=2]
    - text: 已读 1 项 按组件包名精确筛选
    - textbox "按组件包名精确筛选":
      - /placeholder: package_name
    - button "筛选资产"
    - list:
      - listitem:
        - 'link "Synthetic fixture · 资产工作台 完整性未知 快照 #2 · 1 个组件声明 实际观察 2026-10-15T18:00:00+08:00 a0000000-0000-4000-8000-000000000001"':
          - /url: "#assets/a0000000-0000-4000-8000-000000000001"
          - strong: Synthetic fixture · 资产工作台
          - text: 完整性未知
          - paragraph: "快照 #2 · 1 个组件声明"
          - text: 实际观察
          - time: 2026-10-15T18:00:00+08:00
          - code: a0000000-0000-4000-8000-000000000001
    - paragraph: 当前查询已到末页；不是所有资产的完整性证明。
  - region "Synthetic fixture · 资产工作台":
    - paragraph: ASSET / 私有资产检视
    - heading "Synthetic fixture · 资产工作台" [level=2]
    - link "返回资产列表":
      - /url: "#assets"
    - code: a0000000-0000-4000-8000-000000000001
    - text: 服务端标记：活跃
    - paragraph: 业务重要性：未知 · 资产声明不等于已核查影响。
    - heading "快照历史" [level=3]
    - button "刷新历史"
    - paragraph: 按服务端快照顺序读取；点击版本后重新获取该固定快照。
    - 'button "查看快照 #2 · 当前 2026-10-15T18:00:00+08:00"':
      - text: "查看快照 #2 · 当前"
      - time: 2026-10-15T18:00:00+08:00
    - 'button "查看快照 #1 · 历史 2026-10-15T18:00:00+08:00"':
      - text: "查看快照 #1 · 历史"
      - time: 2026-10-15T18:00:00+08:00
    - paragraph: CURRENT SNAPSHOT / 当前快照
    - 'heading "快照 #2" [level=3]'
    - text: 完整性未知
    - term: 快照标识
    - definition:
      - code: b0000000-0000-4000-8000-000000000002
    - term: 实际观察时间
    - definition:
      - time: 2026-10-15T18:00:00+08:00
    - term: 系统记录时间
    - definition:
      - time: 2026-10-15T18:01:00+08:00
    - term: 输入类型
    - definition:
      - code: cyclonedx_json
    - term: 输入来源版本
    - definition: 未知 · 当前响应未提供
    - term: 声明范围
    - definition: 未知 · 未声明
    - term: 快照内容摘要
    - definition:
      - code: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      - text: 内容 SHA-256；摘要不证明清单真实性。
    - heading "组件声明" [level=4]
    - text: 共 1 项 · 每页 20 项
    - table "资产组件声明":
      - rowgroup:
        - row "组件 / 生态 版本 / 比较方案 身份与字段定位":
          - columnheader "组件 / 生态"
          - columnheader "版本 / 比较方案"
          - columnheader "身份与字段定位"
      - rowgroup:
        - row "Synthetic fixture component synthetic-demo-package PyPI 版本未知 pep440 purl pkg:pypi/synthetic-demo-package@1.9.0 镜像摘要 未知 · 未声明 依赖路径 synthetic-root 字段位置 /components/0 组件标识 c0000000-0000-4000-8000-000000000001":
          - rowheader "Synthetic fixture component synthetic-demo-package PyPI":
            - text: Synthetic fixture component
            - code: synthetic-demo-package
            - text: PyPI
          - cell "版本未知 pep440":
            - strong: 版本未知
            - code: pep440
          - cell "purl pkg:pypi/synthetic-demo-package@1.9.0 镜像摘要 未知 · 未声明 依赖路径 synthetic-root 字段位置 /components/0 组件标识 c0000000-0000-4000-8000-000000000001":
            - term: purl
            - definition:
              - code: pkg:pypi/synthetic-demo-package@1.9.0
            - term: 镜像摘要
            - definition:
              - code: 未知 · 未声明
            - term: 依赖路径
            - definition: synthetic-root
            - term: 字段位置
            - definition:
              - code: /components/0
            - term: 组件标识
            - definition:
              - code: c0000000-0000-4000-8000-000000000001
    - heading "内部配置声明" [level=4]
    - term:
      - code: trust_remote_code
    - definition:
      - text: 未知 · 未声明
      - code: /configuration/trust_remote_code
    - term:
      - code: authentication_required
    - definition:
      - text: 声明为 false
      - code: /configuration/authentication_required
    - heading "输入通道声明" [level=4]
    - paragraph: 未知 · 未提供声明，不能解释为 false。
    - heading "网络配置声明（不是外部观测）" [level=4]
    - term:
      - code: public_endpoint
    - definition:
      - text: 声明为 false
      - code: /network_exposure/public_endpoint
    - heading "工具权限声明" [level=4]
    - paragraph: 未知 · 未提供声明
    - region "固定快照 SBOM 声明":
      - paragraph: SBOM / FROZEN DECLARATIONS
      - heading "SBOM 历史声明" [level=4]
      - paragraph: 绑定正在查看的快照，不随当前版本覆盖。来源版本未知；适配器与规范版本单列。以下关系与完整性属于输入声明，核验状态未知。
      - term: 来源格式 / 规范版本
      - definition:
        - code: cyclonedx_json / 1.6
      - term: 适配器版本
      - definition:
        - code: r11-sbom-adapter-1
      - term: 原文摘要
      - definition:
        - code: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
      - term: 组合声明摘要
      - definition:
        - code: cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      - term: 展示限制
      - definition: 0 个位置已隐藏；未恢复原 URI、路径或凭据。
      - heading "组件来源" [level=4]
      - text: 1 项 · 每页 20 项
      - list:
        - listitem:
          - strong: library
          - code: synthetic-root
          - code: c0000000-0000-4000-8000-000000000001 · /components/0
          - group: 字段来源与校验摘要
      - heading "依赖与标准关系" [level=4]
      - text: 1 项 · 每页 20 项
      - table "SBOM 原始关系声明":
        - rowgroup:
          - row "来源引用 声明关系 目标引用 / 字段位置":
            - columnheader "来源引用"
            - columnheader "声明关系"
            - columnheader "目标引用 / 字段位置"
        - rowgroup:
          - row "synthetic-root dependsOn pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env /dependencies/0/dependsOn/0":
            - cell "synthetic-root":
              - code: synthetic-root
            - cell "dependsOn":
              - code: dependsOn
            - cell "pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env /dependencies/0/dependsOn/0":
              - code: pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env
              - code: /dependencies/0/dependsOn/0
      - heading "文档完整性声明" [level=4]
      - text: 1 项 · 每页 20 项
      - list:
        - listitem:
          - strong:
            - code: complete
            - text: · 输入声明
          - code: /compositions/0
          - paragraph: "assemblies: 1 个引用"
          - code: synthetic-root
          - paragraph: "dependencies: 0 个引用"
          - paragraph: "vulnerabilities: 0 个引用"
          - paragraph: 此声明不证明授权资产安装范围完整，也不改变影响状态。
      - heading "外部文档声明" [level=4]
      - text: 0 项 · 每页 20 项
      - paragraph: 该文档未提供这类声明；不能据此排除依赖或风险。
      - heading "未映射字段位置" [level=4]
      - text: 1 项 · 每页 20 项
      - list:
        - listitem:
          - code: /metadata/annotations
      - heading "隐藏位置说明" [level=4]
      - text: 0 项 · 每页 20 项
      - paragraph: 该文档未提供这类声明；不能据此排除依赖或风险。
    - paragraph: OBSERVATION / 外部观察
    - heading "外部观察入口尚未接通" [level=3]
    - paragraph: 本页仅展示内部清单声明。外部不可达不能证明软件已修复；不会从导入动作发起第三方扫描。
    - button "查询授权外部观察 · 未就绪" [disabled]
    - paragraph: ASSESSMENT / 条件与证据
    - heading "研判与导出入口尚未接通" [level=3]
    - paragraph: 条件树、四态结果、缺口、冲突和 freshness 需由已验证业务接口返回。当前快照不显示预设判定；旧结果须重新验证。
    - button "提交研判 · 未就绪" [disabled]
    - button "导出证据包 / OpenVEX · 未就绪" [disabled]
  - text: 环境未由服务端标明 版本未由服务端标明
```

# Test source

```ts
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
  141 |   await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(purl,{exact:true})).toBeVisible();
  142 |   await page.getByText(purl,{exact:true}).scrollIntoViewIfNeeded();
  143 |   await page.screenshot({path:info.outputPath(`must-purl-${target}-disclosed.png`),fullPage:true});
  144 |   await page.screenshot({path:info.outputPath(`must-purl-${target}-viewport.png`)});
  145 |   await info.attach('observed-private-version',{body:JSON.stringify({target,purl,displayed:true,expected:'scope fence must reject this unsafe PURL before DOM',sidecarRequested:api.paths.some(path=>path.endsWith('/sbom'))}),contentType:'application/json'});
> 146 |   await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
      |                                              ^ Error: expect(locator).toBeVisible() failed
  147 | });
  148 | 
```