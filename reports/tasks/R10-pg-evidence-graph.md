# R10 · PostgreSQL 证据图只读切片

状态：`awaiting_review`。本切片 implementation=`complete`；整个 R10 仍需产品注册、Neo4j 投影、前端与独立验收，不能据此登记整 R10 完成。记录时间：2026-10-16T03:09:10+08:00。

基线：`cc1b1d302e22048f567475b7084bcd5490761ed2`。冻结代码：`b0b7a5b856cc38862f64c01565309564d67c34c0`。工作树：`D:/wt/r10-pg-graph`；分支：`codex/r10-pg-evidence-graph`。主 checkout 的既有未提交修改没有触碰；没有 push 或自行 accepted。

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
