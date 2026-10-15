What this change does: 新固定候选在 claim 引用中带回已知 revision，提交新筛选时清除旧详情/证据，并保留非 JSON HTTP 错误的真实状态。产品成功但响应不是 JSON 时仍显示合同错误，不显示上游原始正文。

**结论：本 R04/R17 前端准备与三项修复切片独立复核 passed，初审问题 1、2 关闭；CR-R10 当前依赖组合技术结论继续 passed。** 可由 root 按这个明确切片登记验收。本报告不接受整 R04/R17/T40/T41/G-A/G-B，不签真实来源链或阶段 push；整体实现和 live 缺口仍 partial/blocked。

审查者仍为 `/root/r04_frontend_independent_review`，未参与实现。初审 [G-B-R04-frontend-review-1.md](G-B-R04-frontend-review-1.md) 的固定 `0b983349` needs_changes、5 负例 2 过/3 失败与截图全部保留。新 WT `C:/Users/yinha/.codex/worktrees/recovery-r04-frontend-recheck/dianzi`，分支 `codex/recovery-r04-frontend-recheck`；固定候选 `7f9b6f14e3c7c5ff451fab183f959a11d8daf114`，tree `f2f84f030f4e0ed4016b0800963afb0b92658ca1`。开始 2026-10-15T12:15:34+08:00，固定树检查结束 12:19:41+08:00；报告随后落盘。初末 status clean。

复核采用新版 Ponytail Review 5.2、初审已读冻结合同与原卡。只审 `git diff 5e0699d..7f9b6f1 -- frontend/src` 的四文件：`api/client.ts`、`api/client.test.ts`、`features/events/event-workspace.tsx`、同名测试；`git diff 0b983349..7f9b6f1 -- frontend` 也只有这四个文件。中间网络/游标提交不在本审查范围，不能拿这个候选整体 SHA 为其他模块签字。本轮只写报告/run，未改业务、原测试、阈值、分母、skip、全局状态或 Git 提交/push。

| 初审问题/补充 | 新证据与结果 | 结论 |
|---|---|---|
| 1：claim A 引用显示版本 B | 实际点击 claim 的 href 现在包含 `/revision/...0002`；同 span 响应 B `...0004` 被拒，错误可见，blockquote=0；维度版本拒绝对照仍通过 | closed |
| 2：新 filter 403/503 留旧详情与引用 | 相同原步骤：先加载旧事件/证据，再检索新 scope。403 和 503 下旧详情标题、claim、quote 各从 1 变 0；hash 回到 `#events`，证据栏仅“选择原文引用” | closed |
| 旧非 JSON HTTP 错误语义 | 精确固定 client.ts 内存编译的独立 8 例：空 body/HTML 各测 401/403/503，status/code/retryable 正确，公共消息不含合成私有上游正文；成功非 JSON 仍 502，合法 JSON 不改写 | passed |
| 加载/错误焦点 | 原独立例仍确认 evidence loading 与 503 不抢 citation 焦点；成功引用 desktop/mobile focus/viewport 检查仍过 | passed |

5 个原独立浏览器案例这次 **5 passed/0 failed/0 skipped，exit0**。只将错版本案例改为等待期望的合同错误、检测 quote 不出现；未改变输入 A/B、业务判据或把原失败改 skip。筛选 403/503 两个原案例仍用相同触发和旧内容计数；截图文件沿用原可对照 basename，目录已隔离，文件名中的 `retained` 是原探针名字，不表示本次仍残留。

实际运行证据在 `reports/runs/recovery_r04_frontend_review_1_recheck_20261015/`，完整 command、cwd、固定 SHA、秒级时间、child exit 与 stdout/stderr 均保留。以下时间为 +08:00。

| 实际命令/检查 | 起止 | 结果 |
|---|---|---|
| `npm.cmd ci` | 12:15:36–12:15:41 | exit0，299 包安装 |
| `node node_modules/vitest/vitest.mjs run --reporter=default --reporter=junit --outputFile.junit=.../test.xml` | 12:16:11–12:16:21 | exit0，10 文件、115 passed、0 failure/error/skip |
| `npm.cmd run lint` | 12:16:11–12:16:16 | exit0 |
| `npm.cmd run typecheck` | 12:16:10–12:16:13 | exit0 |
| `npm.cmd run build` | 12:17:08–12:17:11 | exit0，36 模块；成功构建 |
| `npm.cmd audit --json` | 12:17:08–12:17:11 | exit0；当前锁文件时点漏洞 0 |
| `node negative_browser.mjs`，25304 | 12:16:11–12:16:17 | exit0，原独立 5/5，0 skipped |
| `node shared_http_probe.mjs` | 12:17:08–12:17:08 | exit0，独立共享 HTTP 8/8，0 skipped；无外部请求 |
| Playwright `r04_fixture_contract.spec.ts r17_skip_link.spec.ts --reporter=json --output=.../e2e-artifacts`，25304 | 12:17:45–12:17:53 | exit0，4 fixture + 2 匿名键盘，6 expected/0 skipped/unexpected/flaky |
| root 安全 runner `r01_auth.spec.ts`，25305 | 12:17:08–12:17:15 | exit0，3 expected/0 skipped/unexpected/flaky；新前端 7f9，实际后端仍 0b983 |
| CBM 独立 cache index/schema/trace | 12:17:45–50、12:18:03–09 | 各 exit0，151 nodes/505 edges，9 个 fast-pattern 测试文件另由 rg/Vitest核对 |
| `node runner_config.mjs` | checked_at 12:17:09 | exit0；forks/isolate=true/maxWorkers1/fileParallelism=false/jsdom、e2e 排除仍保留 |
| `python -X utf8 source_audit.py` + diff check | checked_at 见 JSON | exit0；diff --check exit0，依赖对与497740a逐字节相同 |

`test-identity-delta.json` 对初审 108 与本次 115 使用多重集合比较，保留参数化用例同名的出现次数：**原 108 无删除，新增恰好 7**（3 个 HTTP 状态、claim 错版本、filter403/503、业务非 JSON401 清身份）。没有用去重后的名称数冒充测试总数。新增/旧单元确实重新运行，包括会话代次的迟到旧 200/401、旧 logout、撤销未确认和未认证缓存边界。root 的红 108过/6失败与第一绿错误测试文案记录未被本审覆盖或改写；本独立运行结果来自干净新 WT，不引用作者 115 结论作通过依据。

共享 HTTP 探针只在内存编译固定 client.ts，stub fetch 并检查 credentials include/cache no-store；不会调用真实网站、服务、秘密或重写业务。源改动的 try/catch 只对非成功且非 accepted status 用 `parseProblem(null,status)`，成功/已接受状态仍要求 DTO。固定公共错误不泄露原 HTML。浏览器 fixture 仍只存在 e2e/隔离探针内；产品没有 mock 成功入口或网络失败 fallback。未知时间、模型假设、维度失败和历史未核验语义保留，没有通过这三个 UI 修复改变业务事实、认证服务器撤销含义或 CSRF/Cookie。

CBM 缓存为 `/tmp/dianzi-cbm-r04-frontend-review-1-recheck-20261015`，项目 `dianzi-r04-frontend-review-1-recheck`，只索引此固定 WT/frontend/src。新 trace 仍是 Workbench→EventWorkspace→EvidenceInspector→getEvidence→fetchJson/parseEvidenceResponse，已与四文件 diff、调用点、实际点击核对，不把图中边或缺边当作测试通过。

实际查看本轮 1366×900 与 390×844（full-page）Fixture PNG、claim 版本拒绝 PNG、filter403 清旧详情 PNG、真实认证手机 PNG。新截图中 claim 错版本呈现合同错误，无 B quote；403 截图不再留旧对象，证据栏回到选择提示。手机长标识、说明与状态可读；原 fixture 4 的 503、九维、未知时间、success focus/scroll 和 reduced-motion 操作继续实际通过。样本始终显著显示 Fixture，不能算真实 PG 内容或來源 live。动态背景源码/CSS本次未改，本轮不重复初审的短窗口粗性能观察或原生 hidden 未证实探针。

新真实 auth 由 root 在受控 API-only 段 `r04_auth_0b983` 注入测试身份；本审查者独立读 JSON/receipt/测试语义并查看新截图，没有读取 DPAPI/.env/KEYS、接收凭据或保留密码输入截图。receipt 准确记录 frontend=7f9、backend=0b983、`artifact_secret_matches=[]`、trace/video/失败自动截图 off。三例再次证明登录/重载/Cookie及退出200后的匿名、键盘/390px、offline健康失败及恢复；不把后台 worker/scheduler 待观测状态改成功。实际后端尚未接 R04 路由，本轮无法也没有证明真实事件/证据投影或两源抓取到页面。

精确文件清单/字节数/SHA256 在 `artifact-manifest.json`。主要产物：`test.xml` 与 `test.*`、`negative-browser.json`/`negative-artifacts/`、`shared-http-probe.json`、`browser.*`/`e2e-artifacts/`、`real-api-auth.*`/`real-api-auth-artifacts/`、`runner-config.json`、`source-audit.json`、`test-identity-delta.json`、`fix-scope.diff`、三套 CBM 日志、`review_start.json`/`review_end.json`，以及五个可复跑审查脚本。辅助核对时一处不存在的旧 service.py 路径被 rg 拒绝，后按实际 persistence.py 路径核对；没有将该只读错误记为业务失败。本复核无业务失败/skip，也没有复用初审 GBK/浏览器路径失败标签。

最终固定 WT clean；只恢复审查者 build 生成的 tracked tsconfig.tsbuildinfo；25304 无监听并交回。root 所有 28000 API 段/25305安全 runner 由 root管理，未擅停。没有本轮业务 commit/push。root 可以登记前端准备切片及 CR-R10 兼容安全修复技术通过，然后继续真实 R04 backend/来源与业务 e2e；不要将此通过扩展成整个系统验收。

Verdict: Ship this frontend preparation/fix slice. Not checked: 尚未接通的真实情报 PG/来源链、原生 hidden 暂停、另两条旧 R17 业务浏览器预期、正式性能、完整 R04/R17/阶段验收。官方13要求/U01–U14和原卡验收门保持。
