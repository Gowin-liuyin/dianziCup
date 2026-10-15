# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: independent.spec.cjs >> 独立负例 B：固定历史 wrong tenant 必须清详情与目录
- Location: ..\reports\runs\recovery_r17_assets_workbench_fix1_20261016\independent.spec.cjs:57:1

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByText('独立合成资产 Alpha', { exact: true })
Expected: 0
Received: 2
Timeout:  2000ms

Call log:
  - Expect "toHaveCount" getByText('独立合成资产 Alpha', { exact: true }) with timeout 2000ms
  - waiting for getByText('独立合成资产 Alpha', { exact: true })
    19 × locator resolved to 2 elements
       - unexpected value "2"

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
        - group [ref=e64]:
          - generic "+ 导入授权清单 JSON v1 / CSV · 最大 1 MiB" [ref=e65] [cursor=pointer]:
            - text: + 导入授权清单
            - generic [ref=e66]: JSON v1 / CSV · 最大 1 MiB
          - option "JSON manifest v1" [selected]
          - option "CSV 组件清单"
        - generic [ref=e67]:
          - region [ref=e68]:
            - generic [ref=e69]:
              - generic [ref=e70]:
                - paragraph [ref=e71]: INVENTORY / 资产目录
                - heading "当前授权资产" [level=2] [ref=e72]
              - generic [ref=e73]: 已读 1 项
            - generic [ref=e74]:
              - generic [ref=e75]: 按组件包名精确筛选
              - generic [ref=e76]:
                - textbox "按组件包名精确筛选" [ref=e77]:
                  - /placeholder: package_name
                - button "筛选资产" [ref=e78] [cursor=pointer]
            - list [ref=e79]:
              - listitem [ref=e80]:
                - 'link "独立合成资产 Alpha 部分清单 快照 #2 · 1 个组件声明 实际观察 2026-10-15T09:00:00+08:00 a1111111-1111-4111-8111-111111111111" [ref=e81] [cursor=pointer]':
                  - /url: "#assets/a1111111-1111-4111-8111-111111111111"
                  - generic [ref=e82]:
                    - strong [ref=e83]: 独立合成资产 Alpha
                    - generic [aria-hidden] [ref=e84]: ↗
                  - generic [ref=e85]: 部分清单
                  - paragraph [ref=e86]: "快照 #2 · 1 个组件声明"
                  - generic [ref=e87]:
                    - text: 实际观察
                    - time [ref=e88]: 2026-10-15T09:00:00+08:00
                  - code [ref=e89]: a1111111-1111-4111-8111-111111111111
            - paragraph [ref=e90]: 尚有后续页；以上仅为已读取记录。
            - button "加载更多资产" [ref=e92] [cursor=pointer]
          - region [ref=e93]:
            - generic [ref=e94]:
              - generic [ref=e95]:
                - paragraph [ref=e96]: ASSET / 私有资产检视
                - heading "独立合成资产 Alpha" [level=2] [ref=e97]
              - link "返回资产列表" [ref=e98] [cursor=pointer]:
                - /url: "#assets"
            - generic [ref=e99]:
              - code [ref=e100]: a1111111-1111-4111-8111-111111111111
              - generic [ref=e101]: 服务端标记：活跃
              - paragraph [ref=e102]: 业务重要性：未知 · 资产声明不等于已核查影响。
            - generic [ref=e103]:
              - generic [ref=e104]:
                - heading "快照历史" [level=3] [ref=e105]
                - button "刷新历史" [ref=e106] [cursor=pointer]
              - paragraph [ref=e107]: 按服务端快照顺序读取；点击版本后重新获取该固定快照。
              - generic [ref=e108]:
                - 'button "查看快照 #2 · 当前 2026-10-15T09:00:00+08:00" [ref=e109] [cursor=pointer]':
                  - generic [ref=e110]: "查看快照 #2 · 当前"
                  - time [ref=e111]: 2026-10-15T09:00:00+08:00
                - 'button "查看快照 #1 · 历史 2026-10-15T09:00:00+08:00" [active] [ref=e112] [cursor=pointer]':
                  - generic [ref=e113]: "查看快照 #1 · 历史"
                  - time [ref=e114]: 2026-10-15T09:00:00+08:00
            - alert [ref=e115]:
              - paragraph [ref=e116]: 资产响应与当前合同或会话范围不一致，结果未用于展示。导入是否提交需从资产列表核对。
              - button "重试固定快照" [ref=e117] [cursor=pointer]
            - generic [ref=e118]:
              - paragraph [ref=e119]: OBSERVATION / 外部观察
              - heading "外部观察入口尚未接通" [level=3] [ref=e120]
              - paragraph [ref=e121]: 本页仅展示内部清单声明。外部不可达不能证明软件已修复；不会从导入动作发起第三方扫描。
              - button "查询授权外部观察 · 未就绪" [disabled] [ref=e122]
            - generic [ref=e123]:
              - paragraph [ref=e124]: ASSESSMENT / 条件与证据
              - heading "研判与导出入口尚未接通" [level=3] [ref=e125]
              - paragraph [ref=e126]: 条件树、四态结果、缺口、冲突和 freshness 需由已验证业务接口返回。当前快照不显示预设判定；旧结果须重新验证。
              - generic [ref=e127]:
                - button "提交研判 · 未就绪" [disabled] [ref=e128]
                - button "导出证据包 / OpenVEX · 未就绪" [disabled] [ref=e129]
      - generic [ref=e130]:
        - generic [ref=e131]: 环境未由服务端标明
        - generic [ref=e132]: 版本未由服务端标明
```

# Test source

```ts
  1   | const { test, expect } = require('../../../frontend/node_modules/@playwright/test');
  2   | const fs = require('node:fs');
  3   | const ASSET = 'a1111111-1111-4111-8111-111111111111';
  4   | const CURRENT = 'b1111111-1111-4111-8111-111111111112';
  5   | const OLD = 'b1111111-1111-4111-8111-111111111111';
  6   | const TENANT = 'independent-synthetic-tenant';
  7   | const NAME = '独立合成资产 Alpha';
  8   | function snapshot(number = 2, tenant = TENANT) {
  9   |   return { schema_version: 'r11-asset-candidate-1', snapshot_id: number === 2 ? CURRENT : OLD, asset_id: ASSET, tenant_id: tenant, snapshot_number: number, observed_at: '2026-10-15T01:00:00Z', recorded_at: '2026-10-15T02:00:00Z', source_kind: 'json_manifest_v1', inventory_completeness: 'partial', declared_scope: ['independent-synthetic-package'], components: [{ component_id: 'c1111111-1111-4111-8111-111111111111', ecosystem: 'PyPI', package_name: 'independent-synthetic-package', display_name: null, purl: null, version: number === 2 ? '2.0.0' : '1.0.0', version_scheme: 'pep440', image_digest: null, dependency_path: null, source_field_locator: '/components/0' }], configuration: [{ name: 'external_inputs', value: null, source_field_locator: '/configuration/external_inputs' }], tool_permissions: null, input_channels: null, network_exposure: null, snapshot_sha256: 'd'.repeat(64) };
  10  | }
  11  | function asset(tenant = TENANT) { return { asset_id: ASSET, tenant_id: tenant, display_name: NAME, criticality: 'unknown', active: true, current_snapshot_id: CURRENT, created_at: '2026-10-15T01:00:00Z', updated_at: '2026-10-15T02:00:00Z', snapshot: snapshot(2, tenant) }; }
  12  | async function click(page, locator) {
  13  |   await locator.scrollIntoViewIfNeeded(); const rect = await locator.boundingBox();
  14  |   if (!rect) throw new Error('鼠标目标不可见');
  15  |   await page.mouse.click(rect.x + rect.width / 2, rect.y + rect.height / 2);
  16  | }
  17  | async function install(page) {
  18  |   const state = { badList: false, badFixed: false, currentHold: false, currentRelease: null, csrfHold: false, csrfRelease: null, history404: false, selectedStatus: 200, imports: [], requests: [], authenticated: true, importHold: false, importRelease: null };
  19  |   await page.route('**/v1/**', async (route) => {
  20  |     const req = route.request(); const url = new URL(req.url()); const path = url.pathname;
  21  |     state.requests.push(req.method() + ' ' + path); let body; let status = 200;
  22  |     if (path === '/v1/auth/me') { status = state.authenticated ? 200 : 401; body = status === 200 ? { user_id: 'independent-synthetic-user', tenant_id: TENANT, role: 'tenant_admin', permissions: ['read:asset', 'write:asset'], permission_version: 1, data_mode: 'fixture', csrf_token: 'independent-synthetic-csrf' } : { error: { code: 'session_expired', retryable: false } }; }
  23  |     else if (path === '/v1/auth/csrf') { if (state.csrfHold) await new Promise(resolve => state.csrfRelease = resolve); body = { csrf_token: 'independent-synthetic-csrf', header_name: 'X-CSRF-Token' }; }
  24  |     else if (path === '/v1/auth/logout') { state.authenticated = false; body = { status: 'logged_out' }; }
  25  |     else if (path === '/v1/health/live') body = { status: 'live' };
  26  |     else if (path === '/v1/health/ready') body = { status: 'ready', reason: '独立合成截获，非后端联测', dependencies: {} };
  27  |     else if (path === '/v1/assets') body = url.searchParams.has('cursor') ? { items: [asset(state.badList ? 'wrong-synthetic-tenant' : TENANT)], next_cursor: null } : { items: [asset()], next_cursor: 'independent-next' };
  28  |     else if (path === `/v1/assets/${ASSET}`) { const frozen = asset(); if (state.currentHold) await new Promise(resolve => state.currentRelease = resolve); body = frozen; }
  29  |     else if (path === `/v1/assets/${ASSET}/snapshots`) { status = state.history404 ? 404 : 200; body = status === 200 ? { items: [snapshot(), snapshot(1)], next_cursor: null } : { error: { code: 'not_found', retryable: false } }; }
  30  |     else if (path === `/v1/assets/${ASSET}/snapshots/${OLD}`) { status = state.selectedStatus; body = status === 200 ? snapshot(1, state.badFixed ? 'wrong-synthetic-tenant' : TENANT) : { error: { code: 'not_found', retryable: false } }; }
  31  |     else if (path === '/v1/asset-imports') {
  32  |       state.imports.push({ key: req.headers()['idempotency-key'], bytes: req.postDataBuffer().toString('base64'), headers: { origin: req.headers()['origin'], csrf: req.headers()['x-csrf-token'] }, query: Object.fromEntries(url.searchParams) });
  33  |       if (state.importHold) await new Promise(resolve => state.importRelease = resolve);
  34  |       status = 503; body = { error: { code: 'inventory_unavailable', retryable: true } };
  35  |     } else throw new Error('独立fixture未知路由 ' + path);
  36  |     await route.fulfill({ status, json: body });
  37  |   }); return state;
  38  | }
  39  | async function fill(page, raw) {
  40  |   await click(page, page.locator('.asset-import-panel summary'));
  41  |   await page.getByLabel('选择本地清单', { exact: true }).setInputFiles({ name: 'independent.json', mimeType: 'application/json', buffer: Buffer.from(raw) });
  42  |   await page.getByLabel('资产名称', { exact: true }).fill(NAME);
  43  |   await page.getByLabel('输入来源版本', { exact: true }).fill('independent-v1');
  44  |   await page.getByLabel('实际观察时间（含时区）', { exact: true }).fill('2026-10-15T01:00:00Z');
  45  | }
  46  | async function record(page, info, state) {
  47  |   fs.writeFileSync(info.outputPath('observation.json'), JSON.stringify({ fixture: true, requests: state.requests, imports: state.imports, privateNameCount: await page.getByText(NAME, { exact: true }).count(), localStorage: await page.evaluate(() => localStorage.length + sessionStorage.length) }, null, 2));
  48  |   await page.screenshot({ path: info.outputPath('observation.png'), fullPage: true });
  49  | }
  50  | test('独立负例 A：后续目录页 wrong tenant 必须清私有状态', async ({ page }, info) => {
  51  |   const state = await install(page); await page.goto('/#assets');
  52  |   await expect(page.getByRole('link', { name: new RegExp(NAME) })).toBeVisible();
  53  |   state.badList = true; await click(page, page.getByRole('button', { name: '加载更多资产', exact: true }));
  54  |   await expect(page.getByRole('alert')).toContainText('会话范围不一致'); await record(page, info, state);
  55  |   await expect(page.getByText(NAME, { exact: true })).toHaveCount(0);
  56  | });
  57  | test('独立负例 B：固定历史 wrong tenant 必须清详情与目录', async ({ page }, info) => {
  58  |   const state = await install(page); await page.goto(`/#assets/${ASSET}`);
  59  |   await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toBeVisible();
  60  |   state.badFixed = true; await click(page, page.getByRole('button', { name: /查看快照 #1/ }));
  61  |   await expect(page.getByRole('alert')).toContainText('会话范围不一致'); await record(page, info, state);
> 62  |   await expect(page.getByText(NAME, { exact: true })).toHaveCount(0);
      |                                                       ^ Error: expect(locator).toHaveCount(expected) failed
  63  | });
  64  | test('独立负例 C：CSRF promise 迟到，登出后不得实际 POST', async ({ page }, info) => {
  65  |   const state = await install(page); await page.goto('/#assets'); await fill(page, '{"format_version":1,"components":[]}\r\n');
  66  |   state.csrfHold = true; await click(page, page.getByRole('button', { name: '提交授权清单', exact: true }));
  67  |   await expect.poll(() => state.csrfRelease !== null).toBe(true);
  68  |   await click(page, page.getByRole('link', { name: '会话与权限', exact: true }));
  69  |   await click(page, page.getByRole('button', { name: '退出登录', exact: true }));
  70  |   state.csrfHold = false; state.csrfRelease();
  71  |   await click(page, page.getByRole('link', { name: '资产自查', exact: true }));
  72  |   await expect(page.getByText('登录后查看授权资产', { exact: true })).toBeVisible();
  73  |   await record(page, info, state); expect(state.imports).toHaveLength(0);
  74  | });
  75  | test('独立负例 D：503 原字节同 key 重试、修改内容新 key、防双提交', async ({ page }, info) => {
  76  |   const state = await install(page); await page.goto('/#assets');
  77  |   const first = ' {"format_version":1,"components":[]}\r\n'; const second = '{"format_version":1,"components":[],"inventory_completeness":"partial"}\r\n';
  78  |   await fill(page, first); state.importHold = true;
  79  |   await click(page, page.getByRole('button', { name: '提交授权清单', exact: true }));
  80  |   await expect.poll(() => state.imports.length).toBe(1);
  81  |   const button = page.getByRole('button', { name: '正在提交实际导入…', exact: true }); await expect(button).toBeDisabled(); await click(page, button);
  82  |   state.importHold = false; state.importRelease();
  83  |   await expect(page.getByRole('button', { name: '重试相同导入', exact: true })).toBeVisible();
  84  |   await click(page, page.getByRole('button', { name: '重试相同导入', exact: true }));
  85  |   await expect.poll(() => state.imports.length).toBe(2);
  86  |   await expect(page.getByRole('button', { name: '重试相同导入', exact: true })).toBeVisible();
  87  |   await page.getByLabel('选择本地清单', { exact: true }).setInputFiles({ name: 'independent.json', mimeType: 'application/json', buffer: Buffer.from(second) });
  88  |   await click(page, page.getByRole('button', { name: '提交授权清单', exact: true }));
  89  |   await expect.poll(() => state.imports.length).toBe(3); await record(page, info, state);
  90  |   expect(state.imports[0].key).toBe(state.imports[1].key); expect(state.imports[2].key).not.toBe(state.imports[1].key);
  91  |   expect(state.imports.map(v => v.bytes)).toEqual([first, first, second].map(v => Buffer.from(v).toString('base64')));
  92  |   expect(state.imports.every(v => v.headers.csrf && v.headers.origin === 'http://127.0.0.1:25719' && !('tenant_id' in v.query) && !('role' in v.query))).toBe(true);
  93  | });
  94  | test('独立负例 E：history 404 后迟到 current 不能恢复私有详情', async ({ page }, info) => {
  95  |   const state = await install(page); state.currentHold = true; state.history404 = true;
  96  |   await page.goto(`/#assets/${ASSET}`); await expect.poll(() => state.currentRelease !== null).toBe(true);
  97  |   await expect(page.getByRole('alert').first()).toContainText('不可用'); state.currentHold = false; state.currentRelease();
  98  |   await expect(page.getByRole('button', { name: '重新读取资产', exact: true })).toBeVisible();
  99  |   await record(page, info, state); await expect(page.getByRole('heading', { name: NAME, exact: true })).toHaveCount(0);
  100 |   await expect(page.getByRole('heading', { name: '快照 #2', exact: true })).toHaveCount(0);
  101 | });
  102 | 
```