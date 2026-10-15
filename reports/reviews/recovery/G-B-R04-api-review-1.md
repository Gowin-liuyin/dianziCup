# G-B / R04 · PG知识只读API独立初审

首次创建：2026-10-15T13:49:05+08:00；写作开始与初审证据截止：2026-10-15T13:47:09+08:00；本次附录写作结束：2026-10-15T13:55:33+08:00。审查Agent：/root/r04_api_independent_review；非作者，未参与实现。状态：needs_changes；只读API范围未通过，整R04、G-A/G-B不因此过门。本文先封存阻断；后续验证与扫描附录将另记实际时点，不覆盖本轮失败。

What this change does: 默认应用新增认证的事件列表、事件详情和证据读取，挂载 `/v1` 与 `/api/v1`。数据来自PG，复用既有DTO与认证；未知时点保留NULL，历史证据按其修订返回。

## 固定范围与身份

实际Git解析的目标：`4934de35a02c1b8841a9e364d31fa281cf3c0f5d`；tree `eecdd8d361898f550795555d3ffd58b8f630dfe7`。独立干净分支 `codex/review-r04-api-20261015`，工作树 `C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1/dianzi`。没有将root可变checkout审为通过。

核心diff为 `d8f924803d1280c929c798313e5c864cec700123^..d8f924803d1280c929c798313e5c864cec700123`：app.py、knowledge_routes.py、knowledge_read_service.py及两项测试，共5文件。来源6c7修复/PDF4934兼容作为固定前置读取，本文结论只及API及直接关联。作者源码 `6e7c4c7aeea5f9d25deaa4b676b63dda65af477e` 与报告自检不是本人的结果；其证据提交双SHA校验待附录。

已读AGENTS、00执行地图、恢复11/12的R04、T40/T41、03数据/05API、来源持久化CR、只读投影CR、knowledge_contracts与真实认证上下文；读取当前progress仅做状态上下文，未修改。真实读取Ponytail 5.2 review SKILL，按调用链和可观察触发报告，无主观行数/假性能问题。

## Must fix

1. **NUL过滤参数被包装为依赖不可用**（`backend/src/ai_intel/api/knowledge_read_service.py:59`，`knowledge_routes.py:97`）。
   - 职责：EventFilters验证q/product/risk_type后交给参数化PG查询。
   - 问题：默认create_application构造的真实PG认证，登录后分别GET `/v1/events?q=review%00input`、product、risk_type，三者实际503而非422。Field只有长度限制，PostgreSQL拒绝NUL后落入SQLAlchemyError的503分支；客户端错误被误报数据库故障。
   - 最小修复：在共享EventFilters中验证NUL与UTF-8可编码文本，使用Pydantic验证错误；复跑三个HTTP原输入，并补同根surrogate模型边界，保持正常文字、`%/_`与原有长度规则。
   - 不修后果：无效客户端输入被标retryable依赖失败，前端错误分类和重试行为不实。

2. **损坏的已保存维度引用伪装为成功空结果**（`backend/src/ai_intel/api/knowledge_read_service.py:507`）。
   - 职责：返回已保存维度，并阻止不可见嵌套引用泄漏。
   - 问题：先保存并读到available维度，再将其reference_ids改为不存在的UUID；数组仍满足现有PG约束。实际返回HTTP200，代码在任一引用不在可见字典时直接continue，丢掉维度。不存在/损坏与真实私有引用被同一路径吞掉，违背“保存数据损坏不能伪造正常”。
   - 最小修复：先验证引用数组的成员类型与有界UUID，在同一快照区分真实不可见对象和不存在/错误来源关联；不可见仍安全隐藏，损坏以KnowledgeProjectionError转固定503。不能通过返回200空列表修复，也不能泄漏私有对象存在性。
   - 不修后果：损坏的available或failed记录被显示为未取得维度，丢失真实失败状态和审计信息。

3. **已知stale主张仍支撑current维度**（`backend/src/ai_intel/api/knowledge_read_service.py:536`）。
   - 职责：每次读取回查保存的输入有效性，不把历史值当当前值。
   - 问题：事件/来源修订版本保持，先读到available/current维度，然后把其支持claim的freshness改stale；这是合法保存状态。实际API仍available/current。检查只覆盖is_current和withdrawn/superseded，没有claim freshness。现有KnowledgeRepository.list_current_claims（persistence.py:891）明确排除stale，但新维度投影绕过这条有效性。
   - 最小修复：将任何引用主张的stale状态传播到维度freshness，保留历史status/引用；定向复跑原输入及已存在event_version、旧revision、withdrawn检查。不能覆盖PG历史或把未知改current。
   - 不修后果：UI向用户展示已经确认失效的当前维度结论。

## 初审实际验证

原始目录：`reports/runs/recovery_r04_api_review_1_20261015/`。正式命令的cwd、argv、+08秒级起止、退出码、固定SHA/tree、clean状态均在各receipt；XML是数量证据。8个初始探针文件 `independent_tests/test_review_api_boundaries.py` 的捕获SHA256：`e8fd5f80663779f323fbbf9ac35f28a7333db44478c1c62c081ee9a9daf6b69b`，不得修改为适应修复。

| 检查 | 时段(+08) | 结果 | 证据 |
|---|---|---|---|
| Windows全unit/原60门 | 13:36:09–13:36:43 | exit0，420 passed、0fail/skip；2716/4420 statements，61.44796380090498% | unit_windows_2.* |
| Linux独立venv全unit/原60门 | 13:43:07–13:43:49 | exit0，420 passed、0fail/skip；同一raw分子/分母 | unit_linux.* |
| 原24个真实PG API回归 | 13:44:43–13:45:09 | exit0，24 passed、0fail/skip | pg_original_replay.* |
| 自有default PG认证与边界8探针 | 13:45:34–13:45:48 | exit1，3 passed / 5 failed / 0skip | reviewer_boundaries.* |
| Windows完整mypy | 13:36:38–13:36:45 | exit0，67源码文件 | static_mypy_windows.* |
| 全src/tests Ruff/format | 13:36:38、13:39:06 | 两项exit0，149文件format | static_ruff.* / static_format.* |

三个自有通过项为两种前缀的默认PG登录→列表/详情/证据及跨租户404，以及退出后携带旧cursor仍401。仅隔离engine工厂被绑定；默认create_application自己装配DatabaseUserDirectory和PgAuthenticationStateStore，cookie是真实PG认证状态，未注入内存身份/AccessScope。用户名、密码和会话显式synthetic；settings data_mode=fixture，不算live来源/正式业务e2e。

数据库为本人新建 `test_dianzi_r04_api_review_20261015`（PG16.14），每例自己的schema并清理；不动作者或其他冻结库，不downgrade。原24测试仅替换api_engine校验的专用库名，所有业务输入/断言原样，资源差异与hash见replay_resource_binding.json。Windows `uv sync --locked`实际68包。Linux为本人venv，将已下载Linux包物理复制，并逐项确认66个Linux平台适用锁版本，排除其他checkout的editable绑定；没有共用Windows.venv或作者Linux site-packages。

独立CBM0.11.0索引仅本人WT backend/src：876nodes/3917edges，0unindexed/partial/skipped。仓外cache `/tmp/dianzi-cbm-r04-api-review-1-20261015`，项目 `dianzi-r04-api-review-1-4934`。实际schema与app/auth/event_detail trace保存，源码/rg交叉显示cookie→build_access_scope→READ_PUBLIC/READ_ASSET ACL→REPEATABLE READ Session→PG关联查询→严格DTO。图对嵌套闭包没有完整边，serve查名失败保留；用源码实际挂载与HTTP补证，不用图推导通过。

## 未检范围与后续

未执行负载/并发快照压力，不能给出性能通过、无限循环或吞吐判断。真实worker来源链、browser/live/manual、全部九维能力、模型问答、整R04和G-A/G-B阶段门均不由本评审签署。q/product/risk_type同根UTF-8补测、完整auth资源复跑、作者双hash/本人manifest及实际秘密扫描将在附录列真实结果。

首轮auth回归30passed/6setup errors，原因是审查runner未装PG资源env，不是业务失败；原日志/XML保留。早期runner argparse/Windows相对exe路径/编码、Linux在线pip未完成与离线uv参数/缓存失败不作为业务测试结果，后续记录最小原因和实际资源路径，不删原失败。

建议主控只修上述三项并提交新的固定候选，由本独立reviewer复跑同一原输入；未新测前保持needs_changes。没有源码/schema/锁/progress修改，无commit/push/accepted。

Verdict: fix 1, 2 and 3 first.


## 初审收尾附录 · 2026-10-15T13:55:33+08:00

主控要求的同根补测 `reviewer_extra_boundaries` 实际13:49:08–13:49:17，exit1，9项中3passed/6failed/0skip：三个surrogate模型输入已被Pydantic拒绝，这三项通过；三个NUL模型输入未被拒绝，这三项失败。没有把surrogate臆测为已确认HTTP缺陷。另三项分别将source_scope/claim_ids/reference_ids写为数组[{}]，现有PG数组约束接受；实际HTTP500纯文本Internal Server Error，不是RFC9457固定503。此为Must2的成员类型损坏补证，原8探针未改。

cursor unit实际13:49:55–13:49:57，exit0，24passed/0fail/skip；完整相关auth/security/contract在私密env连接本人DB实际13:49:55–13:50:46，exit0，36passed/0fail/skip，原30pass/6setup errors保留。新增字段/阈值/分母没有改。

作者证据提交完整SHA `d97703a98593a625214dcdf3edcb744a26c7ab65` 和 `bd16aa3d81062148a5441e3b55bdec79cffaaf63` 实际解析；最终manifest的68项，每项捕获文件SHA256/大小与Git blob SHA256/大小均实校验0不符（13:52:13–13:52:17，exit0）。manifest Git blob SHA256为2970ecf9bb23728e19dad9590027263996593241d6f16f6cfd5f617bc04d665c；四个新增业务/测试文件在作者6e7c与本人4934的Git blob字节相同，app4行挂载diff另按d8f9248核对。首次证据核验误将manifest中五个已授权源码路径当越界而退出1；只扩为准确五路径白名单后核验，不读取其他路径。完整结果见author_evidence_verification.json，不把作者329unit/24PG计为本人结果。

为了实际扫描动态认证值，对原24和原8探针增加仅审查conftest的根0600秘密登记后再执行；13:52:20–13:52:56，exit1，27passed/5failed/0skip，与初始相同的五个业务失败。原探针哈希e8fd5f80663779f323fbbf9ac35f28a7333db44478c1c62c081ee9a9daf6b69b不变；业务源码/原测试没有改。原24copy的断言未改；conftest仅路径绑定、注册秘密并保留原失败脱敏钩子。

实际秘密扫描13:53:26–13:53:27，exit0：70个动态密码/会话值、测试DSN全文/连接密码全文及2577个8字符片段，86个本人证据/报告文件，0命中。最终扫描应在本附录落盘后再次执行；结果不含DSN/password/token值。原始首次8探针与24执行未保存已退出进程的动态秘密；后一次同输入执行以实际登记值补证，没有声称回溯取得旧进程密码。root0600文件只含本测试资源，未读产品keys/.env/KEYS/holdout。模型、测绘、PoC与第三方资产调用0。

初期Windows原始coverage SQLite位于本人raw目录，已按字节哈希不变移至本人仓外cache；后续每次COVERAGE_FILE直接使用仓外独立文件。JSON与日志仍原样，没有跨OS同名coverage冲突。移动清单见coverage_cache_relocation.json。Linux在线pip等待后仅终止本人pip PID25136，包装器GBK解码失败，未取得该子进程完整stdout，不将它列为测试结果；Linux离线uv第一次-r用法退出2、修正后本源缓存索引缺包退出1，原收据/日志保留。改用逐项核对锁版本的物理复制，独立venv完整unit已经实过。最早argparse顺序、相对exe路径两项执行前失败仅有工具消息，没有完整秒级收据，明示缺证，不补造时段。

本轮产物只为报告/raw证据，未改业务/schema/锁/progress，不commit/push，不整卡accepted。资源释放记录见resource_release.json/receipt；结论仍needs_changes，建议主控修三项后交新固定目标定向复核。F1/D2/R1仅有保存情报的三GET读取证据，F2仅逐维保存状态与引用投影；不证明来源持续采集、全部富化或任何评分满分。
