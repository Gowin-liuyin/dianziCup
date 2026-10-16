# G-C · R07 core 独立审查 1

状态：`needs_changes`。结论仅适用于内部九维候选接口和 typed Claim v3 账本基础片，不能签整 R07、原 T 卡或 G-C。

独立 reviewer：`/root/r07_core_independent_review`。审查日期：2026-10-15，时区 Asia/Shanghai；秒级执行起止见各命令 receipt。固定工作树：`D:/wt/r07-core-review-1`，分支 `codex/r07-core-review-1`。run_id：`recovery_r07_core_review_1_20261015`。

## 本切片做了什么

本切片建立九种受限富化值、固定修订/块/引用候选和逐维尝试状态，并允许显式 `schema_version=3` 的已登记谓词进入现有 PostgreSQL 知识账本。旧 v1 文本、v2 结构值、默认版本 2 和 HTTP schema2 保留；v3 大结构只截断旧展示字段，完整 JSONB 可重读。本切片没有生产自动富化作业，不据此判断九维实际在线能力通过。

基线 `1a52e17ffe327fb8a0c1d4f97372948a699910e3`；接口冻结 `098502991f617a5fa9fdfb9c3da91e54aee7ff06`；产品冻结 `74d8e9ba8b49360ca90ade390f7b6c00cd40b815`；实际评审 HEAD `bf660e8a20f606225b1dd881faaeaf9bfc3550b3`。独立执行 `git diff --name-only 74d8e9b bf660e8 -- backend/src backend/tests contracts` 没有输出，确认这两个冻结的被审代码/测试/合同相同。

指定工作树在首次访问时尚不存在，工具返回目录无效 `os error 267`。reviewer 只读主仓库真实 AGENTS 和指定技能，然后从 `bf660e8` 创建新分支与工作树；没有使用作者活动工作树或其虚拟环境作为通过证据。新工作树初始工作区干净。

## 依据与范围

已恢复真实 `AGENTS.md`、计划 00/03/04/05/06/11/12、T13/T19/T20/T22/T23/T41、`CR-R07.md`、`CR-R07_enrichment_candidate_seam.md`、`CR-R07_typed_signal_claim_v3.md`，并读取冻结 `progress/task_state.json` 与最近交接。状态/作者报告仅为索引；下述测试、兼容比较、图谱和负例由 reviewer 独立执行。

采用指定技能 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`：检查具体输入、真实调用者与最小修复；中文交付遵从本次任务。期望负载按共享 PG、多租户和多个 worker 理解，候选本身尚无生产调用。

基线至 HEAD 的被审产品文件：

- `backend/src/ai_intel/domain/enrichment_values.py`
- `backend/src/ai_intel/enrichment/contracts.py`
- `backend/src/ai_intel/domain/records.py`
- `backend/src/ai_intel/knowledge/persistence.py`
- `backend/src/ai_intel/enrichment/persistence.py`
- `backend/src/ai_intel/api/knowledge_contracts.py`
- 三个 R07 新测试文件及 `contracts/schemas/schema_bundle.json`

没有依赖主版本、锁文件、迁移、认证或评分阈值变更。reviewer 只新增本报告和 run 目录，没有修改产品、测试、合同、任务状态或交接，没有提交、push 或登记 accepted。CBM 自生成的 `backend/src/.codebase-memory` 在完成检查后原样移动到 run 的 `cbm_graph_artifact/`；源树最终没有该工具生成修改。

## 必须修复

### 1. [P2] v3 版本区间的导出 schema 缺少已实现的边界约束

位置：`backend/src/ai_intel/domain/enrichment_values.py:71–83`、`backend/src/ai_intel/domain/records.py:78–131`、`contracts/schemas/schema_bundle.json:896`。

这是来源版本区间的结构合同：`fixed` 是排除上界，`last_affected` 是包含上界，运行模型禁止同一区间同时存在，并要求至少一个来源边界。

实际输入使用 `schema_version=3`、`predicate=version_assertion`、kind 同名、package_key=`synthetic-package`、ecosystem=`pypi`、scheme=`pep440`、raw_expression=`<1.2`。两组 intervals 为 `[{"introduced":"1.0","fixed":"1.2","last_affected":"1.1"}]` 和 `[{"branch":"main"}]`。完整记录有合法 UUID、带时区 asserted_at、public scope 和 unverified/model_hypothesis 状态，原字节见 `independent_values.json` 的 `both_upper_boundaries`、`empty_boundary`。

`Draft202012Validator(ClaimRecord.model_json_schema(), format_checker=FormatChecker())` 两组均返回有效；`ClaimRecord.model_validate_json` 两组均返回 ValidationError，分别为上界互斥和缺来源边界。原因是 Pydantic after validator 没有出现在导出的 `VersionInterval` schema，顶层谓词/kind 校验不能弥补该缺口。

实际影响：只按导出合同预检或生成 v3 输入的消费者可得到“合法”结构，账本运行边界却拒绝它。它不会凭此绕过运行模型直接入库，但违反本切片明确承诺的可表达结构合同一致性，后续接线会产生可重复失败。

最小修复：在 `VersionInterval` 的 JSON Schema 增加非空 `fixed`/`last_affected` 互斥以及 introduced/fixed/last_affected 至少一个非空来源边界的约束，再重导出 bundle。应区别字段缺省和显式 null，保留现有运行行为；无需新依赖或改旧合同。

复验：在合同测试同时检查运行模型与导出 schema 拒绝上述两组、`{}`、全 null 和含 branch 的空边界；检查合法 introduced-only/fixed-only/last_affected-only 及可选 null 分支。重跑旧值合同和九类 roundtrip。

### 2. [P2] v3 文献目标的 UUID 配对规则未进入导出 schema

位置：`backend/src/ai_intel/domain/enrichment_values.py:100–115`、`contracts/schemas/schema_bundle.json:643`。

该值可绑定内部目标文档及指定修订，运行模型要求两个目标身份一同给出或一同为空。

实际输入为完整合法 v3 `literature_reference`，uri=`https://example.invalid/independent-paper`、title=`Independent synthetic paper`、reference_kind=`paper`、relation=`background`、support_summary=`Topic context only`，仅给 `target_document_id=12345678-1234-5678-1234-567812345678`。完整输入见 `independent_values.json` 的 `unpaired_literature_target`。

导出 schema/FormatChecker 接受；运行模型拒绝并报告 `target document and revision identity must be paired`。当前 schema 分别将两个字段声明可选 UUID/null，没有配对组合条件。

实际影响：导出合同可接受没有固定修订的目标身份，消费者预检/生成成功而运行边界失败。本项只证明结构不一致，不将 UUID 存在性或语义支持错误归因于 JSON Schema。

最小修复：增加两个身份同时缺省/null或同时非空 UUID 的组合 schema。重导出 bundle，同时保留现有 after validator。

复验：检查仅 document、仅 revision、一个 UUID/一个 null、双方缺省、双方 null、双方合法 UUID；各组在运行模型和 schema 结果一致。目标真实关系与权限由下一项的发布边界处理。

### 3. [P2] 公共 v3 文献可携带私有目标引用，发布未检查目标身份的权限与范围

位置：新增字段 `backend/src/ai_intel/domain/enrichment_values.py:107–108`；接收它的 `backend/src/ai_intel/knowledge/persistence.py:331–402` 与 JSONB 保存 `:501–510`；重读 `:826–849`。

现有发布服务核对断言来源和证据的可见性，但没有查询新 `LiteratureReferenceValue.target_document_id/target_revision_id` 指向的目标。类型配对成立不等于目标存在、真实配对或可见。

独立真实 PG 输入：先在同一随机 UUID schema 中建立 scope=`tenant:independent-private-tenant` 的文档、修订与证据；再用公共来源/公共证据建立 public v3 `literature_reference`，将它的两个目标 UUID 指向前述私有文档与修订。状态保持 `unverified/model_hypothesis`，没有伪造 supported，其他字段合法。

23:52:14+08:00 实际发布成功。`other-tenant` 的 viewer 能通过 `KnowledgeRepository.get_claim` 读公共记录中的两个私有 UUID；直接 `get_evidence` 读取该目标证据却得到 `CrossTenantAccessError`。证据 `independent_target_scope.json` 包含完整合成输入、真实 UUID、可见范围和观察结果。UUID 为隔离 fixture，不含真实用户数据。

实际影响限定为私有内部身份引用可进入公共事实并被其他租户读出，违反 AGENTS/03 的“私有引用不得进入公共衍生对象”和“派生范围不得宽于任一输入”。本复现没有证明私有正文或目标标题被服务自动读取/泄露，也没有使用不可见对象内容作语义支持。HTTP schema2 目前只投影摘要，但 PG 账本的公共完整重读已经存在，不能因未接生产作业忽略其写入边界。

最小修复：在现有发布事务中仅对带内部目标身份的文献值查询目标修订与文档，核对真实配对、认证 AccessScope 可见性和派生 visibility/tenant 不宽于目标；不可见/不存在按既有隐藏资源规则拒绝。保留合法公共目标、同租户目标和无内部目标的外部文献引用。无需另建通用引用服务或新迁移。

复验：公共→公共、同租户→同租户、公共→私有、租户A→租户B、目标不存在、两个 UUID 不属于同一文档等用例；拒绝后 claims/assertions/evidence_links/receipts/change/job/outbox/epoch 不变化。上述 UUID scope 负例必须由允许成功改为实际拒绝，不能只删掉响应中的字段。

## 已实测的通过项

| 检查 | 实际命令/工作目录 | 起止（+08:00） | 结果与证据 |
|---|---|---|---|
| 独立环境 | `uv sync --frozen --offline --extra semantic`，`D:/wt/r07-core-review-1/backend` | 初始 bootstrap 未捕获墙钟起止；工具 wall time 8.0172785s | exit 0，新建本 WT `.venv`，安装 92 包；`environment_sync.log/json`。没有复用作者环境 |
| 定向 unit/contract | `.venv/Scripts/python.exe -m pytest -o addopts= tests/contract/test_r07_signal_claim_values.py tests/contract/test_r02_value_contract.py tests/unit/test_r07_enrichment_contracts.py tests/unit/test_r02_knowledge_publication_contract.py -q --junitxml=…/targeted.xml`，backend | 23:46:26–23:46:30 | exit 0，77 passed，0 failed/error/skip；`targeted.log/json/xml` |
| 真实 PG 回归 | `.venv/Scripts/python.exe -m pytest -o addopts= tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r06_catalog_documents_pg.py -q --junitxml=…/pg.xml`，backend | 23:46:40–23:47:08 | exit 0，34 passed（R07 13、旧 catalog 21），0 failed/error/skip；`pg.log/json/xml` |
| Ruff | `.venv/Scripts/ruff.exe check` 六个变更源文件及三个 R07 测试，backend；完整参数见 receipt | 23:46:40–23:46:40 | exit 0；`ruff.log/json` |
| 格式 | `.venv/Scripts/ruff.exe format --check` 同九文件，backend | 23:46:40–23:46:40 | exit 0，9 files；`format.log/json` |
| 类型 | `.venv/Scripts/mypy.exe src`，backend | 23:46:40–23:46:51 | exit 0，95 source files；`mypy.log/json` |
| 结构/兼容探针 | `.venv/Scripts/python.exe …/probe_values.py`，backend；包装调用 `run_review.py values` | 23:50:28–23:50:30 | exit 0，16 个输入的实测观察；三个新结构差异是本报告阻断，不把脚本 exit 0 当合同通过 |
| 发布负例 | `.venv/Scripts/python.exe …/probe_publication.py`，backend | 23:50:51–23:50:56 | exit 0，4 个真实 PG 拒绝/副作用观察；`publication_probe.log/json`、`independent_publication.json` |
| 私有目标引用 | `.venv/Scripts/python.exe …/probe_target_scope.py`，backend | 23:52:13–23:52:15，业务观察 23:52:14 | exit 0，确认缺陷3；`target_scope_probe.log/json`、`independent_target_scope.json` |
| 继承版本行为 | `.venv/Scripts/python.exe …/probe_inherited_version.py`，backend | 23:53:06–23:53:07，观察 23:53:07 | baseline/candidate 六个观察；`inherited_version_probe.log/json`、`inherited_version.json` |

`-o addopts=` 是定向回归的显式配置，未计全套覆盖率或全套 pure 通过。其真实 pytest/JUnit 结果为上述数量；没有修改、skip 或降低 native CPU guard 门槛。

PG 使用已授权 `DIANZI_TEST_RUN_ID=r06_catalog_worker_20261015` 与 `test_dianzi_r06_catalog_worker_20261015`。私有 connection.json 只通过指定 WSL cat 捕获在 Python 内存，再替换 database；不输出 DSN，不读 DPAPI。每例随机 UUID schema，连接 options 为 statement_timeout=15000/lock_timeout=5000，finally 仅 DropSchema 自己创建的 schema。没有运行原 R02 硬编码库整套测试，没有访问生产库。

通过证据的实际含义：

- 九类 typed value 可 roundtrip；v1/v2/default2 不接受新结构；错 kind、未知版本、未登记谓词、额外字段、bool 概率、缺 kind 在独立探针中运行模型/schema均拒绝。默认旧文本仍为 2，显式旧文本仍为 1。
- 两个旧 DTO 独立从 `git show 1a52e17…` 载入源代码，分别重生成 schema，并与候选逐对象及规范字节比较。`EnrichmentProjection` 完全相同，SHA256 `9e068ccf345f1b544dc94bfa573e08ebfecddc076424e2cca7c2167ddfbdca7d`；`DimensionSubmission` 完全相同，SHA256 `bf929e1fc1fd671c4db09acff9c7b2dc266f42c7a7979b5732653729739fd99b`。before/after 原字节已独立存档，不采信作者给出的 hash 作为比较依据。
- frozen schema_bundle 与本 WT 的 `render_schema_bundle()` 字节相同；这证明导出无漂移，不证明导出语义正确，缺陷1/2正发生在此一致导出的合同中。
- R07 PG 13例覆盖新 session 完整重读/相同输入重放、九类 model_hypothesis 均保持 unverified/unknown、CVSS 机构冲突拒绝、viewer 写入拒绝、其他租户读取私有 claim/evidence 拒绝、过4000 Unicode展示明确截断且完整JSONB重读不变。原 catalog 回归覆盖文档历史、并发重放与事务失败等，不替代 v3 的所有并发历史场景。
- 独立4例确认：supported model_hypothesis 被拒绝；无 validated 语义支持的 structured_source 被拒绝；绕构造检查的错谓词在 publish 重新 model_validate 时被拒绝；同幂等键不同概率被拒绝。前后八张业务表计数完全一致。新结构/hash本身没有使这些发布限制失效；缺陷3是另一条新增目标身份的范围缺口。
- `_claim_display_value` 只对 v3 做超过4000字符截断；原 v1/v2实现路径不改。完整结构保存于 object_json、value_kind和schema_version，并由 `_claim_from_row` 重读；显示摘要不能解析回事实。
- 回滚说明准确区分未写 v3前可代码回退与写入后须保留 v3读取兼容层，不以删事实/覆历史回退。

## CBM 与源码交叉验证

官方二进制为 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，实际 help 显示 0.11.0。reviewer 使用独立缓存 `/tmp/dianzi-r07-core-review-1-cache` 和项目 `r07-core-review-1-20261015`。索引唯一输入为本 WT `backend/src`，排除 reports、holdout、仓外私有配置/秘密与作者 WT。

23:46:40–23:46:46 独立 full index：95 Python files、1289 nodes、6469 edges、not_indexed/skipped/parse_partial/parse_unusable 均 0。独立 schema 和 architecture 成功。初次 trace 未含项目前缀，两个调用实际 exit 1/function not found，原 receipt/log 保留；随后 search_graph 查实 qualified_name，再独立 trace publish、ClaimRecord validator、_save_claim，均 exit 0，见 `cbm_*_search` 和 `cbm_*_exact`。

图中调用线索再用 `rg` 与源码核对：既有 source_documents `_persist_member→KnowledgeRepository.publish→_validate_submission/_save_claim→_claim_display_value`；`_claim_from_row` 用于 get_claim/list_current_claims；API read_event 从 object_value投影到ClaimSummary。新候选接口仅有定义/自校验，没有生产调用。Pydantic validator 图中无调用者不代表运行不执行，已用真正输入验证。图边和 confidence 没有被当作正确性证明。

## 已分清的限制、缺测与原行为

`schema_version="3"` 运行模型接受/schema拒绝；额外 baseline 对照证明 `"1"`、`"2"`、bool True 的同类 int coercion 已在基线存在，候选也相同。本报告不把继承 coercion 混作新增缺陷或要求静默破坏 v1/v2兼容。记录它以限定“结构合同一致”范围。

日期format由 FormatChecker核对，类型/数值边界由schema检查；quote/content hash、quote实际属于哪一块、目标资源存在/ACL、引文语义支持和来源真实性不是仅凭标准JSON Schema或图边可证明的。本报告仅将可直接表达而漏导出的两个新组合约束判为schema阻断。新候选本身未检查真实块身份/active revision/语义/权限是冻结接口明确留给后续验证发布服务的职责，不据“未接线”判整R07本片缺产品。

本次没有独立跑全套 pure、前端/e2e、真实模型、外部来源或公网测绘，均为 `not_run`。主控告知原 native CPU guard在别的全pure运行出现1.03125s>原1s红，归主控另诊断；本reviewer没有复现或修改它，不宣称整pure绿。没有批量付费任务、外网/model调用、主动扫描或PoC运行。

明确仍未覆盖：生产九维worker/API/UI接线、真实块转永久fulltext坐标、真实字段及语义校验、自动更新/冲突重判、v3特有的并发首次发布和双时间修订链、实际模型与各维live。相关原T19/T20/T22/T23/T41与R07最终要求保持；fixture/PG通过不证明F2/P2阈值、真实覆盖或性能。

本报告未提出无具体输入的风格/架构猜测，也无需要删除的已确认代码债务。

工具诊断失败另行保留，不计业务测试失败：初次 `probe_values.py` 引用了不存在的 `EnrichmentDimensionSummary`，exit 1/ImportError，reviewer改用真实类 `EnrichmentProjection` 后观察成功；该首次尝试尚未生成values JSON且未捕获墙钟起止。`probe_publication.py` 首次执行在23:50:28–23:50:29因报告脚本未加入backend到sys.path而exit 1/ModuleNotFoundError，原 `publication_probe_initial_import_failure.log/json`保留；仅修报告脚本导入路径，未改产品/测试，23:50:51开始复跑实际4例成功。两个CBM初始function not found也保留。没有把这些环境/工具错误冒充业务红或skip。

## 交付与下一步

报告和所有本次独立日志/receipt/探针/原字节/CBM图制品的SHA256见同run的 `artifact_manifest.json`；该manifest的SHA256及报告SHA256由 `seal.json` 单独记录，manifest不自包含。封存后不覆盖现有values/probes/log；修复与复验应使用新的冻结SHA与新的run记录。

下一步为作者在独立修复批次解决1/2的导出组合约束以及3的目标引用权限/配对发布校验，增加真实合同/UUID隔离PG回归，然后对新固定版本进行定向独立复核。原77/34绿不能替代三个新负例的拒绝结果。

Verdict: needs_changes（先修复1、2、3）。不登记accepted，不签整R07或G-C。
