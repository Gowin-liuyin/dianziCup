# G-B / R05 问答接线独立初审 1

> 最新限定结论（2026-10-15T17:36:29+08:00）：dc014 修复冻结已定向复核，三 Must 在新预约/事务提交范围关闭，限定 Ship；整 R05/G-B/live 未签。原 d7 初审与全部红例保留，详见文末复核节。

What this change does: 本批把指定单事件的当前公开证据接到真实 PG 向量派生表、生成与第二轮支撑核验、用户答案持久化和两套默认 API 前缀。问答完成前会再次读取认证范围和核查事实 epoch；历史答案从 PG 读取并在 epoch 变化后标 stale。本报告审查这条接线，不把已有生成/grounding/语义基础组件的限定 Ship 扩展为整条链、整 R05 或整 G-B 的验收。

- 任务：G-B / R05 root 问答接线批次；独立 reviewer `/root/r05_question_pipeline_independent_review`，未参与本批业务实现。
- 本次结论：`needs_changes`；Must fix 1、2、3。unit/static 限定通过；integration 同时有通过证据及已证红例；live/manual 未运行。
- 审查开始：2026-10-15T17:08:47+08:00。初审证据冻结：2026-10-15T17:23:22+08:00。
- 目标 SHA：`d7b6bf113f3daa24971297aa9ac867871a8df3c1`；tree：`9eec214f04dec362959201813f2b1afd63d04da9`。
- 基线 SHA：`168836796e4d8414ec72846769e3a6941afbb726`；tree：`d68c34c6e63bb455cf4883f8d94c8360e35fabc4`。
- 独立工作树：`D:/wt/r05-pipe-review`，分支 `codex/r05-question-pipeline-review-1`。最终 `git status --short` 为空；没有审查 root 持续变化的业务目录，没有修改业务、schema、锁、状态、金标、阈值或分母，没有 push/accepted/spawn/付费调用。
- 测试补充冻结：作者仅测试提交 `af73b3e66d6f984fa0071938ff302257cae09711`（父提交为目标 d7），tree `8d58dd770bdb9533193c9beddbc2e6a0964b6811`。两份新测试通过 `git show` 原字节提取到本次 runs 目录，实际执行仍使用固定 d7 的业务源码。

## 范围、依据与负载

初审 diff 恰为以下六文件：`backend/src/ai_intel/answering/service.py`（306 新增）、`backend/src/ai_intel/retrieval/service.py`（368 新增）、`backend/src/ai_intel/api/question_routes.py`（146 新增）、`backend/src/ai_intel/api/app.py`（4 新增）、`backend/tests/integration/test_r05_vector_persistence.py`（120 新增/3 删除）、`backend/tests/unit/test_r05_evidence_chunks.py`（24 新增）。沿调用链还只读认证、PG authentication store、事实读写模型、生成/grounding、semantic/runtime、网络和前端使用方。

已读 AGENTS、执行地图、恢复 R05/R17 卡、状态与最近交接，以及 T18/T30/T31/T43 原卡、02/03/04/05/06/07 相关合同、CR-R05/CR-R04-R05_model_post。指定的字面 `contracts/api/v2/` 目录在冻结树中不存在，现行问答定义实际位于 `contracts/schemas/public_api_v2.json` 的 `QuestionRequest/QAAnswer/TaskHandle/Citation`，已据此核对 `question_contracts.py`。引用存在和第二模型认可不当作人工金标或准确率。

使用 Ponytail 5.2：`C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`。按正确性、安全、并发、测试、速度与必要复杂度审查；中文报告遵从本次明确授权。假设多个 FastAPI 服务实例共享 PG、用户可能重发写请求或在进程重启后重放；没有假设单进程内存 semaphore 能完成跨实例幂等。

现有组件证据仅复用其原范围：grounding b151（集成基线 1688367）、语义/float32 修复 3ab。对本批新接线仍独立执行以下检查。

## 实际调用链核对

`create_application` 同时装 `/v1/questions`、`/api/v1/questions` 和对应 `/answers/{id}` → cookie/CSRF/Origin/READ_PUBLIC → PG answer_id 预约 → PG 当前 public event/document/revision/source/evidence/active supported claim → 本地 semantic 生成派生块、pgvector 查询与重排 → `GenerationClient` 两轮独立结构化调用/精确引用/支撑核验 → 再次读取 scope → PG epoch share lock、引用有效性 → PG completed → HTTP 返回。

GET/同键重放走 owner+tenant 的 PG 答案查询及事实证据回查；epoch 改变时只修改返回投影为 stale，原 PG response 未覆盖。不可见对象统一 404；缺模型配置明确 503；R12 conversation/assets/time/investigate 与非单事件范围明确 422。

独立 CBM cache 为 `/tmp/dianzi-cbm-r05-question-pipeline-review-20261015`，仅索引 `/mnt/d/wt/r05-pipe-review/backend/src`，项目 `r05-question-pipeline-review`，fast 模式得到 1081 nodes/5188 edges/82 files，partial/unusable/skipped 均 0。`get_graph_schema` 与 `trace_path ask/read_grounded_answer --direction both --include-tests true` 已执行。图中 ask 的 61 callees 包括 retriever、grounding、GenerationClient、NetworkGateway；read_grounded_answer 找到 service.ask 和 question_routes 文件调用。由于仅索引 src，include-tests 参数不会产生测试节点；图也未识别路由闭包 `ask_question`，该 trace 返回 function not found，故 API/auth/closure 的连线用 rg 和源码逐段补核，未把图的缺边当作实现没有调用。

## Must fix

1. **缺少幂等键的写请求仍完成并重复生成**（P1；`backend/src/ai_intel/answering/service.py:153`、`:158`；`backend/src/ai_intel/api/question_routes.py:111`）。

   - 职责与触发：05 API 合同 §2 要求写入使用 `Idempotency-Key`。同一个已认证用户、同一个合法单事件问题，分别向 `/v1/questions` 和 `/api/v1/questions` 发送没有该 header 的请求。
   - 预期/实际：预期 422，预约前拒绝，0 模型调用。独立真实 PG + 显式 fixture wire 的实际是两次 200 completed、两条不同答案、4 次模拟 wire 调用（每次请求各生成/核验一次）。代码只在 key 非 None 时验证，None 分支生成 uuid4。测试作者的冻结 API 用例也独立复跑为相同红例。
   - 影响：网络重发或调用方漏 header 不能复用原操作，会重复付费；当前前端是否总传 header 不能修复公共写入口的合同缺口。本审查没有发生真实费用，4 是模拟 wire 次数。
   - 最小修复：服务输入边界要求 key 存在且满足既有字符/长度规则；删除 None→uuid4 分支，在任何预约/检索/模型调用前固定返回 422。不要降低键合同或把此红例改成允许成功。
   - 复验：两前缀的 missing/empty/空白/超长键全部 422，PG 0 预约、semantic/generation 0 调用；合法同键重放返回原 answer_id，异体 409，跨实例并发只形成一条预约及一套生成/核验。
   - 红例：`probes_retry.log/xml`、`probes_expired.log/xml`；冻结作者测试 `frozen_pg.log/xml` 中 `test_missing_empty_or_invalid_key_is_rejected_before_pg_and_generation`。均在本 runs 目录保留。

2. **已中断且过期的 pending 答案永远没有终态**（P2；`backend/src/ai_intel/answering/service.py:94`、`:174`、`:195`、`:284`）。

   - 职责与触发：同键 PG 预约先持久化，再执行生成。独立子 Python 进程在首个模拟付费 wire 边界 `os._exit(73)`，未进入 Exception 清理；随后新 service 重放同 key。另将该隔离 schema 的唯一预约 created_at 设置为当前时间前一小时，明确模拟过期持久状态，不声称真实运行一小时。
   - 预期/实际：进行中的有效 owner 可以继续显示 pending；已死 owner 的过期预约应成为可追踪的中断/结果不确定失败，费用仍 unknown，不能自动重付费。实际即使一小时旧记录，重放仍 409 answer_in_progress；PG 仍 pending、attempts=[]、fee=unknown，0 新调用。代码没有 owner/有界到期/中断终态入口，GET 也只有 pending→answer_in_progress。
   - 影响：用户在重启后无法区分还在运行与永远不会完成，原 key 被永久锁住；尝试新 key 又可能重复付费。此项只要求当前同步预约可安全终止，不要求提前建设 R14 的调查调度或 R20 的完整恢复系统。
   - 最小修复：PG 预约保存可核验 ownership 与有界到期。过期只以 pending+同 ownership 的 compare-and-set（仅在仍是同一预约时更新）转为固定中断/不确定失败，不重发模型。完成及异常写回也必须验证同 ownership、仍 pending，防止晚到 writer 将中断终态覆盖成 completed；必要的安全元数据以既有 PG model_trace 保存，公共 schema 改动仍由主控管理。
   - 复验：有效 owner 尚在期限内时重放不杀死它；硬退出+过期后的 GET/同 key 可看到终态且 0 再次调用；两进程同时回收只转一次；旧 writer 在恢复终态之后回来不能覆盖；已知 attempts/unknown fee 保留，未知上游结果不能记 0 费用或假成功。
   - 红例：`crash_worker.py`、`test_review_probes_expired_frozen.py`、`probes_expired.log/xml`。立即重启结果也在 `probes_retry.log/xml`，但判断 Must 依据过期状态与源码无终态路径，未把立即重启时 pending 单独判错。

3. **最终鉴权与完成提交不在同一事务，撤销可先提交而答案仍成功**（P1；`backend/src/ai_intel/answering/service.py:215`–`:218`、`:251`–`:259`；`backend/src/ai_intel/api/question_routes.py:78`、`:113`）。

   - 职责与触发：正常两轮生成完成，`current_scope = scope_provider()` 取得认证快照后，在最终 `require_current(lock_epoch=True)` 入点安排另一真实 PG 事务先完成 logout，或先更新该 user 的 tenant_id，然后调用原事实核查。这是以 fixture barrier 确定调度窗口，认证/撤销/写回均真实 PG。
   - 预期/实际：撤销或主体范围变更若已在答案提交前生效，应拒绝返回/发布答案：撤销 401，主体租户变化 404。实际两个独立用例均 200 completed、PG completed、2 次模拟 wire；日志确认权限变更已经提交。epoch lock 只保护事实 epoch，不保护 session/users；`require_current` 只检查传入旧 scope 的权限集合。
   - 影响：生成期间较早的撤销检查虽通过，但最后一个 PG 提交窗口仍违反权限撤销后不能返回结果的边界。当前范围只使用 public 证据，本次没有证明跨租户私有内容泄漏；已证问题是已撤销会话或已变更主体仍完成受认证保护操作。
   - 最小修复：最终 session+当前用户身份复查和必要行锁与 epoch/答案完成放在同一个 PG 事务，锁持有到完成状态提交，明确定义完成与撤销的先后顺序。只在事务前/后多调用一次 scope_provider 仍有同类窗口；不要将该旧 AccessScope 当作事务内认证依据。
   - 复验：撤销/tenant 变更先提交时请求拒绝且 PG failed，2 attempts/fee unknown 留存。完成已经取得认证行锁时，并发撤销应等待，只有答案提交后才生效；两线程/两进程使用 barrier 证明此顺序。原红例的同步注入 logout 在修复后可能被行锁阻塞，应另以并发 barrier 验证锁的顺序，不把这种阻塞误报为继续返回已撤销答案。
   - 红例：`test_review_auth_commit_race.py` 与 `auth_commit_race.log/xml`，2 failed。第二轮 wire 期间较早撤销的 401 绿例仍保留，不用绿例替代这个更晚的窗口。

## 独立执行记录

所有主检查实际 cwd 为 `D:/wt/r05-pipe-review/backend`；命令使用 `uv 0.10.9`、固定锁 `--frozen --extra semantic`、Python 3.12.13。各 `*.json` 保存完整 command 数组、cwd、开始/结束 ISO 秒级 +08、exit、完整 HEAD/tree 与日志路径；对应 JUnit 保存真实 tests/failures/errors/skipped。检查执行入口为本 runs 的 `run_review_checks.py`，私密连接只由 WSL root600 配置读取后放入测试子进程环境，未输出连接密码。

| label | 开始→结束 (+08) | 实际命令关键参数 | exit / 实际结果 |
|---|---|---|---|
| unit | 17:13:19→17:13:53 | `pytest tests/unit -q --junitxml=…/unit.xml`，保留默认 coverage 门 | 0；880 passed；6321 lines/2163 missed，即 4158/6321=65.78%，原门 60 未变 |
| core | 17:09:05→17:09:20 | `pytest tests/unit/test_r05_grounded_answer.py tests/unit/test_r05_evidence_chunks.py tests/unit/test_r05_generation.py tests/contract/test_r05_grounded_answer_contract.py tests/contract/test_r05_question_contracts.py --no-cov -q` | 0；184 passed |
| vector_pg | 17:09:05→17:09:29 | `pytest tests/integration/test_r05_vector_persistence.py --no-cov -q` | 0；11 passed，真实 PG/pgvector，synthetic vectors |
| static | 17:10:18→17:10:28 | `mypy src` | 0；82 source files，无问题 |
| ruff | 17:10:18→17:10:18 | `ruff check src tests/integration/test_r05_vector_persistence.py tests/unit/test_r05_evidence_chunks.py` | 0；通过 |
| format | 17:18:35→17:18:35 | `ruff format --check` 六个目标文件 | 0；6 文件已格式化 |
| probes_retry | 17:13:01→17:13:09 | `pytest -p conftest …/test_review_probes.py --no-cov -q -s` | 1；2 failed / 1 passed，missing key 与立即重启红；会话在第二 wire 期间撤销绿 |
| probes_expired | 17:14:59→17:15:07 | 同上，加入过期预约 fixture 状态 | 1；2 failed / 1 passed，Must 1/2 |
| boundaries_retry | 17:17:27→17:17:46 | `pytest -p conftest …/test_review_boundaries.py --no-cov -q -s` | 0；13 passed |
| auth_commit_race | 17:19:54→17:20:00 | `pytest -p conftest …/test_review_auth_commit_race.py --no-cov -q -s` | 1；2 failed，Must 3 |
| frozen_routes | 17:21:50→17:21:53 | `pytest -p conftest …/frozen_tests_af73b3e/test_r05_question_routes.py --no-cov -q` | 0；6 passed；显式内存 auth/SQLite 只验证拒绝入口，不算 PG |
| frozen_pg | 17:21:50→17:22:24 | `pytest -p conftest …/frozen_tests_af73b3e/test_r05_question_api_pg.py --no-cov -q` | 1；20 passed / 1 failed（缺 key），真实隔离 PG 默认 app auth/service 装配 |

日期均为 2026-10-15。上述套件包含重叠用例，不相加宣称不重复总测试数。主产品 live 模型调用在本审查为 0，费用 unknown；所有 wire 明确 synthetic，fixture 不计 live/准确率/召回率。

PG 专用库为 `test_dianzi_r05_pgvector_20261015`；运行 ID `r05_pgvector_20261015`；每测试创建独立 UUID schema、`search_path=<schema>,public`、有界 statement timeout；引用原 `vector_database` fixture，前向迁移 0013→0014 并验证证据 hash 不变。测试后仅删除自己的 UUID schema，没有全库 reset/downgrade/重启。

通过行为：默认两个前缀 POST→GET→正确 revision 引用；跨应用实例同键并发只有一条 PG pending 和一套两轮生成；同键完成/失败重启重放不再调用；异体 409；匿名/CSRF/Origin/权限/撤销/身份伪造安全错误；owner/tenant 不可见 404；缺配置 503 且旧答案可读；无 verified/current/active support、private event 不送生成；第二轮生成期间 epoch/claim撤回/private/证据失验/revision过期/tenant变化阻止发布；历史 stale 且原 row 不覆盖；R12 范围 422 且没有预约/调用；generation 503 的 attempts/HTTP status/usage None/fee unknown 保存。

## 保留的失败与未检项

- `probes.log/xml` 初轮 3 setup errors：外置测试没有把仓库根加到 PYTHONPATH，无法 import scripts；已加载原 conftest 及根路径后重跑，不算产品失败或通过。
- `boundaries.log/xml` 初轮 12 pass/1 fail：默认 build_engine 的 connect_args options 覆盖测试 URL 的隔离 search_path，GET 查询到基础 schema 而 503。显式注入同一隔离 engine 后 `boundaries_retry` 13 passed。业务未修改，不列 Must。
- `cbm_help.json/log` 的 `cli --json --help` 被工具当成未知 tool，exit 1；按 binary 实际 help 改正的 `cbm_help2` exit 0。`cbm_route` 未识别闭包、exit 1，源码补核；其余 CBM index/schema/ask/read trace exit 0，完整参数/时刻在各 JSON。
- 原红例未删除、未改阈值、未改 skip。私密环境变量和随机 auth 值由已有 conftest 脱敏机制保护；报告中只含标记为 synthetic 的例子，没有访问 `.env`/KEYS/holdout。
- 尚未检：两个实际进程同时成功竞争同 key 的完整完成路径（当前已检跨应用实例并发，以及实际子进程硬退出/新 service 重放）；late writer 与回收器 CAS（d7 尚无回收实现）；最终认证行锁的双进程顺序（d7 无该锁）；真实模型/semantic 产品链 live、人工金标、持续运行、性能阈值、UI。root 后续受控 live 或新修复候选不属于本次独立 d7 初审。

## 计划/合同与评分证据

R05 单事件首答是允许切片，R12/R14 的未支持范围已明确拒绝，没有把多事件/资产/会话/双时间/调查误签为多跳。必填幂等键偏差为已证 Must 1；当前预约不能安全结束为 Must 2；最终权限一致性为 Must 3。没有改公共合同或算法阈值，没有以已有组件 Ship 或作者日志替代本批审查。

F3/E1 的代码级可追溯、安全错误、PG 权威持久化和部分权限/事务行为有上述限定证据；A1/F2 的本批连接仅限受控模型接口和来源引用，第二模型支撑核验仍不是人工事实标注。P3 速度/准确率、多跳；D2 完整问答 UI；整 R05 与 G-B 产品 live/阶段门仍未由本 reviewer 验收。

下一步建议：主控修复 Must 1、2、3，在完整新 SHA 上补充过期 ownership/late writer、事务内认证锁和真实进程并发回归，再由本 reviewer 定向复核。新冻结如触及共享 auth API，应把新增直接调用方纳入复核，不能仅重跑旧六文件检查。报告与原始证据已保存供检查，未更新任务 accepted 或 stage 状态。

Verdict: fix 1、2、3 first. 仅本批修复后才可能给限定 Ship；整 R05/G-B/live 不自签。
Not checked: 真实模型产品 live、人工金标、完整 UI/性能/连续运行，以及尚不存在的恢复/最终认证锁实现。

## 定向复核 1 · 修复冻结 dc014c9（最新限定结论）

- 开始：2026-10-15T17:29:50+08:00；证据冻结：2026-10-15T17:36:29+08:00。
- 被审修复 SHA：`dc014c960f19605c20e0d8e98a93e7c217f94cc6`；tree：`16a487973f05ab0f59dd36c7d50dcda5882133fb`。
- 修复父提交：`dca3a867e9b9ed904bc7d34979523940b5957dfc`；tree：`0a4ccef2c7f5e4137d2bef0b1ffd0bce5d9948eb`。本次修复四文件为 answering/service.py、api/auth_state.py、api/question_routes.py、docs/decisions/CR-R04-R05_question_commit.md；初审六文件的检索等行为仍按初审证据和本次回归核对。
- 新独立工作树：`D:/wt/r05-pipe-recheck`；分支 `codex/r05-question-pipeline-review-1-recheck`；最终 status 为空。没有在初审工作树换版本，没有覆盖初审日志。
- 新测试冻结：`54bd6dbb88c5aed6255b49dc485b1e327fbb7119`（父为 dc014）；tree `f625a09e0a5f079a066f0154099d19e2694728eb`。只提取该提交 PG 测试原字节到 `recheck_dc014c9/frozen_tests_54bd6db/`，未 cherry-pick 业务或改变被审源码。
- 当前结论：初审 Must 1、2、3 在本次限定新预约/提交链路中已关闭；`Verdict: Ship.` 仅适用于 dc014 的 R05 单事件问答接线修复。本 reviewer 没有签整 R05、G-B、产品 live、正式准确率或最终恢复验收。

### 三项 Must 的关闭依据

1. **必需幂等键关闭。** `ask` 的 key 缺失与非法均在预约前返回 422 invalid_key，不再有 uuid4 无键路径。原作者冻结红例在目标修复上的默认两前缀 API/PG 回归通过；同键完成/失败重放、异体 409 仍通过。另一个独立测试启动两个实际 Python 进程共享本测试 UUID schema 和真实 PG session，第一个在模拟 wire 上等待，第二个同键返回 answer_in_progress/0 次 wire；释放第一个后 completed/2 次 wire、PG 1 行，证明跨进程结果，不用两个同进程 app 代替。

2. **新预约中断/late writer 关闭。** PG trace 保存 reservation_id、UTC expiry（420 秒）、reservation_state、usage_status。独立子进程首个模拟付费边界硬退出 73，随后明确把隔离 fixture expiry 设为过去，GET 将 pending CAS 为 failed/answer_interrupted；同键重放不付费。空 attempts 保留且 usage_status=incomplete_interrupted、fee=unknown，没有把缺元数据宣称 0 费用。另一独立测试在生成后 expiry 过期并 GET 回收，再让原 writer 返回：API 409 answer_failed，原 failed/answer_interrupted 不变，2 个已知 attempts 追加为 recorded_after_terminal。没有预先 GET 回收、只将 PG expiry 置为过去时，最终 PG clock_timestamp 完成条件也拒绝；failure 仍记录调用元数据。新增冻结 24 PG 测试中的到期/late writer 回归亦独立通过。

   旧无 reservation_id/expiry 的 pending 仍按 CR 明确要求人工恢复；本次未把这种历史状态伪称已自动修复，也未清理生产/真实试验库。限定 Ship 覆盖新修复产生的预约及旧 completed 历史兼容。进入完整恢复/最终验收前，主控仍需有旧 pending 清单和受控人工恢复证据；“当前试验库没有旧 pending”是 CR 记录的主控资源事实，不是本 reviewer 对生产数据作出的独立查询结论。

3. **最终认证事务窗口关闭。** 新 `auth_state.lock_authenticated_scope` 在调用方 connection 的现有 PG 事务内对 auth_sessions/users 执行 FOR SHARE，复查 token hash/撤销/到期、当前 role/tenant；`_lock_answer_scope` 校验 READ_PUBLIC 与原 user/tenant。答案最终 epoch 检查与完成 CAS 在同一事务，认证锁释放前不再调用模型；GET/重放也使用该锁。

   独立调度分别在事务外 scope 已读取、最终 auth lock 尚未获得时先提交真实 logout 或 tenant UPDATE，API 分别 401/404、PG failed、保留 2 attempts/fee unknown。另两例请求先取得认证 share lock，再在独立线程调用真实 `auth.logout` 或 tenant UPDATE：查询 pg_blocking_pids 明确得到该 writer 正在等待本答案 PG pid，writer Future 未完成；释放请求 barrier 后答案先 completed，再让撤销/租户更新提交；之后 GET 分别 401/404。首次鉴权快照本身不作为通过依据，未在同一持锁线程同步 logout 制造测试自锁。冻结作者新增测试也使用真实 HTTP logout/PG tenant writer 的 pg_blocking_pids 顺序，实际复跑 24/24 通过。

### 定向复核命令与结果

下列实际 cwd 均为 `D:/wt/r05-pipe-recheck/backend`；每项有本次 runs 子目录的同名 JSON/log/XML，完整参数含 `uv run --frozen --extra semantic`。没有修改默认 coverage 门。日期为 2026-10-15、时刻为 +08。

| label | 开始→结束 | 实际命令关键参数 | exit / 结果 |
|---|---|---|---|
| pg_regression | 17:29:50→17:30:47 | `pytest tests/integration/test_r05_question_api_pg.py tests/integration/test_r05_vector_persistence.py --no-cov -q` | 0；32 passed（21 question + 11 vector） |
| routes_core | 17:31:57→17:32:03 | `pytest tests/unit/test_r05_question_routes.py tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py tests/contract/test_r05_question_contracts.py --no-cov -q` | 0；126 passed |
| probes_retry | 17:31:45→17:32:06 | `pytest -p conftest …/recheck_dc014c9/test_review_recheck.py --no-cov -q -s` | 0；8 passed，含硬退出、实际双进程和 PG auth 锁等待 |
| lease_frozen | 17:32:31→17:33:03 | `pytest -p conftest …/frozen_tests_54bd6db/test_r05_question_api_pg.py --no-cov -q` | 0；24 passed |
| unit | 17:34:05→17:34:39 | `pytest tests/unit -q`，保留默认 coverage | 0；1007 passed；6431 total/2143 missed，4288/6431=66.68%，门仍 60 |
| static | 17:31:56→17:32:08 | `mypy src` | 0；82 source files，无问题 |
| ruff | 17:31:57→17:31:57 | `ruff check src tests/integration/test_r05_question_api_pg.py tests/unit/test_r05_question_routes.py` | 0；通过 |
| format | 17:34:05→17:34:05 | `ruff format --check` service/auth_state/question_routes | 0；3 文件已格式化 |
| cbm_index | 17:33:57→17:34:02 | 独立 cache，`index_repository --repo-path /mnt/d/wt/r05-pipe-recheck/backend/src --name r05-question-pipeline-review-dc014c9 --mode fast` | 0；1085 nodes/5218 edges；skipped/partial/unusable 0 |
| cbm_schema | 17:35:09→17:35:15 | `get_graph_schema --project r05-question-pipeline-review-dc014c9` | 0；82 files，29 schema rows |
| cbm_auth_trace | 17:35:09→17:35:12 | `trace_path --project r05-question-pipeline-review-dc014c9 --function-name lock_authenticated_scope --direction both --include-tests true` | 0；5 callers，与 rg/源码相符 |

各套件重叠，不相加为不重复总数。所有 PG 模型 wire 与向量仍显式 synthetic；本 reviewer 未发付费 POST、未读取真实模型 key。复核初轮 `probes.log/xml` 的 8 setup errors 是外置模块没有直接导入 transitive vector_database fixture，纠正 import 后 8/8 通过；原错误日志保留，不算产品失败/通过。前述 d7 初审的业务红例、环境失败和源码固定信息完整保留。

### CR 记录核对、调用方与余项

`CR-R04-R05_question_commit.md` 的当前实现描述与源码一致：必需写入键、stable owner/tenant/key UUID、PG 新预约 420 秒回收、unknown fee、中断状态、late writer CAS、事务内认证锁、内部 keyword-only session_token、无新增公共 v2 字段。rg 和新图确认产品调用方为 question_routes→ask/read_grounded_answer→_lock_answer_scope/_expire_pending_answer→auth helper；所有调用传 Cookie token，token 不写 trace、模型输入或报告。它是对原已批准 API/认证/单事件问答边界的具体修复记录，没有改变角色/租户模型、费用许可、盲测、分母、评分或 R12 范围。此处核对准确落实，不自行把 CR 状态或任务状态写 accepted。

CR 引用的来源库 105 events/434 evidence、旧 23c 单问 17.009 秒及 root dc014 新 live/browser 是主控另行留存的资源/实测记录，本次限定自动复核不据这些记录转签产品 live 或准确率。本 reviewer 未使用这些 root 日志代替上述独立执行，也未将 fixture 的语义/第二模型输出当人工事实真值。

尚未检/尚未完成：旧无 lease pending 的人工恢复、完整 R14/R20 恢复运维、容器 semantic 部署及产品连续运行、真实模型人工金标与正式准确率/性能、多跳/资产/时间范围、完整问答 UI 独立浏览器验收。新代码仍对未支持 R12 范围明确 422，未签多跳。没有发现需要新增框架、通用层或其他扩大复杂度的整改项。

下一步：主控登记此限定意见与源码/测试 SHA，按既有授权继续独立产品 live/UI 与 G-B 阶段验收；不能由本限定 Ship 直接改整卡或整阶段为 accepted。若发布环境存在旧无 lease pending，应先保留清单并取得受控人工恢复记录。

Verdict: Ship. 仅限 `dc014c960f19605c20e0d8e98a93e7c217f94cc6` 本批新预约和事务提交接线；初审三 Must 在该范围关闭。
Not checked: 本 reviewer 的真实模型产品 live/人工金标/完整 UI/性能/持续运行，以及旧无 lease pending 的人工恢复。
