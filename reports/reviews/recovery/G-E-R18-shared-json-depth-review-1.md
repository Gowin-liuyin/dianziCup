# G-E · R18 共享 JSON 深度根因独立初审

What this change does: 本修复把标准库 `json.loads` 解码过深 JSON 时的 `RecursionError` 转为固定 `ValueError("JSON structure outside limit") from None`。原来只能在解码成功后工作的深度、节点检查，现在也能对解码器先行拒绝的输入给出既有业务错误；正常结果与原预算不变。

本次限定结论：**Verdict: Ship.** 未发现本共享解码修复范围的 Must fix、Should fix 或 Nice to have。此结论只覆盖固定源码及直属测试，不登记整 R18、R05、阶段或产品为 accepted。

## 范围、授权与冻结

任务：`R18-shared-json-depth-boundary` 独立非作者初审；审查完成，原实现的状态由 Root 依据此报告登记。审查者没有参与该修复，也没有修改生产代码、原测试、状态、schema、迁移、依赖或锁；没有 push。

- 基线：`3fd9cd68f292afcd1b88ca55f218c4e869e8f706`。
- 被审源码/直属测试：`207d0cc2c3c5edfd06d6f96b24e217d467d74c1b`。
- 作者材料：`f1eb2c8d89050f7a9cbdcd0a439d0848e628501b`。
- 独立工作树：`D:/wt/r18-shared-json-depth-review1-20261017`；分支：`codex/r18-shared-json-depth-review1-20261017`。
- 本次原始证据：`reports/runs/r18_shared_json_depth_review1_20261017/`。审查材料的冻结提交由交接消息提供，不把包含自身的提交 SHA 写入自身。

已读项目 AGENTS、执行索引、R18/R05/R03 报告与任务状态、03 数据合同、05 API/工具合同、T18 模型客户端任务，以及 Ponytail 5.3.1 review。Root 明确授权共享根因的最小修复与所有实际调用方审查；固定输入只含 `json_output.py` 的解码 try/except 和两个新增测试文件。Root dirty 工作区中的新公开 ask、公开写适配、数据库接线不在此源码；没有用其 API 结果为本报告背书。

本轮只新增此报告和 ownrun 证据、运行器、独立合成探针。没有真实模型、PG、Redis、网络请求、付费调用、资产扫描或盲测；HTTP 测试为本机 TestClient 显式 fixture。

## 根因、实现与不变量

`backend/src/ai_intel/infrastructure/models/json_output.py:27–33` 仅包住既有解码调用，精确捕获 `RecursionError`。不捕获整段业务处理，不改变 UTF-8 编解码错误类别，不提高 Python 递归上限，也不把格式错误转为空对象或空列表。

在独立审查进程里装载基线原解析函数，运行完全相同的新增 35 例，实际 **11 failed / 24 passed**；六个 `str/bytes × 300/600/1000` decoder 深度例、aggregate/catalog、investigation/tool parser 与 inventory HTTP 命中原 `RecursionError`。固定源码下同组 **35 passed**。原生产文件没有切换或改写，旧源码仅在明确 `legacy` 模式的临时测试进程中装载，日志路径为 `old_red.*` 和 `new_fixed.*`。

实际保持并验证：合法 str/bytes 值；数组/对象深度 32 通过、33 拒绝；默认节点 10000、自定义合法范围 1–50000；默认字节 262144 与实际 UTF-8 字节数；重复键、非有限数、NUL、非对象拒绝；invalid UTF-8 与孤立 surrogate 仍为 UnicodeError。独立新增探针还亲测 20000 层对象、最大节点预算 50000 的精确两侧、默认字节预算精确两侧和字节拒绝先于 decoder。固定文案不含输入，异常原因被抑制；合成 marker 不进入 HTTP、模型 metadata 或输出结论。

## 全部实际调用面

全库 RG 和 AST 在固定源码上各自检索，确认 **15 个直接模块、21 个直接调用点**，见 `caller_rg.log`、`caller_ast.json`。还读取二级出口，包括 Hunter/Quake、Source job、ToolGateway 与调查 HTTP。下表是实际源码错误归类；“回归”指本次亲跑既有单元/合同，不代表真实服务集成。

| 直接模块及行号 | 观察结果与本次验证 |
|---|---|
| `infrastructure/models/clients.py:62,71` | `ModelContractError`；无 repair 显式失败、恰好一次 repair 成功或仍失败，新增合同与原模型合同通过。 |
| `infrastructure/models/generation.py:454,482` | wire 为 `model_wire_invalid`，输出为 `model_format_invalid`；调用次数、attempt 分类与脱敏通过，原 token/byte/timeout/wire 回归通过。 |
| `assets/aggregate_observations.py:191` | 共享 ValueError 向上抛；独立调用 Hunter/Quake 均返回 `failed / invalid_response / value=None`，各一次 fixture 请求。 |
| `assets/inventory_routes.py:163` | 可信认证的 HTTP 422 `validation_error`；同输入无认证 401，原 inventory/security 回归通过，没有数据库写入。 |
| `assessment/http_routes.py:156` | 既有 422/413 请求分支保持；实际原 HTTP 单元和合同通过。 |
| `assessment/conditions.py:223` | ValueError 在 condition schema 前抛出；独立超深输入及原条件树回归通过。 |
| `api/recommendation_routes.py:134` | 既有 `RecommendationInputError("invalid_json_body")`；亲测实际 `read_body` 和原请求 schema 回归，未跑真实推荐 API。 |
| `investigation/tool_contracts.py:120` | parser 为固定 ValueError；独立走实际 ToolGateway 得 `denied / invalid_tool_input`，计入请求字节且 service_calls=0。 |
| `investigation/graph_contracts.py:130` | parser 为固定 ValueError；实际调查 HTTP 返回 422 `invalid_investigation`，没有调用服务 provider 或数据库。 |
| `enrichment/signal_sources.py:137` | `PublicSignalError("invalid_signal_json")`；实际 EPSS/KEV 选择入口超深输入均为安全失败，原来源/schema 回归通过。 |
| `enrichment/signals.py:80` | `PublicSignalError("invalid_structured_payload")`；亲测实际 CVSS/CWE 富化结果为 failed、无候选，未变为 not_found。 |
| `ingestion/catalog_pages.py:112,160,180,339,380` | 共享 ValueError/已有 RepositoryFetchError 显式拒绝目录、blob、release 与 OSV 页面；直接探针及既有 catalog/source 回归通过。Source job 既有 `source_response_invalid / normalization_failed` 分支由源码核对，PG 持久结果未跑。 |
| `ingestion/sources/avid_records.py:92` | `RepositoryFetchError("invalid AVID JSON record")`；新读取合同与原真实来源形状 fixture 回归通过。 |
| `ingestion/sources/github_releases.py:26` | `RepositoryFetchError("invalid release JSON response")`；数组包络仍有原字节/记录数边界，新超深合同及原回归通过。 |
| `ingestion/sources/osv.py:105` | `OsvContractError`；其解码前 `json.dumps` 深度错误仍由既有捕获处理，独立探针与既有 OSV 回归通过，未扩大此补丁。 |

这些入口中已有部分边界原就捕获 RecursionError；本修复没有删除或改变它们。必须统一的共享 parser 现在返回 ValueError，aggregate/catalog 的裸调用、inventory 以及 parser 本身不再泄漏 decode RecursionError；没有只修单条 HTTP route。

## 当前 CBM 图与完整资源

Root 释放工具窗后，实际用 `Ubuntu-22.04` 的 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` v0.11.0 建本次新独立缓存。二进制 SHA-256 为 `ce11c141431aeadd788506c3a7e6942db8fd438dec369d0707a39ec9fd8c6510`，没有沿用作者或旧 R05 缓存。

复制固定源码的 10 个明确文件，排除配置、秘密、测试、fixture、holdout、日志。CBM 默认排除目录名 `assets`，所以索引副本显式映射为 `asset_boundary`；`cbm/source_manifest.json` 保存每条原真实源码路径、索引路径、raw 字节/hash 与 Git filtered blob。副本字节逐条相等，不把图的合成路径写成实际源码路径。

help/index/schema/strict parser both depth 3/inventory router both depth 3 共 **5 条实际命令全部 exit 0**。181 nodes、609 edges；skipped/not_indexed/partial/unusable 均 0。parser 图返回 13 callers（含二级），它只是这 10 源窄图，不替代全库 15 模块/21 点。图对 parser 的 callee 只识别 len/pop；实际 `json.loads`、Unicode 转换、pairs/constant 与迭代预算由源代码/AST/RG核对，不宣称图完整识别标准库调用。

实际窗口 **2026-10-17T07:32:46.078 至 07:33:04.463+08:00**。Win 峰 7、guest 峰 6、组合峰 **13≤16**；guest 控制祖先到 PID1，birth 全匹配。PID1只作为共享祖先计数，没有当工具子树根或终止对象。监督器在启动 child 前加入 Native Job：每进程 536870912 bytes、总 1073741824 bytes、CPU rate 833/24 logical CPUs = 1.9992 cores。guest affinity 两 CPU、Go 480 MiB 软限；没有声称 guest 内存硬限。

`cbm/cbm_resource_recheck.command.json` 保留完整监督收据；`cbm_terminal_final.json` 在工具返回后另外核对 Win 退出信号与 guest `/proc` birth/absence，4 个新增 Win 工具进程和 2 个 guest 工具进程均已 absent，owned active=0。Windows OpenProcess 失败必须是已不存在 PID 的 error87，其他错误不会当作 absent；此检查不是仅凭 GetProcessTimes 宣称退出。工具窗结束即归还 Root。

## 本次真实命令和结果

所有运行使用实际 CPython 3.12：`C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe`；现有依赖通过 `site.addsitedir(D:/dianzi/backend/.venv/Lib/site-packages)` 加载，同一路径传给既有 PDF child。没有虚拟环境 launcher 双 Python，没有新增依赖。fixture 环境去除服务/模型凭据并关闭轮询和生成；每条命令都先加入固定 Native Job，再调用成熟 Root helper，普通完整 Win cap 10、deadline 60 秒，终态 owned=0。

执行入口为 `run_owned.py <label> fixed|legacy pytest -q -o addopts= <文件集合> --junitxml=<本次XML>`。工作目录固定为本 WT 的 `backend`；完整 argv、起止、实际 exit、完整 birth 进程链、资源和日志在每组 `.command.json/.owned.json/.stdout.log/.stderr.log`，不是从作者结果抄通过数。`-o addopts=` 只关闭聚焦集合的全项目 coverage 默认门，不改变项目配置或原60%门，本次全项目覆盖率 not_run。

| 标签 / 实际文件集合 | exit | 实际结果 / Win峰 |
|---|---:|---|
| `old_red`：新 unit + contract，临时进程装载未修复原函数 | 1 | 11 failed、24 passed / 4 |
| `new_fixed`：新 unit + contract | 0 | 35 passed / 4 |
| `model_read_harness_fixed`：生成/修复/预派发/wire、T18、catalog/source、aggregate 原 8 文件 | 0 | 251 passed / 8 |
| `request_signal_harness_fixed`：public signals 两 unit、sources/schema 两 contract、assessment HTTP 两文件、tool 两文件、LangGraph contract | 0 | 277 passed / 4 |
| `security`：inventory 与 SBOM security + 新 unit | 0 | 43 passed（含已计25新unit）/ 4 |
| `condition_inventory`：T27、inventory unit/contract、recommendation input | 0 | 153 passed / 4 |
| `independent_callers_fixture_fixed`：ownrun 非作者出口和预算探针 | 0 | 16 passed / 4 |
| `lint`：Ruff check 被审3文件 | 0 | All checks passed / 5 |
| `format`：Ruff format --check 被审3文件 | 0 | 3 files already formatted / 5 |
| `type_json`：mypy --follow-imports=skip 变更 parser | 0 | 1 source file passed / 4 |

有效 JUnit 按 `classname + name` 去重：原/新增作者测试 **734 distinct passed**，另 **16 非作者 distinct passed**，本次合计 **750 distinct passed、0 fail/error/skip**。不把安全组重复的25例再加一次，也不把旧红灯的24通过或失败收集计入绿色总数。`summary.json` 从本次 XML 与原收据生成；本次没有因通过而删困难用例、扩误差、降阈值、改金标或分母。

失败如实保留，均已定位为审查运行器/新增探针的问题，不作为产品通过证据：`model_read` 路径把 wire 写成 unit，exit4、未运行；`model_read_corrected` 因运行器未把现有依赖传给 PDF child，250passed/1failed，随后只修 ownrun 环境、同8文件251passed；`request_signal` 缺 backend 包路径导致3 collection errors，exit2，修 ownrun 后同9文件277passed。非作者新探针第一次 import 了错误模块（exit2、1 collection error），第二次新 fixture 将 Pydantic 对象误用 dataclass.replace 且猜错调查错误码（14passed/2failed）；查实际类型和既有文案后仅修 ownrun fixture，16passed。原业务/原assert完全未改。

早期运行器已按首轮收据 SHA 原字节重建并核对，存入 `historical_harness/`；首轮失败、修正后的日志没有覆盖。封存辅助程序第一次未显式用 UTF-8 读中文 docstring，产生 UnicodeDecodeError/exit1；补编码后 exit0，也保留两条收据。

## 字节、计划差异与未查

被审生产文件 raw 2146 bytes/53 CRLF，作者与review相等；Git blob 2093 bytes。两个新测试在作者工作树分别是4177/7188 LF bytes，在独立 checkout是4282/7358 bytes（105/170 CRLF）。`summary.json/source_snapshots`分别保存 raw SHA、blob SHA、CRLF数量、filter 后 OID；所有 reviewer/author filtered OID 都等于固定 source blob，source 与 material 的三条 blob也逐字节相等。没有裁剪、换旧数据或把 LF raw hash冒称CRLF raw hash。

业务合同与计划没有偏差；被审三个文件 diff exit0，材料暂存前 tracked status空，所有修改限定 report/ownrun。采用成熟监督器仅改明确 ROOT/输出目录/import path与四条源码 hash路径，资源判断未改。此工作没有引入抽象框架或额外依赖。

最终完整材料 `git diff --cached --check` exit2，原因是保留原失败 traceback 的 JUnit XML 中有行尾空白。没有修改这些原始日志或新增忽略规则；被审 source diff check及报告自身 diff check均exit0，见`freeze_material.stdout.log`和最终收据。此生成证据格式提示不计成业务测试失败，也没有把完整材料检查写成通过。`artifact_manifest.json`分别记录原磁盘raw与Git暂存blob字节/hash，避免Git换行过滤后误称raw一致。

unit、contract、本次有界security：passed。integration、frontend、e2e、live、产品manual：**not_run**。Source job 的PG错误持久化、公开 ask 当前候选接线、真实模型、真实来源、完整Agent、性能/吞吐、六小时稳定与正式评分均未查。mypy只查改变的1源，Ruff只查被审3文件，没有声称全库类型或全项目覆盖率通过。

评分项证据仅支持 E1/X1 的固定输入失败、预算和脱敏，以及 F3/A1 的模型/工具错误分类回归，不提升准确率、P95、正式分母或阶段状态。下一步建议 Root 合入固定共享 parser与测试，并对自己的新公开 ask 与完整默认入口另做独立审查；本报告不能替代该新源码的 HTTP/PG验证。

Verdict: Ship. 本共享根因与原预算回归可进入 Root 后续整合。

Not checked: PG/网络/live、Root dirty公开ask、全产品/阶段/人工验收。
