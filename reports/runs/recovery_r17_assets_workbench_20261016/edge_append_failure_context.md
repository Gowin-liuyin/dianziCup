# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_assets_fixture.spec.ts >> synthetic Edge assets 03: JSON original bytes import 201 and server UUID deep-link refresh
- Location: e2e\r17_assets_fixture.spec.ts:47:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('导入成功 · 服务端已保存快照', { exact: true })
Expected: visible
Error: strict mode violation: getByText('导入成功 · 服务端已保存快照', { exact: true }) resolved to 2 elements:
    1) <strong>导入成功 · 服务端已保存快照</strong> aka getByRole('status').filter({ hasText: '导入成功 · 服务端已保存快照快照 #2 · b0000000-0000-4000-8000-000000000002。当前内容请以重新读取的资产详情为准。' }).getByRole('strong')
    2) <strong>导入成功 · 服务端已保存快照</strong> aka locator('details').getByText('导入成功 · 服务端已保存快照')

Call log:
  - Expect "toBeVisible" getByText('导入成功 · 服务端已保存快照', { exact: true }) with timeout 10000ms
  - waiting for getByText('导入成功 · 服务端已保存快照', { exact: true })

```

# Page snapshot

```yaml
- generic [ref=f1e3]:
  - link "跳到主要内容" [ref=f1e4] [cursor=pointer]:
    - /url: "#main-content"
  - complementary [ref=f1e5]:
    - link "安全情报 DEFENSE INTELLIGENCE" [ref=f1e6] [cursor=pointer]:
      - /url: "#runtime"
      - generic [aria-hidden] [ref=f1e7]: DI
      - generic [ref=f1e9]:
        - text: 安全情报
        - generic [ref=f1e10]: DEFENSE INTELLIGENCE
    - navigation "工作台导航" [ref=f1e11]:
      - generic [ref=f1e12]:
        - paragraph [ref=f1e13]: 研究
        - link "情报列表" [ref=f1e14] [cursor=pointer]:
          - /url: "#events"
          - generic [aria-hidden] [ref=f1e15]: ≡
          - text: 情报列表
        - link "来源监测" [ref=f1e16] [cursor=pointer]:
          - /url: "#sources"
          - generic [aria-hidden] [ref=f1e17]: ◉
          - text: 来源监测
        - link "资料库" [ref=f1e18] [cursor=pointer]:
          - /url: "#documents"
          - generic [aria-hidden] [ref=f1e19]: ▤
          - text: 资料库
        - link "知识图谱" [ref=f1e20] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=f1e21]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=f1e22] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=f1e23]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=f1e24] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=f1e25]: ⬡
          - text: 资产自查
      - generic [ref=f1e26]:
        - paragraph [ref=f1e27]: 协作
        - link "任务轨迹" [ref=f1e28] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=f1e29]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=f1e30] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=f1e31]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=f1e32] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=f1e33]: ▤
          - text: 证据报告
      - generic [ref=f1e34]:
        - paragraph [ref=f1e35]: 系统
        - link "运行状态" [ref=f1e36] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=f1e37]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=f1e38] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=f1e39]: ◎
          - text: 会话与权限
    - generic [ref=f1e40]:
      - paragraph [ref=f1e41]: 可追溯的事实清晰的判断边界
      - text: AI 安全知识情报系统
      - code [ref=f1e42]: READ · VERIFY · CONNECT
  - generic [ref=f1e43]:
    - banner [ref=f1e44]:
      - generic [ref=f1e45]:
        - generic [aria-hidden] [ref=f1e46]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=f1e47]: /
        - text: 资产自查
      - generic [ref=f1e48]:
        - text: 数据模式
        - strong [ref=f1e49]: 合成 / Fixture
    - main [ref=f1e50]:
      - generic [ref=f1e51]:
        - generic [ref=f1e52]:
          - paragraph [ref=f1e53]: ASSESSMENT / ASSETS
          - heading "版本与资产" [level=1] [ref=f1e54]: 版本与资产_
          - paragraph [ref=f1e55]: 在固定资产快照上核查版本、条件与影响。
        - button "刷新状态" [ref=f1e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=f1e57]: ↻
          - text: 刷新状态
      - generic [ref=f1e58]:
        - generic [ref=f1e59]:
          - paragraph [ref=f1e60]:
            - generic [ref=f1e61]: PRIVATE INVENTORY / 授权清单
            - text: 仅显示当前认证租户的资产声明
          - generic [ref=f1e62]: 合成 Fixture · 非真实资产
          - button "刷新资产与快照" [ref=f1e63] [cursor=pointer]
        - status [ref=f1e64]:
          - strong [ref=f1e65]: 导入成功 · 服务端已保存快照
          - paragraph [ref=f1e66]:
            - text: "快照 #2 ·"
            - code [ref=f1e67]: b0000000-0000-4000-8000-000000000002
            - text: 。当前内容请以重新读取的资产详情为准。
        - group [ref=f1e68]:
          - generic "− 导入授权清单 JSON v1 / CSV · 最大 1 MiB" [ref=f1e69] [cursor=pointer]:
            - text: − 导入授权清单
            - generic [ref=f1e70]: JSON v1 / CSV · 最大 1 MiB
          - generic [ref=f1e71]:
            - paragraph [ref=f1e72]: 仅导入已获授权的资产。原文件保留在浏览器与私有后端，页面不展示原文件内容。完整性属于输入声明，不代表独立核验。
            - status [ref=f1e73]:
              - strong [ref=f1e74]: 导入成功 · 服务端已保存快照
              - paragraph [ref=f1e75]:
                - text: "快照 #2 ·"
                - code [ref=f1e76]: b0000000-0000-4000-8000-000000000002
              - link "查看导入资产" [ref=f1e77] [cursor=pointer]:
                - /url: "#assets/a0000000-0000-4000-8000-000000000001"
            - generic [ref=f1e78]:
              - group [ref=f1e79]:
                - generic [ref=f1e80]:
                  - generic [ref=f1e81]: 清单格式
                  - combobox "清单格式" [ref=f1e82]:
                    - option "JSON manifest v1" [selected]
                    - option "CSV 组件清单"
                - generic [ref=f1e83]:
                  - generic [ref=f1e84]: 选择本地清单
                  - button "选择本地清单" [ref=f1e85]
                - generic [ref=f1e86]:
                  - checkbox "追加到当前所选资产（名称保持一致）" [checked] [ref=f1e87]
                  - text: 追加到当前所选资产（名称保持一致）
                - generic [ref=f1e88]:
                  - generic [ref=f1e89]: 资产名称
                  - textbox "资产名称" [disabled] [ref=f1e90]: Synthetic fixture · 资产工作台
                - generic [ref=f1e91]:
                  - generic [ref=f1e92]: 输入来源版本
                  - textbox "输入来源版本" [ref=f1e93]:
                    - /placeholder: 填写实际清单版本
                    - text: synthetic-append-v2
                - generic [ref=f1e94]:
                  - generic [ref=f1e95]: 实际观察时间（含时区）
                  - textbox "实际观察时间（含时区）" [ref=f1e96]:
                    - /placeholder: 2026-10-15T18:00:00+08:00
                    - text: 2026-10-15T11:00:00Z
                  - paragraph [ref=f1e97]: 不要用上传时间代替观察时间；时间未知时，本接口暂不支持提交。
              - paragraph [ref=f1e98]: "JSON 需包含 format_version: 1、components；组件生态、版本、配置与声明范围由原文件提供。CycloneDX / SPDX 尚不支持。"
              - button "提交授权清单" [disabled] [ref=f1e99]
        - generic [ref=f1e100]:
          - region [ref=f1e101]:
            - generic [ref=f1e102]:
              - generic [ref=f1e103]:
                - paragraph [ref=f1e104]: INVENTORY / 资产目录
                - heading "当前授权资产" [level=2] [ref=f1e105]
              - generic [ref=f1e106]: 已读 1 项
            - generic [ref=f1e107]:
              - generic [ref=f1e108]: 按组件包名精确筛选
              - generic [ref=f1e109]:
                - textbox "按组件包名精确筛选" [ref=f1e110]:
                  - /placeholder: package_name
                - button "筛选资产" [ref=f1e111] [cursor=pointer]
            - list [ref=f1e112]:
              - listitem [ref=f1e113]:
                - 'link "Synthetic fixture · 资产工作台 部分清单 快照 #2 · 1 个组件声明 实际观察 2026-10-15T18:00:00+08:00 a0000000-0000-4000-8000-000000000001" [ref=f1e114] [cursor=pointer]':
                  - /url: "#assets/a0000000-0000-4000-8000-000000000001"
                  - generic [ref=f1e115]:
                    - strong [ref=f1e116]: Synthetic fixture · 资产工作台
                    - generic [aria-hidden] [ref=f1e117]: ↗
                  - generic [ref=f1e118]: 部分清单
                  - paragraph [ref=f1e119]: "快照 #2 · 1 个组件声明"
                  - generic [ref=f1e120]:
                    - text: 实际观察
                    - time [ref=f1e121]: 2026-10-15T18:00:00+08:00
                  - code [ref=f1e122]: a0000000-0000-4000-8000-000000000001
            - paragraph [ref=f1e123]: 当前查询已到末页；不是所有资产的完整性证明。
          - region [ref=f1e124]:
            - generic [ref=f1e125]:
              - generic [ref=f1e126]:
                - paragraph [ref=f1e127]: ASSET / 私有资产检视
                - heading "Synthetic fixture · 资产工作台" [level=2] [ref=f1e128]
              - link "返回资产列表" [ref=f1e129] [cursor=pointer]:
                - /url: "#assets"
            - generic [ref=f1e130]:
              - code [ref=f1e131]: a0000000-0000-4000-8000-000000000001
              - generic [ref=f1e132]: 服务端标记：活跃
              - paragraph [ref=f1e133]: 业务重要性：未知 · 资产声明不等于已核查影响。
            - generic [ref=f1e134]:
              - generic [ref=f1e135]:
                - heading "快照历史" [level=3] [ref=f1e136]
                - button "刷新历史" [ref=f1e137] [cursor=pointer]
              - paragraph [ref=f1e138]: 按服务端快照顺序读取；点击版本后重新获取该固定快照。
              - 'button "查看快照 #2 · 当前 2026-10-15T18:00:00+08:00" [ref=f1e140] [cursor=pointer]':
                - generic [ref=f1e141]: "查看快照 #2 · 当前"
                - time [ref=f1e142]: 2026-10-15T18:00:00+08:00
              - button "加载更多历史" [ref=f1e143] [cursor=pointer]
            - generic [ref=f1e144]:
              - generic [ref=f1e145]:
                - generic [ref=f1e146]:
                  - paragraph [ref=f1e147]: CURRENT SNAPSHOT / 当前快照
                  - 'heading "快照 #2" [level=3] [ref=f1e148]'
                - generic [ref=f1e149]: 部分清单
              - generic [ref=f1e150]:
                - term [ref=f1e151]: 快照标识
                - definition [ref=f1e152]:
                  - code [ref=f1e153]: b0000000-0000-4000-8000-000000000002
                - term [ref=f1e154]: 实际观察时间
                - definition [ref=f1e155]:
                  - time [ref=f1e156]: 2026-10-15T18:00:00+08:00
                - term [ref=f1e157]: 系统记录时间
                - definition [ref=f1e158]:
                  - time [ref=f1e159]: 2026-10-15T18:01:00+08:00
                - term [ref=f1e160]: 输入类型
                - definition [ref=f1e161]:
                  - code [ref=f1e162]: json_manifest_v1
                - term [ref=f1e163]: 输入来源版本
                - definition [ref=f1e164]: 未知 · 当前响应未提供
                - term [ref=f1e165]: 声明范围
                - definition [ref=f1e166]: Synthetic fixture runtime
                - term [ref=f1e167]: 快照内容摘要
                - definition [ref=f1e168]:
                  - code [ref=f1e169]: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
                  - generic [ref=f1e170]: 内容 SHA-256；摘要不证明清单真实性。
              - generic [ref=f1e171]:
                - generic [ref=f1e172]:
                  - heading "组件声明" [level=4] [ref=f1e173]
                  - generic [ref=f1e174]: 共 1 项 · 每页 20 项
                - table "资产组件声明" [ref=f1e176]:
                  - rowgroup [ref=f1e177]:
                    - row [ref=f1e178]:
                      - columnheader "组件 / 生态" [ref=f1e179]
                      - columnheader "版本 / 比较方案" [ref=f1e180]
                      - columnheader "身份与字段定位" [ref=f1e181]
                  - rowgroup [ref=f1e182]:
                    - row [ref=f1e183]:
                      - rowheader "Synthetic fixture component synthetic-demo-package PyPI" [ref=f1e184]:
                        - text: Synthetic fixture component
                        - code [ref=f1e185]: synthetic-demo-package
                        - generic [ref=f1e186]: PyPI
                      - cell [ref=f1e187]:
                        - strong [ref=f1e188]: 版本未知
                        - code [ref=f1e189]: pep440
                      - cell [ref=f1e190]:
                        - generic [ref=f1e191]:
                          - term [ref=f1e192]: purl
                          - definition [ref=f1e193]:
                            - code [ref=f1e194]: pkg:pypi/synthetic-demo-package@1.9.0
                          - term [ref=f1e195]: 镜像摘要
                          - definition [ref=f1e196]:
                            - code [ref=f1e197]: 未知 · 未声明
                          - term [ref=f1e198]: 依赖路径
                          - definition [ref=f1e199]: synthetic-root
                          - term [ref=f1e200]: 字段位置
                          - definition [ref=f1e201]:
                            - code [ref=f1e202]: /components/0
                          - term [ref=f1e203]: 组件标识
                          - definition [ref=f1e204]:
                            - code [ref=f1e205]: c0000000-0000-4000-8000-000000000001
              - generic [ref=f1e206]:
                - heading "内部配置声明" [level=4] [ref=f1e207]
                - generic [ref=f1e208]:
                  - generic [ref=f1e209]:
                    - term [ref=f1e210]:
                      - code [ref=f1e211]: trust_remote_code
                    - definition [ref=f1e212]:
                      - text: 未知 · 未声明
                      - code [ref=f1e213]: /configuration/trust_remote_code
                  - generic [ref=f1e214]:
                    - term [ref=f1e215]:
                      - code [ref=f1e216]: authentication_required
                    - definition [ref=f1e217]:
                      - text: 声明为 false
                      - code [ref=f1e218]: /configuration/authentication_required
              - generic [ref=f1e219]:
                - heading "输入通道声明" [level=4] [ref=f1e220]
                - paragraph [ref=f1e221]: 未知 · 未提供声明，不能解释为 false。
              - generic [ref=f1e222]:
                - heading "网络配置声明（不是外部观测）" [level=4] [ref=f1e223]
                - generic [ref=f1e225]:
                  - term [ref=f1e226]:
                    - code [ref=f1e227]: public_endpoint
                  - definition [ref=f1e228]:
                    - text: 声明为 false
                    - code [ref=f1e229]: /network_exposure/public_endpoint
              - generic [ref=f1e230]:
                - heading "工具权限声明" [level=4] [ref=f1e231]
                - paragraph [ref=f1e232]: 未知 · 未提供声明
            - generic [ref=f1e233]:
              - paragraph [ref=f1e234]: OBSERVATION / 外部观察
              - heading "外部观察入口尚未接通" [level=3] [ref=f1e235]
              - paragraph [ref=f1e236]: 本页仅展示内部清单声明。外部不可达不能证明软件已修复；不会从导入动作发起第三方扫描。
              - button "查询授权外部观察 · 未就绪" [disabled] [ref=f1e237]
            - generic [ref=f1e238]:
              - paragraph [ref=f1e239]: ASSESSMENT / 条件与证据
              - heading "研判与导出入口尚未接通" [level=3] [ref=f1e240]
              - paragraph [ref=f1e241]: 条件树、四态结果、缺口、冲突和 freshness 需由已验证业务接口返回。当前快照不显示预设判定；旧结果须重新验证。
              - generic [ref=f1e242]:
                - button "提交研判 · 未就绪" [disabled] [ref=f1e243]
                - button "导出证据包 / OpenVEX · 未就绪" [disabled] [ref=f1e244]
      - generic [ref=f1e245]:
        - generic [ref=f1e246]: 环境未由服务端标明
        - generic [ref=f1e247]: 版本未由服务端标明
```

# Test source

```ts
  1   | import { expect, test, type Locator, type Page } from "@playwright/test";
  2   | import { assetFixture, fixtureAssetId } from "../src/features/assets/synthetic-fixtures";
  3   | import { installAssetsFixture } from "./r17-assets.fixture";
  4   | 
  5   | async function mouseClick(page: Page, target: Locator) {
  6   |   await target.scrollIntoViewIfNeeded();
  7   |   const box = await target.boundingBox();
  8   |   if (box === null) throw new Error("fixture interaction target is not visible");
  9   |   await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  10  | }
  11  | async function fillImport(page: Page, raw: string, format = "json_manifest_v1") {
  12  |   await mouseClick(page, page.locator(".asset-import-panel summary"));
  13  |   await page.getByLabel("清单格式", { exact: true }).selectOption(format);
  14  |   await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: format === "json_manifest_v1" ? "synthetic-fixture.json" : "synthetic-fixture.csv", mimeType: format === "json_manifest_v1" ? "application/json" : "text/csv", buffer: Buffer.from(raw) });
  15  |   await page.getByLabel("资产名称", { exact: true }).fill("Synthetic fixture · 资产工作台");
  16  |   await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-v1");
  17  |   await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-15T10:00:00Z");
  18  |   await expect(page.getByRole("button", { name: "提交授权清单", exact: true })).toBeEnabled();
  19  | }
  20  | 
  21  | test("synthetic Edge assets 01: loading and empty remain distinguishable", async ({ page }, info) => {
  22  |   const api = await installAssetsFixture(page); api.hold = true; api.empty = true;
  23  |   await page.goto("/#assets");
  24  |   await expect(page.getByText("正在读取资产页…", { exact: true })).toBeVisible();
  25  |   await expect(page.getByRole("button", { name: "刷新资产与快照" })).toBeDisabled();
  26  |   await page.screenshot({ path: info.outputPath("synthetic-loading.png") });
  27  |   api.hold = false; api.release();
  28  |   await expect(page.getByText("尚无可见资产清单", { exact: true })).toBeVisible();
  29  |   await expect(page.getByText(/空查询不等于零影响或安全/)).toBeVisible();
  30  |   await mouseClick(page, page.locator(".asset-import-panel summary"));
  31  |   await expect(page.getByLabel("选择本地清单")).toBeVisible();
  32  |   await page.screenshot({ path: info.outputPath("synthetic-empty-import.png") });
  33  | });
  34  | 
  35  | test("synthetic Edge assets 02: 403 clears catalog and viewer gate makes no private request", async ({ page }, info) => {
  36  |   const api = await installAssetsFixture(page);
  37  |   await page.goto("/#assets"); await expect(page.getByRole("link", { name: new RegExp(assetFixture().display_name) })).toBeVisible();
  38  |   api.assetStatus = 403; await mouseClick(page, page.getByRole("button", { name: "刷新资产与快照" }));
  39  |   await expect(page.getByText(/当前会话没有此项资产权限/)).toBeVisible();
  40  |   await expect(page.getByText(assetFixture().display_name, { exact: true })).toHaveCount(0);
  41  |   await page.screenshot({ path: info.outputPath("synthetic-403.png") });
  42  |   api.permissions = ["read:public"]; api.paths.length = 0; await page.reload();
  43  |   await expect(page.getByText("当前会话无资产读取权限", { exact: true })).toBeVisible();
  44  |   expect(api.paths.some((path) => path.includes("/v1/assets"))).toBe(false);
  45  | });
  46  | 
  47  | test("synthetic Edge assets 03: JSON original bytes import 201 and server UUID deep-link refresh", async ({ page }, info) => {
  48  |   const api = await installAssetsFixture(page); api.empty = true;
  49  |   await page.goto("/#assets"); await expect(page.getByText("尚无可见资产清单", { exact: true })).toBeVisible();
  50  |   const raw = ' {"format_version":1,"components":[],"inventory_completeness":"unknown"}\r\n';
  51  |   await fillImport(page, raw); api.empty = false;
  52  |   await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
  53  |   await expect(page.getByText("导入成功 · 服务端已保存快照", { exact: true })).toBeVisible();
  54  |   await expect(page).toHaveURL(new RegExp(`#assets/${fixtureAssetId}$`));
  55  |   expect(api.uploads).toEqual([Buffer.from(raw)]);
  56  |   expect(api.writeKeys[0]).toMatch(/^[0-9a-f-]{36}$/);
  57  |   await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
  58  |   await page.evaluate(() => window.scrollTo(0, 0));
  59  |   await page.screenshot({ path: info.outputPath("synthetic-import-success.png"), fullPage: true });
  60  |   await page.reload(); await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
  61  |   await mouseClick(page, page.locator(".asset-import-panel summary"));
  62  |   await mouseClick(page, page.getByLabel("追加到当前所选资产（名称保持一致）", { exact: true }));
  63  |   await expect(page.getByLabel("资产名称", { exact: true })).toBeDisabled();
  64  |   await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: "synthetic-append.json", mimeType: "application/json", buffer: Buffer.from(raw) });
  65  |   await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-append-v2");
  66  |   await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-15T11:00:00Z");
  67  |   await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
> 68  |   await expect(page.getByText("导入成功 · 服务端已保存快照", { exact: true })).toBeVisible();
      |                                                                    ^ Error: expect(locator).toBeVisible() failed
  69  |   expect(api.appendAssetIds).toEqual([fixtureAssetId]);
  70  |   await mouseClick(page, page.getByRole("link", { name: "返回资产列表", exact: true }));
  71  |   await expect(page).toHaveURL(/#assets$/); await page.goBack();
  72  |   await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
  73  | });
  74  | 
  75  | test("synthetic Edge assets 04: history pages fixed snapshot partial failure and retry at 390px", async ({ page }, info) => {
  76  |   const api = await installAssetsFixture(page); api.historyStatus = 503;
  77  |   await page.setViewportSize({ width: 390, height: 844 }); await page.emulateMedia({ reducedMotion: "reduce" });
  78  |   await page.goto(`/#assets/${fixtureAssetId}`);
  79  |   await expect(page.getByRole("heading", { name: "快照 #2", exact: true })).toBeVisible();
  80  |   await expect(page.getByRole("button", { name: "重试历史页", exact: true })).toBeVisible();
  81  |   api.historyStatus = 200; await mouseClick(page, page.getByRole("button", { name: "重试历史页", exact: true }));
  82  |   await mouseClick(page, page.getByRole("button", { name: "加载更多历史", exact: true }));
  83  |   await mouseClick(page, page.getByRole("button", { name: /查看快照 #1 · 历史/ }));
  84  |   await expect(page.getByText(/正在查看历史快照/)).toBeVisible();
  85  |   await expect(page.getByText("1.9.0", { exact: true })).toBeVisible();
  86  |   await expect(page.getByText("pkg:pypi/synthetic-demo-package@1.9.0", { exact: true })).toBeVisible();
  87  |   await expect(page.getByText("/components/0", { exact: true })).toBeVisible();
  88  |   await page.screenshot({ path: info.outputPath("synthetic-history-390.png"), fullPage: false });
  89  |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  90  |   expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  91  |   const targets = await page.locator(".asset-workspace button:not(:disabled), .asset-workspace summary, .asset-workspace .asset-catalog-link").evaluateAll((elements) => elements.filter((element) => element.getClientRects().length > 0).map((element) => element.getBoundingClientRect().height));
  92  |   expect(targets.every((height) => height >= 44)).toBe(true);
  93  |   await mouseClick(page, page.getByRole("button", { name: "查看当前快照", exact: true }));
  94  |   await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
  95  |   await expect(page.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪" })).toBeDisabled();
  96  | });
  97  | 
  98  | test("synthetic Edge assets 05: CSV errors and uncertain import reuse the same key and bytes", async ({ page }, info) => {
  99  |   const api = await installAssetsFixture(page); api.importStatus = 422;
  100 |   await page.goto("/#assets"); await expect(page.locator(".asset-import-panel summary")).toBeVisible();
  101 |   const raw = "package_name,ecosystem,version\r\nsynthetic-demo-package,PyPI,1.9.0\r\n";
  102 |   await fillImport(page, raw, "csv_components_v1");
  103 |   await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
  104 |   await expect(page.getByText(/CSV 表头与映射列名不一致/)).toBeVisible();
  105 |   await page.screenshot({ path: info.outputPath("synthetic-csv-field-error.png") });
  106 |   await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-v2");
  107 |   api.importStatus = 503; await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
  108 |   await expect(page.getByRole("button", { name: "重试相同导入", exact: true })).toBeVisible();
  109 |   api.importStatus = 201; await mouseClick(page, page.getByRole("button", { name: "重试相同导入", exact: true }));
  110 |   await expect(page.getByText("导入成功 · 服务端已保存快照", { exact: true })).toBeVisible();
  111 |   expect(api.writeKeys[1]).toBe(api.writeKeys[2]); expect(api.writeKeys[0]).not.toBe(api.writeKeys[1]);
  112 |   expect(api.uploads.every((bytes) => bytes.equals(Buffer.from(raw)))).toBe(true);
  113 | });
  114 | 
  115 | test("synthetic Edge assets 06: paging logout expired session and cross-tenant late response stay isolated", async ({ page }, info) => {
  116 |   const api = await installAssetsFixture(page); api.paged = true;
  117 |   await page.goto("/#assets");
  118 |   await mouseClick(page, page.getByRole("button", { name: "加载更多资产", exact: true }));
  119 |   await expect(page.getByRole("link", { name: /第二页资产/ })).toBeVisible();
  120 |   api.hold = true; await mouseClick(page, page.getByRole("button", { name: "刷新资产与快照" }));
  121 |   await expect(page.getByText("正在读取资产页…", { exact: true })).toBeVisible();
  122 |   await mouseClick(page, page.getByRole("link", { name: "会话与权限", exact: true }));
  123 |   await mouseClick(page, page.getByRole("button", { name: "退出登录", exact: true }));
  124 |   api.hold = false; api.release();
  125 |   await mouseClick(page, page.getByRole("link", { name: "资产自查", exact: true }));
  126 |   await expect(page.getByText("登录后查看授权资产", { exact: true })).toBeVisible();
  127 |   await expect(page.getByText(assetFixture().display_name, { exact: true })).toHaveCount(0);
  128 |   await page.screenshot({ path: info.outputPath("synthetic-logout-cleared.png") });
  129 |   api.authenticated = true; api.tenant = "synthetic-assets-other-tenant"; api.empty = true; await page.reload();
  130 |   await expect(page.getByText("尚无可见资产清单", { exact: true })).toBeVisible();
  131 |   await expect(page.getByText(assetFixture().display_name, { exact: true })).toHaveCount(0);
  132 |   api.assetStatus = 401; await mouseClick(page, page.getByRole("button", { name: "刷新资产与快照" }));
  133 |   await expect(page.getByText("登录后查看授权资产", { exact: true })).toBeVisible();
  134 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  135 | });
  136 | 
```