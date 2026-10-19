# R12 · 索引创建原错误与总预算入口修复

本切片状态 `awaiting_review`，实现 `complete`；整 R12/G-D 保持 `partial`，没有 accepted、阶段签字或 push。作者 `/root/r12_projection_failure_budget_implementation`，分支 `codex/r12-pfb`，工作树 `D:/wt/r12-pfb`。固定基线 `8c48b61c02860166bdda0986e984058e8a824188`，源码冻结 `9cd6381eacc67853c055643d634ffb1812875214`。报告实际文件创建/修改时间由 `report_file_metadata.json` 记录，不推测模型开始写作秒数。

## 合同、输入输出与修改范围

已读 AGENTS、00 执行地图、R12 恢复任务卡、原 T30、04 工作流、05 API、06 测试、08 风格、三个 R12 正式 CR、progress 状态和交接；采用 Ponytail 5.3.1 full。输入 raw SHA 与 baseline/current Git blob、冻结源码 raw/Git 版本见 [input_metadata.json](../runs/r12_projection_failure_budget_20261017/input_metadata.json)。原 R10 默认 worker 报告亲读并核 hash，原根目录未提交的前端缓存/push 台账和材料未修改。

本轮输入为固定 generation、可信内部 OpenSearch client、当前 worker 的 PG outbox/change 以及单调总截止时间；输出是合法幂等创建/映射校验，或保留第一个安全错误码，成功处理仍 `partial/knowledge_change_other_consumers_pending`。原索引代际、维度、模型空间、映射严格性、PG 权威、事实/收据/epoch、容量 10000 和总预算 20 秒没有改变。

Root 仅批准两个业务路径及直属测试；不改 settings、indexing、retrieval/service、R14、ContentStorage、worker、认证、API/协议、迁移、锁、金标/分母、progress 或盲测材料。确认 ApplicationSettings 没有 projection_timeout 字段，因此没有新环境字段、解析默认值或静默 fallback。非法格式新增反例只验证现有内部预算入口的严格类型边界。

## 原红与根因

本作者在固定基线亲复原 `test_r12_projection_total_budget_fix2.py`，实际 2026-10-17 04:35:37.962725–04:35:40.668684 +08，exit 1，5 passed / 12 failed / 0 error / 0 skip。

7 个创建失败是原 `create_index` 捕获全部 HybridRetrievalError 后继续 GET mapping：PUT 的 timeout、connect、400 非已存在、409 非已存在、500 伪已存在、403、超限错误被覆盖或多一次 IO。另 5 个非法预算用例实际是 `_new_projection_deadline` 缺失导致 AttributeError；两个生产构造点直接使用 `clock + PROJECTION_TIMEOUT_SECONDS`，没有共同校验。不能将这 5 例写成已经存在的环境解析器返回错误。

原 Oracle Git blob `14b93c44927a005393150aa4b0fece869b99da79`，raw SHA256 `d0d43ee90a50590a225f3a5154c91d529eefee2298a631c2143862664d08b6d3`，与基线逐字/规范化一致，未改断言、timeout、阈值、skip 或文件。

## 实现与直属测试

1. `retrieval/opensearch_client.py`：去掉无差别捕获。仅 400/409 且严格 JSON `error.type == resource_already_exists_exception` 允许随后核查 mapping。其他状态、间接 root_cause、reason 文本、格式错误和 transport 未知结果保留原 typed 安全错误并终止 IO。创建成功只有 PUT；已存在必须再通过原 generation/model/dimension、dynamic=strict、唯一索引检查。
2. 同一路径中，异步候选错误体在原 `asyncio.timeout(remaining)` 内有界收集；共享 2 MiB 上限，超限不解析不 GET。已存在后 GET 使用相同绝对 deadline，原 headers/body/关闭取消、同源、TLS、固定索引、无重定向边界保留。普通同步路径沿用现有 client.request 与严格较短 phase timeout，不新增任意 URL 工具。
3. `retrieval/runtime_policy.py`：新增私有有限正数预算入口，严格拒绝 bool、NaN、inf、零、负数、字符串/None；工厂在创建 client/SSL 配置前只建立一个 deadline，模型和搜索沿用同一值。直接 handler 先创建或复用 deadline，并在 PG 查验前复用 require_projection_deadline；prepare_generation 和 refresh_scope 接收同一值，不在两阶段重置。
4. 新 `tests/contract/test_r12_projection_failure_budget.py` 共 53 例：异步错误分类、同步/异步畸形或间接已存在、映射格式/空间/dynamic/多个索引拒绝、成功单 PUT、2 MiB 与 +1 字节、已存在后的权限错误、同一截止时间取消和 client 关闭、非法预算首次 IO 前拒绝、直接 handler 准备/刷新共享 D、工厂配置耗时不重置 D。全部 MockTransport/合成模型夹具明确离线，不计语义或服务 live。

官方 [Create Index API](https://docs.opensearch.org/latest/api-reference/index-apis/create-index/) 核对固定 PUT 路径；官方 [opensearch-py JSON guide](https://github.com/opensearch-project/opensearch-py/blob/main/guides/json.md)说明 400 已存在错误。409 支持来自原冻结 Oracle，而不是根据外部文档改本地合同。没有新增正式 CR 语义差异。

## 真实命令与结果

完整 argv/cwd/UTC 起止/exit、own PID/birth、峰值/停止/剩余进程、源码 raw SHA 和原日志 SHA 均在 [run 目录](../runs/r12_projection_failure_budget_20261017/)。执行前缀为 `D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/r12_projection_failure_budget_20261017/checks.py <label>`，测试 cwd=本 WT/backend，随后真实 `-m pytest / ruff / mypy` 参数。shell 实际是 `C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe`、login=false，不记录不存在的 Tool 别名为物理可执行文件。

| label / 实际检查 | +08 起止 | exit / 数量 | 结论 |
|---|---|---|---|
| baseline_oracle，原17 | 04:35:37.962725–04:35:40.668684 | 1；5 pass / 12 fail | 本作者最小红复现 |
| oracle_first_green，原17 | 04:37:49.528613–04:37:51.640954 | 0；17 pass | 原 Oracle 原样转绿 |
| expanded_first，5文件初扩展 | 04:38:32.414475–04:38:35.606782 | 1；75 pass / 1 fail | 新 harness SSL setup 消耗 0.1s 测试预算，原红保留 |
| expanded_fixed，修正新 harness | 04:38:48.954589–04:38:52.299382 | 0；76 pass | 复用验证 TLS context，setup 后计时；0.1s 原阈值不改 |
| focused_final，新 factory 反例首次 | 04:39:45.551279–04:39:48.389255 | 1；84 pass / 1 fail | 作者误用相对模型缓存路径，真实配置校验拒绝；改 tmp_path，产品不放宽 |
| focused_fixed，最终5文件 | 04:40:08.996321–04:40:11.459128 | 0；85 pass / 0 fail/error/skip | 原17+新53+旧15 |
| related_regression，误文件名 | 04:40:11.669072–04:40:13.192324 | 4；0执行 | test_r03_workers.py 不存在，属于命令错误，不当业务通过 |
| related_regression_fixed，真实10文件 | 04:40:46.900672–04:40:53.076988 | 0；82 pass / 0 fail/error/skip | 原混合检索、合同、配置/worker/job与权限投影回归 |
| static_first / lint_autofix | 04:39:48–04:39:55（两命令） | 1 / 1；9后6 style问题 | 原日志保留；只修直属测试布局，不加 ignore |
| static_final，3业务/测试+2仪器文件 | 04:40:19.396902–04:40:19.544028 | 0；5文件 | 08 命名/导入/风格实际通过 |
| types_final，mypy src/ai_intel | 04:40:19.734567–04:40:41.895567 | 0；194 source | 无新增 Any/cast/ignore |
| format_final，同5文件 | 04:40:53.271483–04:40:53.424184 | 0；5文件 | 实际格式通过 |
| integration_collect，五原PG/OS文件 | 04:41:17.239372–04:41:19.578315 | 0；61 collected / 0执行 | 集成 not_run，不读旧 DSN 或连接服务 |

最终两个测试集合互不重叠，共 167 distinct：unit 59、contract 82、security 26。85 的正确分项是原17+新53+旧15；作者早期向 Root 手算成55新/13旧已更正，JUnit/日志未改。中间重复绿/红不能累计成最终通过数。针对性 pytest 使用 `-o addopts=`，避免将全仓 coverage 阈值冒用于局部子集；未改 pyproject 或原验收门槛，全仓 coverage/not_run。

源码 commit 前 `git diff --check`、源码 staged check 通过。所有测试 receipt 的 Git HEAD 为8c48加当时源码 WIP；其 raw SHA 与冻结9cd源码逐项相同，不声称测试是在一个不存在的提前 commit 上执行。

封包脚本首轮 material_style exit1（5条E501）及 material_format exit1保留，格式化后 material_static_fixed/material_format_fixed实际exit0。这些是材料检查，不累加为业务用例。Root于本轮确认保持9cd三文件最小范围；authority SQL timeout留作下一必要切片，不扩大本包或完整R12结论。

## CBM、资源与材料保留

Root 授本包独占 CBM，实际窗口 04:36:22.023002–04:37:11.956119 +08，结束即交回。首次 help/index 填错 distro Ubuntu，各未进入 Linux；已 `wsl --list --quiet` 核实际 Ubuntu-22.04。原 WSL exit4294967295、UTF16 错误日志与 wrapper GBK打印错误保留；修正 stdout UTF8 后实际官方 global --help/index/schema/create_index trace/factory trace 均 exit0。未伪造 CLI 帮助或 trace 参数。

官方 portable 0.11.0，binary SHA256 `ce11c141431aeadd788506c3a7e6942db8fd438dec369d0707a39ec9fd8c6510`；使用明确 `CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-pfb-cache-20261017`，只索引本 WT 固定8c48公开 backend/src，无秘密/holdout/fixtures/reports。2692 nodes、15984 edges、178 files；工具自行排除 assets等10目录并截断列表，不称全仓覆盖。源码更改后未刷新本索引，所以 trace 明确只代表基线。create_index trace 的 callers0及错误 Neo4j.run 边是静态解析限制；实际 rg 确证 HybridIndexer.prepare_generation→create_index、consume_job→build_projection_job_handlers，再人工沿 `_request` 和 async 分支核对。没有用缺边签未接线。

普通离线成功命令 Windows own峰≤5、Linux0；CBM成功命令 Windows峰5、Linux峰2，合≤7，上限10+6=16；每工具最长<8秒，outer58/inner54秒防护，结束 own descendants均0。cap是完整进程数，不是CPU核数；未开启 daemon、模型下载、PG/OS/来源、浏览器或 paid API。

原 `.log` 与 JUnit `.xml` bytes 全部保留在本 WT；版本归档用 mtime=0的 `.log.gz`/`.xml.gz`，解压逐字相同，以 [raw_log_manifest.json](../runs/r12_projection_failure_budget_20261017/raw_log_manifest.json) 同时记录 raw/gzip SHA256与bytes。这避免改变失败 traceback 尾空白，原日志没有清洗、覆盖或删除。首次材料 staged whitespace检查exit2，原因是原失败JUnit含尾空白；记录原输出后只把原XML无损压缩归档，没有修改失败内容或新增ignore。新 checkout 只需解压即可按原文件名核 raw SHA；Git LF/CRLF与raw版本分别记录，不能推定它们相同。封包仪器的格式化发生在运行后，历史监控命令不声称与归档仪器 raw相同。actual exact secret scan/not_run，未读取秘密值；不称全秘密安全门通过。

## 各类状态、限制与下一任务

| 类别 | 本切片状态 | 证据与限度 |
|---|---|---|
| unit | passed | 59离线 distinct；首次外部IO前非法/过期拒绝及默认工厂共享D |
| contract | passed | 82 distinct，含原17与新53；没有修改原Oracle |
| integration | not_run | 61仅collect；没有授权的新 PG+OpenSearch 实跑 |
| security | 定向offline passed | 26既有scope/job边界及新拒绝例；真实认证、并发与全秘密扫描未验 |
| frontend | not_run | 无前端修改或UI执行 |
| e2e | not_run | 未证明 publication→真实搜索/模型→问答全链 |
| live | not_run | 无真实语义/PG/OS/来源调用；费用未知服务未触发 |
| manual | not_run | 新独立 reviewer 尚未签；无人工 gold/质量验收 |

原有完整 worker claim/read/complete、WAL flush/COMMIT ACK硬20秒问题未闭合。`find_projection_change` 的调用者 Session SQL没有原生剩余 statement timeout；本包只在查验前检查 deadline。直接手工注入未带预算的裸模型/搜索不会因 prepare/refresh传D自动变成原生可取消 client；产品默认工厂使用已配置同D的端口。同步遗留 `_request` 先由httpx整收body再len校验，其下载/内存硬上限改造也不在本包。这些限度不影响原12红修复，但不能用本包167绿宣称完整投影/worker硬时限验收。

F3/P3/E1/T30证据仅支持索引幂等创建、错误原因保留、预算边界与既有过滤回归，不支持真实检索召回率、多跳正确率、全链SLA、当前性并发或正式评分达标。无新合同偏差；如需扩展authority read的原生SQL预算或裸indexer端口装配，由Root另定精确scope，不能静默改共享worker/接口。

下一任务建议：Root核source9cd与材料hash后派新非作者review；先复跑原17、新53与82回归，再按新B资源收据提供fresh owned PG+OpenSearch窗口，验证失败不写PG generation/watermark/receipt、已存在映射误配、重放/并发与默认工厂deadline。不得执行原hardcoded旧DSN、借Source数据库、延长旧窗口或downgrade；整R12/阶段不accepted。
