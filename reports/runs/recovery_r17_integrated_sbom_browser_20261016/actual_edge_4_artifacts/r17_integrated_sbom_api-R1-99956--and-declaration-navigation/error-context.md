# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_integrated_sbom_api.spec.ts >> R17 actual API 01: empty catalog, raw POST, typed sidecar and declaration navigation
- Location: e2e\r17_integrated_sbom_api.spec.ts:80:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('.sbom-panel').getByText(/redacted-field:/)
Expected: visible
Error: strict mode violation: locator('.sbom-panel').getByText(/redacted-field:/) resolved to 2 elements:
    1) <code>/redacted-field:c8b8e7c2ba92c645ac86c30698a99d4c0…</code> aka getByText('/redacted-field:').first()
    2) <code>/redacted-field:c8b8e7c2ba92c645ac86c30698a99d4c0…</code> aka getByText('/redacted-field:').nth(1)

Call log:
  - Expect "toBeVisible" locator('.sbom-panel').getByText(/redacted-field:/) with timeout 10000ms
  - waiting for locator('.sbom-panel').getByText(/redacted-field:/)

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - link "跳到主要内容" [ref=e4] [cursor=pointer]:
    - /url: "#main-content"
  - complementary [ref=e5]:
    - link "安全情报 DEFENSE INTELLIGENCE" [ref=e6] [cursor=pointer]:
      - /url: "#runtime"
      - generic [aria-hidden] [ref=e7]: DI
      - generic [ref=e9]:
        - text: 安全情报
        - generic [ref=e10]: DEFENSE INTELLIGENCE
    - navigation "工作台导航" [ref=e11]:
      - generic [ref=e12]:
        - paragraph [ref=e13]: 研究
        - link "情报列表" [ref=e14] [cursor=pointer]:
          - /url: "#events"
          - generic [aria-hidden] [ref=e15]: ≡
          - text: 情报列表
        - link "来源监测" [ref=e16] [cursor=pointer]:
          - /url: "#sources"
          - generic [aria-hidden] [ref=e17]: ◉
          - text: 来源监测
        - link "资料库" [ref=e18] [cursor=pointer]:
          - /url: "#documents"
          - generic [aria-hidden] [ref=e19]: ▤
          - text: 资料库
        - link "知识图谱" [ref=e20] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=e21]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=e22] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=e23]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=e24] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=e25]: ⬡
          - text: 资产自查
      - generic [ref=e26]:
        - paragraph [ref=e27]: 协作
        - link "任务轨迹" [ref=e28] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=e29]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=e30] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=e31]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=e32] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=e33]: ▤
          - text: 证据报告
      - generic [ref=e34]:
        - paragraph [ref=e35]: 系统
        - link "运行状态" [ref=e36] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=e37]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=e38] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=e39]: ◎
          - text: 会话与权限
    - generic [ref=e40]:
      - paragraph [ref=e41]: 可追溯的事实清晰的判断边界
      - text: AI 安全知识情报系统
      - code [ref=e42]: READ · VERIFY · CONNECT
  - generic [ref=e43]:
    - banner [ref=e44]:
      - generic [ref=e45]:
        - generic [aria-hidden] [ref=e46]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=e47]: /
        - text: 资产自查
      - generic [ref=e48]:
        - text: 数据模式
        - strong [ref=e49]: 合成 / Fixture
    - main [ref=e50]:
      - generic [ref=e51]:
        - generic [ref=e52]:
          - paragraph [ref=e53]: ASSESSMENT / ASSETS
          - heading "版本与资产" [level=1] [ref=e54]: 版本与资产_
          - paragraph [ref=e55]: 在固定资产快照上核查版本、条件与影响。
        - button "刷新状态" [ref=e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=e57]: ↻
          - text: 刷新状态
      - generic [ref=e58]:
        - generic [ref=e59]:
          - paragraph [ref=e60]:
            - generic [ref=e61]: PRIVATE INVENTORY / 授权清单
            - text: 仅显示当前认证租户的资产声明
          - generic [ref=e62]: 合成 Fixture · 非真实资产
          - button "刷新资产与快照" [ref=e63] [cursor=pointer]
        - status [ref=e64]:
          - strong [ref=e65]: 导入成功 · 服务端已保存快照
          - paragraph [ref=e66]:
            - text: "快照 #1 ·"
            - code [ref=e67]: 8183a308-ab29-5ac8-8448-bd82a53c5354
            - text: 。当前内容请以重新读取的资产详情为准。
        - group [ref=e68]:
          - generic "+ 导入授权清单 JSON / CSV / CycloneDX / SPDX · 最大 1 MiB" [ref=e69] [cursor=pointer]:
            - text: + 导入授权清单
            - generic [ref=e70]: JSON / CSV / CycloneDX / SPDX · 最大 1 MiB
          - option "JSON manifest v1" [selected]
          - option "CSV 组件清单"
          - option "CycloneDX JSON 1.5 / 1.6 / 1.7"
          - option "SPDX JSON 2.3"
        - generic [ref=e71]:
          - region [ref=e72]:
            - generic [ref=e73]:
              - generic [ref=e74]:
                - paragraph [ref=e75]: INVENTORY / 资产目录
                - heading "当前授权资产" [level=2] [ref=e76]
              - generic [ref=e77]: 已读 1 项
            - generic [ref=e78]:
              - generic [ref=e79]: 按组件包名精确筛选
              - generic [ref=e80]:
                - textbox "按组件包名精确筛选" [ref=e81]:
                  - /placeholder: package_name
                - button "筛选资产" [ref=e82] [cursor=pointer]
            - list [ref=e83]:
              - listitem [ref=e84]:
                - 'link "Synthetic browser · 授权测试清单 完整性未知 快照 #1 · 2 个组件声明 实际观察 2026-10-16T08:00:00+08:00 74fc2eb6-75eb-4a8f-9e36-986c39b34df9" [ref=e85] [cursor=pointer]':
                  - /url: "#assets/74fc2eb6-75eb-4a8f-9e36-986c39b34df9"
                  - generic [ref=e86]:
                    - strong [ref=e87]: Synthetic browser · 授权测试清单
                    - generic [aria-hidden] [ref=e88]: ↗
                  - generic [ref=e89]: 完整性未知
                  - paragraph [ref=e90]: "快照 #1 · 2 个组件声明"
                  - generic [ref=e91]:
                    - text: 实际观察
                    - time [ref=e92]: 2026-10-16T08:00:00+08:00
                  - code [ref=e93]: 74fc2eb6-75eb-4a8f-9e36-986c39b34df9
            - paragraph [ref=e94]: 当前查询已到末页；不是所有资产的完整性证明。
          - region [ref=e95]:
            - generic [ref=e96]:
              - generic [ref=e97]:
                - paragraph [ref=e98]: ASSET / 私有资产检视
                - heading "Synthetic browser · 授权测试清单" [level=2] [ref=e99]
              - link "返回资产列表" [ref=e100] [cursor=pointer]:
                - /url: "#assets"
            - generic [ref=e101]:
              - code [ref=e102]: 74fc2eb6-75eb-4a8f-9e36-986c39b34df9
              - generic [ref=e103]: 服务端标记：活跃
              - paragraph [ref=e104]: 业务重要性：未知 · 资产声明不等于已核查影响。
            - generic [ref=e105]:
              - generic [ref=e106]:
                - heading "快照历史" [level=3] [ref=e107]
                - button "刷新历史" [ref=e108] [cursor=pointer]
              - paragraph [ref=e109]: 按服务端快照顺序读取；点击版本后重新获取该固定快照。
              - 'button "查看快照 #1 · 当前 2026-10-16T08:00:00+08:00" [ref=e111] [cursor=pointer]':
                - generic [ref=e112]: "查看快照 #1 · 当前"
                - time [ref=e113]: 2026-10-16T08:00:00+08:00
            - generic [ref=e114]:
              - generic [ref=e115]:
                - generic [ref=e116]:
                  - paragraph [ref=e117]: CURRENT SNAPSHOT / 当前快照
                  - 'heading "快照 #1" [level=3] [ref=e118]'
                - generic [ref=e119]: 完整性未知
              - generic [ref=e120]:
                - term [ref=e121]: 快照标识
                - definition [ref=e122]:
                  - code [ref=e123]: 8183a308-ab29-5ac8-8448-bd82a53c5354
                - term [ref=e124]: 实际观察时间
                - definition [ref=e125]:
                  - time [ref=e126]: 2026-10-16T08:00:00+08:00
                - term [ref=e127]: 系统记录时间
                - definition [ref=e128]:
                  - time [ref=e129]: 2026-10-16T10:43:47+08:00
                - term [ref=e130]: 输入类型
                - definition [ref=e131]:
                  - code [ref=e132]: cyclonedx_json
                - term [ref=e133]: 输入来源版本
                - definition [ref=e134]: 未知 · 当前响应未提供
                - term [ref=e135]: 声明范围
                - definition [ref=e136]: 未知 · 未声明
                - term [ref=e137]: 快照内容摘要
                - definition [ref=e138]:
                  - code [ref=e139]: 949dd62fde83feeb4faeb110cea61bd4949d572e21bc2dc70b058bf4ef2c3ce0
                  - generic [ref=e140]: 内容 SHA-256；摘要不证明清单真实性。
              - generic [ref=e141]:
                - generic [ref=e142]:
                  - heading "组件声明" [level=4] [ref=e143]
                  - generic [ref=e144]: 共 2 项 · 每页 20 项
                - table "资产组件声明" [ref=e146]:
                  - rowgroup [ref=e147]:
                    - row [ref=e148]:
                      - columnheader "组件 / 生态" [ref=e149]
                      - columnheader "版本 / 比较方案" [ref=e150]
                      - columnheader "身份与字段定位" [ref=e151]
                  - rowgroup [ref=e152]:
                    - row [ref=e153]:
                      - rowheader "synthetic-root @synthetic/root npm" [ref=e154]:
                        - text: synthetic-root
                        - code [ref=e155]: "@synthetic/root"
                        - generic [ref=e156]: npm
                      - cell [ref=e157]:
                        - strong [ref=e158]: 1.0.0
                        - code [ref=e159]: semver
                      - cell [ref=e160]:
                        - generic [ref=e161]:
                          - term [ref=e162]: purl
                          - definition [ref=e163]:
                            - code [ref=e164]: pkg:npm/%40synthetic/root@1.0.0
                          - term [ref=e165]: 镜像摘要
                          - definition [ref=e166]:
                            - code [ref=e167]: 未知 · 未声明
                          - term [ref=e168]: 依赖路径
                          - definition [ref=e169]: 未知 · 未声明
                          - term [ref=e170]: 字段位置
                          - definition [ref=e171]:
                            - code [ref=e172]: /components/0
                          - term [ref=e173]: 组件标识
                          - definition [ref=e174]:
                            - code [ref=e175]: bf39ff44-8c7d-5212-a489-dd841144322b
                    - row [ref=e176]:
                      - rowheader "synthetic-child synthetic-child 生态未知" [ref=e177]:
                        - text: synthetic-child
                        - code [ref=e178]: synthetic-child
                        - generic [ref=e179]: 生态未知
                      - cell [ref=e180]:
                        - strong [ref=e181]: 版本未知
                        - code [ref=e182]: 比较方案未知
                      - cell [ref=e183]:
                        - generic [ref=e184]:
                          - term [ref=e185]: purl
                          - definition [ref=e186]:
                            - code [ref=e187]: 未知 · 未声明
                          - term [ref=e188]: 镜像摘要
                          - definition [ref=e189]:
                            - code [ref=e190]: 未知 · 未声明
                          - term [ref=e191]: 依赖路径
                          - definition [ref=e192]: 未知 · 未声明
                          - term [ref=e193]: 字段位置
                          - definition [ref=e194]:
                            - code [ref=e195]: /components/1
                          - term [ref=e196]: 组件标识
                          - definition [ref=e197]:
                            - code [ref=e198]: 0d0fe718-1895-5f0d-80e2-a38abf22f4cc
              - generic [ref=e199]:
                - heading "内部配置声明" [level=4] [ref=e200]
                - paragraph [ref=e201]: 未知 · 未提供声明，不能解释为 false。
              - generic [ref=e202]:
                - heading "输入通道声明" [level=4] [ref=e203]
                - paragraph [ref=e204]: 未知 · 未提供声明，不能解释为 false。
              - generic [ref=e205]:
                - heading "网络配置声明（不是外部观测）" [level=4] [ref=e206]
                - paragraph [ref=e207]: 未知 · 未提供声明，不能解释为 false。
              - generic [ref=e208]:
                - heading "工具权限声明" [level=4] [ref=e209]
                - paragraph [ref=e210]: 未知 · 未提供声明
              - region "固定快照 SBOM 声明" [ref=e211]:
                - paragraph [ref=e212]: SBOM / FROZEN DECLARATIONS
                - heading "SBOM 历史声明" [level=4] [ref=e213]
                - paragraph [ref=e214]: 绑定正在查看的快照，不随当前版本覆盖。来源版本未知；适配器与规范版本单列。以下关系与完整性属于输入声明，核验状态未知。
                - navigation "当前固定 SBOM 的声明导航" [ref=e215]:
                  - button "组件来源 2" [ref=e216] [cursor=pointer]:
                    - generic [ref=e217]: 组件来源
                    - generic [ref=e218]: "2"
                  - button "依赖与标准关系 1" [ref=e219] [cursor=pointer]:
                    - generic [ref=e220]: 依赖与标准关系
                    - generic [ref=e221]: "1"
                  - button "文档完整性声明 1" [ref=e222] [cursor=pointer]:
                    - generic [ref=e223]: 文档完整性声明
                    - generic [ref=e224]: "1"
                  - button "外部文档声明 0" [ref=e225] [cursor=pointer]:
                    - generic [ref=e226]: 外部文档声明
                    - generic [ref=e227]: "0"
                  - button "未映射字段位置 1" [ref=e228] [cursor=pointer]:
                    - generic [ref=e229]: 未映射字段位置
                    - generic [ref=e230]: "1"
                  - button "隐藏位置说明 1" [ref=e231] [cursor=pointer]:
                    - generic [ref=e232]: 隐藏位置说明
                    - generic [ref=e233]: "1"
                - generic [ref=e234]:
                  - term [ref=e235]: 来源格式 / 规范版本
                  - definition [ref=e236]:
                    - code [ref=e237]: cyclonedx_json / 1.6
                  - term [ref=e238]: 适配器版本
                  - definition [ref=e239]:
                    - code [ref=e240]: r11-sbom-adapter-1
                  - term [ref=e241]: 原文摘要
                  - definition [ref=e242]:
                    - code [ref=e243]: 1515832bc890d4fe137e7480e8a76164d3f70e70a3544eb7fa9b9cb8e72a6960
                  - term [ref=e244]: 组合声明摘要
                  - definition [ref=e245]:
                    - code [ref=e246]: 4706f008d796243cf33a57a7e3a19e8d8ab52549e94e3c643454b8bfac273a73
                  - term [ref=e247]: 展示限制
                  - definition [ref=e248]: 1 个位置已隐藏；未恢复原 URI、路径或凭据。
                - generic [ref=e249]:
                  - generic [ref=e250]:
                    - heading "组件来源" [level=4] [ref=e251]
                    - generic [ref=e252]: 2 项 · 每页 20 项
                  - list [ref=e253]:
                    - listitem [ref=e254]:
                      - generic [ref=e255]:
                        - strong [ref=e256]: synthetic-root
                        - generic [ref=e257]: library
                      - code [ref=e258]: root
                      - code [ref=e259]: bf39ff44-8c7d-5212-a489-dd841144322b · /components/0
                      - group [ref=e260]:
                        - generic "字段来源与校验摘要" [ref=e261] [cursor=pointer]
                    - listitem [ref=e262]:
                      - generic [ref=e263]:
                        - strong [ref=e264]: synthetic-child
                        - generic [ref=e265]: library
                      - code [ref=e266]: child
                      - code [ref=e267]: 0d0fe718-1895-5f0d-80e2-a38abf22f4cc · /components/1
                      - group [ref=e268]:
                        - generic "字段来源与校验摘要" [ref=e269] [cursor=pointer]
                - generic [active] [ref=e270]:
                  - generic [ref=e271]:
                    - heading "依赖与标准关系" [level=4] [ref=e272]
                    - generic [ref=e273]: 1 项 · 每页 20 项
                  - table "SBOM 原始关系声明" [ref=e275]:
                    - rowgroup [ref=e276]:
                      - row [ref=e277]:
                        - columnheader "来源引用" [ref=e278]
                        - columnheader "声明关系" [ref=e279]
                        - columnheader "目标引用 / 字段位置" [ref=e280]
                    - rowgroup [ref=e281]:
                      - row [ref=e282]:
                        - cell [ref=e283]:
                          - code [ref=e284]: root
                        - cell [ref=e285]:
                          - code [ref=e286]: dependsOn
                        - cell [ref=e287]:
                          - code [ref=e288]: child
                          - code [ref=e289]: /dependencies/0/dependsOn/0
                - generic [ref=e290]:
                  - generic [ref=e291]:
                    - heading "文档完整性声明" [level=4] [ref=e292]
                    - generic [ref=e293]: 1 项 · 每页 20 项
                  - list [ref=e294]:
                    - listitem [ref=e295]:
                      - strong [ref=e296]:
                        - code [ref=e297]: unknown
                        - text: · 输入声明
                      - code [ref=e298]: /compositions/0
                      - generic [ref=e299]:
                        - paragraph [ref=e300]: "assemblies: 1 个引用"
                        - code [ref=e303]: root
                      - paragraph [ref=e305]: "dependencies: 0 个引用"
                      - paragraph [ref=e307]: "vulnerabilities: 0 个引用"
                      - paragraph [ref=e308]: 此声明不证明授权资产安装范围完整，也不改变影响状态。
                - generic [ref=e309]:
                  - generic [ref=e310]:
                    - heading "外部文档声明" [level=4] [ref=e311]
                    - generic [ref=e312]: 0 项 · 每页 20 项
                  - paragraph [ref=e313]: 该文档未提供这类声明；不能据此排除依赖或风险。
                - generic [ref=e314]:
                  - generic [ref=e315]:
                    - heading "未映射字段位置" [level=4] [ref=e316]
                    - generic [ref=e317]: 1 项 · 每页 20 项
                  - list [ref=e318]:
                    - listitem [ref=e319]:
                      - code [ref=e320]: /redacted-field:c8b8e7c2ba92c645ac86c30698a99d4c03a0fa62de067a93e58823a9cc362820
                - generic [ref=e321]:
                  - generic [ref=e322]:
                    - heading "隐藏位置说明" [level=4] [ref=e323]
                    - generic [ref=e324]: 1 项 · 每页 20 项
                  - list [ref=e325]:
                    - listitem [ref=e326]:
                      - code [ref=e327]: /redacted-field:c8b8e7c2ba92c645ac86c30698a99d4c03a0fa62de067a93e58823a9cc362820
                      - generic [ref=e328]: URI / 路径展示限制
            - generic [ref=e329]:
              - paragraph [ref=e330]: OBSERVATION / 外部观察
              - heading "外部观察入口尚未接通" [level=3] [ref=e331]
              - paragraph [ref=e332]: 本页仅展示内部清单声明。外部不可达不能证明软件已修复；不会从导入动作发起第三方扫描。
              - button "查询授权外部观察 · 未就绪" [disabled] [ref=e333]
            - generic [ref=e334]:
              - paragraph [ref=e335]: ASSESSMENT / 条件与证据
              - heading "研判与导出入口尚未接通" [level=3] [ref=e336]
              - paragraph [ref=e337]: 条件树、四态结果、缺口、冲突和 freshness 需由已验证业务接口返回。当前快照不显示预设判定；旧结果须重新验证。
              - generic [ref=e338]:
                - button "提交研判 · 未就绪" [disabled] [ref=e339]
                - button "导出证据包 / OpenVEX · 未就绪" [disabled] [ref=e340]
      - generic [ref=e341]:
        - generic [ref=e342]: 环境 test
        - generic [ref=e343]: 版本 0.1.0
```

# Test source

```ts
  1   | import process from "node:process";
  2   | import { createHash } from "node:crypto";
  3   | import { execFileSync, spawn } from "node:child_process";
  4   | import { writeFileSync } from "node:fs";
  5   | import { expect, test, type Page, type TestInfo } from "@playwright/test";
  6   | import { cyclonedxInput, spdxInput } from "./helpers/r17-sbom-inputs";
  7   | 
  8   | const httpFlows = new WeakMap<Page, { path: string; method: string; status: number; observed_at: string }[]>();
  9   | test.beforeEach(async ({ page }) => {
  10  |   const responses: { path: string; method: string; status: number; observed_at: string }[] = [];
  11  |   httpFlows.set(page, responses);
  12  |   page.on("response", (response) => {
  13  |     const path = new URL(response.url()).pathname;
  14  |     if (path.startsWith("/v1/")) responses.push({ path, method: response.request().method(), status: response.status(), observed_at: new Date().toISOString() });
  15  |   });
  16  | });
  17  | 
  18  | function actor(index: number): { username: string; password: string } {
  19  |   const accounts: unknown = JSON.parse(process.env.R17_BROWSER_ACCOUNTS ?? "null");
  20  |   if (!Array.isArray(accounts)) throw new Error("isolated browser actors must be injected");
  21  |   const account: unknown = accounts[index];
  22  |   if (typeof account !== "object" || account === null || !("username" in account) || !("password" in account) || typeof account.username !== "string" || typeof account.password !== "string") throw new Error("isolated actor schema invalid");
  23  |   return { username: account.username, password: account.password };
  24  | }
  25  | 
  26  | function control(action: string, payload: Record<string, string> = {}): unknown {
  27  |   const output = execFileSync("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", action, JSON.stringify(payload)], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 10_000 });
  28  |   return JSON.parse(output);
  29  | }
  30  | 
  31  | async function login(page: Page, index: number) {
  32  |   const account = actor(index);
  33  |   await page.goto("/#session");
  34  |   await page.getByLabel("用户名", { exact: true }).fill(account.username);
  35  |   await page.getByLabel("密码", { exact: true }).fill(account.password);
  36  |   await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  37  |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  38  |   await page.getByRole("link", { name: "资产自查", exact: true }).click();
  39  |   await expect(page.getByText("合成 Fixture · 非真实资产", { exact: true })).toBeVisible();
  40  |   const session = (await page.context().cookies()).find((cookie) => cookie.name === "ai_intel_session");
  41  |   expect(session?.httpOnly).toBe(true);
  42  |   expect(session?.sameSite).toBe("Strict");
  43  | }
  44  | 
  45  | async function record(page: Page, info: TestInfo, name: string) {
  46  |   const screenshot = info.outputPath(name + ".png");
  47  |   await page.screenshot({ path: screenshot, fullPage: true });
  48  |   writeFileSync(info.outputPath(name + ".json"), JSON.stringify({ name, observed_at: new Date().toISOString(), url: page.url(), viewport: page.viewportSize(), screenshot, data_mode: "fixture", actual_api: true }, null, 2));
  49  | }
  50  | 
  51  | async function importThroughUi(page: Page, raw: Buffer, format: "cyclonedx_json" | "spdx_json", append = false) {
  52  |   if ((await page.locator(".asset-import-panel").getAttribute("open")) === null) await page.locator(".asset-import-panel summary").click();
  53  |   await page.getByLabel("清单格式", { exact: true }).selectOption(format);
  54  |   await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: "synthetic-browser.json", mimeType: "application/json", buffer: raw });
  55  |   if (append) await page.getByLabel("追加到当前所选资产（名称保持一致）", { exact: true }).check();
  56  |   else await page.getByLabel("资产名称", { exact: true }).fill("Synthetic browser · 授权测试清单");
  57  |   await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-browser-r17");
  58  |   await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-16T08:00:00+08:00");
  59  |   const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/asset-imports" && response.request().method() === "POST");
  60  |   await page.getByRole("button", { name: "提交授权清单", exact: true }).click();
  61  |   const response = await responsePromise;
  62  |   expect(response.status()).toBe(201);
  63  |   const capturedBody = response.request().postDataBuffer();
  64  |   if (capturedBody !== null) expect(capturedBody).toEqual(raw);
  65  |   const created: unknown = await response.json();
  66  |   if (typeof created !== "object" || created === null || !("asset_id" in created) || typeof created.asset_id !== "string" || !("snapshot" in created) || typeof created.snapshot !== "object" || created.snapshot === null || !("snapshot_id" in created.snapshot) || typeof created.snapshot.snapshot_id !== "string") throw new Error("actual import response invalid");
  67  |   await expect(page.getByRole("heading", { name: "Synthetic browser · 授权测试清单", exact: true })).toBeVisible();
  68  |   await expect(page.getByText("r11-sbom-adapter-1", { exact: true })).toBeVisible();
  69  |   const rawSha = createHash("sha256").update(raw).digest("hex");
  70  |   expect(control("verify-upload", { snapshot_id: created.snapshot.snapshot_id, raw_sha256: rawSha })).toMatchObject({ raw_sha256: rawSha, snapshot_id: created.snapshot.snapshot_id, migration: "0022_sbom_sidecars", public_schema: "public" });
  71  |   return { assetId: created.asset_id, snapshotId: created.snapshot.snapshot_id, rawSha };
  72  | }
  73  | 
  74  | test.afterEach(async ({ page }, info) => {
  75  |   const logout = page.getByRole("button", { name: "退出登录", exact: true });
  76  |   if (await logout.isVisible()) await logout.click();
  77  |   writeFileSync(info.outputPath("actual-http-flow.json"), JSON.stringify(httpFlows.get(page), null, 2));
  78  | });
  79  | 
  80  | test("R17 actual API 01: empty catalog, raw POST, typed sidecar and declaration navigation", async ({ page }, info) => {
  81  |   await login(page, 0);
  82  |   await expect(page.getByRole("heading", { name: "尚无可见资产清单", exact: true })).toBeVisible();
  83  |   await record(page, info, "empty-catalog");
  84  |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  85  |   await expect(page.getByText("pkg:npm/%40synthetic/root@1.0.0", { exact: true })).toBeVisible();
  86  |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  87  |   await expect(page.locator(".sbom-source-heading").filter({ hasText: "synthetic-root" })).toBeVisible();
  88  |   const navigation = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" });
  89  |   await expect(navigation.getByRole("button")).toHaveCount(6);
  90  |   await navigation.getByRole("button", { name: "依赖与标准关系 1", exact: true }).focus();
  91  |   await page.keyboard.press("Enter");
  92  |   await expect(page.locator(`[id='sbom-${created.snapshotId}-relationships']`)).toBeFocused();
  93  |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" }).getByText("dependsOn", { exact: true })).toBeVisible();
  94  |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
> 95  |   await expect(page.locator(".sbom-panel").getByText(/redacted-field:/)).toBeVisible();
      |                                                                          ^ Error: expect(locator).toBeVisible() failed
  96  |   const delay = spawn("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", "sidecar-delay", "{}"], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  97  |   const ended = new Promise<number | null>((resolve) => delay.once("exit", resolve));
  98  |   await new Promise<void>((resolve, reject) => { delay.stdout.once("data", () => resolve()); delay.once("error", reject); });
  99  |   await page.reload();
  100 |   await expect(page.getByText("正在读取固定快照 SBOM 声明…", { exact: true })).toBeVisible();
  101 |   await record(page, info, "actual-loading");
  102 |   expect(await ended).toBe(0);
  103 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  104 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  105 |   await record(page, info, "cdx-declarations-desktop");
  106 | });
  107 | 
  108 | test("R17 actual API 02: SPDX relations and public link keep private URI hidden", async ({ page }, info) => {
  109 |   await login(page, 1);
  110 |   await importThroughUi(page, spdxInput(), "spdx_json");
  111 |   await expect(page.getByText("DESCRIBES", { exact: true })).toBeVisible();
  112 |   await expect(page.getByText("pkg:pypi/synthetic-spdx@2.0", { exact: true })).toBeVisible();
  113 |   await expect(page.getByRole("link", { name: "打开服务器提供的公开文档 ↗", exact: true })).toHaveAttribute("href", "https://example.com/synthetic.spdx.json");
  114 |   await expect(page.getByText("原 URI 已隐藏 · 不恢复或点击不安全定位", { exact: true })).toBeVisible();
  115 |   await expect(page.locator("a[href^='file:']")).toHaveCount(0);
  116 |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  117 |   await record(page, info, "spdx-privacy");
  118 | });
  119 | 
  120 | test("R17 actual API 03: three immutable snapshots, unknowns and stale pointer revalidation", async ({ page }, info) => {
  121 |   await login(page, 2);
  122 |   const first = await importThroughUi(page, cyclonedxInput("1.0.0", false), "cyclonedx_json");
  123 |   const second = await importThroughUi(page, cyclonedxInput("2.0.0", true), "cyclonedx_json", true);
  124 |   const third = await importThroughUi(page, cyclonedxInput(null, false), "cyclonedx_json", true);
  125 |   expect(new Set([first.snapshotId, second.snapshotId, third.snapshotId]).size).toBe(3);
  126 |   await expect(page.getByRole("heading", { name: "快照 #3", exact: true })).toBeVisible();
  127 |   await expect(page.getByText("版本未知", { exact: true }).first()).toBeVisible();
  128 |   await expect(page.getByText("未知 · 当前响应未提供", { exact: true })).toBeVisible();
  129 |   await page.getByRole("button", { name: /查看快照 #1 · 历史/ }).click();
  130 |   await expect(page.getByText(first.rawSha, { exact: true })).toBeVisible();
  131 |   await expect(page.getByText(/正在查看历史快照/)).toBeVisible();
  132 |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" })).toHaveCount(0);
  133 |   await record(page, info, "fixed-history");
  134 |   await page.getByRole("button", { name: "查看当前快照", exact: true }).click();
  135 |   await page.reload();
  136 |   await expect(page.getByText(third.rawSha, { exact: true })).toBeVisible();
  137 |   await page.getByRole("button", { name: /查看快照 #2 · 历史/ }).click();
  138 |   await expect(page.getByText(second.rawSha, { exact: true })).toBeVisible();
  139 |   await expect(page.getByText("dependsOn", { exact: true })).toBeVisible();
  140 |   await expect(page.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪", exact: true })).toBeDisabled();
  141 |   await expect(page.getByRole("button", { name: "查询授权外部观察 · 未就绪", exact: true })).toBeDisabled();
  142 | });
  143 | 
  144 | test("R17 actual API 04: database sidecar outage is partial 503 and recovers on retry", async ({ page }, info) => {
  145 |   await login(page, 3);
  146 |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  147 |   control("sidecar-unavailable");
  148 |   try {
  149 |     const response = page.waitForResponse((value) => new URL(value.url()).pathname.endsWith("/sbom"));
  150 |     await page.reload();
  151 |     expect((await response).status()).toBe(503);
  152 |     await expect(page.getByRole("heading", { name: "快照 #1", exact: true })).toBeVisible();
  153 |     await expect(page.getByRole("table", { name: "资产组件声明" })).toBeVisible();
  154 |     await expect(page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true })).toBeVisible();
  155 |     await expect(page.getByText(created.rawSha, { exact: true })).toHaveCount(0);
  156 |     await record(page, info, "actual-503-partial");
  157 |   } finally { control("sidecar-restore"); }
  158 |   await page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true }).click();
  159 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  160 |   await record(page, info, "actual-503-recovery");
  161 | });
  162 | 
  163 | test("R17 actual API 05: real role and session revocation clear private DOM", async ({ page }, info) => {
  164 |   await login(page, 4);
  165 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  166 |   control("revoke-read", { username: actor(4).username });
  167 |   const denied = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
  168 |   await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  169 |   expect((await denied).status()).toBe(403);
  170 |   await expect(page.getByText("当前会话没有此项资产权限，请联系租户管理员。", { exact: true })).toBeVisible();
  171 |   await expect(page.getByRole("heading", { name: "当前授权资产", exact: true })).toHaveCount(0);
  172 |   await expect(page.getByRole("heading", { name: "快照历史", exact: true })).toHaveCount(0);
  173 |   await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  174 |   await record(page, info, "actual-403-revocation");
  175 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  176 |   await login(page, 5);
  177 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  178 |   control("revoke-session", { username: actor(5).username });
  179 |   const expired = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
  180 |   await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  181 |   expect((await expired).status()).toBe(401);
  182 |   await expect(page.getByText("会话已失效，私有资产已清除", { exact: true })).toBeVisible();
  183 |   await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  184 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  185 |   await record(page, info, "actual-401-revocation");
  186 | });
  187 | 
  188 | test("R17 actual API 06: 390px keyboard, declaration focus and reduced motion", async ({ page }, info) => {
  189 |   await login(page, 6);
  190 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  191 |   await page.setViewportSize({ width: 390, height: 844 });
  192 |   await page.emulateMedia({ reducedMotion: "reduce" });
  193 |   const target = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" }).getByRole("button", { name: "组件来源 2", exact: true });
  194 |   await target.focus();
  195 |   await page.keyboard.press("Enter");
```