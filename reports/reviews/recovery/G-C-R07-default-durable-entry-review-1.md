# G-C/G-D · R07/R03 默认持久富化与 R10/R11 默认入口初审

What this change does: 本批把富化请求接入默认认证 API，按 PostgreSQL 工作流调度固定父、逐维和发布任务，并把已审图与私有资产服务接入两个 URL 前缀。模型预算与私有外发由服务器配置决定，任务状态与事实仍来自 PG。

任务状态：**needs_changes**。Verdict: **fix 1 first**；本意见只覆盖该默认入口小批及内部 durable 执行，不是 G-C/G-D 阶段门，也不接受整 R07/R03/R10/R11 或原 T 卡。

独立 reviewer：`/root/r07_default_durable_entry_first_independent_review`，未实现本批；skill：ponytail-review 5.2.0。WT：`D:/wt/r07-default-entry-review1`，分支 `codex/r07-default-entry-review1`。报告首次写作：2026-10-16T06:32:32+08:00；review commit：null；未提交、未 push、未改 progress/accepted、未改业务/原测试/迁移/依赖/金标/阈值/计分分母。

## 固定对象与权限范围

- 业务最终 SHA：`1f0522e3f3fb9547ea55136efa64fc589466c992`；含 root 合同/0017 `281371b072a696d972aa3c38519b8646393c98e2`、内部 `595e42a91a830f78fd11d0e4fc7a79a1aaf767cb` 的 871 行 job_service/types/handlers、root API/policy/runtime `b18349962cb6bee251d0f1d57310366c49175239`，以及 graph/inventory 默认装配。
- 最初材料：`1b894daaa4523f37600c8ff8f9990c5df534a3fa`；144 原始材料 manifest SHA-256 `7d710ba8be7898f96d7aec796ef02a5fdbdf22ed9f476f5a2487152d928965e1`。逐项来源 raw 和材料 Git blob 均 144/144 相符；独立 checkout 唯一原始差异是任务报告 CRLF，LF 与 Git blob 相符。证据在 `source_evidence_audit.json`，没有把 LF 当原始 raw。
- 元数据测试兼容 SHA：`8a0cc6b6a93551d9d6060b7ab6abd949326e5cb6`；最终审查材料：`e61d9d6dd1215c337755d32d112dfe70f13d9e94`。新材料 manifest SHA-256 `1fdce98903d41868a6036b57845135b158d1d5d4fb84b193d63a0072087d829d`，5 条材料 raw/blob 逐项核对相符；业务 src/迁移相对 `1f0522e3f3fb9547ea55136efa64fc589466c992` 无差异。
- 已读 AGENTS、00 地图、03/04/05/06 合同、恢复 R03/R07/R10/R11、T07/T19/T20/T35/T40、CR-R07_enrichment_jobs、CR-R11_default_readers、CR-R07_metadata_head_test_compatibility、作者报告。进度快照 R03 accepted、R07/R10/R11 pending 只是索引，不用它替代本批代码/日志证据。
- 只使用现有本地 PG 25432，连接来自 WSL connection.json 并只留在进程内；新专用数据库 run ID 分 `r07_execution_api_review1_20261016` 与 `r06_catalog_r07_metadata_review1_20261016`，原守卫保留。新 forward 测试 schema 明确 `test_independent_r07_forward_*`，只前向 0017→0019，留存 schema 收据，不运行破坏性 downgrade。Redis 26379 只作原测试 import 配置，未发送 broker 消息、未清理 DB15、未干预来源采集。

## Must fix

1. **不同用户和事件路由共用了一个幂等作用域**（`backend/src/ai_intel/enrichment/job_service.py:258–280`）。

   - **职责：**创建 workflow UUID，并通过事务 outbox 保存该次请求的父 job。
   - **问题：**UUID 只绑定 `(tenant_id, 原 Idempotency-Key)`，父 job 也直接使用原 key；当前 actor 和 event 只在 payload 的 binding 中。05 合同 §2 要求作用域包括当前 tenant、route、主体。真实默认 HTTP 中，两个合法 public SYSADMIN 对同一事件各自使用同 key，第二个 409；同一 SYSADMIN 对两个不同事件路由使用同 key，第二个同样 409 `idempotency_conflict`。两例在最终 `e61d9d6dd1215c337755d32d112dfe70f13d9e94` 均可复现，既非越权，也非同作用域变更 payload。
   - **最小修复：**统一内部幂等 namespace，绑定 tenant、canonical event route/event_id、actor user_id 和原 key；父 job 键和 workflow UUID 使用同一规范值。session 不应成为独立作用域：同一用户换 session 后重用旧 key 仍需通过已有绑定检查，不能隐式换执行身份；不同请求 body/policy 仍应 409。已有旧工作流的重放兼容必须显式保留或拒绝，不能 silently 建新付费任务。
   - **不修后果：**一个管理员或事件占用的键会阻断另一个合法请求，客户端按合同在自己的作用域重试也无法提交。该行为会出现在多用户/多事件的正常负载，并削弱可用的幂等契约。
   - **复验：**保留我的 `test_independent_idempotency_scope.py` 两例及原红；修复后应两例通过，并重跑同 scope 重放/并发/不同 payload/policy/session 冲突和默认入口 PG35。新增业务改动须另冻结 SHA 和做有界 recheck，不能把本报告直接改成 accepted。

## 已关闭的初审回归与未改原红

最初 `1b894daaa4523f37600c8ff8f9990c5df534a3fa` 的原 metadata20 真实复跑为 19 pass/1 fail：`test_r07_enrichment_job_metadata_pg.py:73` 要求 head0017，但实际是 `0019_aggregate_observations`。作者此前 metadata20 在 pre0019 环境，不能据此为最终版本背书。兼容变更只要求 installed 等于冻结 Alembic head，并要求0017在真实祖先链；检查后亲复跑同原20，20/20通过。原 `independent_metadata_pg.log/xml/json` 保留，未改为绿。

我的 forward/asset 额外探针 v1 为 1 fail/2 pass：误把 seed 后总 job 数当2，实际原 source seed 已形成4个 job。保存 v1 实际源码和原失败计数，v2 改为迁移前后完整 job ID 集合守恒，0017预约与既有 PG状态保留；3/3通过。未改产品或原测试断言。

这个外目录探针 v1 最初未继承 `backend/tests/conftest.py` 的失败脱敏 hook，失败 log/XML 回显了实际连接秘密。作为秘密保护必要例外，明文原字节未备份/提交/归档，已就地替换；只保留原文件 hash、脱敏文件 hash、命令、失败和计数、原因，见 `probe_harness_redaction.json`。后续外目录探针加载同一既有 hook。脱敏不算测试通过，v1 仍记1 fail/2 pass；最终对全部 owned raw/gzip/report 及作者 manifest 所列材料按内存中的实际 PG password/完整 DSN 逐值扫描，而非只用形状正则。

作者已有 API v1–v6 红、combined harness 49 errors、fixed report directory missing、CVSS 图样本误期待非空强边等历史证据只读且 hash 核对。原全仓 strict CPU 门红未关闭、未重跑，也未扩签完整工程门。

## 实际调用链与通过证据

源索引独立于作者：`r07_default_entry_review1_src_root`，backend/src 为1588 nodes/8454 edges、116文件；默认排除了 assets，因此另 index `r07_default_entry_review1_assets_root`，198 nodes/823 edges、12文件。schema、architecture、qualified inbound/outbound trace 和 source/rg 注册声明都已留日志。consume_job 与 bound handler 入边空是静态 callback/decorator 图限制；源码固定注册和真实 consume_job 验证补证，不能把空边解释为没注册。

实际链：create_application→同 authentication provider/engine→enrichment router→锁当前 auth→enqueue/outbox→consume_job 的本地 handler 副本→固定 initialize/execute_step/publish→PG job lease/状态。initialize冻结完整事件来源 roster、原文/blocks/hash、版本和父 source/document/revision ACL；execute_step 用当前输入与 current auth 再校验，读取 ContentStorage.read_verified，经本地 structured 或独立 GenerationClient；预约先提交独立 metadata UPDATE，真实回执独立事务写入后才复查权限/来源；publish 复用原 source→document/revision→publication→event 锁序与原子事务。失败回滚不写 current，原来源失败 handler 不推进 cursor。

通过事实如下，均显式 synthetic/recorded fixtures 加真实 PG，不计模型/source live：

- 默认 PG35（原执行21 + API/registered consume_job9 + reader5）：HTTP202、唯一 job reader、两别名、strict输入、Origin/CSRF、policy、执行后当前角色校验、父 succeeded 不等 workflow_complete、CVSS structured 完整成功、generation false 的 versions BLOCKED/model_budget_not_authorized 与最终 partial、原子发布、重复 consume not_claimed。
- 元数据20最终通过：真实前向表/索引/约束、PG唯一状态、预约并发等；独立额外 forward 证明0017→0019保留预约和完整既有 job ID集合。
- 原执行21中真实 PG验证 source ACL/修订/用户 role/tenant/session撤销与过期/policy/input hash变化阻断发布；PERMISSION_VERSION 是服务器常量并在执行比对，不是用户表中不存在的version字段。独立 receipt 在 offline wire期间撤销 auth 后仍保存 metadata，而 result/fact不发布；reservation不等待executor持有job的FK锁；中断预约只记incomplete_interrupted、不再wire。
- 新独立负例 PG10：注册 worker 前角色/source version变动阻断；合法 digest 的伪造 queue tenant/URL字段与binding拒绝；3并发reservation仅1预约；private egress deny在模型factory之前；两个默认图前缀执行最新scope404；viewer资产拒绝；source job仅public SYSADMIN、private workflow跨scope404/job403。
- 额外 asset 2例：两别名正常导入、重放不增snapshot、第二snapshot成为current、固定历史仍可读、换tenant后current/history404和list为空，未知tenant query422。asset module沿用当前角色 READ_ASSET/WRITE_ASSET，没有给analyst/viewer增权。
- unit/contract/security选定194和133通过，133与194重叠，不累计；全src Ruff/format/mypy通过。没有为低影响报告另造覆盖率或准确率。

## 实际命令与结果

每个下表收据含完整 argv/cwd、+08起止、exit、对应log/XML和 hash。Python来自作者已有venv只是运行依赖；cwd和PYTHONPATH均指向独立WT源码。读文档、创建WT及早期工具 discovery 的开始/结束未独立写磁盘收据，时间记历史未记录，不补造；测试、CBM与证据核对均有实际收据。

|收据|开始 / 结束（+08）|exit|tests/failures/errors/skipped|
|---|---|---:|---|
|[independent_default_pg.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_default_pg.json)|2026-10-16T06:21:38+08:00 / 2026-10-16T06:22:49+08:00|0|35/0/0/0|
|[independent_metadata_pg.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_metadata_pg.json)|2026-10-16T06:22:50+08:00 / 2026-10-16T06:23:21+08:00|1|20/1/0/0|
|[independent_metadata_final_pg.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_metadata_final_pg.json)|2026-10-16T06:27:27+08:00 / 2026-10-16T06:27:53+08:00|0|20/0/0/0|
|[independent_negative_pg.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_negative_pg.json)|2026-10-16T06:23:27+08:00 / 2026-10-16T06:23:41+08:00|0|10/0/0/0|
|[independent_forward_asset_pg.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_forward_asset_pg.json)|2026-10-16T06:25:14+08:00 / 2026-10-16T06:25:23+08:00|1|3/1/0/0|
|[independent_forward_asset_pg_v2.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_forward_asset_pg_v2.json)|2026-10-16T06:27:54+08:00 / 2026-10-16T06:28:00+08:00|0|3/0/0/0|
|[independent_idempotency_scope_pg.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_idempotency_scope_pg.json)|2026-10-16T06:30:07+08:00 / 2026-10-16T06:30:13+08:00|1|2/2/0/0|
|[independent_contract133.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_contract133.json)|2026-10-16T06:22:16+08:00 / 2026-10-16T06:22:22+08:00|0|133/0/0/0|
|[independent_related194.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_related194.json)|2026-10-16T06:25:14+08:00 / 2026-10-16T06:25:19+08:00|0|194/0/0/0|
|[independent_ruff.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_ruff.json)|2026-10-16T06:21:56+08:00 / 2026-10-16T06:21:57+08:00|0|不适用|
|[independent_format.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_format.json)|2026-10-16T06:21:57+08:00 / 2026-10-16T06:21:57+08:00|0|不适用|
|[independent_mypy.json](../../runs/recovery_r07_default_entry_review1_20261016/independent_mypy.json)|2026-10-16T06:21:57+08:00 / 2026-10-16T06:22:16+08:00|0|不适用|

`run_review.py`、probe源码、CBM/source注册日志和 `source_evidence_audit.json` 位于 `reports/runs/recovery_r07_default_entry_review1_20261016`。固定输出目录只在独立WT临时准备；原测试生成NVD观察已移到本次resources，未覆盖作者run bytes。我的 v1 脱敏 log 原hash与新hash分列，不伪称 raw unchanged。

## 评分项证据和明确缺口

F2/P2：有真实PG逐维状态和CVSS结构化原子发布，unknown/blocked/failed区分及一维失败不抹他维；没有九维真实正例/完整召回/准确率证据。E1/F1：持久API/outbox/lease/注册consume路径及PG回执可复跑；消费发生在同一测试进程，真实 broker/Celery worker进程 e2e未运行。R1：hash、文档版本、来源ACL和当前权限可追溯；没有来源持续运行或live能力实测。

R10 graph default floor只有CVSS样本，一个event node和空edges是正确输出，不能据此冒称六关系。六关系服务复用先前独立R10证据；本评审只验证默认装配和权限入口，不签Neo4j/完整六关系live。R11默认入口可导入和读取私有current/history，不能据此签版本研判/条件/FOFA/整个资产闭环；未写“MCP实际关系完成”。

R08 available aggregate→PG事实发布故意未连接，默认aggregate=false，registered query无client明确blocked；未知产品不外发、不伪0。后续7dae模型schema/input selector尚未集成本对象；prompt/schema/selection策略版本尚未纳入durable request政策指纹，durable coverage审计缺口仍须传播到升级、排队旧任务、逐维富化和正式评测。任何新算法/prompt部署前必须补版本绑定/旧任务阻断，不能沿用本slice的通过把整R07涂绿。原full NVD input超过模型选片预算的失败留存，wire=0，同时CVSS保存，不能把partial等价完整覆盖。

真实模型/provider/sourceHTTP calls：0。live/source/model、真实worker进程/Redis broker e2e、frontend浏览器/manual、stage/full-repo严格CPU门、盲测/人工金标：未在本评审执行；live缺口记blocked_live或not_run，不算通过。未触碰付费模型、外部聚合、holdout、第三方资产或PoC执行。

## 业务小批文件清单

以下是四个root/内部执行提交的并集；完整 Git blob ID/raw/LF hash见source_evidence_audit.json。复用服务的graph/inventory callers另源码crosscheck，不将仅8个API文件当全部评审范围。

- `backend/migrations/versions/0017_enrichment_job_workflows.py`
- `backend/src/ai_intel/api/app.py`
- `backend/src/ai_intel/api/enrichment_contracts.py`
- `backend/src/ai_intel/api/enrichment_routes.py`
- `backend/src/ai_intel/api/job_routes.py`
- `backend/src/ai_intel/api/source_routes.py`
- `backend/src/ai_intel/enrichment/job_contracts.py`
- `backend/src/ai_intel/enrichment/job_handlers.py`
- `backend/src/ai_intel/enrichment/job_models.py`
- `backend/src/ai_intel/enrichment/job_service.py`
- `backend/src/ai_intel/enrichment/job_types.py`
- `backend/src/ai_intel/enrichment/runtime_policy.py`
- `backend/src/ai_intel/infrastructure/settings.py`
- `backend/src/ai_intel/workers/runtime.py`
- `backend/tests/contract/test_r07_enrichment_api_response.py`
- `backend/tests/contract/test_r07_enrichment_execution_policy.py`
- `backend/tests/contract/test_r07_enrichment_job_request.py`
- `backend/tests/contract/test_r07_enrichment_runtime_policy.py`
- `backend/tests/contract/test_r07_job_execution_views.py`
- `backend/tests/integration/test_r07_enrichment_api_pg.py`
- `backend/tests/integration/test_r07_enrichment_job_metadata_pg.py`
- `backend/tests/integration/test_r07_job_execution_pg.py`
- `backend/tests/integration/test_r11_default_readers_pg.py`
- `backend/tests/security/test_r07_job_execution_boundaries.py`
- `backend/tests/unit/test_r07_job_execution_helpers.py`
- `docs/decisions/CR-R07_enrichment_jobs.md`
- `docs/decisions/CR-R11_default_readers.md`

后加仅metadata测试兼容与 `CR-R07_metadata_head_test_compatibility.md`，已单独diff/真实20复跑。评审新增文件只本报告、本run与resources/probes；无业务或progress diff。

下一步：修复Must 1的作用域与旧任务重放兼容，补入正式回归，冻结fix1后有界复验。其他已审切片可保留其真实通过记录；本初审不能据部分通过签整个R07或G-C/G-D。

Verdict: **fix 1 first / needs_changes**。Not checked: 真实Celery broker/worker进程、浏览器/live/manual、九维真实完整覆盖、prompt/selection跨版本durable升级及完整阶段/全仓工程门。
