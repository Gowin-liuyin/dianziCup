# G-C · R06 live 来源兼容修复独立审查 1

What this change does: 本包允许固定 Ollama release 页在 50,000 个 JSON 节点预算内解析，并在两处来源解析使用相同预算。AVID 0.2 只新增 `type=screenshot` 且 URL 全串匹配 `../img/R[0-9]{5}.png` 的仓库截图上下文例外；保留原文、Git 身份及引用元数据，同时说明没有读取图片或验证 PoC。

**Verdict: Ship.** 仅限冻结代码 `e900cd6b95dde7c6fe8d11d8c15122eb48a4acdc` 的本兼容包集成。未证实影响本包正确性、安全、事务或合同的阻断缺陷；没有待修编号。整 R06、原 T 卡及 G-C 状态未签 accepted。本 reviewer 未参与实现，未修业务代码。

记录时间：2026-10-15T23:59:16+08:00。命令均记录实际 Asia/Shanghai 秒级起止；证据 run 为 `recovery_r06_live_compat_review_1_20261015`。本报告时间不用于计算来源时效。

## 固定版本、合同与边界

| 项目 | 固定值 |
|---|---|
| 基线 | `1a52e17ffe327fb8a0c1d4f97372948a699910e3` |
| 唯一审查产品代码 | `e900cd6b95dde7c6fe8d11d8c15122eb48a4acdc` |
| 材料 tip / 独立 WT 起点 | `837fd22e655e6f2fb39eaf828e6ad91a78914ba4` |
| 独立 WT / 分支 | `D:/wt/r06-live-compat-review-1` / `codex/r06-live-compat-review-1` |
| 作者 WT | `D:/wt/r06-live-compat-fix`，只读材料，没有修改 |
| 本轮新增 | 本报告与本 run 内审查脚本、日志、JUnit、观察和不可变 manifest；不提交、不 push |
| 费用和外部动作 | 费用 unknown；新外部来源请求、模型、测绘、付费调用均为 0；本地 PostgreSQL 实际执行 |

`git diff BASE CODE` 恰好四文件：`backend/src/ai_intel/ingestion/catalog_pages.py`、`backend/src/ai_intel/ingestion/sources/avid_records.py`、`backend/src/ai_intel/ingestion/sources/github_releases.py`、`backend/tests/unit/test_r06_live_source_compatibility.py`。材料提交未再改 src/tests；工作树四文件的 Git blob 与代码 SHA 完全一致。未改原业务测试期待、金标、阈值、分母、公共合同、认证或状态。主 WT 原有用户修改没有接触。细项 hash 见 `scope_audit.json`。

已读真实 `AGENTS.md`、00/03/05/06/11/12、当前 `progress/task_state.json`、交接、T12/T14/T16 与引用 04/07/09；18 项输入 hash 固定在 scope audit。使用最新 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`，按实际调用链和可复现行为审查，不将纯风格列作阻断。

00/11/12 保留完整恢复 G-C：R06 的八类、九通道、每源游标/失败记录和真实运行证据不能由本小包替代。03 的末版去重、A→B→A、证据坐标、历史不可变和 PG 权威保持；05 的认证身份、写权限、分页与失败语义保持；06 禁止 fixture 补 live、失败改 skip、指标分母变化。本包只对 R06 来源兼容及相关 T12/T14/T16 的代码与局部集成行为给证据，不删除原 C01–C06，也不验收原整卡。

## 独立调用链审查

官方 CBM CLI 为 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，v0.11；独立项目 `r06-live-compat-review-1-src`，唯一允许根 `/mnt/d/wt/r06-live-compat-review-1/backend/src`，外置 cache `/tmp/dianzi-cbm-r06-live-compat-review-1-cache`。未索引 reports、holdout 或秘密。version/index/schema/architecture 与 10 项 trace 共 14 命令 exit 0；93 个源文件，1,253 nodes / 6,299 edges，未索引/部分/不可用均 0。CBM 关系用 `callers.log` 的 `rg` 和真实源码逐项交叉，没有把图当运行证据。

实际链路为 `source_jobs._fetch_catalog_page`（320 行）固定请求及最多两次 AVID tree/blob读取 → release 或 AVID normalizer → `build_source_page_handler.collect_page`（409 行）登记原始响应、FetchAttempt（463 行） → `persist_catalog_documents`（154 行）验证来源/范围、保存不可变修订与 JSON 指针证据 → `SourceCursorRepository.commit_page`（505 行调用） → continuation/完成状态。`executor.execute_job`（103 行）让业务、页回执、游标和 job 完成同 PG 事务；异常回滚后另记 retry/blocked。对象存储可能留下未引用对象，不能把 PG 回滚称为所有物理对象已删除。

REST 经过 `document_routes.serve` 的 cookie 认证、READ_PUBLIC 与 PG 内重新锁定身份（63–69 行），然后 `DocumentReadService.document_detail`（247 行）按指定 revision 和文档/修订/来源可见性读取，最后核验永久证据。`/v1`、`/api/v1` 两前缀均实测；不是只调用 read service 或数 collection。

## 两种原始输入及边界结果

只本地读取仓外既有输入，不请求新来源，不把原全文复制入 Git。路径为 `D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/diagnostic-originals/`。

| 输入 | 独立 hash / 字节 | 结果 |
|---|---|---|
| release 原始响应 | `972aa16090d1bbeae02a8deb2c32352ff77be894754e998e7a8c7555b031a5cf` / 616,207 B | 20 条；原数组 24,815 nodes，外层对象加 key 后 24,817；每条 591–592 blocks；原字段/资产数组等逐条 JSON 比较完整，cursor `{page:2}`，risk 未研判 |
| AVID 原始 blob envelope | `f8808b9479707e2b3ca074e569f9f678d692033c85767b387e15fbf31c3b246e` / 2,860 B | 解码原文 1,871 B；sha256 `b5c4be5ed298e38eba9cba4ae81d880b3968dafe52dfc14130b95266743b9819`；AVID-2023-V027；引用保留，未制造 advisory ID |
| AVID 原始 tree response | `0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5` / 445,091 B | tree `8eda5f4e6f74a3738eb980b795c4f813c6e52ca8`、offset 1 指向 blob `2571bc68a6be88cd93af9b31ca14eb85791828d4`，path `vulnerabilities/2023/AVID-2023-V027.json`；下一 offset 2 |

release 两处调用（github_releases 26–29 行、catalog_pages 339–342 行）显式传 50,000；50000 包装节点可被来源 parser 接受，50001 被拒。单记录的后续证据/块预算仍可能单独拒绝过大文档，未把来源预算等同无限可持久化。原 2 MiB、depth 32、100 records、重复 key、NUL、非有限数（含 `1e400`）、UTF-8、孤立 surrogate 等边界保持；模型 `strict_json_object` 默认仍 10000，模型调用方未新传 50000。

AVID 例外只在 `avid_records.py:24–29` 精确 type/path 命中；先校验 reference object、type 与 label，再跳过 advisory 身份解析。`catalog_pages.py:184–210` 仍保存已 hash 验证 payload、0.2 版本、原 references、tree/blob/path，并加入“未获取或读取图片”说明。真实输入和合成输入均验证 screenshot path 留在规范文本，referenced_advisory_ids 为空，没有额外 URL 请求、图片抓取、事件或成功利用判断。16 个恶意 URL 变体、4 个错误 type 的真实记录变异均拒绝；新增产品 32 项测试还覆盖更多 traversal、端口、凭据、非 ASCII 与空值。

## 真实 PG、事务、重放和权限证据

独立 venv 使用 `uv sync --frozen --offline --extra semantic`，92 缓存包；没有复用 main 或作者 `.venv`，没有生成全仓 coverage 冒充覆盖通过。所有 PG 调用只使用库 `test_dianzi_r06_catalog_worker_20261015`，`DIANZI_TEST_RUN_ID=r06_catalog_worker_20261015`，loopback 专用测试用户。连接 JSON 由明确 Ubuntu-22.04/root 的 WSL capture 留在内存，未打印/复制入报告；fixture 核对 current_database 和迁移 schema。每例新 UUID schema，finally 只删除本例 schema；没有 dev/production DSN、down migration 或共享表清理。

实际 handler 使用注入的离线 fetcher，数据模式 fixture，传输与观察明确标回放，不能计新 live。真实 release 原始页写入 20 documents/20 revisions、11,827 blocks/11,827 evidence、21 content objects、1 FetchAttempt、1 receipt；原页 bytes read_verified 比对成功，游标 page 2 且 window_complete=false。真实 AVID 使用已钉住的原 tree offset 1，写入 1 document/revision、28 blocks/evidence、3 content objects、2 FetchAttempts、1 receipt；原 tree/envelope 和解码原文均能 hash 回查，offset 2 且 window_complete=false。两个任务都是有界页 partial，没有把余下 14 页或 AVID 全树称完成。

每个 evidence 都检查 `block_text` 上的 Unicode 坐标、quote sha256，supports_claim=false，事件总数 0。两种来源相同 job 重放均 not_claimed，不再读取，也不新增修订；独立的四轮 A/A/B/A（B 为显式 reviewer 合成修订）保留 revision 1/2/3、正确 previous/current 链，末版重复不新建，历史 A hash 与第三版相同而允许新修订。AVID 修订检查用显式单条合成 tree+重新计算 Git blob，未声称遍历整个真实 tree。

两种来源各实际触发 50001-node / 恶意 traversal 输入、文档写后抛错、cursor commit 抛错：非法页 blocked/source_response_invalid，注入存储/事务异常 retry_wait/handler_failed；业务七表和 cursor 均无未提交写入。已有 PG 回归另测 AVID pin 重启/坏 blob 不推进已有游标、continuation/storage/cursor 失败、空结果与请求身份冲突。

两个实际来源经 PG 认证后 REST 双前缀详情 200、正确 revision 和证据数量；viewer 发起采集 403，修订改为另租户后详情 404。tenant-scoped job 在读取前 blocked/source_scope_denied，外部读取函数未调用。现有套件还实测 CSRF、Origin、角色、会话撤销/并发授权变更、幂等与原文权限。

## 实际命令和结果

完整 argv/cwd/起止/exit 保存在每项 `*_command.json`，stdout/stderr 为同名 `.log`，测试数量来自对应 `.xml`，不引用作者通过数作本结论。下表是本 WT 的实际执行；测试 cwd 均为 `D:/wt/r06-live-compat-review-1/backend`，其余见收据。所有 pytest 都显式 `--no-cov`，作为定向行为复验，不声明整体覆盖率。没有 skip。

| 日志 / 精确检查入口 | exit | tests / failures / errors / skipped | 实际结果 |
|---|---:|---:|---|
| environment：`uv sync --frozen --offline --extra semantic` | 0 | 非测试 | 独立 92 包环境 |
| unit：`pytest -q` 七个 r06 unit 文件（release_adapter、catalog_pages、source_boundary_regressions、feed_parsers、avid_record_adapter、source_worker、live_source_compatibility） | 0 | 328 / 0 / 0 / 0 | 23:43:00–23:43:07 |
| contract_security：repository_source_samples、archived_feed_replay、t08_network_and_sources | 0 | 13 / 0 / 0 / 0 | 5 contract + 8 security，23:45:41–23:45:43 |
| offline_inputs 初次 reviewer 脚本 | 1 | 33 / 1 / 0 / 0 | 自身把 raw/wrapper node 口径混淆，原失败保留 |
| offline_inputs_recheck：本 run/test_offline_inputs.py | 0 | 33 / 0 / 0 / 0 | 真实 bytes+恶意边界，23:47:40–23:47:41 |
| handler_pg 初次 reviewer 脚本 | 1 | 12 / 5 / 0 / 0 | seed 缺恢复字段 1；异常码预期错误 4，原日志保留 |
| handler_pg_diagnostic：只选真实 AVID | 1 | 1 / 1 / 0 / 0 | 11 deselected，证实 legacy_window_recovery_unverifiable 为 reviewer seed 错误 |
| handler_pg_recheck：本 run/test_handler_pg.py | 0 | 12 / 0 / 0 / 0 | 23:50:04–23:51:09，完整 handler/PG/REST 修订事务权限 |
| pg_regression：source_worker_pg、source_worker_api_pg、document_api_pg（与 handler_pg_recheck 并行） | 1 | 92 / 2 / 0 / 0 | 23:50:04–23:51:40，release 正常/坏页都 retry_wait，原红保留 |
| pg_regression_release_recheck：原 worker `-k ollama_releases` | 0 | 2 / 0 / 0 / 0 | 31 deselected；23:52:31–23:52:35 |
| pg_regression_serial：相同三原文件，串行完整重跑 | 0 | 92 / 0 / 0 / 0 | 23:53:33–23:55:04 |
| advisory_lock_namespace：reviewer `-k uuid_search` | 0 | 1 / 0 / 0 / 0 | 12 deselected；23:55:28–23:55:31 |
| ruff check / format --check 四改动文件 | 0 / 0 | 非测试 | 全通过/4 files already formatted |
| mypy src | 0 | 非测试 | 93 source files，无问题 |
| diff_check：`git diff --check BASE CODE` | 0 | 非测试 | 无空白错误 |
| CBM / callers / scope_audit | 全 0 | 非测试 | 14 CBM、rg 源码与固定 blob 交叉 |

最终定向通过 479 个不同测试实例：328 原 unit + 33 reviewer 纯解析 + 13 contract/security + 104 handler/既有 PG + 1 advisory namespace。重跑实例没有再次加到通过总数；第一次红没有改成绿或 skip。

初始 runner 也曾遇 Windows 相对 executable 无法定位和默认 WSL 用户 Permission denied；当时子测试未运行，无完整 wrapper 时间收据，记录 `timestamp=not_recorded_before_wrapper_failure`，不编造秒数。工具路径修正后离线 venv 和 PG 捕获成功。三项 reviewer 断言/seed 修正细节保存在 `harness_corrections.json`；没有改产品期待。

同库不同 UUID schema 仍共享 advisory lock namespace 已由两连接实证：一个 UUID search_path 持有固定来源锁，另一个 pg_catalog search_path 的 `pg_try_advisory_xact_lock` 返回 false。`ensure_source_registration`（source_documents.py:373）确实使用 DB-wide source ID 锁；初次两红发生在同来源大页长事务并行期间、原两例及整套顺序复跑均成功，因此判为审查套件并行资源干扰。原红没有捕获底层 SQLSTATE；“这两次失败由该锁造成”仍是有实证支持的归因推断，不是假称观测到原锁栈。本包不改业务锁。后续独立 WT 使用各自专用测试库的 fixture 参数化由主控另包冻结，不能夹带本兼容修复。

## 缺测、偏差与评分证据范围

证实缺陷：本固定 diff 范围内没有。缺测和未交付项：arXiv 首次失败 bytes 缺失仍不能确定 parser 根因；失败 body 在 normalizer 前失去 typed 审计与跨 rollback 留存、持久来源健康 API、全来源 live 与原完整 R06 验收均不在本包。截图实际图像内容未检查；任何图中 PoC 成功或资产影响均未知。新网络、真实模型、FOFA、部署 worker/Celery、MinIO、前端浏览器、漏采参考集合、正式≤6h时效、持续运行、holdout和人工均未运行。本轮后端 TestClient 不算前端 e2e 或新来源 live。

与本 diff 无关的 native CPU guard 严格 1 秒案例，主控另 A 全 pure 记录 1.03125 秒；本 reviewer 没有重新运行它，未改门槛或 skip，不能据本定向结果称全仓绿。其他阶段问题不由本 Ship 结论消失。

E1：本范围原文/修订/证据/游标/权限及事务有真实 PG 复验；F1：两个来源原 bytes 兼容后通过实际 handler 回放与去重；R1：未把社区截图引用当漏洞或实验结论。P1 只有明确 partial 页/游标行为，没有新的时效或连续运行统计；T14 的实际学术入口与完整 T12/T16 六验收均未以本包替代。合同及计划没有变更。

下一任务建议：主控只集成本固定代码与本审查证据，在受控产品环境继续两个来源 live/PG/API/UI 观测；独立批次恢复失败响应审计、arXiv 原样本和来源健康持久化。本 reviewer 到本报告和 manifest 即停止，不改任务状态，不扩大批次。

Not checked: 完整 R06/G-C、arXiv 原失败、失败审计/健康 API、新 live、截图内容、全仓/native CPU、性能及阶段验收，详见上列边界。

Verdict: Ship.（仅本兼容包）
