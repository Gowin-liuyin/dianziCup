# R18 typed task binding · 非作者首独审复查

本轮限定切片复查通过：原两项业务 Must 已被新源码修复，窄 ActorReference 异常断言纠正符合现有合同。建议 Root 依据本报告处理切片验收；我未签 accepted、未改中央状态。整 R18 仍 `partial`：默认 typed producer/reader/worker/GET 尚未装配，stack、多 event、会话与双时间 async 明示 unsupported，真实 QA/current proof 与产品 live 未完成。

固定源码 `f316c7af54bfc14de3b345c39d90aac2b9699872`，材料 `a8b8aa153663eb3bce94a18c2644b058b42384a1`，业务修复父源码 `2133d9d8fbaa311eb12e9b9488f6183f599ca2b2`，原审源码 `3e84d7655c0f6afcf19094265298cfc43b8afd2a`，共同基线 `0f8c1f6d047387cfca8a62f8dbc352b8c6415b96`。独立 clean worktree `D:/wt/r18-typed-task-binding-review1-recheck`，分支 `codex/r18-typed-task-binding-review1-recheck`；自备报告和取证脚本可本地提交，业务源码、作者原 oracle、App、worker、state、金标、阈值、分母、依赖和 push 均未修改。测试用 fixture 凭据与 QA 明确隔离；未读 secret 或 holdout。

本轮已重读 AGENTS、execution map、progress、R18/T35/T33 映射与相关 actor/public/enqueue 冻结合同，并按最新 Ponytail review 核实连接代码及调用者，未新增 child。ownrun 在 `reports/runs/r18_typed_task_binding_review1_recheck_20261017`；逐条 argv、起止时间、退出码、进程 birth/完整控制链、JUnit 和实际 raw hash 均保存。

## 修复与窄 CR 的独立核验

1. **原 M01 已修复**。新 `publish_result_in_session` 不再在同 locator replay 读完 QA 后直接返回。新 locator 与 replay 都从 `_read_result` 获取 reader/模型校验后的数据库时间，再统一核当前 actor、JobRun lease/attempt 和 deadline，之后才 return 或 CAS。`_read_result` 的时间采样发生在模型 dump/validate 和时间绑定校验之后，未将 reader 前的时间冒作 reader 后时间。真实同 Session/同事务 PG 负例沿用原字节、原 0.7s PG reader 等待和 0.5s lease，不把 locator 单独 commit。

2. **原 M02 已修复**。`_connection` 对所有已登记 metadata table 的 SQLAlchemy get_bind 逐一验证，拒绝 default Engine 正确而 public/JobRun/user/QA table 被路由到其他 bind 的 Session。三个公开端口统一用 `_session_fence`：固定 SessionTransaction、ConnectionTransaction 与实际 Connection，`do_orm_execute` 验证动态语句路由，`after_begin` 验证显式 connection 路由，结束复验并移除监听。原独立真实 SQLite 混合 bind 负例通过；新 22 个 fence case 还覆盖未登记 reader table、同 Engine 不同 Connection、显式 bind、事务替换和正常 Engine/Connection 使用。这里证明真实 SQLAlchemy/SQLite 路由边界，不冒称 M02 已另跑 PG 混合 Engine 专用负例。

3. **窄 CR 合同成立**。实际输入是 ActorReference。`lock_actor_reference_scope → _validate_lifetime → _deny` 明确抛 `InvalidActorReferenceError(PermissionDeniedError)`；只有旧 cookie 的 `lock_session_scope` 转换为 `SessionExpiredError`。f316 不改实际异常实现、cookie/HTTP 合同、权限或产品成功条件。

   我从 Git blob 直接独立 AST 比对 2133→f316：仅旧 cookie exception import 集合换成 actor exception import，另仅目标 `pytest.raises` 的一个 Name。反向还原 Name 后，全部其他非 import AST 精确等于原16，包括 fixtures、锁、expired 时点、wait/sleep、timeout、所有正文/assert。原16在2133与3e84的 Git 原字节也精确相同；0031 migration blob未变。非 import SHA256 `515ca803ed490caf03bd063d9fb786b344e89d1ebf523f701181c574668ae686`，归一 import SHA256 `09f57ef4b0027604e9d0644dc3a78066b673f7e56d991233e9f39942899d4add`。证据 `independent_ast_delta.json`。

   原 CR raw `2de13bc4fb765f5770ecab5bfba3b9e39a9fe0011ab676ad1188410f648fc6cc` 保存在 `CR_input.md`。Root 09:00:10 导入集合澄清 raw `0fa98e0bb8df3dcc9af76a701a4e6763067cce23b11b5a82db73f1bfed5d6ce8` 另存 `CR_clarification_090010.md`，未覆盖前者；明确允许移除 F401 旧导入、合并 actor import，并澄清原case没有显式 reader0/DB不出版断言。新的直属 fixture 回归另外证明 reader0、业务 Session.execute0、commit0，未谎称这些是原 PG case 已有断言。

上述 3 项属于原已证问题的关闭，不新增猜测性 Must。对未来可信 reader 自行进行产品 IO/模型推理等装配风险，仅保留合同要求及未验证范围，不声称当前 default 已正确实现。

## 离线实际复跑

使用 uv base Python 3.12：`C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe`，只复用批准 site-packages，不双 venv。每条通过自备 `review_checks.py` 和成熟 NativeJob 检查：512MiB/process、1GiB/job、24逻辑 CPU 上 CPUrate833（约1.9992核）、native active9、birth-aware 普通完整 Win10、每窗60s。以下全部 exit0、owned残留0；验证字段与源码 raw 在最终 receipt。

| label / 实际命令 | 结果 |
|---|---|
| `related_275`：`python -m pytest` 原12相关文件，另 `tests/unit/test_r18_public_task_binding_fences.py` 与 `tests/contract/test_r18_actor_expiry_assertion_contract.py`，`--no-cov -q --junitxml=../reports/runs/r18_typed_task_binding_review1_recheck_20261017/related_275.xml`；完整14文件 argv 在 `related_275.command.json` | 275 passed，0 failure/error/skip；原249+新22+新4；不累计重复运行 |
| `independent_original3`：`python -m pytest <ownrun>/test_independent_negative.py --no-cov -q --junitxml=.../independent_original3.xml` | 原3独立负例均 passed：post-reader lease、无typed真实结果failclosed、真实SQLite混合bind；fixture单元不冒PG/live |
| `source_style8`：`python -m ruff check` 服务、0031及直属6测试文件 | exit0；完整8文件 argv 收据 |
| `source_format8`：`python -m ruff format --check` 同8文件 | exit0，8 files already formatted |
| `source_mypy`：`python -m mypy src/ai_intel/api/public_task_bindings.py` | exit0，正常 imports；没有 skip imports/Any 掩盖合同 |
| `pg_support_collect_author` / `pg_support_collect_negative_v2`：固定 worker 加 `pg_phase_plugin`、`task_pg_identity`，负例另 exact-path repository fixture plugin，`--collect-only --fixtures-per-test --no-cov -q` | 16+1完整收集和 fixture closure；各exit0；执行业务0，与实际PG通过分别登记 |
| `caller_head_full_rg`：`rg -n 'PublicTaskBindingService\|bind_in_session\|publish_result_in_session\|public_task_result_reader_not_configured\|0030\|0031'` 全src及迁移/六组相关旧PG调用方 | exit0，保留完整raw；补图中被默认排除的assets源码，未修改旧测试 |

本轮 unit/contract/相关security=`passed`；限定PG integration=`passed`。全仓 coverage 门、其他旧PG套件、frontend/e2e、live/manual=`not_run`；`--no-cov`只用于本有界检查，原门槛未改。没有用收集或文件行数计通过。

## Root 唯一资源桥的真实 PG17

独立自备packet revision3先固定241条源码/fixture raw hash、controller和helper，再由Root唯一DPAPI内存桥注入；我没有访问DPAPI或连接共享PG。新版独立controller raw `14be2516201868d4efd1725a65b6123fc5bffb07cf0b7cd24dabadbd2f5eeeac`，admission raw `fd4b0926fd158531566d76fafc04a2f69decf73650a8105755c0a02e4aa5abee`，worker raw `c6bf4c406fc7bc61652999dc70c1e7f57ec82ddcf3a2cc5432e9f1ae75f83dbe`。Root外层launch script raw `0070eb919e6a62bd18c5b259d590df4f0ad7296b8dd44429b77b0d61acd26300`。新目录/label防覆盖原五窗。

我已亲读并程序交叉核所有controller receipts、outer receipts、JUnit、identity和raw migration日志。五窗原16为16 passed，原字节同事务负例为1 passed；17 distinct，0 failure/error/skip，不叠加到原版本。

| 新label | Root外层起止（UTC+08） | 实际结果 |
|---|---|---|
| `typed_task_fix1_pg_atomicity_owner` | 09:01:08.013→09:01:16.210 | 5 passed，exit0 |
| `typed_task_fix1_pg_0031_constraints` | 09:01:33.340→09:01:41.530 | 5 passed，exit0 |
| `typed_task_fix1_pg_publication` | 09:01:42.398→09:01:50.085 | 3 passed，exit0 |
| `typed_task_fix1_pg_integrity_expiry` | 09:01:51.015→09:01:59.541 | 3 passed，exit0；包括原ActorReference真实锁等待过期拒绝 |
| `typed_task_fix1_pg_locator_replay_expiry` | 09:02:00.387→09:02:08.453 | 1 passed，exit0；同Session/同Txn reader跨lease |

最后负例 DB lease deadline `01:02:06.750981 UTC`，第二 publication进入 `01:02:06.274445`，reader进入 `01:02:06.282225`，真实 `SELECT pg_sleep(0.7)` 返回 `01:02:06.986076`，已晚235.095ms；`lease_rejected=true`，未 separately commit QA locator或complete_job。该负例真实PG提供存储/时钟/lease证据；QA内容/current proof仍明确fixture，不计模型/原文live。

五窗均：PG16实际 `160014`；真实parent role OID10/commentNULL由身份插件接收，未编造COMMENT；nonce DB原OID/owner/9字段COMMENT、schemaOID/COMMENT核验一致；完整migration child到`0031_public_task_bindings` exit0并退出，之后才启动pytest。Native limits实际读回512MiB/process、1GiB/job、CPU833，Win峰4以内、owned残留0。采样物理target最多2、parent sampler1、合计最多3；这仍是20ms观察的soft cap，role connection_limit=-1，没有谎称DB硬2限制。五个自建nonce DB精确drop后 own DB/target/sampler残留0，保护Source OIDs `10451302/10434264` catalog身份不变；未查询Source业务内容，因此此证据不扩张成逐行内容校验。secret scan五窗各9 artifacts passed，付费/模型/外部请求0。

完整新 `pg_execution_summary.json` 记录每窗时间、argv/JUnit/raw hash、roleNULL、native/物理采样和精确清理；原始PG材料在 `pg_support`，Root outer收据/log按原字节复制为 `root_outer_*`。`seal_actual_pg_cbm` 对上述冻结输入、17 distinct及所有资源/identity/cleanup门实际exit0。

## 新源码的独立 CBM 图

Root先授权PGpacket freeze后给≤45s独占窗。独立Git-exact f316 `backend/src` 快照197文件，command-local `core.autocrlf=false` 导出，不改repo配置。使用本reviewer先前sealed owned同cache，未启动、停止或重启共享daemon。新project从本次index解析，路径明确含 `review1-recheck`；没有以旧3e图代签f316。

实际9条 help/index/schema/architecture/bind/read/publish/actor_scope/complete_job均exit0、isError=false，窗口30.422s≤45。完整Win/guest ancestry至PID1、birth和retained owned identity，配对总峰15≤16，两平台own残留0，197文件前后raw一致。guest GOMEMLIMIT480MiB是Go软限制，硬guest内存未知；Native Windows硬limits照实记录。工具binary raw `ce11c141431aeadd788506c3a7e6942db8fd438dec369d0707a39ec9fd8c6510`。结束即告知Root释放。

新index2783 nodes/16514 edges；not indexed/skipped/partial/unusable各0，但工具默认排除`ai_intel/assets`的16 Python files（1dir），不能宣称197源码全图。完整源码rg另行核调用方，architecture为实际工具默认summary，不冒作全部architecture aspects已执行。

当前bind/read/publish business caller各0，两跳图都新增 `_session_fence` 路径；三个port仍不调用 `complete_job`。JobRun完成沿现 `_WorkflowRuntime.finish/finish_stale`、`workers.executor.execute_job`、`schedule_retry_or_fail`直接caller；graph同时含间接/文件节点，不能把total行数当直接函数数。actor图也有file/indirect节点。逐图raw和caller/callee记录在 `cbm_support/runtime_f316/trace_summary.json`，schema/architecture raw完整保留。冻结2ec enqueue依赖仍为独立source，不合进这个f316图。

guest只写一次的sample原字节已ZIP无损归档，逐entry核SHA256并保存manifest，磁盘原件未删除；局部ignore仅排除可从ZIP原字节重建的解压源码及重复sample。没有排除失败证据或业务源码。局部 `.gitattributes` 仅保ownrun原字节与CR-at-EOL，业务检查继续；无根属性变更。

## 尚未验收的明确范围与交接

- 新 head0031 对六组既有hardcoded0030测试的影响仍在：`test_r18_public_producer_fix2_pg.py:50`、`fix1_pg.py:68`、`test_r06_source_data_mode_pg.py:67`、`test_r11_assessment_http_pg.py:91`、`test_r16_revalidation_runtime_pg.py:58`、`test_r01_migration_engine_disposal_pg.py:283`。本轮静态确认，没有把未跑旧套件写成实际失败；Root须统一前向校验，不能私改这些原oracle。新5窗已真实完整迁移到0031，原作者task fixture另外`metadata.create_all+直接0031`这一事实仍区分记录。
- 可信reader只定义接口，并由明确fixture验证真实实体ID/同task/request参数和当前proof合同。生产reader未供应；默认App/worker/task GET没有typed service caller，不能报产品已端到端接通。Root需把真实QA/currentproof生产、locator CAS及complete_job放同Session/txn，GET只读取，不调用模型或扣quota；succeeded没有typed结果必须failclosed。
- 用户、角色、credential createdAt与绑定immutable actor、租户/owner、DB clock锁后过期、重放/concurrency/CAS、typed结果和latency绑定均已审查所连源代码及相关测试。271/275 fixture、真实17PG和CBM不是多跳问答效果、产品P95/长期稳定/live指标；不计这些评分。
- stack、多event、会话和双时间async unsupported是诚实边界，不能因此减少R18/T33/T35原验收条件。余下默认装配、真实live、六组migration forward与整R18必须继续由Root处理。

旧版历史已sealed在原review WT commit `4907e4388d4fbeda779f7eadbc88f0c26f34f123` 与实际补记commit `d776400f`。原source3e84的16例15 passed/1 failure、原同Txn M01负例0 passed/1 failure（晚229.883ms）和原M02真实SQLite红均保留；旧not_run snapshot、旧prepare/CBM首次观察失败也不覆盖。新17绿只作用于f316新版本。

本轮没有新已证业务缺陷；原M01/M02和错误型别测试问题已关闭。限定切片复审通过，中央R18状态、最终accepted及整任务/live结论交Root，不越权代签。
