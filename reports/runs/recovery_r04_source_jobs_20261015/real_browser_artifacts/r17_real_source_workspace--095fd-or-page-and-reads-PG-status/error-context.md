# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_real_source_workspace.spec.ts >> R17 actual administrator submits one bounded vendor page and reads PG status
- Location: e2e\r17_real_source_workspace.spec.ts:5:1

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.selectOption: Test timeout of 60000ms exceeded.
Call log:
  - waiting for getByLabel('固定来源', { exact: true })

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
        - link "知识图谱" [ref=e18] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=e19]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=e20] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=e21]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=e22] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=e23]: ⬡
          - text: 资产自查
      - generic [ref=e24]:
        - paragraph [ref=e25]: 协作
        - link "任务轨迹" [ref=e26] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=e27]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=e28] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=e29]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=e30] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=e31]: ▤
          - text: 证据报告
      - generic [ref=e32]:
        - paragraph [ref=e33]: 系统
        - link "运行状态" [ref=e34] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=e35]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=e36] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=e37]: ◎
          - text: 会话与权限
    - generic [ref=e38]:
      - paragraph [ref=e39]: 可追溯的事实清晰的判断边界
      - text: AI 安全知识情报系统
      - code [ref=e40]: READ · VERIFY · CONNECT
  - generic [ref=e41]:
    - banner [ref=e42]:
      - generic [ref=e43]:
        - generic [aria-hidden] [ref=e44]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=e45]: /
        - text: 来源监测
      - generic [ref=e46]:
        - text: 数据模式
        - strong [ref=e47]: 真实 / Live
    - main [ref=e48]:
      - generic [ref=e49]:
        - generic [ref=e50]:
          - paragraph [ref=e51]: COLLECTION / SOURCES
          - heading "来源与采集" [level=1] [ref=e52]: 来源与采集_
          - paragraph [ref=e53]: 区分来源覆盖、实际接通与采集时效。
        - button "刷新状态" [ref=e54] [cursor=pointer]:
          - generic [aria-hidden] [ref=e55]: ↻
          - text: 刷新状态
      - generic [ref=e56]:
        - generic [ref=e57]:
          - generic [ref=e58]: FIXED SOURCES / 有界调度
          - paragraph [ref=e59]: 仅管理两个固定公开来源。任务状态读取PG，不代表整个来源覆盖、持续在线或监控总量。
          - generic [ref=e60]: 真实 / Live · 模式来自当前会话
        - generic [ref=e61]:
          - region [ref=e62]:
            - generic [ref=e64]:
              - paragraph [ref=e65]: COLLECT / 固定来源
              - heading "提交采集轮次" [level=2] [ref=e66]
            - generic [ref=e67]:
              - generic [ref=e68]:
                - strong [ref=e69]: NVD · Ollama
                - paragraph [ref=e70]: 固定Ollama关键词；每个任务处理一页。
                - code [ref=e71]: nvd_ollama
              - generic [ref=e72]:
                - strong [ref=e73]: vLLM · 厂商公告
                - paragraph [ref=e74]: 固定官方仓库公开公告；服务端处理分页游标。
                - code [ref=e75]: vllm_vendor
            - form "固定来源采集" [ref=e76]:
              - generic [ref=e77]:
                - text: 固定来源
                - combobox "固定来源" [ref=e78]:
                  - option "NVD · Ollama" [selected]
                  - option "vLLM · 厂商公告"
              - generic [ref=e79]:
                - generic [ref=e80]:
                  - text: 采集流
                  - combobox "采集流" [ref=e81]:
                    - option "实时流 / live" [selected]
                    - option "回补流 / backfill"
                - generic [ref=e82]:
                  - text: 本轮页上限
                  - spinbutton "本轮页上限" [ref=e83]: "5"
              - generic [ref=e84]:
                - text: 观察窗口截止（含时区）
                - textbox "观察窗口截止（含时区）" [ref=e85]: 2026-10-15T15:56:50+08:00
              - paragraph [ref=e86]: 窗口是本轮观察标识，不保证上游快照或完整时间过滤。202只表示PG受理，不表示来源采完。
              - button "提交本轮采集" [ref=e87] [cursor=pointer]
          - region [ref=e88]:
            - generic [ref=e89]:
              - generic [ref=e90]:
                - paragraph [ref=e91]: JOB / PG单页任务
                - heading "任务状态查询" [level=2] [ref=e92]
              - generic [ref=e93]: 手动刷新
            - form "查询单页任务" [ref=e94]:
              - generic [ref=e95]:
                - text: 任务标识
                - textbox "任务标识" [ref=e96]:
                  - /placeholder: 输入已保存的job UUID
              - button "查询 / 刷新任务" [disabled] [ref=e97]
              - paragraph [ref=e98]: 保存任务标识可在返回本页后重新查询。此处没有任务历史、全来源计数或自动轮询。
            - generic [ref=e99]:
              - heading "尚未查询任务" [level=3] [ref=e100]
              - paragraph [ref=e101]: 提交一轮取得任务标识，或输入已有标识查询。尚未查询不等于没有任务。
      - generic [ref=e102]:
        - generic [ref=e103]: 环境 test
        - generic [ref=e104]: 版本 0.1.0
```

# Test source

```ts
  1  | import fs from "node:fs/promises";
  2  | import process from "node:process";
  3  | import { expect, test } from "@playwright/test";
  4  | 
  5  | test("R17 actual administrator submits one bounded vendor page and reads PG status", async ({ page }, testInfo) => {
  6  |   const username = process.env.DIANZI_E2E_USERNAME;
  7  |   const password = process.env.DIANZI_E2E_PASSWORD;
  8  |   if (!username || !password) throw new Error("isolated browser identity unavailable");
  9  |   await page.setViewportSize({ width: 1366, height: 900 });
  10 |   await page.goto("/#session");
  11 |   await page.getByLabel("用户名", { exact: true }).fill(`${username}-r04-admin`);
  12 |   await page.getByLabel("密码", { exact: true }).fill(password);
  13 |   await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  14 |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  15 |   await page.goto("/#sources");
  16 |   await expect(page.getByRole("heading", { name: "提交采集轮次", exact: true })).toBeVisible();
> 17 |   await page.getByLabel("固定来源", { exact: true }).selectOption("vllm_vendor");
     |                                                  ^ Error: locator.selectOption: Test timeout of 60000ms exceeded.
  18 |   await page.getByLabel("本轮页上限", { exact: true }).fill("1");
  19 |   await page.getByLabel("观察窗口截止（含时区）", { exact: true }).fill(new Date(Date.now() - 1000).toISOString());
  20 |   const receipt = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/sources/vllm_vendor/collect"));
  21 |   await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  22 |   const submitted = await receipt;
  23 |   expect(submitted.status()).toBe(202);
  24 |   const first: unknown = await submitted.json();
  25 |   await fs.writeFile(testInfo.outputPath("actual_submission.json"), JSON.stringify({ observed_at: new Date().toISOString(), body: first }, null, 2));
  26 |   await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  27 |   await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toBeVisible();
  28 |   const readouts: unknown[] = [];
  29 |   await expect(async () => {
  30 |     const response = page.waitForResponse((result) => result.request().method() === "GET" && /\/jobs\/[a-f0-9-]{36}$/.test(result.url()));
  31 |     await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  32 |     const result = await response;
  33 |     expect(result.status()).toBe(200);
  34 |     const body: unknown = await result.json();
  35 |     readouts.push({ observed_at: new Date().toISOString(), body });
  36 |     await expect(page.getByRole("article", { name: "当前单页任务", exact: true }).getByRole("heading")).toHaveText(/^(部分完成|本页处理完成)$/);
  37 |   }).toPass({ timeout: 45_000, intervals: [7000] });
  38 |   await fs.writeFile(testInfo.outputPath("actual_job_observations.json"), JSON.stringify(readouts, null, 2));
  39 |   await expect(page.getByText(/仅本页任务成功|本轮页数上限已到/)).toBeVisible();
  40 |   await page.screenshot({ path: testInfo.outputPath("real-source-workspace-1366.png"), fullPage: true });
  41 |   await page.goto("/#session");
  42 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  43 |   await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeVisible();
  44 | });
  45 | 
```