# R05 / G-B 问答 API 与 PG 接线测试包

状态：awaiting_review（测试实现者，不是本批独立 reviewer；未自签 accepted）。测试实现 complete；当前限定 unit/contract/integration 自检 passed，基线 API 必需 key 红例保留并已在主控修复后定向复跑关闭。完整 live/人工及整卡验收仍未运行。

初始基线 `d7b6bf113f3daa24971297aa9ac867871a8df3c1`，独立分支 `codex/r05-question-api-tests`，工作树 `D:/wt/r05-api-tests`。测试代码首冻结 `af73b3e66d6f984fa0071938ff302257cae09711`，主控已合并等价测试提交。主控修复冻结 `dc014c960f19605c20e0d8e98a93e7c217f94cc6` 确认后，本分支 rebase 到该基线，仅追加测试提交 `54bd6dbb88c5aed6255b49dc485b1e327fbb7119`。作者业务提交仅包含指定测试文件；主控业务代码、公共 schema、迁移、锁、配置、progress、金标及评分分母未由本作者修改。

## 范围与输入输出

读取 AGENTS、execution_map、task_state、context_handoff、恢复 R05/R17 卡、T31、03/04/05/06 合同、`question_contracts.py` 和 `contracts/schemas/public_api_v2.json`，新基线另读 `CR-R04-R05_question_commit.md`。派发所称 `contracts/api/v2` 路径不存在，实际冻结合同在上述 schemas 路径；仅记录，不修改合同。采用最新 Ponytail 5.2 full，复用既有 `test_r05_vector_persistence.py` 的逐 test UUID schema 夹具。

输入为服务端认证 viewer 身份、指定 public 事件、非空问题、合法幂等 key；输出为可打开永久证据的 completed 回答，或明确安全问题响应与 PG pending/failed 行。默认 `create_application(settings=...)` 真正装配 PG 用户目录、会话服务、问题服务、检索器和 GenerationClient。只替换模型 IO 边界：LocalSemanticModels 使用标注为 fixture 的固定向量；NetworkGateway transport 返回合成生成/支持核验两轮 wire，让真实 GenerationClient 运行 codec、schema、attempts。结果为 fixture，不能作为真实模型、召回率或 live 能力证明。

实际 PG 仅使用 `test_dianzi_r05_pgvector_20261015`，run ID `r05_pgvector_20261015`。连接配置从 WSL root 600 私密文件读取，仅放入 pytest 子进程 env；无明文连接串写入报告、命令、日志。每 test 独立 UUID schema，夹具清理自身 schema；未重启/降级/清理共享库。

改动文件：

- `backend/tests/integration/test_r05_question_api_pg.py`：24 个 PG/API case，含两默认前缀；完成/失败及新应用读取；同 key 同体重放和异体冲突；并发与 PG pending；无已验证/当前/未撤回支持不调用生成；生成中 epoch/撤回/权限变化阻止新回答；历史 stale 投影不覆盖已保存响应；生成失败 attempts 与 fee unknown；完成前会话撤销/读权限/tenant 复鉴权；owner/tenant 404；private 事件不调用模型；模型未配置明确 503 且历史仍可读；R12 范围 422；必需 key 前置拒绝；到期 pending 及晚到 writer 的终态保护；最终认证锁内外的 logout/迁租提交顺序。
- `backend/tests/unit/test_r05_question_routes.py`：6 个 HTTP 边界 case，显式内存认证 fixture，匿名两前缀 POST/GET、CSRF 与 Origin、读权限、撤销、身份注入与安全错误投影、数据库/模型配置缺失。
- 本报告与 `reports/runs/recovery_r05_question_api_tests_20261015/` 自有日志/runner。

不做 R12/R14 全库、多轮、多跳、资产或调查扩展；不执行付费 API，不 push，不建新聊天/子 agent，不修改业务使红例通过。

## 实际命令与结果

各 `.json` 保存完整 argv、cwd、Asia/Shanghai 秒精度 +08 开始/结束、exit、基线 SHA；pytest 同名 `.xml` 给出逐例证据；`.log` 保存实际脱敏输出。下表计数不累计不同轮次。

| 日志标签 | 时间 +08 | 实际结果 |
|---|---|---|
| `unit` / `pg` | 17:10:02–17:10:06 | 选用既有 R04 WSL venv 缺 pgvector，collect exit 2；各 1 collection error，业务测试未执行，非业务失败；未 skip |
| `unit_ready` | 17:11:30–17:11:35 | 新 unit 6 + 原 question contract 7 = 13 passed，exit 0，0 skip |
| `pg_ready` | 17:11:30–17:12:14 | 初轮 20 PG case passed，exit 0，0 skip；尚未覆盖必需 key，不泛化 API 全合同通过 |
| `unit_final` | 17:13:47–17:13:51 | 13 passed，exit 0，0 skip；包含补充的无数据库 HTTP 503 |
| `regression` | 17:13:47–17:14:09 | grounded/generation/review-fixes/semantic/vector 270 passed，exit 0，0 skip（其中 vector 真 PG 11） |
| `unit_gate` | 17:13:47–17:14:26 | 默认 tests/unit 886 passed，exit 0，0 skip；原 60% 覆盖门不改，实际 66.35% |
| `pg_key_contract_red` | 17:14:57–17:15:39 | 21 case = 20 passed / 1 failed / 0 error / 0 skip，exit 1；缺 key 返回 200 而合同要求拒绝 |
| `ruff_ready` / `format` | 17:12:26 | 两新增文件 lint/format 检查 exit 0；首 `ruff` 发现 unused import/长行后仅修测试格式 |
| `mypy` | 17:12:26–17:12:44 | 82 源文件 no issues，exit 0 |
| `ruff_freeze` / `format_freeze` | 17:20:28 | af73b3e 两新增文件 lint/format exit 0，记录两个文件 SHA256 |
| `diff_windows` | 17:23:07 | Windows 原生 Git diff --check exit 0；此前两次 WSL Git 读 Windows worktree/index 产生换行误判或阻滞，停止自有只读进程并保留 -15 日志，不修改既有文件纠错 |
| `pg_fenced` | 17:29:23–17:30:10 | 主控 dc014c9 + 本包当前测试 SHA256，24 passed / 0 failed / 0 error / 0 skip，exit 0 |
| `unit_fenced` | 17:30:24–17:30:29 | 同一新基线 6 新 unit + 7 原 contract = 13 passed，exit 0，0 skip |
| `ruff_fenced` / `format_fenced` | 17:30:24 | 当前两个新增文件 lint/format exit 0，记录源文件 SHA256 |
| `secrets_packaged` | 17:34:45–17:34:46 | 83 个证据/报告文件（包括解压归档）检查，私密连接 URL/密码 0 泄漏，exit 0 |

执行 runtime 为自有 `/tmp/dianzi-r05-api-tests-20261015/venv`，通过现有 uv `sync --frozen --project /mnt/d/wt/r05-api-tests/backend` 建立，不改共享 venv。PG 与定向 fixture 命令使用 `--no-cov`；默认单元门另行实际执行，未改阈值。

可复跑入口（cwd `D:/wt/r05-api-tests`）：

```text
wsl -u root -- /tmp/dianzi-r05-api-tests-20261015/venv/bin/python /mnt/d/wt/r05-api-tests/reports/runs/recovery_r05_question_api_tests_20261015/run_evidence.py unit fresh_unit
wsl -u root -- /tmp/dianzi-r05-api-tests-20261015/venv/bin/python /mnt/d/wt/r05-api-tests/reports/runs/recovery_r05_question_api_tests_20261015/run_evidence.py pg fresh_pg
```

runner 将进入 WT backend，并把 fixture 模式、输出、实际 SHA 和 JUnit 计数写入本 run 目录；末参数必须使用新标签保留先前失败日志。pytest 私密 env 在 runner 内注入，不需打印配置或传入命令行。

平台误判诊断的原 `diff.log` 为 64,278,013 字节，完整无损保存在提交的 `diff.log.gz`（6,244,640 字节）；`large_diagnostic_archive.json` 绑定原文/归档 SHA256 和解压回环成功。原日志仍在此 WT 作为未跟踪文件保留，未覆盖或删除；提交不重复加入 733,205 行平台误判输出。该诊断不是业务/测试失败。Windows 原生检查和此前测试源码 cached diff 检查通过。

## 已复现缺口

`05_api_and_tool_contracts.md` §2 明定写接口必须有 Idempotency-Key。d7 `answering/service.py:156` 仅在 key 非 None 时校验，`:163`–`:165` 对缺失 key 创建 uuid4，导致已认证且 CSRF 正确的 POST 无 key 返回 completed 200、两 fixture wire 调用并落库。最小红例 `test_missing_empty_or_invalid_key_is_rejected_before_pg_and_generation` 和 `pg_key_contract_red.*` 保留；主控修业务，测试不吞失败、不 skip、不降低条件。

初轮并发 case 不证明进程中断后的有界恢复或 late writer 保护。主控授权后追加三 case，并在 dc014c9 实际通过：生成第二轮用同步屏障暂停，仅在该 test 自身 schema 将 reservation_expires_at 明确 backdate 到 2000；新应用重放将 pending CAS 到 failed/answer_interrupted，usage_status=incomplete_interrupted、fee unknown；释放原 writer 后，响应仍 failed，reservation_state 仍 expired，只追加两次已取得 fixture attempts，未重复模型请求。此例验证预约到期处理，不声称实际 kill/restart、420 秒连续运行或真实账单 exactly-once。

认证顺序另有两个 PG case：在最终 auth_sessions/users FOR SHARE 已取得、外部生成已结束后设置屏障；另一线程真实 HTTP logout 或 PG tenant UPDATE。通过 pg_stat_activity + pg_blocking_pids 实际确认它们被答案事务阻塞，随后释放回答 commit，变更才完成；返回已提交 completed、后续 GET 分别 401/404。屏障不在持锁线程同步 logout，避免 harness 自锁。原生成回调内先提交撤销/迁租的 401/404 case 也在新基线通过。未重跑已经通过且不受改动影响的全 886/270，未将旧基线结果说成新基线全量回归。

## 图与源码核对

先实际执行 CBM 0.11.0 `--help`、`cli --help`；独立 cache `/tmp/dianzi-cbm-r05-api-tests-20261015`，project `dianzi-r05-api-tests`，只索引 WT `backend/src`。`cbm_index`：1081 节点 / 5188 边，0 未索引，exit 0。初次 `GroundedQuestionService.ask` trace 名称不匹配返回真实错误；用 `search_graph --name-pattern ask` 找到限定名后 `trace_path --function-name ask` 成功，日志完整保留。ask 直接连接 generate_grounded_answer/require_current/read_grounded_answer；CBM 未推断路由 questions 变量的入边，不能把 callers=0 当无调用。`rg_trace` 实际核对 app.py:121、question_routes.py:111、service.py:213/219 的路由与返回前复验。

新基线 `cbm_index_fenced`（17:30:24–17:30:30）刷新为 1085 节点 / 5218 边、0 未索引；`cbm_trace_fenced`（17:30:50–17:30:53）实际新增 ask→_lock_answer_scope→lock_authenticated_scope 与 read_grounded_answer→_expire_pending_answer 路径，均 exit 0。初次 59 个日志/报告/JUnit 私密连接扫描 0 泄漏，最终新日志再次扫描并保留独立标签。

## 验证分类与评分证据

unit passed（新基线本包 6；旧基线默认门 886）；contract passed（新基线 7）；integration passed（新基线 24）；security 为限定 fixture/真实 PG 身份隔离路径通过，完整 security scope not_run；frontend/e2e/live/manual 均 not_run。本包未取得真实生成、embedding 或 rerank live，不把 fixture 计为 live；真实产品 live 由主控另交证据。

F3 的证据限定为 API 引用永久版本、当前证据复验、历史 stale 与身份边界；工程证据限定为真实隔离 PG 状态、幂等重放、失败 attempts/费用 unknown。未测正式准确率、5 秒性能门、持续采集、前端可用性和人工支持判断，不宣称 R05/R17/T31 整卡或阶段完成。

下一建议：主控已合并首轮测试，继续合并 `54bd6dbb88c5aed6255b49dc485b1e327fbb7119` 的三补例和精确 invalid_key 断言；本作者定向复跑已结束，交不同独立 reviewer 复跑 dc014c9 及当前测试。原红例证据、环境失败和未运行类别完整保留；本包完成即停止，不扩大下一任务。
