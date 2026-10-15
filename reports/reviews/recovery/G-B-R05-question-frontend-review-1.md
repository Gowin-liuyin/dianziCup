# G-B / R05 单事件问答前端独立初审（含同批等待预算复验）

本次改动作用：把已登录用户的单事件 library 提问接入实际前端客户端，按冻结 DTO 展示完整回答、三类结论、限制、时效和固定修订引用。未知提交保留原正文与请求键，GET 已存回答不编造事件绑定；同批增量仅把问答 POST 的等待预算设为有界 90 秒。

审查结论：**Ship，仅本问答前端批次。** 首轮确认的 Must 1 已在新冻结版本定向关闭；没有开放 Must/Should/Nice finding。整 R05、R17、T31、T43、G-B 和真实端到端验收均不由本报告判为 accepted，状态文件未改。

- reviewer：`/root/r05_question_frontend_independent_review`，未参与本批实现；应用 [Ponytail review 5.2.0](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)。审查与测试均在自己的 worktree 执行，未在作者 worktree 修改或签通过。
- 记录时间：**2026-10-15T17:15:55+08:00**；时区 Asia/Shanghai；命令分别记录带秒 `+08:00` 的起止时间。
- 基线：`a1c703ad7f885767055f3a3fa1071cc8b68110dc`。
- 首轮目标：`ebbdc9a3c687a1da460de78c6bf825ac6a01363d`；tree：`5ab7c88e54e8da162e81367c9b0d2cdef18caa04`。
- 最终目标：**`a0a94f1007dfdb1811df327ca2f931034af33a2e`**；tree：**`163295b004bd7cab7138017d1876eea5e70f12ea`**。该增量父提交为首轮目标，由主控明确追加本批审查范围；独立分支仅 `merge --ff-only` 到该冻结提交，无 reviewer 业务补丁。
- 分支：`codex/r05-question-frontend-independent-review-1`；worktree：`D:/dianzi-wt-r05-question-frontend-independent-review-1`。最后 `git status --porcelain` 为空。
- 原始证据根目录：[recovery_r05_question_frontend_review_1_20261015](../../runs/recovery_r05_question_frontend_review_1_20261015/)；[manifest.json](../../runs/recovery_r05_question_frontend_review_1_20261015/manifest.json) 绑定完整 SHA/tree、各命令源码版本和 13 文件 SHA256；[final_scope.json](../../runs/recovery_r05_question_frontend_review_1_20261015/final_scope.json) 与 [business.diff](../../runs/recovery_r05_question_frontend_review_1_20261015/business.diff) 保存范围。

## 范围、合同与前置

读了 AGENTS、00 执行索引、11 恢复计划、12 恢复 R05/R17 卡、T31/T43、03 数据合同、04 工作流、05 API、09 运维、CR-R04/CR-R05、冻结任务状态及交接；R05/R17 原状态是 in_progress/partial，整卡验证 not_run，已有组件证据不能替代本批复跑。核对了目标提交 `backend/src/ai_intel/api/question_contracts.py`、其 `CitationProjection` 和公共 v2 的 Citation/QAAnswer/AskRequest/AskResult 及正负样例。

请求中指定的 `contracts/api/v2/*` 在实际冻结仓库不存在；`rg` 实际定位到 `contracts/schemas/public_api_v2.json` 与 `public_api_v2_examples.json`。以实际冻结合同审查，未创建或猜测第二套合同。public v2 的 task 联合和多事件上限仍保留，本批只按恢复 R05 明确支持的 library 单事件范围接线，不验收异步、多轮、多跳、资产或推荐。

首轮授权 11 个前端文件；同批 4 文件等待增量与其重叠两项，最终基线 diff 共 **13 个文件**：

1. `frontend/src/App.tsx`、`frontend/src/features/events/event-workspace.tsx`：问答路由与事件提问入口。
2. `frontend/src/api/question-client.ts`、`question-contracts.ts` 及各自 `.test.ts`：客户端、严格解析和测试。
3. `frontend/src/features/questions/question-workspace.tsx`、`.test.tsx`、`question.fixture.ts`、`questions.css`：表单、阅读状态、显式隔离夹具、布局。
4. `frontend/e2e/r05_question_workspace.spec.ts`：原作者 fixture 浏览器测试。
5. `frontend/src/api/client.ts`、`client.test.ts`：主控追加的最小有界等待参数和测试。

连接代码另外只读 App/导航、AuthProvider、fetchJson、知识客户端/证据检视、状态组件、AmbientBackdrop、全局 CSS。未改业务、公共合同、认证、锁文件、金标、阈值、计分分母或状态；只写本报告和自有 raw 目录。未 push、未提交 reviewer 补丁、未新建聊天、未读 `.env` 或附件 KEYS；没有付费模型 API 调用。预计负载按本批单用户单事件同步回答、重复点击、并发离页/换会话审查；不据此确认生产并发容量。

## Must fix 的首轮红例与关闭

1. **12 秒完成的合法回答被 10 秒客户端计时器丢弃（已关闭）**
   - **具体位置：**首轮 `frontend/src/api/question-client.ts:L12` 直接继承 `frontend/src/api/client.ts:L84` 的 10,000 毫秒预算；生成客户端 `backend/src/ai_intel/infrastructure/models/generation.py:L76` 默认总预算 60 秒，冷模型/检索/有限修复可能越过 10 秒。
   - **触发与影响：**自拟 NEG01 通过隔离浏览器真实等待 12 秒才返回合同完整的 completed 回答，期望页面显示完整回答。首轮 16 秒断言失败，页面停在“提交结果未确认”，没有答案。幂等保护仍有效，但正常预算内完成的同步回答无法直接交付用户，用户须另行同 key 重试。
   - **最小修复：**公共 fetchJson 增加可选、整数且 1..120000 毫秒的参数，保留默认 10 秒；仅问答 POST 显式 90 秒。CSRF、GET、健康、认证、来源和知识读接口不传该参数。
   - **首轮证据：**[e2e_negative.log](../../runs/recovery_r05_question_frontend_review_1_20261015/e2e_negative.log)、[e2e_negative.json](../../runs/recovery_r05_question_frontend_review_1_20261015/e2e_negative.json) 和 `e2e_negative_artifacts/independent_negative-NEG01-76548-onds-must-remain-observable/error-context.md` 完整保留：7 项中 6 passed、1 failed、0 skip，exit 1。没有删断言、改阈值或把失败改 skip。
   - **复验：**最终 SHA 原样 NEG01 在 12.7 秒显示答案；TIME01 浏览器时钟检查 10 秒仍等待、90 秒显示未知、重试 body/key 完全一致；TIME02/TIME03 证实 CSRF/GET 仍 10 秒；TIME04 外部离页 abort 不恢复迟到答案。11/11 独立浏览器例通过、exit 0；[e2e_recheck.json](../../runs/recovery_r05_question_frontend_review_1_20261015/e2e_recheck.json)。90 秒边界使用浏览器虚拟时钟，只验证控制逻辑，不计作真实模型耗时或性能达标。

未发现另一条可具体触发且属于本批的阻断缺陷。非阻断外观偏好未列 finding，未要求作者循环改样式。

## 实际验证命令与结果

Node `v24.13.1`、npm `11.8.0`、Playwright `1.64.1`。独立 WT 先实际执行 `npm ci --ignore-scripts --no-audit --no-fund`，exit 0、299 packages，锁未改。下列 npm/Playwright cwd 均为该独立 WT 的 `frontend`；命令通过自有 `run_command.ps1` 执行，每项 `<label>.command.json` 保存完整 executable/arguments/cwd/开始结束/退出码，`manifest.json` 绑定当次 SHA；没有用原作者自检数量替代复跑。

| 源码 | 命令（真实参数） | 2026-10-15 起止 +08:00 | 退出码与数量 | raw label |
|---|---|---|---|---|
| 首轮 ebbdc9a | `npm.cmd run test -- --reporter=json --outputFile=D:/dianzi/reports/runs/recovery_r05_question_frontend_review_1_20261015/vitest_original.json` | 17:01:32–17:01:48 | 0；17 文件，249/249 passed，0 failed/skip；问答 71 项 | `vitest_original` |
| 首轮 ebbdc9a | `npm.cmd run typecheck` | 17:01:32–17:01:35 | 0 | `typecheck` |
| 首轮 ebbdc9a | `npm.cmd run lint` | 17:01:32–17:01:38 | 0 | `lint` |
| 首轮 ebbdc9a | `npm.cmd run build` | 17:02:14–17:02:18 | 0；45 modules | `build` |
| 首轮 ebbdc9a | `node.exe node_modules/@playwright/test/cli.js test --config=D:/dianzi/reports/runs/recovery_r05_question_frontend_review_1_20261015/playwright_original.config.cjs r05_question_workspace.spec.ts` | 17:02:14–17:02:21 | 0；9/9 fixture passed，0 failed/skip | `e2e_original` |
| 首轮 ebbdc9a | 同 CLI，`--config=…/playwright_negative.config.cjs independent_negative.spec.ts` | 17:04:18–17:04:43 | **1；6 passed、1 failed、0 skip** | `e2e_negative` |
| 最终 a0a94f1 | `npm.cmd run test -- --reporter=json --outputFile=D:/dianzi/reports/runs/recovery_r05_question_frontend_review_1_20261015/vitest_final.json` | 17:06:45–17:07:04 | 0；17 文件，254/254 passed，0 failed/skip；问答 72 项，另有公共 client 预算测试 | `vitest_final` |
| 最终 a0a94f1 | `npm.cmd run typecheck` | 17:06:44–17:06:48 | 0 | `typecheck_final` |
| 最终 a0a94f1 | `npm.cmd run lint` | 17:06:45–17:06:48 | 0 | `lint_final` |
| 最终 a0a94f1 | `npm.cmd run build` | 17:07:19–17:07:23 | 0；45 modules | `build_final` |
| 最终 a0a94f1 | 同 CLI，`--config=…/playwright_recheck.config.cjs independent_negative.spec.ts independent_timeout.spec.ts` | 17:06:45–17:07:08 | 0；11/11 独立 fixture passed，0 failed/skip | `e2e_recheck` |
| 最终 a0a94f1 | 同 CLI，`--config=…/playwright_final.config.cjs r05_question_workspace.spec.ts` | 17:08:12–17:08:18 | 0；原 9/9 fixture 再次通过，0 failed/skip | `e2e_final` |

所有浏览器检查设置 `PLAYWRIGHT_BROWSERS_PATH=C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248`，未下载浏览器。每份 config 固定独占 loopback 端口（25317/25318/25319/25320）、1 worker、不复用已有 server，截图输出只到自有 raw 目录；全部 `/v1/**` 显式 fixture 路由，不访问真实模型后端。原配置输出目录没有被写入。失败不留自动截图、trace 或 video；仅显式无秘密 fixture 截图。

最终实际 `git diff --check a1c703ad7f885767055f3a3fa1071cc8b68110dc a0a94f1007dfdb1811df327ca2f931034af33a2e -- frontend` exit 0；[business_diff_check.log](../../runs/recovery_r05_question_frontend_review_1_20261015/business_diff_check.log) 为空。build 对受跟踪 tsbuildinfo 的自生改动由 reviewer 只恢复自己 WT 的该文件；最终无业务 diff。探索路径/glob、CLI help 和首次 tree 参数错误分别记在 [exploratory_notes.md](../../runs/recovery_r05_question_frontend_review_1_20261015/exploratory_notes.md)，均未冒充业务测试结果。

## CBM 图与实际源码交叉核对

实际工具是官方 portable WSL `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`；实际 `cli --help` exit 0，命令日志 `cbm_help`。隔离 cache 为 `/tmp/dianzi-cbm-review-r05-questions-ui-20261015`；仅索引 `/mnt/d/dianzi-wt-r05-question-frontend-independent-review-1/frontend/src`，不索引仓库外附件、`.env`、秘密或 holdout。

完整参数形式：`wsl.exe -d Ubuntu-22.04 -u root --exec /usr/bin/env CBM_CACHE_DIR=/tmp/dianzi-cbm-review-r05-questions-ui-20261015 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json <tool> <args>`。

| tool / 实际 args | 结果 | 日志 |
|---|---|---|
| `index_repository --repo-path /mnt/d/dianzi-wt-r05-question-frontend-independent-review-1/frontend/src --name r05-question-ui-review --mode fast` | 原/最终均 exit 0，232 nodes、822 edges，partial/unusable/skipped 各 0；16 个文件按 fast-pattern 未索引 | `cbm_index`、`cbm_index_final` |
| `get_graph_schema --project r05-question-ui-review` | exit 0，11 node labels、10 edge types | `cbm_schema` |
| `trace_path --project r05-question-ui-review --function-name fetchJson --direction both --include-tests true` | 原/最终 exit 0，5 callees、26 callers | `cbm_trace_fetchJson`、`cbm_trace_fetchJson_final` |
| 同 trace，`--function-name submitQuestion` | exit 0，18 callees、4 callers | `cbm_trace_submitQuestion` |

图显示 `QuestionWorkspace → AuthenticatedQuestions/runRequest → submitQuestion/getAnswer → fetchJson` 及 `submitQuestion → getCsrfToken → fetchJson`。用 `rg` 与完整源码确认：只有 `question-client.ts:L12` 传第 5 参数 `90_000`，其余 CSRF/GET/认证/健康/来源/知识调用保留默认；`submitQuestion:L9-L11` CSRF 前后都复核会话/abort。图不表示参数值或业务真实性，fast 模式也未覆盖测试；上述判断以源码与实际 254 项回归、独立浏览器时钟/网络行为补证，不据图声称所有 test 已索引。

## 可观察边界、可用性与评分证据

| 边界 | 实际核对与证据 |
|---|---|
| 输入与 DTO | strict TypeScript 开启；只提交 question/library/恰一 event UUID；4096 Unicode code points、空/空白/NUL/孤立 surrogate、unsafe key 受检。completed DTO 字段精确，extra/null/错枚举/逆时间/负或非整数耗时、事实无 support、支持 ID 不在 citation、重复 citation、危险 URI 均拒绝。自拟 NEG03 nested extra 不显示答案；GET 核对返回 answer_id。 |
| 写入和重放 | 实际 fetchJson `credentials:include`、no-store；POST CSRF 与 Idempotency-Key。请求锁和同步 inFlight 防双击/并发读取；未知网络与 90 秒超时保留相同 body/key，重试无自动写入；明确开始新问题才生成新 key。原 fixture 及 TIME01 断言实际请求数量和等值。 |
| auth fencing | App `L152/L195` 的 user/tenant/permission_version/data_mode/sessionGeneration/hash key 卸载私有问答；runRequest `L78` 复核 mounted/abort/generation；CSRF 后旧会话不会 POST。原测试覆盖重新验证、401、logout 迟到回答；NEG02 切换事件不产生旧事件 POST，TIME04 离页后不恢复答案。 |
| 引用和来源 | 固定 evidence/revision 两 UUID 显示并生成同页已确认 POST 的内部链接；键盘 Enter 聚焦 citation，原 E2E 实际打开正确修订检视。GET 没有 event_id：无可信 POST 绑定时不造内部 event 深链；NEG04 刷新后读取仍无该链接。HTTP(S) 合同可解析，但只 HTTPS 生成 noopener/noreferrer 外链，HTTP 显式不可打开；javascript/data/credentials/backslash 等拒绝。 |
| 模式、时效与错误 | answer data_mode 必须与会话一致，fixture 各处显式标注。空/loading、stale/unknown 与 limitations 明示，不能推论无风险；401 清身份，403 权限/CSRF、409 处理中/失败/冲突、429 容量、503 缺模型/证据/变化/核验等说明分开。错误 raw message 不显示；没有假成功或模板后备。 |
| HTML 与私有持久化 | React 文本渲染 answer/claims/quote/locator，没有 dangerouslySetInnerHTML；NEG05 script/img 字样保留为文本且无 DOM/执行。正文不进入 URL/localStorage/sessionStorage；刷新后只能凭 answer UUID 查服务器，不把前端存储作为业务真相。 |
| 桌面/390 与键盘 | 两轮原 E2E 共用实际 1280 和 390 viewport；长正文/引文/locator 和 HTML 负载仍 `scrollWidth <= innerWidth`，表单与操作可用。实际截图人工查看（Agent visual QA），无裁切的业务文本；citation Enter 聚焦、证据检视聚焦及未知重试 Enter 均断言。没有另做真人 manual 验收。 |
| 背景与 reduced-motion | 暗色青绿终端风沿用已有中文 shell；NEG07 真实 1.2 秒前后 CSS transform 不同，并显式截图看到拓扑；reduced-motion 后 animationName=none、transform 静止。原 390 reduced-motion 断言通过。不把装饰动画当业务进度；原生隐藏窗口暂停尚无真人实测。 |

[F3/T31-C01、C04、C05 的前端部分]：回答/结论/支持/固定修订/限制与异常路径有 fixture 证据；不证明模型语义支持、来源真实性、T31-C02 多轮或多跳准确率。[D2/R17]：桌面/窄屏/长文本/键盘和状态有独立浏览器与截图证据，仅此切片。[P3]：展示完整 latency_milliseconds，90 秒等待参数只是控制预算，未测真实完整延迟/P95/准确率。[A1]：无伪 Agent 台词，未验 Agent 能力。

## 未测、偏差和交接

- unit/contract/frontend：本批 fixture 与静态检查 passed；e2e：最终原 9 + 独立 11 passed。首轮 red 保留，不重写为通过。
- integration：**not_run**，没有真实 PostgreSQL/认证/问答服务串联测试；live：**not_run / blocked_live 于本审查范围**，全部问答响应来自显式 fixture，不作为 G-B 过门材料；manual：**not_run**，截图 Agent QA 不替代真人。
- 未验：真实来源/语义模型/重排/PG 问答完整链、真实跨租户后端 ACL、语义引用支持、服务端 90 秒内预算可行性、真实性能、多轮/多跳/异步调查/刷新任务恢复、持续运行、FOFA。fixture 不替代上述缺口，外部调用费未由本批测得。
- 原 `contracts/api/v2/*` 路径与实际冻结路径的差异已记录；公共合同未改。初始 11 文件外追加共享 client 2 个独立文件，是主控明确冻结的同批有界增量；前端 shared timeout 不改变认证或 API schema。原 T 卡六类验收与跨阶段检查点继续保留。
- 下一步建议：主控整合最终冻结前端与独立后端候选，跑真实登录→单事件提问→完整回答→固定修订证据链，并单独记录完整真实延迟、模型调用/费用、fixture 拒绝和 ACL 结果；由阶段新 reviewer 验 G-B。无需继续本批外观改动。

**Verdict: Ship（仅 `a0a94f1007dfdb1811df327ca2f931034af33a2e` 本前端批次）。**

**Not checked:** 真实问答/API/数据库/模型端到端、真人 manual 与原生隐藏页暂停、真实延迟/准确率、完整 R05/R17/G-B。


