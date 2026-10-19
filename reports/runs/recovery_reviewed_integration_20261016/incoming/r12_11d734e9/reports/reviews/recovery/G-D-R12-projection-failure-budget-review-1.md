# G-D / R12 projection failure + total budget 独立初审

What this change does: 本切片保留索引 PUT 首次失败的安全错误分类，只允许精确的 400/409 already-exists 响应进入映射核查；默认工厂和直接 handler 共用经过有限正数校验的单调绝对截止时间，prepare/refresh 不重开预算。结论 **LimitedShip，仅固定三路径的离线修复**；未发现本切片新增 Must/Should/Lean 问题，整 R12/T30/T31/G-D 仍 partial，不签 accepted、完整 worker 20 秒或 live。

审查人：非作者 `/root/r12_projection_failure_budget_first_independent_review`；分支 `codex/r12-pfbr1`，隔离 WT `D:/wt/r12-pfbr1`。Root 基线 `8c48b61c02860166bdda0986e984058e8a824188`；作者 source `9cd6381eacc67853c055643d634ffb1812875214`；材料 `7813bbf27e31e66d5f53cd595a0278d962092a39`。业务测试与资源复核执行HEAD固定source；交付本地commit按Root新增明确授权，仅增加自有report/run/独立测试，业务、原测试、合同、阈值、金标、状态、认证和共享资源均未改。无 push，无服务启动，无秘密/.env/holdout 读取，费用 unknown，本审查 paid 调用 0。

已读 AGENTS、执行图、实际恢复 R12 卡、原 T28–T31、03/04/05/06/08、task_manifest/task_state/handoff、三个 R12 正式 CR 及作者冻结报告。使用 Ponytail 5.3.1 review 正文 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.3.1/skills/ponytail-review/SKILL.md`，沿调用方审查，不用代码存在或旧绿推断通过。

## 固定范围、源码与原 Oracle

baseline→source `git diff --name-status` 精确只有以下三路径；`source_manifest.json` 保存 baseline/current blob、raw/LF SHA、源码字节与 Git LF 的逐项一致结果。`git diff --check` 实际 exit0。

| 路径 | 冻结 source blob | 本 WT raw SHA256 |
|---|---|---|
| `backend/src/ai_intel/retrieval/opensearch_client.py` | `171ae9fdbbfe0880081fb196da84fe97419ead62` | `873f0b586b397cc59d98473d9a4e6558e90650ed9867ec41d4fe5fa77b76a289` |
| `backend/src/ai_intel/retrieval/runtime_policy.py` | `ad7316e06cfb2233bb3288bfc3bb1dbb67faa82a` | `839ed79318d4c5897d9e49b7a1f67066b3cd2034751e35fff1c3b9690f013e2a` |
| 新 `backend/tests/contract/test_r12_projection_failure_budget.py` | `b16316d2fad5fd2fdfe78b7e9206ef2eb1cba4a8` | `0a75493b0537ceb04e675178241320415c6c423a61a1232551706cf7f8cc2b5f` |

新 contract 作者测试 raw 为 LF，SHA `e245417c7cb533198c5911cc13242d8e2c891a805713f23b11b3bcf1b251fb6a`；本 fresh checkout 为 CRLF，规范化后逐字等于同一 Git blob。没有把 raw 与 LF hash 说成相同。

原 17 例正确路径是 `backend/tests/contract/test_r12_projection_total_budget_fix2.py`。Root 初始派发写成 unit，导致最初 read/rg 找不到；Root 已更正，属指令路径问题，不是业务测试失败。原 blob `14b93c44927a005393150aa4b0fece869b99da79`，raw `d0d43ee90a50590a225f3a5154c91d529eefee2298a631c2143862664d08b6d3`，与 baseline 完全不变；原 Oracle 未改字节/断言/timeout/skip。

## 真实调用与逐项判断

真实产品链是 `workers/runtime.py:160 consume_job` → `:178 build_projection_job_handlers` → `workers/executor.py:95 execute_job` → `runtime_policy.py:107 make_knowledge_change_handler` → `:123 prepare_generation(deadline=D)` / `:124 refresh_scope(deadline=D)` → `indexing.py:194 search.create_index`。已用 `rg` 与源码交叉，不依赖图缺边判断。

- `opensearch_client.py:286–297` 严格解析顶层 `error.type`，只有状态 400/409 且值完全等于 `resource_already_exists_exception` 才允许返回错误响应给 create；`299–339` 只对这个返回执行 GET。timeout/connect/permission、其他 HTTP、reason/root_cause 提示、畸形 JSON、超限都不追加 GET，不被后续 404 重分类。成功 PUT 只一次请求；允许的已存在仍通过 generation/model/dimension/dynamic/唯一索引的旧校验。
- `opensearch_client.py:255–282` 在原绝对截止时间内流式收集候选错误体；累计 2 MiB 上限在解析前生效，超限不 GET。PUT 之后的 mapping GET 沿用同一 D。我的慢错误体、跨 chunk 超限和 mapping 409 不递归三类负例验证安全码、请求列表与 client 已关闭。
- `runtime_policy.py:45–53` 拒绝非有限正数和 bool；工厂 `:152` 在 client/SSL 准备前只创建一次 D，`:169–188` 将 D 给模型、搜索与 handler；直接 handler `:117–124` 创建/复用 D，在 authority read 前校验，并传入 prepare 与 refresh。我的 supplied bool/NaN/inf 和 client setup 从 clock100 推到121的负例均在首次 authority IO 前失败，没有重新给20秒。
- 没有改变 TLS、trusted origin、固定索引、无重定向、PG 权威、维度384、模型代际、容量10000、20秒常量或 `partial/knowledge_change_other_consumers_pending`。异常转换仍输出已有安全码，不把原始网络异常/凭据暴露给产品。

## 亲跑命令、数量与证据

实际物理 shell：`C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe`，login=false。实际 base Python：`C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe`，子进程通过明确 `D:/dianzi/backend/.venv/Lib/site-packages` 复用依赖，未调用 venv shim。cwd 为本 WT/backend；入口 `.../reports/runs/r12_projection_failure_budget_review1_20261017/run_review.py <label>`，完整实际 argv、起止、exit、源码 SHA 与原始 stdout/stderr 在各 `<label>.command.json` / `.stdout.log` / `.stderr.log`。

| label / 实际子命令 | +08 起止 | exit / 结果 |
|---|---|---|
| focused；`-m pytest <原17> <新53> <自有12> -o addopts= -q -p no:cacheprovider --basetemp=... --junitxml=...` | 04:47:42.096–04:47:45.178 | 0；82 passed，0 failed/error/skip |
| related；同参数，原 deadline/default/terminal 三文件 + 作者相关十文件 | 04:48:11.958–04:48:19.280 | 0；97 passed，0 failed/error/skip |
| style；`-m ruff check <三路径>` | 04:48:19.797–04:48:19.975 | 0；all checks passed |
| format；`-m ruff format --check <三路径>` | 04:48:20.125–04:48:20.322 | 0；3 files already formatted |
| types；`-m mypy --cache-dir=<自有cache> <两个源码>` | 04:48:20.495–04:48:29.928 | 0；no issues in 2 source files |
| material / material_fixed；独立 gzip/raw、来源版本及 JUnit 核查 | 04:49:03.037–04:49:06.591 / 04:49:22.037–04:49:25.281 | 首轮1，修正后0；见下面原错误保留 |
| callers；固定五源码 `rg -n` | 04:49:56.232–04:49:56.401 | 0；入口与调用证据 |
| boundary；`git diff --check baseline source -- <三路径>` | 04:49:56.603–04:49:56.724 | 0 |
| CBM；实际 Ubuntu-22.04 / 官方 portable CLI 七工具 | 04:51:28.279–04:51:57.269 | 0；七工具分别0 |

`material_validation.json` 以 `(classname,name)` 合并两次最终 JUnit，**179 distinct**，不是累计多次运行：作者最终85+82=167全被亲跑覆盖，加自有12。新 contract 是53，旧 focused 三文件是15；没有沿用作者早期55/13的手算。原17、新53均包含在focused82中，不能再次相加。局部检查显式 `-o addopts=`，没有修改 pyproject/coverage门；全仓coverage not_run。

作者材料冻结 commit 的42份 `.log.gz`/`.xml.gz` 已解压逐字核 raw SHA/bytes与archive SHA/bytes，全部一致，原红保留。作者基线原17实际5pass/12fail/0error/skip；最终focused85、related82均全绿。receipt当时HEAD为baseline加WIP，源码raw或LF与冻结9cd逐项对应，未将其说成提前在9cd commit上运行。

我的首轮材料脚本误把作者baseline receipt源码和新source比较，实际material exit1。原脚本 `verify_material_first.py.txt`、日志与receipt保留；修正按baseline与source各自核hash后material_fixed exit0，不改作者材料。没有把仪器错误当业务红，也没有覆盖失败文件。

首轮收件封存为 `review_evidence_manifest_fixed.json`，代理补证封存为 `review_delivery_manifest.json`，最终交付封存为 `review_delivery_manifest_v2.json`。首manifest纳入了seal自身仍在写的stdout，随后末尾打印使该条hash过时；首manifest/脚本/原空stdout归档保留。修正排除正在写的seal标签，不把首封包当有效整体hash证明；其余既有raw/gzip先逐字比对再复用，不修改原日志。最终仪器快照是在offline跑完后加入CBM/terminal支持的版本，不冒充此前监控仪器的执行时raw；首轮报告原字节另存 `review_report_first.md.txt`。

提交前限定模式检查仅解压/读取待交付own报告与proof，不加载秘密值。三次prepare gate实际exit1，index始终空：首轮匹配到JUnit的固定合成credential URI，第一次谓词误比较完整URI与仅到@的regex；修正regex后还剩原安全Oracle第二个URI。两次修复无stage进展即停止扩大scanner，提交根因并以XML testcase名及固定源码人工归类：`test_r01_runtime_settings.py:45/50` 的origin拒绝例、`test_r12_retrieval_boundaries.py:18/24` 的search URL拒绝例，以及对应仪器源码快照中的同一显式合成常量。原raw/JUnit、三个仪器红与脚本快照均保留；不会删参数或清洗日志。private-key/OpenAI-key/PG-URL/AKIA等其余模式无命中；已知合成case的credential模式命中单列，不把该检查称为全秘密registry验证。最终本地commit仅stage精确自有report/run proof，raw失败以无损gzip入包，缓存/临时目录不入包；staged diff与范围检查记录在`commit_boundary_manual.json`。

## 资源与 CBM 边界

使用Root冻结成熟 `batch13_checks_helper.py` / `batch13_process_metadata.py`，适配自有ROOT/RUN、basePython/site、source hash；PID/birth按真实外层PWSH树采样。原样复制Root批准CORE984c公开 `runtime_limits.py`，raw SHA `6c60580dbc5f44c8bf13212d08feb16e515efcedc62d15ebd57a6dedaf9fd156`，只在本 supervisor import 后设置512MiBprocess/1GiBjob/CPU率833。

每次 spawning前 `OwnedJob()`；实际QueryInformationJobObject9 flags8960/process536870912/job1073741824，15 flags5/rate833，24逻辑处理器折合1.9992核。Job包括supervisor与继承子进程，PWSH/工具祖先另采样，未说全部链都在Job。KILL_ON_CLOSE handle保留至supervisor退出；普通命令Windows峰≤6、最长9.433秒、峰Job内存371474432字节。各receipt最终Job active1是supervisor本身，child已wait且新后代残留0；后续`terminal_boundary.json`按已捕获PID/birth核same-birth active0，当前Linux工具后代0。

CBM专窗获Root批准且结束即释放。官方0.11.0 binary SHA `ce11c141431aeadd788506c3a7e6942db8fd438dec369d0707a39ec9fd8c6510`；实际help后索引同一fixed9cd公开backend/src，独立 `CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-pfbr1-20261017`、Linux工具affinity2，不索引secret/holdout/test/run。2697nodes/16006edges/178files；not_indexed/skipped/parse_partial/parse_unusable0。工具排除assets等18目录，列表truncated，不称全仓覆盖。

consumer/factory/prepare/create trace均实际exit0。prepare/create callers0，create仍有错误的Neo4j.run边，是解析器缺口；`callers.stdout.log`和人工源码确证真实入口。graph不替代调用方与源码核对，也不证明运行成功。

CBM完整Windows已捕获峰7，成熟metadata的guest Python+CBM工具树峰2，同时已捕获合峰9；原helper只对comm为SessionLeader的代理祖先纳入，未保存guest init代理完整祖先birth。因此**不能将9写成全部guest代理已计的完整合树上界**。该资源采样限度已及时报告Root，后续终态只证明已捕获工具birth退出；若必须核完整guest代理，须另获短专窗补充，不能凭估计补造。WindowsJob限制不声称约束WSL guest内存。

Root后续批准同9cd、≤30秒的窄资源复核，待前一R10只读探针结束ACK后才执行。新窗口 **04:58:11.537–04:58:19.878+08，8.341秒，outer/schema/factory trace均exit0**；没有重建索引或重跑179例。此前Windows已有树单列，preexisting自有Linux工具0；新guest记录从Python10728/startticks9947946完整向上到 fish10654/9947756、Relay10653/9947755、SessionLeader10652/9947754、init PID1/65960。祖先PID/startticks全部在每次完整工具树采样中核对，complete_to_pid1=true、missing0；共享PID1保守纳入峰值，从未作为自有进程终止。

新Window完整Windows峰7、Linux工具子树2+控制祖先4=峰6，实际同时combined峰13≤16；25秒outer与23秒guest工具墙钟保护，原生WindowsJob限制仍实际Query9/15保持。`cbm_resource_recheck.command.json`、`cbm_resource_control.json`与两个raw日志保存新证据。`terminal_resource_boundary.json`逐identity复查Python/fish/Relay/SessionLeader及两次CLI工具共6个临时guest全部退出/非同birth，unresolved0；Windows旧窗口same-birth active0，shared init继续正常存在。新观察补足代理计数，首采局限作为历史保留，不改旧receipt或把旧合峰9解释为完整树。

## 未检查、既有限制与评分边界

PG/OpenSearch integration **not_run**，未读取旧/生产DSN，未借Source数据库，未启动或改变服务。真实模型、默认consumer端到端、并发/replay/PG generation-watermark-receipt原子失败、UI/e2e/live、manual gold、全秘密检查与正式性能均not_run。fixtures只支持unit/contract与定向安全边界，不计真实语义召回、多跳正确率或评分达标。

以下既有缺口不被这三路径修复覆盖：

| 触发与位置 | 影响 / 最小后续范围 |
|---|---|
| `runtime_policy.py:78–101 find_projection_change` 在executor传入Session查询；这里只做`:121`查询前deadline检查 | SQL本身没有剩余statement/lock timeout，慢authority read仍可跨D；Root另定调用方Session的原生SQL预算切片，不能用本次绿签硬20秒 |
| `workers/executor.py:105/118/138/166` claim/read/complete事务没有接收该D；`workers/runtime.py:180`仍原execute入口 | 完整worker预算未闭合；应由Root接整事务链，本review不擅改worker或状态 |
| 直接注入裸models/search给handler，端口未带D；只向prepare/refresh传D | 不自动得到原生模型/网络取消；默认factory已有同D端口，自定义注入须保持同样装配 |
| `opensearch_client.py:220–229` 遗留同步client.request先完整收body再len检查 | 下载/内存硬上限仍非流式保障，不能将2MiB校验冒充同步读取取消；新default async边界维持原限制 |
| `indexing.py:136–164` 最终约束显式检查后commit | WAL flush/网络COMMIT ACK仍不能保证硬20秒或receipt0；按原CR保留不确定ACK与幂等有限重验 |

这些均在作者报告与已批准CR/Root状态中可见，不是本切片新增Must；不静默扩大修复或完整R12签字。F3/P3/E1/T30本证据只支持索引幂等创建、错误分类和离线总预算入口，不支持全链SLA、历史/当前性并发、正式accuracy/recall或阶段通过。

下一建议：Root按精确source三路径登记本窄LimitedShip；完整worker authority SQL预算及fresh owned PG/OpenSearch故障/replay/并发另排有界切片。普通本地改动保留报告与原证据供复核，progress不改。

Verdict: **LimitedShip（source三路径、179 distinct离线亲复）；完整R12/worker20秒与外部验证不通过签字。**

Not checked: fresh PG/OpenSearch/model/live/e2e/manual/正式性能；首CBM代理祖先采样不足保留历史，新窄复核已补齐。
