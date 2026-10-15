What this change does: 本次最小修复让“跳到主要内容”只移动焦点，保留当前研究页的 hash 和标题；新增事件页、来源页的组件与真实键盘回归。

# G-A / R17 UI 准备切片 P2 定向复核

结论：**初审 Must fix 1 / P2 已闭合，定向复核 `passed`。仅该 UI 准备切片可继续使用，未签整 R17、整 T40–T44 或 G-A。**本 reviewer 不修改全局任务状态或 accepted 字段，不实现业务、不 commit/push。

审查者 `/root/hacker_ui_independent_review`，与初审相同、未参与实现。开始 `2026-10-15T11:14:25+08:00`，结束见文末。已检查新固定树 AGENTS、00、R17 原任务卡和 task_state，沿用初审已读取且本 diff 未改变的 03/05/06/11/12 与 T40–T43 合同；继续采用 Ponytail 5.2.0 review 的具体输入、真实调用、最小修复原则。

## 固定输入与改动边界

基线 `cafbe7f7c451479ce38b0674de0cf71aa44154b2`；修复源码 `bb3a3b3d4b3f40c88633adba1ae131db03bb2480`；证据提交及本次审查 HEAD `90da778c8054ae2127248fbfb05870345293519b`；完整 tree `9a8f22d3e0c30484cefb20d68f05f9b029497fa1`。本轮通过 managed worktree 工具新建独立固定树 `C:/Users/yinha/.codex/worktrees/hacker-ui-skip-recheck/dianzi`，初始和收尾 `git status --porcelain` 均为空；未审作者 R04 活动源。

源码差异只有三个文件：

- `frontend/src/App.tsx:156`：skip link 的 click 事件 `preventDefault()`，随后 focus `#main-content`；保留原可访问链接和 `main tabIndex=-1`，没有改变全局 hash 解析器。
- `frontend/src/App.test.tsx:52`：新增 events/sources 两例，检查焦点、hash、当前标题和运行概览未出现。
- `frontend/e2e/r17_skip_link.spec.ts:4`：新增两匿名真实键盘流程，包括 Tab → skip link → Enter → main → Tab → 刷新按钮。

没有新依赖、router、接口、认证或业务真值计算。`preserved_baseline.diff` 为空：auth/client/navigation/CSS/package/lock 与原 6 real browser 文件未改变，旧回归未删、阈值/分母/金标未改。作者 90da 的报告/日志仅用于定位；本轮测试使用新的 WT 和新的原始日志。

## 复现与修复验证

初审固定 `00a5c99` 的 N08 实際观察为：`/#events` 按 skip Enter 后 hash `#main-content`、h1 `运行概览_`、main_focused=true。初审原始失败报告保留在 `recovery_hacker_ui_review_1_20261015/independent_negative_second_report.json`，没有改写为通过。

本轮在新固定树、新端口 **25303** 独立执行 Chromium 1248：

| 输入 | 实际断言与结果 |
|---|---|
| 打开 `/#events`，按 Tab → Enter | skip link 首先获得焦点；Enter 后 main 获得焦点、URL 仍以 `#events` 结束、h1 仍为“情报工作区”、运行概览标题不存在；随后 Tab 聚焦刷新按钮。passed |
| 打开 `/#sources`，按 Tab → Enter | main 获得焦点、URL 仍以 `#sources` 结束、h1 仍为“来源与采集”、运行概览标题不存在；随后 Tab 聚焦刷新按钮。passed |

这两例真实执行，没有用 `focus()` 代替首次 Tab，也没有人工派发 hashchange 或只检查“无报错”。组件点击回归另外验证同一可观察行为。没有新 must/should-fix 发现。

## 实际命令与原始证据

证据根目录 `D:/dianzi/reports/runs/recovery_hacker_ui_review_1_20261015/recheck_20261015`。每项 `*.command.json` 保存实际 cwd、参数、秒级 +08 起止和退出码；表中前端命令 cwd 均为新固定树 `/frontend`。

| 命令 | +08:00 开始–结束 | 真实结果 / 日志 |
|---|---|---|
| `npm.cmd ci` | 11:15:42–11:15:55 | exit0；原锁安装；`npm_ci.stdout.log`/stderr/command |
| `npm.cmd run test -- --run src/App.test.tsx src/app/workspace-navigation.test.ts` | 11:17:18–11:17:21 | exit0；2 files/21 passed/0 failed/0 skipped；`targeted.*` |
| `npm.cmd run test` | 11:17:21–11:17:28 | exit0；7 files/64 passed/0 failed/0 skipped，原62+新增2；`test.*` |
| `npm.cmd run lint` | 11:17:28–11:17:34 | exit0；`lint.*` |
| `npm.cmd run typecheck` | 11:17:34–11:17:36 | exit0；`typecheck.*` |
| `npm.cmd run build` | 11:17:36–11:17:39 | exit0；`build.*` |
| `node node_modules/@playwright/test/cli.js test --reporter=json --output=<本run>/anonymous_e2e_artifacts r17_skip_link.spec.ts` | 11:17:30–11:17:35 | exit0；expected2/skipped0/unexpected0/flaky0、errors=[]、两例 retry0；`anonymous_e2e.json` 与 `anonymous_results_summary.json` |
| `git diff --check cafbe7f7 90da778c -- frontend/src frontend/e2e` | 11:18:11–11:18:11 | exit0；`source_diff_check.*`；不改作者原始日志 EOF 字节或扩大 ignore |

21 targeted、64 full 和2 browser有重叠，不相加为独立覆盖数。匿名浏览器使用仓库原 Playwright 配置、`DIANZI_E2E_FRONTEND_URL=http://127.0.0.1:25303`、既有非秘密 browser cache；只 GET，没有账号/秘密注入或 POST。trace/video/自动截图 off，无截图或录像；未启动下载、改锁或读 DPAPI。

API proxy 指向当时 28000，测试在该受控段到期前结束，但两例只检验匿名前端键盘行为，**没有断言后台就绪或认证成功，不能计为 auth/health live 或真实来源业务通过**。原初审固定 00a 的真实六例仍是其原版本证据，本轮未将它们改写成新版本的 fresh live 通过。未需要延长后台，也未操作 API、数据库、容器、worker、scheduler 或作者服务。

## CBM 与调用链核对

使用初审已读取 help 的官方 portable CBM v0.11.0，唯一 root 为新固定树 `frontend/src`，独立仓外 cache `/tmp/dianzi-cbm-hacker-ui-skip-recheck-20261015`、persistence=false，未索引 secrets/holdout/reports；fast 模式排除6个 test，测试通过实际执行另核。

- 本轮独立 index exit0，79 nodes/218 edges、skipped0/partial0/unusable0；实际时间见 `cbm_index.command.json`。
- schema `11:16:44–11:16:47` exit0，Function 全表 `11:16:47–11:16:50` exit0，使用实际 project-prefixed qualified name。
- `hacker-ui-skip-recheck.App.Workbench` outbound trace `11:16:50–11:16:53` exit0，23 callee；JSON args-file、schema与原始结果均保留。trace 仍到 readWorkspacePage、AuthProvider context、getLiveness/getReadiness/client，端点调用没有变化。
- `source_trace_rg.log` 对齐 App.tsx:156 原生 preventDefault/focus、main ID 与 hashchange；native DOM 方法是否出现图边不作为行为证明，真实键盘断言补足该部分。没有以“无边”推断“无入口”。

## 保留限制、评分边界与交接

初审的动态图像变化、reduced-motion停止、390px说明可读与已测auth边界结论仍按原版本与实际范围保留；本修复没有触及这些源码。本轮没有重复全部负例、完整真实登录六例、正式性能、真实情报/证据/图谱/问答/资产/任务/推荐/报告操作。

**原生 hidden 暂停仍是 manual 缺口，未通过。**没有以组件派发事件或本轮匿名键盘测试代替原生 visibility 验证，也没有再次扩大无进展探针。准备页面仍然待接通，R04–R16业务前置、原T41/T42/T43及R17剩余验收继续保留。D2只追加此键盘可用性证据，F1/F2/F3不追加业务得分，不判整平台完成。

`npm ci` 的既有依赖漏洞仍按初审和 CR-R10 处理；本轮未批准或执行主版本升级。build 改写已跟踪 `frontend/tsconfig.tsbuildinfo` 后，reviewer恢复固定 HEAD 原始 bytes，哈希见 `generated_restore.json`；没有业务修改。Playwright 自动收尾，`final_state.json` 于 `11:19:11+08:00` 记录 25303 无 listener、固定 HEAD/tree 不变、status 空。独立缓存只保留登记，没有删除。

Verdict: Ship this fix. 仅初审 P2 的最小修复和 UI 准备切片有限范围通过；全局登记/集成由主控管理，整阶段须另独立审查。

报告结束：2026-10-15T11:20:53.6152086+08:00。精确 artifact 清单见本 run `artifact_manifest.json`。
