# G-C / R10 PostgreSQL 证据图只读切片 · 独立初审 1

审查结论：`needs_changes`。必须先修复下列 1–3，再在新冻结版本复核；第 4 项是已实测的重复查询问题。此结论只覆盖本次 PG 只读切片，不接受整 R10、G-C 或原 T17/T21/T22/T23/T41。审查者没有改业务代码、状态、金标、合同、依赖、认证实现，没有提交或 push。

这次变更从 PostgreSQL 的当前事件关联、typed claim 和证据生成六类内部图边，并增加带认证的只读路由工厂。它校验三层来源权限、原文坐标和 hash，限制输出为 200 节点、400 边，并给选集计算确定性摘要。当前实现还不能保证关系内容得到证据支持，也不能阻止请求期间已撤权或撤回的旧快照作为有效结果返回。

## 审查对象、规范与独立性

- 代码基线：`cc1b1d302e22048f567475b7084bcd5490761ed2`。
- 固定代码：`b0b7a5b856cc38862f64c01565309564d67c34c0`；独立 detached 工作树 `D:/wt/r10-graph-review1`。业务源码与测试均从这个工作树读取、导入和执行；未审作者活动源码。
- 材料冻结：`16803ce6be9ad6adb6d89f46c594cfa420190c24`。材料报告通过 `git show` 读取，作者目录仅对封存清单内 37 个报告/日志文件读取原始 bytes 以核对 raw hash，未运行作者脚本。
- 已读：AGENTS、执行地图、恢复 R10、主计划 6.2、T17/T21/T22/T23/T41、docs 03/04/05/06、public_api_v2 Relation、进度/交接、README、相关发布/事件/认证服务及调用方。使用 Ponytail Review **5.2.0**，按正确性、安全、数据历史、实际负载、测试和复杂度检查。按明确授权只写本报告和独有 run，不 spawn，不写 accepted 或 progress。
- 实际服务名为 `EvidenceGraphReadService(session, scope)`，入口 `event_graph(event_id: UUID, max_nodes=200, max_edges=400)`；不是另一个推测的服务签名。
- 进度索引冻结时 R10 仍 pending。这是历史索引，不作为否认本次已授权切片的依据，也没有由 reviewer 改写。

业务变更仅六个新文件：`knowledge/evidence_graph.py`、`api/graph_routes.py`，及对应 unit、contract、security、PG integration 四个测试文件。公共 `Relation.source_revision/citations` 未改；内部复数修订/证据 DTO 尚未成为公共适配。

## 必须修复

### 1. [P1] 精确存在的无关引文仍被当成六类关系的支持依据

位置：`backend/src/ai_intel/knowledge/evidence_graph.py:124`、`:240`、`:351`、`:360`、`:405`、`:423`。连接代码：`backend/src/ai_intel/knowledge/persistence.py:386`–`:418`。

- **职责：** 图读取已经发布的事实，并为每条 supported 边保留 claim、修订和原文证据。
- **触发与问题：** 独立测试通过实际 `KnowledgeRepository.publish` / `EventRepository.publish_events` 发布 source_explicit typed 值。支持原文只有 **`explicit source`**，不含事件身份、`fixture-package`、`1.4.2`、`AML.T0051`，更没有论文组件/机制或修复措辞；坐标/hash/validated 标记均合法。六个分例却分别返回 `same_event`、版本正反向、ATLAS、论文、处置的 supported 边。图只核原文存在和发布标记，不核 claim value 与 quote / SourceAssertion binding 的对应；上游发布校验也只依赖 `supports_claim/validated` 标记，没有可用的字段支持验证记录。因此不能把“PG source_verified”视为此处已证明语义支持。
- **影响：** 一个错误或误标的已发布输入能产生可供回答/研判使用的强关系，包含错误的影响范围和厂商修复。`same_event` 虽有真实 PG event_documents 关联，却使用任意事实证据作为确认理由，未检查可靠事件标识或已核验归并依据。论文当前可见不代表它分析这个组件和机制。
- **最小修复：** 在 strong-edge admission 中核对结构化值与精确来源字段/JSON pointer 的绑定；source_explicit/human_confirmed 需要与 claim 值、证据 hash、规则/校验版本绑定的支持结果。无这种依据的输入只留缺口或候选。same_event 使用已核验的事件关联依据；版本/处置需保留边界、否定、条件，ATLAS/论文需保留组件和机制支持。单纯关键词出现仍不能替代语义验证；无法由程序检查的语义必须明确依赖可审计校验记录，不能编造已验证。
- **复验：** `test_unrelated_quote_cannot_become_supported_relation[...]` 六例全红；首轮与扩展复跑一致。另六个带明确事件和 typed 字段的合成正例、六个 condition=unknown 负例通过。修复后应保留所有这些反例，并增加否定/限定条件与结构化字段错绑例。

合同依据：AGENTS §5“引文存在不等于内容支持”；docs03 §3.3、docs04 W04；恢复主计划 6.2 要求每条关键关系发布前逐条证据/结构校验；T22-C02、T23-C04。

### 2. [P1] 已提交的父级撤权、事实撤回和版本变化未阻止 HTTP 返回旧图

位置：`backend/src/ai_intel/api/graph_routes.py:54`–`:58`；`backend/src/ai_intel/knowledge/evidence_graph.py:289`、`:302`、`:451`。

- **职责：** REPEATABLE READ 为图提供内部一致的读取快照；这个 HTTP 接口提供当前有效的图。
- **触发与问题：** 在 HTTP 第一条事件 SELECT 已建立快照后，使用第二个真实 PG 事务分别提交 source/document/revision 的撤权，或 claim withdrawn；同时递增相关 public scope_epoch 与 event business_version。每个变更均在响应前已提交。接口仍 200 返回旧五条 supported 边；仅更新事件版本的分例仍返回 business_version=1，而当前已为 2。路由直接 return 快照，没有独立于旧 RR 快照的当前 epoch/业务版本/输入 ACL 校验。服务没有缓存并不解决这次请求中快照已失效的问题。
- **影响：** 已经不可见的来源证据或已撤回的事实仍作为当前有效关系展示；内容摘要也是旧选集摘要，不能充当当前性校验。原测试证明旧事务快照稳定、新事务见变化，这一数据库行为本身正确，但没有覆盖 HTTP 响应的最终有效性边界。
- **最小修复：** 记录本次所用的 scope epoch / 事件版本和输入版本，在返回前用新的当前读校验它们，并重新核对必要父级 ACL/当前性；变化时有限重读或明确返回失效/重试错误。不要在原 RR Session 中重复读 epoch 后声称看到了当前状态；ACL 变化若不 bump epoch，也要由当前父级检查覆盖。
- **复验：** `test_http_does_not_return_snapshot_invalidated_before_response[source_acl/document_acl/revision_acl/claim_withdrawn/event_version]` 五例全红，扩展复跑同样失败。修复后仍需保留快照内部一致性正例，同时让这五例不再返回有效旧图，并补充空结果→新支持输入时的最终校验。

合同依据：AGENTS §5 PostgreSQL 当前真值；docs04 W08/W09；docs06 §8 不返回已知 stale 为 current；R10 的落后/跨租户有效结果负例。

### 3. [P1] 已提交的账号降权未阻止私有图返回

位置：`backend/src/ai_intel/api/graph_routes.py:48`、`:56`；相关认证入口 `backend/src/ai_intel/api/authentication.py:366`。

- **职责：** 每次请求从服务端会话取得权限，viewer 不能读取私有图。
- **触发与问题：** 使用真实 PG 会话，以 owner 的 analyst 访问 tenant 图。在事件 SELECT 后提交 `users.role='viewer'`，然后继续请求。响应仍 200 返回这个 tenant 事件及私有 supported 边；scope 只在查询前构造一次，返回前未检查账号/会话是否仍有该权限。现有测试只验证降权发生在下一次请求之前的情况。
- **影响：** 权限已经撤销后，该请求仍泄漏私有标题、节点和证据标识。它不同于第 2 项的来源父 ACL 变化，即使所有业务数据版本不变也会发生。
- **最小修复：** 最终响应检查重新从 PG 验证当前会话和账号，核对 scope/权限与图所用范围仍匹配；失效/降权使用现有 401/403/404 边界，不回显对象。可与第 2 项共享一个明确的最终检查点，无需新认证系统。
- **复验：** `test_http_rechecks_current_role_before_returning_private_graph` 红，首轮和扩展复跑一致。修复后同时覆盖 analyst→viewer、登出/撤销、tenant 改变；保留已存在的请求前降权与跨租户 404 正例。

## 应当修复

### 4. [P2] 同一论文目标在一个请求中重复查询 2000 次

位置：`backend/src/ai_intel/knowledge/evidence_graph.py:252`、`:408`；最终输出限额执行于 `:425` 之后。

- **职责：** 每个文献关系回查目标 paper 文档/修订及三层 ACL。
- **触发与问题：** 独立真实 PG 输入有 2001 个支持行，全部指向同一文档/修订；最终请求 `max_nodes=1,max_edges=1` 只返回 root、0 边、truncated=true。实现仍对前 2000 行逐一执行完全相同的目标 SELECT：总 2002 SQL、2000 次目标查询。采用含明确 typed 字段的证据后再次复跑仍红，避免只因第 1 项的无关引文触发负载。
- **影响：** 合法的有界输入也能使一个极小结果重复占用数据库连接与 CPU。实测是本地合成观察，不是正式性能分数；它足以确认重复 IO，而不需要猜测生产并发数字。
- **最小修复：** 在一次服务调用内按目标 document/revision 对去重或复用该目标的验证结果，保留同一次授权快照；不要添加跨请求事实缓存。必要时批量查唯一目标。
- **复验：** `test_support_row_cap_and_repeated_paper_target_lookups` 在普通引文和明确字段引文两轮均红，期望同目标最多一次查询。行读取 2001→处理 2000、输出限额和 truncated 断言均通过。修复后检查同目标去重和多目标不误复用。

## 实际验证、命令与资源隔离

独有证据目录：`reports/runs/recovery_r10_pg_evidence_graph_review1_20261016/`。所有 Python 执行使用 own locked editable venv：`D:/wt/r10-graph-review1/backend/.venv/Scripts/python.exe`；`uv sync --locked --group dev --no-default-groups` exit 0。元数据证实 ai_intel 导入路径是本审查工作树的 `backend/src/ai_intel/__init__.py`，Python 3.12.13。

PG 专用数据库为 `test_dianzi_r06_catalog_r10_graph_review1_20261016`，run ID 为 `r06_catalog_r10_graph_review1_20261016`，loopback:25432。连接从指定 WSL 私有 connection.json 仅 capture 到进程内存/环境，未打印 DSN、秘密或带凭据 argv。迁移前核准指定测试库/测试账号，连接后核对 actual current_database/current_user；每个图用例使用 UUID schema，结束后剩余 r10 UUID schema=0。未操作 development、G-B/作者/root 业务库，未 downgrade、未清库；保留审查者专用 DB 供复现。

原 PG 测试硬编码作者数据库名。独立复制到 run 的 `test_original_graph_pg.py` 只将这一身份断言改为 reviewer 独有库名，逐字核对其余测试逻辑（换行/BOM差异单独记录）。原始与副本 SHA 在 `metadata_and_diff_receipt.json`；没有修改冻结测试或业务。

以下 cwd 均为 `D:/wt/r10-graph-review1/backend`。完整实际 argv、+08:00 开始/结束、exit、code SHA 分别在同名 `.json`；原始 stdout/stderr 为 `.log`，计数取同名 JUnit `.xml`，不借作者通过数作独立通过数。

| label / 命令文件 | 真实执行内容 | exit / JUnit |
|---|---|---|
| `r10_pure` | `python -m pytest -o addopts= -v` 加冻结 R10 unit/contract/security 3 文件 | 0；10 passed / 0 fail/error/skip |
| `r10_pg_original` | 同上，加隔离身份副本 `test_original_graph_pg.py` | 0；35 passed / 0 fail/error/skip |
| `r10_related` | R02 publication/boundaries/dimension；R07 typed-value contract、signal PG、paper target ACL PG；R02 relation identity 共 7 冻结文件 | 0；103 passed / 0 fail/error/skip |
| `r10_pg_independent` | 独立首轮 20 分例；保留原红日志 | 1；8 passed / 12 failed / 0 error/skip |
| `r10_pg_independent_extended` | 六类明确字段正例、六类 unknown 负例、六类无关引文反例、并发五例/角色撤权、限额/digest/重读、损坏与 PoC | 1；20 passed / 12 failed / 0 error/skip；32 total |
| `r10_pg_load` | 2001 支持行、同论文目标，极小输出限额 | 1；1 failed / 0 error/skip |
| `r10_pg_load_exact` | 将负载证据换为明确字段引文，独立复验同一 IO 问题 | 1；1 failed / 0 error/skip |
| `r10_ruff` | `python -m ruff check` 六个变更 Python 文件 | 0 |
| `r10_format` | `python -m ruff format --check` 同六文件 | 0；6 files already formatted |
| `r10_mypy` | `python -m mypy src/ai_intel/api/graph_routes.py src/ai_intel/knowledge/evidence_graph.py` | 0；2 source files |


实际 +08:00 执行窗口如下；完整 argv 保持在同名 command receipt，不记录 DSN。

| label | 开始 | 结束 | exit |
|---|---|---|---|
| `r10_pure` | 2026-10-16T03:09:46.553091+08:00 | 2026-10-16T03:09:51.639865+08:00 | 0 |
| `r10_pg_original` | 2026-10-16T03:10:50.899537+08:00 | 2026-10-16T03:11:37.461402+08:00 | 0 |
| `r10_related` | 2026-10-16T03:15:08.488656+08:00 | 2026-10-16T03:15:32.886813+08:00 | 0 |
| `r10_pg_independent` | 2026-10-16T03:12:42.198766+08:00 | 2026-10-16T03:13:12.125776+08:00 | 1 |
| `r10_pg_independent_extended` | 2026-10-16T03:14:41.033205+08:00 | 2026-10-16T03:15:21.791221+08:00 | 1 |
| `r10_pg_load` | 2026-10-16T03:17:35.914230+08:00 | 2026-10-16T03:17:43.578413+08:00 | 1 |
| `r10_pg_load_exact` | 2026-10-16T03:19:53.363487+08:00 | 2026-10-16T03:20:03.074377+08:00 | 1 |
| `r10_ruff` | 2026-10-16T03:11:23.901371+08:00 | 2026-10-16T03:11:24.305883+08:00 | 0 |
| `r10_format` | 2026-10-16T03:11:24.458519+08:00 | 2026-10-16T03:11:24.656761+08:00 | 0 |
| `r10_mypy` | 2026-10-16T03:11:24.821964+08:00 | 2026-10-16T03:11:31.785825+08:00 | 0 |


原冻结测试和相关回归合计独立通过 **148** 个。新增扩展 32+最终负载 1 分例为 **20 passed、13 failed**，不能用 148 绿例抵消它们。历史首轮 20 和首次负载重复执行另列，不混为新增案例数。focused pytest 明确 `-o addopts=`，未运行全仓覆盖率门，也没有降低已有门槛。Starlette/httpx 弃用 warning 仅记录，不冒充业务失败。

目前 unit/contract 定向检查 passed；integration/security 因上述独立红例 failed。frontend/e2e/live/manual、产品入口、Neo4j 集成/重建/滞后测试均 **not_run**。0 外网、0 模型/provider/source 请求、0 PoC 执行、0 资产扫描；未访问盲测或金标。剩余缺口不是环境阻塞造成这 13 个失败，它们均为真实业务/安全/重复 IO 断言失败。

## 已证实的能力与不能签出的结论

静态及原 35 PG 分例确认：source/document/revision 三父 ACL 都在 SQL 过滤，不只是 revision；目标 paper 也同样重新检查三父 ACL、kind、current、成对文档/修订。请求前撤权、角色降权、跨租户及 viewer 访问有一致的 404；无 cookie 401、无权限 403、依赖失败固定 503；未知额外 query 参数拒绝，不提供任意 SQL/URL/DSL。候选/模型假设、disputed、withdrawn、superseded、冲突、非当前、stale、损坏 quote/hash/offset 不发布有效边。

版本身份包含 ecosystem/package/scheme/区间/显式版本，异生态和不同区间不合并；正反向边使用同一 claim/evidence。没有合并不同版本范围，也没有因 PoC URL/static_reviewed 宣称利用成功。数据损坏的 predicate/value 不一致、typed schema 无效返回固定 503；block hash 损坏没有有效边。现有重复发布和新读保持确定结构；撤回后的新事务没有旧边，未覆盖或删除历史。

独立核对 nodes/edges/gaps 的 canonical JSON hash、scope、rule_version 和 event business_version，以及端点完整和 max_nodes/max_edges。`truncated` 包含支持行、节点或边限额造成的截断；缺失 relation gap 在截断时使用 truncated 原因。**摘要只描述选集**，不等价完整 PG/Neo4j 一致性，也不保证 current；后两者正是尚未实现/已发现的边界。

`rg` 的调用核对显示生产 `api/app.py` 没有注册 build_graph_router。CBM trace 也只能作为导航，不能凭零 inbound 边断言能力不存在。产品端到端、可点击图页面、Neo4j 投影与全量重建/撤回/落后处理没有由这次工厂 TestClient 测试取得验收证据。

负载假设为这次切片明确允许的单请求最多 2000 支持行、200 节点、400 边；没有假设无限记录或推测生产并发。只测一次本地请求的实际 IO，未测正式吞吐、长期内存、服务 SLA。代码没有新万能框架/CRUD层/依赖；不提出按行数删改建议。第 4 项通过请求内复用已有检查即可改善。

## CBM 与封存材料核验

使用指定官方 CLI `WSL Ubuntu-22.04 root /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 0.11.0，实际执行 help、cli help、index/schema/trace 参数 help。独立 full 索引自己的 `backend/src`，project=`r10_graph_review1_backend_src`：1476 nodes / 7550 edges，未索引/skip/partial/unusable=0；实际列出的排除项为 5 个 __pycache__，没有排除 assets。assets 搜索返回 60 个符号，不能把别的默认/filtered 索引的 assets 排除行为当作本次事实。

先猜缺 project 前缀的 qualified name 导致 `function not found` exit 1，错误记录保留；通配符错误查询返回 0 后，使用正则 `event_graph` 查明准确限定名，再执行两个 exact qualified traces，exit 0。新服务 trace 指向 _support_rows/_verified_span/_paper_scope，工厂 trace 指向 GET route；`rg` 补查调用方与 api/app.py。没有把图无边当作无能力证明。所有原 CLI 输出未裁剪。

材料清单 byte 核对在 `author_archive_verification.json`：37/37 的 raw bytes/hash、Git blob OID/bytes/hash 与封存 manifest 相符；六个代码文件在 final material 与 b0 blob 完全一致，review WT 规范换行后亦一致。

- manifest **raw**：15245 bytes，SHA-256 `96bdabb2f8d3141046f848796845c0a3f09a5948a9d719ded5333a1d1a9e3820`。
- manifest **frozen Git blob**：14944 bytes，SHA-256 `53ad7e5323fcedae5941f82569ab224d6d78669c41a433ac0563591efc0c9d4d`。
- 作者冻结 JUnit 实际为 pure 10、PG 35、related 103，均 0 fail/error/skip。这是作者材料核对，与上面的独立复跑分开记账。
- 作者 `initial_unit.log` 的 ModuleNotFoundError collection error 原红日志仍在且 hash 匹配；不是 PG 业务失败或环境缺失。
- 独立 `git diff --check baseline b0 -- backend` exit 0；`git diff --check baseline final` exit **2**，只报 `cbm_schema.json:36: new blank line at EOF`。没有清洗 raw 日志，也没有宣称全材料 diff 为 0。
- known private credential/DSN byte 扫描未发现泄漏，结果见 `review_summary.json`；秘密值未写入该摘要。

## 评分证据、偏差与交接

F2/A1/P2：有固定六类、证据 ID、规则版本、scope、有界摘要的代码和合成 PG 证据；关系语义支持与响应当前权限因红例不能放行。不能据此给关系准确率/召回率、多跳效果或优秀档分数。

T17：实际 PG event association、distinct subject 过滤、生态身份和历史修订有局部证据；可靠归并支持仍需第 1 项。T21：不做冲突投票、状态排除和历史保持有证据。T22：paper 目标 ACL/当前性有证据，内容组件/机制支持仍未证明。T23：PoC 静态状态不晋升成功，处置来源支持未证明。T41：尚无真实图 UI/点击边流程。本轮没有修改冻结公共 Relation，也没有走未授权合同变更。

建议下一任务：在这六文件切片及直接必要的支持校验/最终检查范围内修复 1–3，并处理 4；提交新的固定代码、保留本次所有红证据，再由非作者复核。若支持校验需要新增公共合同/存储字段，先提交具体变更单，不能通过把 supported 文案降级或删反例绕过验收。产品注册、公共 DTO 适配、Neo4j/UI 是后续独立能力，不是本审查批准事项。

**Verdict: needs_changes，先修复 1–3。** 未检查：真实来源/模型的关系语义质量、产品端到端、前端、Neo4j、正式性能/长期运行和人工复核。
