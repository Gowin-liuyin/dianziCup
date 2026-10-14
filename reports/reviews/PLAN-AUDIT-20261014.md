# PLAN-AUDIT-20261014：规划、赛题与代码现状核查

状态：**awaiting_review**。任务类型：规划与只读代码核查；未执行产品修复。本报告不替代原任务的独立验收。

基线：`D:\dianzi`，分支 `main`，提交 `8e265dc039a67319140f003f6a070ea714bf7bef`。开始核查时工作区无未提交变更。本轮新增计划、任务卡、报告和证据文件；未修改业务源码、依赖、冻结合同或 `progress/task_state.json`，未提交、push或公开发布。

## 1. 结论

当前代码有可复用的基础，但距离新规划和官方赛题要求仍有结构性差距。最主要问题是：**验收停留在局部函数和测试替身，真实运行入口及跨模块业务链尚未建立**。这比“外部API没配置”更严重；部分已经标 accepted 的代码在真实输入上直接失败。

建议保留已有枚举、权限判断、原文修订、SQL任务/outbox等基础，重开真实接口、持久化与集成验收；先构建真实可操作闭环，再补齐广度和深度。后续方案见[完整交付恢复计划](../../docs/plan/11_full_delivery_recovery_20261014.md)和[25张恢复任务卡](../../docs/plan/12_recovery_task_cards_20261014.md)。

不报告一个无法审计的“项目完成百分比”。当前状态索引有24项accepted、36项pending；22项accepted未单独填写verification字段。这只能说明历史任务登记情况，不能证明24项业务能力已经完整工作。

## 2. 已核查材料与方法

| 材料 | 核查范围 / SHA-256 |
|---|---|
| 用户 `team-ai-intel.zip` | MASTER-PLAN、architecture、connectors-spec、plugin-sdk-spec、excellence-plan、demo-script、report-preview、接入与情报调研；`c07474d923079b6d31d9b9b74f3b64126416e69c9b823e7095f782d6f528d822` |
| 用户 `MASTER-PLAN.docx` | 提取段落/表格，与压缩包内同名DOCX比较一致；`c9a087410741eb735587bf24e6690be2504dc55cf1eba742f11179ef2117e54f` |
| 官方赛题PDF | 四页文本提取，评分页视觉核对；`37f28bc38db91ec0407551b1254c8bc882432a8488ce896c681e1210814c6cf3` |
| 仓库合同 | 执行地图、评分、架构、数据/API、算法、测试合同、任务卡、状态和交接 |
| 当前实现 | 后端源文件、测试、迁移、认证入口、前端、Compose、CI和检查脚本 |
| 运行核查 | 本轮重新运行153项离线后端测试、静态检查和前端检查；直接探测默认应用、PDF、真实NVD响应、账本和模型入口 |

附件中的 `.env`、`KEYS-AND-USAGE.*` 没有读取或复制到仓库。附件作者关于网络、接口、配额和统计数量的历史表述，未当作本轮实测结果。没有调用付费模型或测绘接口，没有扫描第三方资产，没有执行PoC。

### codebase-memory-mcp 的实际使用

按用户指定使用[codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)，并非只参考README。使用官方 `v0.11.0` portable Linux发布包，在WSL内建立临时代码图，未改变用户全局MCP配置或目录ACL。发布包SHA-256：`1f9e8293eb2bc5c05cfa27a7e8fc033da6d729ffad525ccfcdaa3fd606306683`。

Windows版本受其信任目录检查限制；普通Linux包需要本机未具备的GLIBC版本；改用官方portable包后成功。不是通过关闭校验或修改系统库绕过。

| 图查询 | 结果与意义 |
|---|---|
| 仓库索引 | 4547节点、8159边；包括文档/测试，不能当生产代码规模 |
| `backend/src`范围架构 | 47个Python文件、495节点、1130边；帮助区分局部模块与接线 |
| `commit_page_persisted`入向调用，不含测试 | 0个；包含测试后6个，说明当前调用主要在测试侧 |
| `normalize_nvd_record`入向调用 | 仅1个测试调用 |
| `ClaimsLedger.publish_claims`调用链 | 测试调用与内存操作，未发现数据库事务执行链 |
| `create_application`出向调用 | 存在条件式认证注册；结合运行探针确认默认实例未注入认证服务 |

图未发现调用本身不是“绝对不存在运行路径”的证明，因此同时检查了源码、文本搜索和运行结果。原始JSON与schema输出位于[本轮证据目录](../runs/plan_audit_20261014/)。

## 3. 关键差距与证据

| 编号 | 当前证据 | 影响 | 建议 |
|---|---|---|---|
| A01 | [默认应用](../../backend/src/ai_intel/api/app.py)的`app=create_application()`不传认证服务；本轮OpenAPI只有`/health/live`、`/health/ready`；`/auth/me`404、ready503 | 生产入口没有登录/业务装配，不能从现有API开始使用产品 | R01接真实依赖、注册服务路由；保留如实not-ready行为直到装配完成 |
| A02 | [PDF解析](../../backend/src/ai_intel/ingestion/parsing/parsers.py)第98行函数只提取`TEXTLAYER:`前缀；真实四页赛题PDF被判为扫描页/不可解析，独立pypdf可提取文本 | T09所谓PDF能力不是正常PDF文本层解析，影响论文、标准、政策和证据 | R04引入真实解析并保留页码/片段；真实文本PDF与扫描PDF分开验证 |
| A03 | [NVD解析](../../backend/src/ai_intel/ingestion/sources/nvd.py)第32行要求`vulnerability`包装；实际API的`vulnerabilities[i]`直接含`cve`。第58行取`entry.baseScore`，真实分值在`entry.cvssData.baseScore` | 真响应报错；人为加包装后仍丢CVSS。现有合成测试未覆盖官方形状 | R04用留档真实响应补合同样本；分页、状态、指标版本一并校准 |
| A04 | [模型模块](../../backend/src/ai_intel/infrastructure/models/clients.py)只有校验、能力描述与`FixtureProvider`，未提供真实generate/embed/rerank接口 | T18并非“实现完成只差live”，真实语义检索、富化与问答尚不能执行 | R05实现真实提供者接口和网关，测试替身仅留测试 |
| A05 | [ClaimsLedger](../../backend/src/ai_intel/knowledge/claims.py)为内存字典/列表；publish返回`transactional:true`，新实例无任何记录 | T21不能满足PG事实权威、事务发布、重启恢复或多worker一致性 | R02迁移到真实事务；断言和关系版本化、supersede不覆盖历史 |
| A06 | [StreamState](../../backend/src/ai_intel/ingestion/scheduler.py)是内存dataclass；提交函数只调用传入callback、修改内存游标，无真实scheduler/worker装配。复现：页内唯一条目持久化失败、成功数0，live_cursor仍变为下一页 | T16不等于持续监测；游标已前进但失败隔离清单只在内存，重启后的补采无可靠保证 | R03/R06真实PG游标与任务消费；失败可恢复，先提交后推进 |
| A07 | [认证服务](../../backend/src/ai_intel/api/authentication.py)第194–196行会话、登录尝试、审计驻内存；有PG用户目录但不等于全认证持久化 | 多进程状态不共享，重启丢会话/审计；权限模块存在不代表产品已接通 | R02跨进程后端和审计；R01装配 |
| A08 | [前端](../../frontend/src/App.tsx)只有标题与“后端API未连接”状态，前端src合计3文件 | 来源、详情、图、问答、资产、任务、推荐等均未有可用页面 | R04开始逐链路做页面，R17验收完整工作台 |
| A09 | [Compose](../../infra/compose/compose.yaml)只有PG/Redis/OpenSearch基础服务；CI的pytest只跑unit；[dev.py](../../scripts/dev.py)只实现unit/integration/security scope | 文件和测试命令存在不等于全流程工程化；contract大量存在却未进入统一命令 | R01补入口/部署/检查，R20做CI/CD和恢复 |
| A10 | [维度定义](../../backend/src/ai_intel/enrichment/dimensions.py)当前是六个内部字段，未形成附件九维；未有完整版本/资产/检索/Agent/推荐/增量重判链 | 新旧两份规划的大量核心效果尚缺，无法靠页面包装实现 | R07–R18按可观察场景交付 |
| A11 | [任务worker](../../backend/src/ai_intel/workers/jobs.py)可立即领取`retry_wait`，无next_retry_at；complete按owner检查，未同时检查租约是否过期 | 已有SQL基础仍需并发/租约/退避复核，不能原样当可靠自动运维 | R03加入真实时间/竞争测试；本轮未运行数据库复现，列为代码审查风险 |
| A12 | 状态索引仍显示T00–T23 accepted；T18有重复`note`键，常规JSON解析会只保留后一项；交接/README/状态摘要口径不一致 | 后续Agent可能误信前置已实现，历史审查注记可能被覆盖 | R00加重复键检测和证据化状态纠偏，保留旧历史 |

NVD本轮只读请求为[官方API中的CVE-2024-34359](https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-34359)，HTTP200，返回样本CVSS为9.6；原响应hash记录在行为探针中。该事实用于验证解析结构，不用于判断某个实际资产受影响。API结构依据[NVD官方文档](https://nvd.nist.gov/developers/vulnerabilities)。

上述A02/A03/A04/A05是实现缺口，不应全部归因于外部环境。A11尚缺真库运行复现，必须与已实证失败区分。各来源的归一化纯函数中有可复用逻辑，不应把整个仓库判为无价值后推倒重写。

## 4. 新规划的价值与必须修正之处

| 规划部分 | 价值 | 必须修正 |
|---|---|---|
| 无CVE公告与AI垂直数据 | 比只做CVE查询更贴题 | 稳定内部ID，新增CVE后不能换主键或丢历史 |
| 九维富化与图谱 | 展示内容丰富，可支撑跨文档分析 | 九维是适用性矩阵，不要求每条事件九格全绿；关系要有可验证证据 |
| 来源等级裁决 | 可帮助排序候选 | 等级/模型置信度/更新时间不能自动覆盖事实冲突；范围不能一律并集 |
| GraphRAG、Critic | 目标方向合理 | 必须有真实向量/重排/图路径；引用存在不等于支持，抽检不替代关键事实发布校验 |
| MCP/CLI/插件 | 可验证实用性和扩展性 | 修正async schema、200项限制矛盾、`clean`语义；子进程不等于沙箱 |
| 演示脚本 | 分镜、备用录像与界面场景具体 | 模拟注入不能证明公网源实时性；无CVE模拟事件不能有伪造真实EPSS/KEV |
| 时效统计 | 已考虑时间戳和P95 | 同时报漏采、无时间、max和超6h；日更采集不能天然保证≤6h |
| 初赛自评表 | 方便演示围绕评分 | 补决赛权重、富化召回、个性化推荐、完整问答时间、匿名材料 |
| 新技术栈 | 能实现完整预期 | 与原冻结栈冲突，先变更；PG仍是唯一权威，图与索引都是投影 |
| 200关系/100题 | 可作为起步覆盖 | 不缩减原评测范围，不以模型自评代替双人核验和holdout |

附件的三天以上工作量、网络可达与客户端接入描述不能直接作为当前能力证明。预算充足可减少资源约束，但不能消除来源权限、真实标注、软件集成和连续运行所需时间。

## 5. 本轮真实执行结果

以下为本轮重新运行，不引用历史通过数量充当本轮结果。完整argv、工作目录、UTC开始时间、耗时、退出码在[commands.json](../runs/plan_audit_20261014/commands.json)。

| 工作目录 | 实际命令 | 退出码 / 结果 |
|---|---|---|
| `backend` | `uv run --locked --offline pytest tests/unit tests/contract tests/security tests/integration/test_t16_incremental_monitoring.py tests/integration/test_t21_claims_entities_conflicts.py --ignore=tests/contract/test_t07_jobs_outbox.py -q -ra` | 0；153 passed，1 warning；本次选择范围覆盖率87.84% |
| `backend` | `uv run --locked --offline ruff check .` | 0，静态检查通过 |
| `backend` | `uv run --locked --offline ruff format --check .` | 0，79文件无需格式修改 |
| `backend` | `uv run --locked --offline mypy src` | 0，47源文件无类型错误 |
| 仓库根目录 | `python scripts/verify_plan.py` | 0，PLAN_OK；这是原计划一致性检查，不是产品验收 |
| `frontend` | `cmd /c "npm run lint && npm run typecheck && npm run test && npm run build"` | 0；lint/typecheck/build通过，Vitest 1项通过 |
| `backend` | `uv run --locked --offline python ../reports/runs/plan_audit_20261014/reproduce_probes.py` | 0；默认路由、PDF、NVD、账本、模型和失败游标6组观察；探针成功执行不等于被测能力通过 |
| WSL | CBM `index_repository/get_architecture/trace_path` | 成功；调用图结果已保存 |
| 仓库根目录 | bundled Python执行`reports/runs/plan_audit_20261014/verify_artifacts.py` | 0；三份文档链接、60任务映射、25卡、14场景和13要求齐全；详细路径与输出见证据目录 |

后端此次153项中失败0、跳过0；不包含的真库测试属于未运行，不记作skip或pass。文档检查另行统计，不混入业务测试数量。独立pypdf提取官方PDF共4页3970字符，证明不能以原解析器的“scanned page”备注推断该文件没有文本层。

后端warning为Starlette TestClient/httpx弃用提示，非业务测试失败。本轮没有运行有破坏性数据库操作的旧集成测试：当前Docker引擎不可连接，且部分旧测试使用固定默认数据库地址并执行迁移、降级或容器重启。不能为了本次审计贸然操作用户数据库。

当前结论：unit/contract的本次选择范围passed；真实数据库integration本轮not_run（环境前置blocked）；live模型/测绘not_run；live来源仅一次公开NVD读取；完整浏览器业务e2e、正式准确率/召回率/性能、持续运行、人工金标和独立复现均not_run。前端build和1项骨架测试通过不代表产品可用。

153项测试通过与真实PDF/NVD探针失败并不矛盾：测试输入和验收边界没有覆盖真实产品合同。后续要补真实留档响应、跨进程持久化、真实服务调用与浏览器闭环，而不是追求更多同类合成测试数量。

## 6. 本轮产物、偏差与后续

新增文件：

- [完整恢复计划](../../docs/plan/11_full_delivery_recovery_20261014.md)：13项要求、14个最终场景、架构决策、来源/富化/问答/生态、72h窗口、评测与9项变更。
- [恢复任务卡](../../docs/plan/12_recovery_task_cards_20261014.md)：R00–R24，每卡输入输出、文件边界、前置、六类验收和证据，覆盖原T00–T59。
- 本报告与[原始证据](../runs/plan_audit_20261014/)：测试日志、探针、来源样本、CBM调用图和校验摘要。

本轮不直接更新已有accepted状态，避免把规划核查当作已完成独立重审；R00负责保留历史并落实更正。没有新增应用单元测试或修改业务实现，审计探针属于证据复现工具。方案提出架构/合同/执行顺序变化，但尚未使冻结合同生效。

评分项证据性质：本轮补的是F1/F2/F3/P1/P2/P3/A1/E1等的缺口定位与D1计划材料；**没有取得新的正式评分成绩**。D2、X1、R2也不能因写完方案被勾选通过。

建议下一任务：R00。落地可审查的合同与状态纠偏后，进入R01–R05真实运行闭环。若用户批准有界实施批次，按主计划阶段推进；达到时间盒只触发检查，不触发“完成”。
