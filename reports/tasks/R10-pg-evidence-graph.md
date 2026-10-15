# R10 · PostgreSQL 证据图只读切片

状态：`awaiting_review`。本切片 implementation=`complete`；修复代码冻结 `3516b9109b9b7f2c5691d78ad0439aea4a659f4f`，等待原独立 reviewer 定向复核。整个 R10 仍需产品注册、Neo4j 投影、前端与独立验收，不能据此登记整 R10 完成。修复记录时间：2026-10-16T04:18:48+08:00。

基线：`cc1b1d302e22048f567475b7084bcd5490761ed2`。初版历史冻结代码：`b0b7a5b856cc38862f64c01565309564d67c34c0`；初版归档截止 `16803ce6be9ad6adb6d89f46c594cfa420190c24`。工作树：`D:/wt/r10-pg-graph`；分支：`codex/r10-pg-evidence-graph`。主 checkout 的既有未提交修改没有触碰；没有 push 或自行 accepted。

## 独立初审后的修复交付

独立 reviewer 在初版复现了 3 个 P1：typed value/空泛 quote 被提升为六类强关系；首次 RR event SELECT 后实际提交的父 ACL/claim/epoch/版本变更仍返回旧图；同窗口角色降权仍返回私图。另有 2000 支持行重复论文目标 ACL SELECT 的 P2。初审原 20 为 8 passed/12 failed，扩展 32 为 20 passed/12 failed；作者初版 35 通过不足以否认这些缺陷。以下修复说明与冻结复跑取代后文初版的语义及单 RR HTTP 说明；初版日志和叙述保留为历史。

主控已明确批准最小读围栏设计和 10 个旧正例 fixture 的语义迁移，正式记录在 [CR-R10_graph_validity](../../docs/decisions/CR-R10_graph_validity.md)。公共 schema/auth/lock 配置、发布服务、迁移、app 注册、进度及金标分母没有改变。

修复的两个源码文件仍为 `backend/src/ai_intel/knowledge/evidence_graph.py` 与 `backend/src/ai_intel/api/graph_routes.py`。已有 R10 unit 和 PG fixture 的版本输入/原文迁移、专属 `backend/tests/integration/test_r10_graph_validity_pg.py`、上述 CR、本报告和新 run 目录是其余改动。冻结版本相对初版归档共 6 个代码/CR 文件，精确清单、原始字节和规范 Git blob 在新 run 的 `frozen_code_manifest.json`。

关系投影按 claim 聚合已验证引用后复用现有 `validate_field_candidate`，同时检查 typed value 与肯定原文中的组件/生态/版本边界/限定条件、体系 ID/固定 commit/机制/前提、论文正文/URI/title/目标身份和修复/缓解句。事件绑定由 PG subject/当前来源关联以及真实外部 CVE/GHSA 原文 ID 或精确 owner JSON 字段共同核验；非 CVE 使用同主来源验证后的 affected_product/source_excerpt 与安全描述。原文不需要内部 UUID。主题相似、背景 ID、条件省略、缺内容覆盖或目标父 ACL 均保持 unknown。复用模型专用校验器时只中和临时候选的模型权限限制，然后核对 PG 目标，不改已有 rule_derived 的比较支持或 static_reviewed，不写回事实。投影规则明确升为 `r10-graph-1.1.0`。

HTTP 首次 REPEATABLE READ 只生成候选和有界输入摘要。关闭该事务后，新的 READ COMMITTED 事务重新调用现有 `lock_authenticated_scope`，比较完整 role/permissions/tenant；按认证 → source → document → revision → event → claim/evidence/block/关联 → epoch 取锁。当前输入、关系和父 ACL 全部重读，即使直接撤权不 bump epoch 也会失效。在锁内构造 JSONResponse 字节后提交；0 重试，没有 epoch 锁内回拿父锁。变化返回 409，身份失效/权限变更/不可见分别为 401/403/404，继承原锁等待超时后 503。直接 service 调用的上层仍须建立一致性事务；产品交付应使用此路由围栏。

论文目标/文档仅在本次已认证 scope 的 event_graph 调用中 memo，下一调用重查 ACL。图节点/边/支持行上限保持 200/400/2000，围栏超容量明确 409。内部输入摘要只用于当前读有效性比较；`content_sha256` 仍为有界选集摘要，不替代 business_version，也不能用于截断全图的 Neo4j 一致签名。

新 run：`reports/runs/recovery_r10_graph_validity_20261016/`。完整 argv、cwd、+08 起止、退出码和验证 SHA 逐次保存为对应 JSON；JUnit 保存实际 case/参数/失败。冻结复跑时间为 2026-10-16T04:10:58+08:00 起，主组于 04:12:38+08:00 结束；没有在复跑中改代码。

| 冻结检查 | 实际结果 | 证据 |
|---|---|---|
| 原 pure 10 + 迁移后的原 PG 35 + 新 PG 30 | exit 0；75 passed，0 fail/error/skip | `frozen_author_and_validity.json/log/xml` |
| R02/R07 原相关回归 7 文件 | exit 0；103 passed，0 fail/error/skip | `frozen_regression.json/log/xml` |
| 原作者 PG 35 原 bytes | exit 1；24 passed/11 failed，0 error/skip | `frozen_original_author35.json/log/xml` |
| 原 reviewer 扩展 32 原 bytes | exit 1；22 passed/10 failed，0 error/skip | `frozen_original_reviewer32.json/log/xml` |
| 原 reviewer 20 case 子集 | exit 1；16 passed/4 failed，12 deselected，0 error/skip | `frozen_original_reviewer20_subset.json/log/xml` |
| Ruff / 格式 / mypy / 代码+CR diff check | 各 exit 0；7 文件格式已符合，2 源文件类型通过 | `static_commands.json`、对应 `*_frozen.log`、`code_diff_check.log` |

primary suite 与回归合计 178 passed。旧材料复跑另列，不并入这个通过分母，不将旧红改 skip。20 子集是从保持原 bytes 的现存 32 脚本按 `-k 'not exact_fixture_fields and not unknown_condition'` 选取原 20 case；它不是另一个可验证的最初 20 脚本字节版本。所有脚本 hash 和 case 名称在清单/summary 中保留。

原作者 PG 文件 raw SHA-256=`dca8f657fc384c6af9363b020c7ce49ce9bd1d2b08f913fa73625ff2d13d3bf9`，原 Git blob=`2ccfb158d3d231af1a442cdda0e20d41023d515e`；其旧引用缺六类实际内容，10 个正例在新语义保持红，另 1 是旧 REST `1.0.0` 版本期待。迁移逐 case 原缺口、新自然公告输入及保留断言见 CR。合成原文字节实际存入内容寻址对象，新增检查直接读取验证坐标/hash，不在原文插入系统 UUID；仍是 fixture。

reviewer 原 32 脚本 raw SHA-256=`cfbbb95d227f4e884d2765bde6da5dbd1121c5ffd9c159ac99a1e9eadf0bfe16`。原 12 个 P1 反例均通过；10 个 known loss 是 6 个内部 UUID/不完整原文的旧强边正例、3 个由旧虚构边驱动的截断期待、1 个缺绑定的 PoC same_event 期待。原脚本/原期待不修改，原作者 helper 副本也保持旧 bytes；新增真实字段/原文正负例、截断和 PoC 安全检查另列。独立 reviewer 决定迁移与新语义是否可接受。

新 30 PG 覆盖：父 source/document/revision/claim/epoch/event version 12 个真实提交窗口（分别 bump/no-bump epoch）；role/tenant/session 三种身份变更；真实父锁等待与继承 5000ms 超时；错误组件/限定条件/边界/修复/事件背景 ID；ATLAS 前提省略；精确 owner 字段 rule_derived；非 CVE 描述缺失/普通描述；PoC 只做 presence；原文字节和 2000 支持行负载。实际 HTTP body/hash 与 SQLstate 保存在 `frozen_author_and_validity_http.jsonl`：窗口变化为 409，角色/租户为 403，会话为 401；父→epoch writer 提交时 reader 返回 409，0.216s、无 40P01；父锁超时返回 503，5.154s、SQLstate=55P03，没有假成功。此负载运行观测不证明所有并发调度均无死锁。

2000 支持行来自 100 claims ×20 evidence，目标相同、max_nodes=1/max_edges=1，单次 service 读取观测 7 SELECT、其中 1 目标 ACL、0.407s；root-only truncated=true。下一次将目标改为 other 私有后重查拒绝，缓存未跨请求。这是受控 fixture 查询计数，不是 HTTP 全围栏总 SQL，也不作为官方性能评分或关系准确率。

CBM 官方 CLI 冻结后自己的 backend/src fast 索引为 1426 nodes/7311 edges、未索引 0，qualified graph/fence traces 和 architecture 原输出已保存。首次 architecture 使用 JSON 数组 flag 被实际 CLI 拒绝（exit 1）；按 CLI help 的 `--aspects all` 重跑 exit 0，两个原始输出均保留。修改前 auth/field qualified trace 从旧 run 原字节复制到新 run。工具图只作导航，不证明业务正确。

修复源码/CR 的提交差异及 staged 检查均 exit 0；完整归档 staged diff check 为 exit 2，来自保留的 CBM stdout EOF 空行、原始 diff patch 的空上下文行、旧失败 log/XML 的 traceback 空行。命令、原输出在 `archive_diff_commands.json`、`staged_archive_diff.log`，没有裁剪旧 red/原输出或添加忽略规则。该归档空白检查没有计作通过。`original_preservation.json` 另用 AST 实际确认原作者 test IDs、参数装饰器及全部断言一致，仅归一规则版本 1.0.0→1.1.0；raw 与 canonical Git blob 分别登记。

开发阶段所有红记录保留，包括旧作者24/11、reviewer22/10、owner 字段诊断 NameError/大小写绑定失败、原文字节检查 import 失败及修后重跑。focused pytest 仍清空默认 addopts，全仓覆盖率门=`not_run`，未改门槛；观察到已有 Starlette/httpx 弃用 warning。unit/contract/security/integration=`passed`；原材料兼容预期=`failed`；frontend/e2e/live/manual=`not_run`。0 外网、model/provider、费用、扫描或新服务。

剩余约束：没有完整原文/体系 coverage/精确源字段或非 CVE 安全描述时保守返回 gap；未接 R09 知识卡生产发布、Neo4j、consumer、UI 和产品入口。下一步原独立 reviewer 定向复核冻结代码、CR、日志和 manifests，之后主控注册路由/冻结正式公共图合同并做集成回归。不得自行 accepted 或据此接受整 R10。

## 初版交付记录（历史，已被上述修复替代）

## 本轮输入、范围与合同核对

已读 AGENTS、执行图、恢复主计划 6.2 与 R10 卡、T17/T21/T22/T23/T41、数据/工作流/API/测试合同、进度与交接、public_api_v2 Relation、KnowledgeReadService/路由、KnowledgeRepository/EventRepository、Ponytail 5.2.0 全文。进度索引中的 R07/R09 旧 pending 不作为否认已集成代码的证据；以主控明确给定的 R07 独立 Ship 基线和已有源码为输入，R09 知识卡生产发布未接通这一缺口保持。

主控授权本轮独立实现已有 PG 事实的只读切片，不等待 R09，也不生成知识卡或模型候选替代它。没有改公共合同、认证、应用装配、迁移、锁、配置、既有发布服务、UI 或 progress。

public_api_v2 已有六类 Relation，使用单 `source_revision` 和 `citations`。本次冻结内部 `GraphSnapshot`/`GraphEdge` 使用复数修订与证据 ID，不冒充同一个公共 DTO。主控已经同意内部补 `content_sha256`；它不替代事件业务版本，截断时只描述当前选集。公开合同和适配由主控后续冻结。

## 改动文件和可接入口

- `backend/src/ai_intel/knowledge/evidence_graph.py`：内部严格 DTO、固定六类自动关系、范围/当前性/支持校验、有界图快照与内容摘要。
- `backend/src/ai_intel/api/graph_routes.py`：`build_graph_router(service_provider, engine)`，复用现有 AuthenticationSessionService 工厂，路由为 `GET /events/{event_id}/graph`，由上层统一加 `/v1` 或 `/api/v1` 前缀。
- `backend/tests/unit/test_r10_evidence_graph.py`、`backend/tests/contract/test_r10_graph_contract.py`、`backend/tests/security/test_r10_graph_boundary.py`、`backend/tests/integration/test_r10_evidence_graph_pg.py`：本轮直接测试。
- 本报告和 `reports/runs/recovery_r10_pg_evidence_graph_20261016/`：实际日志、JUnit、命令、代码 patch、文件/字节/规范 Git blob 清单。

输入是调用方已认证的 `AccessScope` 和 UUID，输出含 `event_id/business_version/rule_version/nodes/edges/truncated/gaps/content_sha256`。`event_graph(event_id, max_nodes=200, max_edges=400)` 严格拒绝越界、bool 和非 UUID。HTTP 不接受 tenant、scope、depth、任意查询或排序表达式；认证错误、不可见对象、无权限、依赖失败分别为 401/404/403/503。

REST 在同一 Session 使用 REPEATABLE READ。直接调用服务的上层也必须建立一致性读事务；本服务不提交、写表或缓存事实。

## 实现事实与证据边界

1. 每条有效关系必须来自该事件当前 active 关联、当前可见修订、subject 精确等于事件 UUID 的当前事实、匹配来源/修订/origin 的 SourceAssertion，以及同修订的 validated/supports 证据。原文 quote/hash/block hash/坐标重新核验；来源、文档、修订、证据、claim 的 ACL 均在 SQL 中过滤。
2. 只投影 `supported + source_verified + condition=true` 的非 stale 明示/结构化/人工确认事实。`MODEL_HYPOTHESIS`、unverified/disputed/withdrawn/superseded/conflict、缺失断言、非当前或损坏证据不会成为有效边。没有候选晋升或默认 confirmed。
3. same_event 来自真实 event_documents 与上述支持事实；同一篇多漏洞文档不能因相同修订就把另一 subject 的事实连到当前事件。
4. 漏洞到组件/版本和反向漏洞清单共同引用同一支持 claim/evidence。版本节点身份保留 ecosystem、package_key、scheme、原表达式、区间/显式版本和 scope。不同生态、区间或版本不合并，也不对范围做并集。未知比较器/方案或无明确版本边界保留缺口。
5. ATLAS 边读取已发布 typed taxonomy ID/version、机制和前提；论文边要求已发布非 background 的 paper 关系、成对目标文档/修订、当前 paper 目标及其来源/文档/修订父 ACL。只共享主题、未绑定目标或目标不可见/过期不强连。
6. 处置只来自该版本事实显式保存的 vendor_fix 或 mitigations，标签区分厂商修复和缓解；不凭修复边界自行生成升级建议，不运行 PoC。
7. 节点/边 UUID 可重现；相同语义重复输入合并支持标识，机制/条件不同的断言不被覆盖为同一理由。边保留 `relation_type/source_revision_ids/evidence_span_ids/supporting_claim_ids/rule_or_model_version/reason/status/scope`，引用可从既有证据入口回查。不输出来源凭据 URI、原始 metadata、对象存储路径或认证秘密。
8. 私有输入只产生同范围或更窄的派生节点/边；公开事件的私有支持也不变为公开边。不存在有效关系返回显式 unknown gap；依赖错误不返回空成功。
9. SQL 支持记录最多读取 2001 行，用首 2000 行进行投影，溢出标 `truncated`；输出最多 200 节点/400 边，不返回悬挂端点。选集、引用标识、节点/边/缺口排序固定；SHA-256 不含查询时间或耗时。

## 真实执行与冻结复跑

专用数据库：`test_dianzi_r06_catalog_r10_graph_20261016`；`DIANZI_TEST_RUN_ID=r06_catalog_r10_graph_20261016`。连接只从已授权 WSL 私有 connection.json 捕获到进程内存/测试环境，没有输出或保存 DSN。固定验证 loopback:25432、原测试账号前缀和实际库/用户，再使用 `test_r10_graph_<UUID>` schema。每个 schema 经真实迁移并在用例后清理；没有启动新服务。所有输入均为显式合成 fixture，经既有 R02 KnowledgeRepository/EventRepository 的真实 PG 发布接口写入，不是 live 或预设演示图。

冻结复跑的完整 argv、cwd、+08 开始/结束、退出码及代码 SHA 在 `commands_frozen.json`。以下 cwd 均为 `D:/wt/r10-pg-graph/backend`，解释器为现有 `D:/dianzi/backend/.venv/Scripts/python.exe`；runner 统一设置本工作树 PYTHONPATH。

| 检查 | 实际命令摘要 | 结果 | 日志 |
|---|---|---|---|
| 本轮 unit/contract/security | `python -m pytest -o addopts= tests/unit/test_r10_evidence_graph.py tests/contract/test_r10_graph_contract.py tests/security/test_r10_graph_boundary.py -q --junitxml=.../pure_frozen.xml` | exit 0；10 passed，0 failed/error/skip | `pure_frozen.log/xml` |
| 真实 PG/REST | `python -m pytest -o addopts= tests/integration/test_r10_evidence_graph_pg.py -q --junitxml=.../pg_frozen.xml` | exit 0；35 passed，0 failed/error/skip | `pg_frozen.log/xml` |
| 相关已有回归 | `python -m pytest -o addopts=` 加 R02 publication/boundaries/dimension、R07 typed value 合同、R07 signal/literature PG、R02 relation identity 共 7 文件 | exit 0；103 passed，0 failed/error/skip | `regression_frozen.log/xml` |
| Ruff | `python -m ruff check` 本轮 6 个 Python 文件 | exit 0 | `ruff_frozen.log` |
| 格式 | `python -m ruff format --check` 同 6 文件 | exit 0；6 files already formatted | `format_frozen.log` |
| 类型 | `python -m mypy src/ai_intel/knowledge/evidence_graph.py src/ai_intel/api/graph_routes.py` | exit 0；2 source files 无问题 | `mypy_frozen.log` |

冻结复跑共 148 个通过的测试执行，未运行仓库全量覆盖率门，未修改覆盖阈值/测试配置/金标/计分分母。focused pytest 显式清空默认 addopts，避免将局部执行误报为全仓覆盖率结果。pure 和 PG 各观察到现有 Starlette/httpx 弃用 warning 1 条；未改依赖锁。

保留开发阶段证据：`initial_unit.log` 为模块尚未实现时的 collection error，exit 2（非环境缺失、非业务测试失败）；此前纯测试 9 passed、PG 27 passed、相关回归 103 passed 的日志与旧命令收据保留。初次定向 mypy 的 3 个类型错误已修正；冻结复跑不再出现。

业务冻结 diff 的 `git diff --check <baseline> <code_commit> -- backend` 为 exit 0；全归档版本的同项检查为 exit 2，只因 `cbm_schema.json` 原始 CLI stdout 在 EOF 带一个额外空行。该原始材料保留，没有裁剪原始输出或添加忽略规则；实际命令/输出见 `diff_checks.json`。这不计作 Python 检查或测试失败，也不宣称全归档空白检查通过。

## 验收与评分项证据

| 要求 | 可观察证据 |
|---|---|
| 六类正例与反向同 claim | `test_six_relations_are_derived_from_published_pg_claims_and_preserve_reverse_support`，实际发布多源 typed 事实，逐类检查，重读/重复发布不增边 |
| 六类缺证据负例 | `test_invalid_or_unrelated_support_never_enters_effective_graph` 的 17 场景，以及 paper 背景/无目标/过期/父 ACL 和未知版本缺口测试 |
| 同名异生态、不同范围与冲突 | 独立 component_version 身份；disputed/conflict 不入图；不做来源投票或范围并集 |
| 当前变更与并发读 | `test_current_version_changed_withdrawal_and_truncation_do_not_resurrect_edges`：旧事务快照稳定、新事务见撤回；同事件版本下内容变化的摘要不同 |
| 跨租户与私有派生 | 私有事件/查看者拒绝、公开事件私有边保持私有、五层父 ACL 参数化用例、真实 PG 账户降权后 HTTP 404 |
| 有界与错误 | node/edge 截断无悬挂端点、UUID/范围边界、depth/query/tenant 拒绝、真实会话与固定 503 不回显异常 |

本轮提供 F2/A1/P2 所需关系可解释与工程边界的代码/fixture 证据；没有测量关系准确率、召回率、真实自动采集或评分优秀档。

CBM 使用官方 WSL Ubuntu-22.04 root 下既有 0.11.0 CLI，修改前执行 help/schema、自己的 backend/src index、architecture 与 KnowledgeReadService/KnowledgeRepository 的准确 qualified traces，并用 rg 人工核对业务链。冻结后索引为 1416 nodes/7214 edges、未索引文件 0；新服务 qualified trace 另存。CBM 图边只用于导航，不证明业务正确。原始证据见 `cbm_cli_help.log`、`cbm_schema.json`、`cbm_architecture.json`、`cbm_*_trace_qualified.json`、`cbm_frozen_index.json`、`cbm_frozen_graph_trace.json`。

## 验证状态、未做与交接

unit/contract/integration/security=`passed`；frontend/e2e/live/manual=`not_run`。0 外网、0 模型调用、0 费用、0 资产扫描、0 新服务启动。R09 正式知识卡发布未接；有缺口时图为空/unknown，未造替身。没有把 fixture 测试写为 live。

原 R10 任务中的 Neo4j 重建/物化/滞后、图页面和真实场景还未交付。当前内容摘要不能为截断图签全图一致；事件 business_version 也不保证覆盖每次事实状态变化，主控后续必须结合 PG scope epoch/outbox 失效与完整投影策略。严格 subject UUID 和明确 typed 支持的范围意味着旧的文本/未确认候选、未发布知识卡、没有明确身份的合并遗留事实可能只有缺口；本切片不推测补齐。

建议下一步：新的非作者 reviewer 在冻结代码上复跑本轮命令并检查 ACL/证据/空结果；主控依据审查再正式注册路由、冻结公开图合同，并接 Neo4j 投影和 UI 集成回归。不要据本报告直接接受整 R10 或原 T17/T21/T22/T23/T41。
