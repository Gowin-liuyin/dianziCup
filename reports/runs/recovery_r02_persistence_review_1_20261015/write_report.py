from pathlib import Path
import datetime,json
ROOT=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
TARGET=Path(r'D:\dianzi\reports\reviews\recovery\G-A-R02-persistence-review-1.md')
start=datetime.datetime.now().astimezone().isoformat()
text=r'''# G-A / R02 · 会话与知识账本持久化独立初审 1

What this change does: 候选把默认认证会话、共享限流和授权审计放到 PostgreSQL，并新增知识事实、来源断言、证据、状态历史、事件操作和发布收据的事务仓储。它同时增加 0007–0009 前向迁移、严格值合同和显式 fixture 边界，知识 API/worker 和九维状态服务尚未接线。

**限定结论：needs_changes。Must fix 1–4 均阻塞本次会话与知识账本 slice 的放行。** 普通回归、质量门和已有真实 PG 正例通过，不能覆盖本审新增负例的实际失败。仅本报告和专属运行目录有写入；不写 accepted、不业务实现、不提交、不 push，不签整 R02、G-A 或原 T 卡。

## 冻结、权限与依据

- 被审 SHA：`0fe642b1c9e5fe4dafa2774e9432bd96079c1b72`，tree：`01e42cfe03ae508566b5f3d23edac40a578dfe20`。
- 基线：`adb86df7149d2f753f4afe1e08d721160dd780fe`。工作树：`C:\Users\yinha\.codex\worktrees\recovery-r02-review\dianzi`，detached HEAD，开始及结束核对均 clean；10:48:00+08:00 冻结快照见 [freeze_final.json](../../runs/recovery_r02_persistence_review_1_20261015/freeze_final.json)。主仓原有脏 progress/报告未覆盖，独立只读状态快照见 [authority_and_main_status.json](../../runs/recovery_r02_persistence_review_1_20261015/authority_and_main_status.json)。
- reviewer 为 `/root/r02_persistence_independent_review`，未参与 root 公共集成、认证和知识实现，没有使用作者正确性结论作验收。已读 AGENTS、00/03/04/05/06/11、12:R02、T04/T05/T06/T17/T19/T21、CR-R04-R02 实施合同、CR-R05、R02-preflight、状态及交接；适用文件 hash 已归档。使用最新 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`，按正确性、安全、并发、测试、性能及复杂度顺序审查。
- R00 已生效合同不改。已读非作者 runtime/cache 复核中 R02 有限 PG 子步骤的理由：R01 整体仍 needs_changes，同 G-A 可独立实施专用库中的会话/限流/事实事务，不跨阶段门；本审也不据此把 R01:T03、全部 requires_slices 或 G-A 置通过。
- 真实资源仅两份 root 0600 仓库外 auth/knowledge 专用配置，WSL Ubuntu-22.04 `-u root` 捕获赋值而不输出。使用两 DB 的已批准 TEST 环境，唯一用户/source/document/claim/event/key 或专属随机 schema；不清共享库、不 downgrade、不停止 API28000 或其它容器/daemon、不读提供者密钥/DPAPI、不调用付费 live。
- 候选业务源码始终从固定 WT 导入。锁安装到专属 run 中的隔离 venv，`PYTHONPATH` 明确指向固定 `backend/src`；七个入口 `__file__`/SHA-256 已实际核验，见 [actual_schema_module_identity.observed.json](../../runs/recovery_r02_persistence_review_1_20261015/actual_schema_module_identity.observed.json)。禁用字节码/pytest 缓存写入候选，coverage/mypy 缓存也在 run；WT 没有写入业务或测试文件。

源码差异覆盖：`api/app.py/auth_state.py/authentication.py`、`domain/records.py`、`knowledge/{claims,event_linking,evidence,models,persistence,persistence_models,revisions}.py`、`enrichment/{structured,persistence_models}.py`、0007/0008/0009、相关 tests 与 schema_bundle；完整 name-status 见冻结快照。原工程依赖主版本、评分、金标、分母和 60% 门未改。

## 本审实际命令与结果

所有时间为 2026-10-15 Asia/Shanghai。命令 cwd 都是固定 WT 的 `backend`，graph cwd/argv 另有 receipt。外层统一 `python …/run_review.py <name> <auth|knowledge|none> <args>`，内部实际 `uv run --locked <args>`；下表记录内部真实命令，没有把外层成功当作内层通过。

| 命令 / run 名 | 开始–结束（+08:00） | 实际结果 |
|---|---|---|
| `pytest tests/unit tests/contract tests/security --showlocals -p no:cacheprovider -q` / full_unit_contract_security | 10:34:03–10:35:04 | exit 0；325 passed，0 fail/error/skip；cov 80.38% |
| `pytest tests/unit tests/integration/test_r02_auth_state.py tests/integration/test_r02_default_application.py tests/security/test_r02_auth_state_boundaries.py tests/security/test_r02_default_auth_failure.py --showlocals -p no:cacheprovider -q` / auth_integration | 10:35:35–10:36:23 | exit 0；130 passed，0 fail/error/skip；cov 68.06% |
| `pytest tests/unit tests/contract/test_r02_value_contract.py tests/integration/test_r02_knowledge_revisions.py tests/integration/test_r02_schema_migration.py tests/integration/test_t05_persistence_and_raw_store.py tests/integration/test_t21_claims_entities_conflicts.py --showlocals -p no:cacheprovider -q` / knowledge_integration | 10:35:36–10:36:03 | exit 0；177 passed，0 fail/error/skip；cov 75.01% |
| `pytest tests/unit --showlocals -p no:cacheprovider -q` / frozen_unit | 10:37:53–10:38:06 | exit 0；111 passed，0 fail/error/skip；冻结整体 cov 60.22%，未降低 60% |
| `pytest tests/unit <run>/test_review_negatives.py --showlocals -p no:cacheprovider -q`（当时 3 个独立 PG 负例） / independent_pg_negatives | 10:39:08–10:39:23 | exit 1；111 passed、3 failed，0 error/skip；cov 67.45% |
| 同上加 `-k 'not test_existing_event and not test_supersede'`（新增模型负例） / independent_pg_model_negative | 10:41:06–10:41:21 | exit 1；111 passed、1 failed、3 deselected，0 error/skip；cov 66.06% |
| 同上加 `-k 'not test_existing_event and not test_supersede and not test_dispute_must'`（三个新持久化正例） / independent_persistence_positive | 10:45:51–10:46:08 | exit 0；114 passed、4 deselected，0 fail/error/skip；cov 66.11% |
| `python <run>/credential_failure_probe_v2.py`（内部完整 unit + 原 session hash 测试，返回值受控扰动，保留 --showlocals） | 10:44:51–10:45:08 | recorder exit 0；内部 **111 passed、1 个故意失败、exit 1**，cov 62.36%；原失败文本 token/hash 泄漏，见 Must 4 |
| `python <run>/inspect_schema.py` | 10:43:53–10:43:56 | exit 0；实际 head0009、fingerprint UNIQUE、0009 列/约束及源码路径核对通过 |
| `ruff check . --no-cache` | 10:40:26–10:40:26 | exit 0；All checks passed |
| `ruff format --check . --no-cache` | 10:40:26–10:40:26 | exit 0；111 files formatted |
| `mypy src --cache-dir <run>/mypy_cache` | 10:40:26–10:40:34 | exit 0；54 source files 无问题 |
| `git diff --check adb86df…HEAD`、末次 SHA/tree/status 核对 | 只读工具记录；冻结快照 10:48:00 | exit 0；候选仍 clean |

每个 run 有同名 `.command.json/.stdout.log/.stderr.log`，argv、cwd、秒级真实起止、exit 和摘要可复查。测试数量有重叠，**没有相加声称独立测试总数**；T21 的 8 条旧台账测试明确 `fixture_mode=True`，本审不计为 PG。`deselected` 只是定向复跑没有执行先前已记录失败的负例，未修改测试/金标/阈值，也未转 skip。唯一常规 warning 是固定锁中 Starlette/httpx 的弃用提示，本审没有擅自升级依赖。

run 内 [test_review_negatives.py](../../runs/recovery_r02_persistence_review_1_20261015/test_review_negatives.py) 是独立审查输入，调用固定 WT 的准备夹具和业务仓储；不在产品或现有测试树添加补丁。外层在 stdout/stderr 写盘前替换 TEST DSN、密码及密码的全部连续 8 字符片段，故意认证失败另在内存扫描并替换四类敏感值与连续 8 字符片段；没有写原始 JUnit，没有用缩略/showlocals=False 当保护。

初版 credential tracer 探针也保留：10:43:01–10:43:15，recorder exit0，内部 111 passed/1 个故意失败，同时因 tracer 干扰 coverage 导致 44.60% 门失败。这是本审 harness 失真，未冒称业务覆盖退化；改用 v2 返回值扰动后仍真实暴露 token/hash，且 60% 门实际通过。初版 graph cache 放 Windows mount，被 portable 安全校验拒绝（exit1）；改用唯一 Linux 私有 cache 后成功，初版 stderr 保留。误用不存在的 `get_schema` CLI 名称及 PowerShell glob 的读取错误没有算测试结果，随后按官方 help 的 `get_graph_schema` 与实际目录读取完成。

## Must fix（全部 blocking）

1. **[P1] 已有事件可以吞入第二个不同 CVE** — proven bug。位置：`backend/src/ai_intel/knowledge/event_linking.py:L172–244`，特别是 216–232；DTO 在 77–81 只校验本次输入。
   - **What this is / 输入：**先真实 PG 发布稳定事件 X，external_ids 只有 CVE-A；另一个合法 EventSubmission 使用同 X、只有 CVE-B、新 publication_key。同 article/revision 可复用，两个 CVE 各自都只出现一次，所以两个 DTO 均合法。
   - **Problem / 期望与实际：**期望拒绝硬 ID 冲突或形成两个事件。实际第二次未匹配已有 external ID 后直接按 X 更新并追加映射，同 X 最终拥有两个 distinct CVE；独立 `test_existing_event_cannot_gain_a_second_distinct_cve` 失败，见 [existing_event_second_cve.observed.json](../../runs/recovery_r02_persistence_review_1_20261015/existing_event_second_cve.observed.json)。`one_cve_per_event` 的单 DTO 检查不能保护已有数据库身份。
   - **Fix：**在已有 event 分支、任何版本/映射/消息写入前，读取其已存 CVE 并校验与待加 ID 的联合；无 CVE → 后补一个 CVE仍允许，有不同既存 CVE则拒绝。保留两次提交、共享 GHSA 命中已有 event 和无 CVE 后补的 PG 回归，失败后 event/business_version/epoch/receipt/outbox 都不得改变。
   - **If we skip it / 影响与复验：**原 T17-C04/C05 的多 CVE 不误并不变量被绕过，下游事实和图会归到错误身份。复验上述负例、同文双事件和 merge/undo 已有 PG 用例；预期本例通过且不减少原两事件覆盖。

2. **[P1] supersedes 撤掉另一版本分支或评分机构的独立事实** — proven bug。位置：`backend/src/ai_intel/knowledge/persistence.py:L712–759`；不同 authority/branch 的拒绝仅出现在 disputed 分支 766–779。
   - **What this is / 输入：**同 subject/predicate、同 source 与 document 的后续 revision。第一例旧 `affected_versions` 为 pypi/branch1.x `<1.5`，后版为 branch2.x `<2.5`；第二例旧 CVSS authority vendor-A、后版 vendor-B。两侧 supported、证据坐标与语义标记合法，明确提交 supersedes 关系。
   - **Problem / 期望与实际：**期望不同 branch/authority 保持独立，错误 supersedes 要整体拒绝。实际只确认同来源且 revision 后移，就把旧记录写 `superseded/is_current=false`；两例都只剩新 claim 当前可读，见 [supersede_branch](../../runs/recovery_r02_persistence_review_1_20261015/supersede_branch.observed.json)、[supersede_authority](../../runs/recovery_r02_persistence_review_1_20261015/supersede_authority.observed.json)。这违反 CR-R05 和 R02-preflight 的不同作用范围并列语义。
   - **Fix：**supersedes 前复核断言的评分机构及 typed version range 的生态/分支和字段作用范围相同；同文后版不自动证明“同一字段自修订”。不需要另一层仓储，直接在现有 relation 校验中拒绝不匹配并保持保存点回滚。
   - **If we skip it / 影响与复验：**某个分支或机构仍有效的断言从读/搜索候选/导出消失，历史虽保留但当前结论错误。复跑两个独立参数例、同一字段正常 supersede、不同 authority disputed 拒绝、A→B→A 与历史；负例需核对旧 status/当前候选/epoch/messages 原值。

3. **[P1] disputed 关系把模型假设升级为当前事实候选** — proven bug。位置：`backend/src/ai_intel/knowledge/persistence.py:L761–789` 与当前查询 882–886；初始发布约束在 333–337。
   - **What this is / 输入：**同 subject/predicate/time/authority：A 是 model_hypothesis、unverified、condition=true，B 是 source_explicit、supported、condition=false；均有合法引文，提交 disputed 关系。
   - **Problem / 期望与实际：**期望模型记录始终 unverified，并且不进入当前已核验事实候选；允许拒绝该状态转换。实际关系分支无双方 supported/核验状态检查，把 A/B 一并设 disputed，A 因 source_verified/is_current 被 `list_current_claims` 返回，导出共享同入口。独立测试失败且保存了实际模型记录，见 [dispute_model_hypothesis.observed.json](../../runs/recovery_r02_persistence_review_1_20261015/dispute_model_hypothesis.observed.json)。这里没有声称实际状态变 supported；失效点是模型只能 unverified 的冻结规则及事实候选边界。
   - **Fix：**转换前要求双方为可核验的有效事实，拒绝 model_hypothesis/legacy/未验证支持的 dispute 发布；防御性当前查询也排除模型假设和未核验 provenance。保留未验证材料可读历史，不把所有缺失转成空成功。
   - **If we skip it / 影响与复验：**一个相反条件关系即可让候选假设进入搜索和事实导出，后续问答/规则可能将其当已核验事实。复跑本例和正常两 supported 条件冲突；再加 legacy/schema1、未核验语义支持负例，均不得产生部分状态/history/receipt/epoch/outbox。

4. **[P1] 原认证测试失败会把 session token/hash 写入 pytest 输出** — proven security/test bug。位置：`backend/tests/integration/test_r02_auth_state.py:L382–394` 与 `backend/tests/conftest.py:L18–49`；其它含 raw token 的测试 locals 需一并核查，未假定全部已复现。
   - **What this is / 输入：**对原 `test_session_hash_only_is_stored` 保留 `--showlocals`，成功 PG 登录后仅受控扰动返回的 SessionRecord.session_id，触发其原最终 assert。DB 中会话仍是实际生成的随机 token/hash，未改变生产配置。
   - **Problem / 期望与实际：**期望故意失败的终端/JUnit 内容也不含密码/token/CSRF/hash/DSN 或连续 8 字符片段。原 conftest 只脱敏 TEST URL/密码，原测试 locals 中 `token`、`stored` 为普通字符串；**完整 token、完整 session_hash 和连续 8 字符片段实际出现**。密码/CSRF 本次没出现，未外推。内层失败 exit1、外层记录器 exit0，见 [credential_failure_v2.observed.json](../../runs/recovery_r02_persistence_review_1_20261015/credential_failure_v2.observed.json) 和 [先脱敏的原失败文本](../../runs/recovery_r02_persistence_review_1_20261015/credential_failure_v2_sanitized.log)；原始敏感文本仅在内存扫描，未输出/落盘。
   - **Fix：**测试敏感 Credentials/session/hash locals 使用 SecretStr 等安全 repr，并在失败报告写盘之前保证实际值及其连续 8 字符片段脱敏。新增保留 --showlocals 的故意失败 canary，验证 stdout/stderr/JUnit；原子进程测试内部 `showlocals=False` 和 dataclass `repr=False` 不覆盖普通 token/hash locals。
   - **If we skip it / 影响与复验：**一次真正断言失败就会把当时仍有效的测试 session bearer 留在 CI/审查日志。复跑同一受控故障，所有四类值与片段暴露布尔均为 false，再复跑既有进程/日志安全用例；禁止以关闭 locals、截断或不跑失败例作为修复。

没有额外可证明的 Should/Nice finding；没有为追求更短代码要求重写事务层。上面每项同时缺少原仓回归，但本审已用独立可观察输入证明，不把它们只登记为 missing test 或 unproven concern。

## 已独立核对的有限能力

- **认证：**默认 factory 显式 PG state，不回退内存；不同 factory 与真正独立 spawn 进程 issue/read/revoke、当前 role 单 join、30 分钟到期、hash-only 存储、8 并发共享 5 占位、跨进程失败窗口、成功仅释放己方占位、审计失败 rollback 都已复跑。CSRF 非 ASCII/错误 Origin 不撤销有效会话；PG 故障固定 503、不回显诊断；审计 READ_AUDIT、tenantless 拒绝、未知账户失败仅 system_admin、稳定分页/no-scope 拒绝与固定字段通过。实际 API 回应边界和 PG 仓储均有证据，但 Must4 留日志安全缺口。
- **知识与原文：**source/evidence scope 不得升公开、tenant B/viewer/无 tenant system_admin 读 ID/搜索候选/导出不可见、semantic-unverified 和模型初始 unsupported 拒绝、非零 Unicode block/重复 quote 位置、错误坐标/哈希拒绝、legacy 缺 provenance 不进入当前候选均复跑。claims/evidence/assertions/history/entity/alias/relation/receipt/epoch/job/outbox 同 Session/保存点，第二行非法和真正 PG outbox trigger 异常均回滚；异 digest collision 抛 IdempotencyConflictError，独立进程 samekey 同 receipt、重启同 claim identity。
- **事件：**同文双 CVE建两事件、两事件合并拒绝、同 scope merge/undo 保留来源/历史/outbox、merge 后新增 association 的 version fence 拒绝 undo 均通过；这不抵消 Must1 的已有身份追加漏洞。
- **时间、历史、内容：**supersede 旧 claim 历史、404 不撤回正例通过。独立同 timestamp 两次状态转换按 `transition_sequence`，新连接连续五读稳定为最后 disputed；A→B→A三修订、1/3同hash不同UUID，新 ContentStore 逐条 `read_verified` 字节等于原输入，见 [same_timestamp_history](../../runs/recovery_r02_persistence_review_1_20261015/same_timestamp_history.observed.json)、[a_b_a_read_bytes](../../runs/recovery_r02_persistence_review_1_20261015/a_b_a_read_bytes.observed.json)。
- **payload 与迁移：**新连接从 `change_events.payload` 读回非空 canonical JSON 字节，重新计算 digest 等于 receipt，job/outbox 都指同 `pg:change:<UUID>`，见 [persisted_payload](../../runs/recovery_r02_persistence_review_1_20261015/persisted_payload.observed.json)。空随机 schema 与带旧 claim 的 0006 schema升级到0009实际通过，原 text/时间/unknown/scope保留、schema1+legacy隔离；0007 field_fingerprint 实际 `unique=true`，并非旧草案的普通索引；0009列与模型一致。本审没有降级现有 head9 或清任何共享历史。

## 入口、未完成与不外推范围

portable CLI 为官方 `codebase-memory-mcp 0.11.0`；本审 cache `/tmp/dianzi-cbm-r02-persistence-review1-20261015`，仅索引固定 `backend/src`，642 nodes/2637 edges。实际执行 `get_graph_schema`、精确 qualified `search_graph`、`trace_path`（AuthenticationSessionService.authenticated_session / KnowledgeRepository.publish / create_application）；[graph receipts](../../runs/recovery_r02_persistence_review_1_20261015/graph_traces.py) 及对应 JSON 已保存，并用 rg/源码/callsite复核。图显示通过协议调用时也有解析局限，本审没有把有边/无边当业务运行证明。

真实 `create_application → build_auth_router/build_health_router` 已核对；默认路由只有 auth/health，知识仓储没有 API/worker caller。0009 `enrichment_results` 仅表和 mapping，`EnrichmentLedger` 仍只允许显式 fixture，没有实际逐维状态 service；MinIO adapter 没有实现。`pg:change` 有真实可读 payload，但真实 relay/worker消费、重投递副作用及恢复属于 R03 未通过范围，不能从存储可读推断消费可运行。以下为明确未完成/未验证，不被四项修复自动关闭：

| 范围 | 本审状态与限制 |
|---|---|
| 会话与知识账本 slice 的 correctness/security | **failed / needs_changes**（Must1–4） |
| 九维结果状态 service、MinIO | **partial/not_started**；本审只检查0009 schema，整 R02明确缺项 |
| 显式 withdrawn / 双时间 valid_at 与条件作用域完整服务 | canonical 仓储本轮仅 supersedes/disputed 和 known_at；没有独立 PG 撤回/valid_at能力实测，整 R02/后续合同不得删验收 |
| 实际 API知识读搜导出/worker 和浏览器闭环 | **not_run / 尚未接线**；本审 PG repository 隔离不计实际产品端到端权限通过，R04后才可验证 |
| 备份恢复、MinIO故障/重启、多进程原文字节重读 | **not_run**；未拿随机schema升级/新store对象冒充备份或MinIO验收 |
| 提供者模型、FOFA/来源、正式盲测、连续运行 | **not_run/blocked_live**；未访问key、不付费，不填写正式准确率/时效/稳定时长 |
| 性能 | 未做容量/吞吐指标；按有界本地多进程负载审查锁/事务/唯一性。scope级public锁目前串行发布，未测目标吞吐，不凭猜测出性能finding或容量通过 |
| 人工最终验收、前端/e2e、CI云端复现 | **not_run**；独立源码评审不能代替这些证据 |

仅 E1 获得共享 PG/事务/迁移和授权边界有限证据；F1 获得修订与去重存储证据，F2 获得来源断言/关系持久化证据，F3 获得仓储 ACL/历史/候选复核证据。这些不是整评分项或 T04/T05/T06/T17/T19/T21 的最终验收；关系正确性、模型语义、实际接口、安全日志仍有上面失败/未完成项。

## 修复与下一步

主控可按四项最小修复分工，新增原仓回归，保持公共合同/迁移唯一所有权。修复提交冻结后由本审继续定向复核：7个独立测试全部运行（不得选择性 deselect 失败例）、故意失败的完整输出安全探针、auth/knowledge相关PG及整体unit60%门；如新变更影响合同/迁移，再补相应回归。R02之外不在本审批准范围。

**Verdict: fix 1, 2, 3 and 4 first.** 不放行本完整会话与知识账本批次，不签整 R02/G-A/原T。

Not checked: MinIO、九维state service、真实知识API/worker重投递、双时间/撤回全合同、备份恢复、产品浏览器/模型/来源live、容量性能、正式盲测/持续运行与人工最终验收。
'''
TARGET.parent.mkdir(parents=True,exist_ok=True)
end=datetime.datetime.now().astimezone().isoformat()
text+='\n本报告写作开始：'+start+'；写作结束：'+end+'。命令日志起点 10:34:03+08:00；最初只读读取没有单独保存秒级 receipt，不编造起点。\n'
TARGET.write_text(text,encoding='utf-8')
(ROOT/'report_freeze.json').write_text(json.dumps({'report_path':str(TARGET),'write_started_at':start,'write_ended_at':end,'sha':'0fe642b1c9e5fe4dafa2774e9432bd96079c1b72','verdict':'needs_changes','must_fix':[1,2,3,4]},ensure_ascii=False,indent=2),encoding='utf-8')
print(str(TARGET))
