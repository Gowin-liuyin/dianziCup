# G-C · Root 批次16默认入口独立审查 1

文档首次创建、本次写作开始：2026-10-17T09:32:19+08:00。此版本为独立离线/部署审查及真实资源包准备结果；真实 PG 与修复后定向复验尚待后续追加。当前状态：`needs_changes`，不签整 R01/R17/R18 或 G-C，不修改 progress/accepted。

What this change does: 默认 App 构造一份 GroundedQuestionService，旧 questions 与新 `/api/v1/ask` 共享该实例。公开 Ask 复用冻结输入、当前 cookie/Bearer 身份与 PG 预约，严格 JSON、组件上下文、MCP 凭据渠道和问答私密状态清理也在本批整合。

## 冻结、范围与独立性

- 固定候选：`9d8b222cd6cfcc87e618867c918a1b8fcdafa32f`，tree `e29b420c4f07fff362c07797e1f67db035b8a907`。
- 比较基线：`0f8c1f6d047387cfca8a62f8dbc352b8c6415b96`。
- 独立 clean detached 工作树：`D:/dz16r1`。本 reviewer 没有参与被审实现；只新增自己的 reports/reviews、reports/runs 与其中负例/运行控制，没有改生产代码、原测试、公共合同、状态、迁移、锁、阈值、Gold 或用户资产，没有 commit/push。
- Root 原工作树 `D:/dianzi` 的 tsbuildinfo、push 台账、Root-batch13-index 及所有原 dirty 文件未改动。独立 strict TS 使用 `--incremental false`；Root tsbuildinfo 实际 SHA256 仍 `3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d`。
- 读取 AGENTS、执行索引、R01/R05/R17/R18 卡、数据/API/公开 Ask/API key/共享提交合同、三个本批 CR、进度与 Root-batch16 报告；使用 Ponytail review 5.3.1。六份源报告只作为切片依据读取，不代签当前 Root 组合。

实际变更产品路径是 6 个 backend 源文件、1 个 SDK 源文件、2 个 frontend 源文件、2 个 frontend e2e 仪器文件；其中 App/provider/OpenAPI 是本次新增默认装配。23 个冻结代码/直属测试文件逐项对照固定 Git blob，规范化换行后全部相等；独立 clean checkout 的 raw 与 Root freeze 的 raw 只有 1/23 相等，原行尾差异分别记录，未声称 raw 完全一致。完整映射见 ownrun `independent_freeze_and_counts.json`。

沿源码/rg 核对所有 `build_question_service`、两 router 和共享 service 调用者；核对默认 App→PG认证→retriever/models→共享问答预约与最终身份/证据围栏。新可选 keyword provider 不破坏原三参数调用；两个 router 只在无 provider 时自行构造服务，Root 传同一对象，原兼容测试真实复跑。索引没有替代 closure 内实际身份、事务或模型调用证据。另以同一site/worker/PYTHONPATH有界执行 `runtime_import_provenance`（exit0）：App、两router、write/selector/json/sharedservice/database及SDK HTTP共9模块的实际 `__file__` 和raw哈希全来自独立固定工作树，不是Root moving editable目录；该检查没有连接真实资源，断言不加到pytest计数。

## Must fix

1. **默认容器及安装包在导入 App 时找不到 AskRequest schema**（`backend/src/ai_intel/api/public_ask_routes.py:115–118`，`backend/src/ai_intel/api/app.py:144`；`infra/docker/backend.Dockerfile:10–13`）。

   - 职责：router 构造时给公开 Ask 的 OpenAPI requestBody 注入冻结 AskRequest。
   - 问题：它按源码仓库布局读取 `Path(__file__).parents[4]/contracts/...`。当前 Dockerfile 只复制 `backend/src` 和 `backend/migrations`，ignore 也排除 contracts；已构建 wheel 同样没有仓库根 contracts。因此任何默认 App 导入立即抛 FileNotFoundError，认证和健康路由都不可启动，与是否配置 PG/模型无关。
   - 实际触发：独立 `test_review_deployment.py` 按现 Docker COPY 布局建 fresh 源目录，在 fresh 子进程导入默认 App，真实 `1 failed / exit1`。另执行 `uv build --offline --wheel` 成功，201 个 wheel members，解包到独立 site 后 fresh 子进程 import 仍 `exit1`，同一缺失路径；没有复制外置合同来洗掉失败。
   - 最小修复：将冻结 AskRequest 作为包内资源，使用标准库 importlib.resources 读取，并用合同测试逐值比对既有 schema；验证 Docker source 布局和实际 wheel import。Root 已确认此问题并负责修复，本 reviewer 未改业务。
   - 不修后果：源码工作树 77 项绿不能转化为默认部署可启动。本固定候选不能 Ship。

2. **新 Ask 拒绝自报身份字段时漏记既有脱敏审计**（`backend/src/ai_intel/api/public_ask_routes.py:225–231`；对照 `backend/src/ai_intel/api/app.py:99–116`）。

   - 职责：`docs/plan/05_api_and_tool_contracts.md:15` 要求请求体同名租户、角色和权限字段拒绝或忽略并记录，身份仍只由认证上下文产生。现有 App 验证错误处理只记录四个固定字段名，不记录值。
   - 问题：新路由手工解析 JSON，直接捕获 ValueError 返回422，不进入 App 的 RequestValidationError 审计处理。请求带 `tenant_id/user_id/role/permissions` 时虽被拒绝，identity_spoof_attempt事件缺失，成为新默认入口的审计盲区。
   - 实际触发：独立 `test_review_identity_audit.py` 使用同一默认App工厂、既有真实InMemory认证审计作为显式fixture，不patch路由/业务/审计。旧 `/v1/questions` 返回422且写一条只含固定字段名的审计，通过；新 `/api/v1/ask`同422但审计为空，失败。实际 `1 passed /1 failed /exit1`，2.05s、Windows峰4/own残留0；输入值与错误均无泄漏。真实PG审计落库尚未执行，不能把内存port回归当PG证明。
   - 最小修复：在新手工输入拒绝边界复用既有审计port；仅记录固定字段名、禁止原值，保留SQL失败503分类，并以本同输入与实际PG审计复验。不修改公开schema、身份来源或阈值。
   - 不修后果：公开默认入口违反冻结API审计规则，旧入口的安全监测不能覆盖此新路径。

除上述两项，本范围没有另外已证实的 Must/Should/Lean finding；未实现的 stack/tasks/插件装配和完整 live 能力保持任务披露，未作为本切片已实现功能验收。Must2于09:41追加；此前09:32仅Must1的证据截止不冒称当时已发现第二项。

## 真实离线执行与失败保留

ownrun：`D:/dz16r1/reports/runs/root_batch16_review1_20261017/`。每条完整 argv/cwd/起止/exit、NativeJob 查询、Windows 完整链、stdout/stderr 与 XML 在对应 `<label>.command.json`、`.native_job.json`、日志中。下列简写省略固定 base Python/worker_entry 前缀，实际完整命令由收据提供。

| label / 实际命令核心 | exit | 实际结果 |
|---|---:|---|
| offline_default_retry：`pytest tests/unit/test_public_ask_routes.py tests/contract/test_public_ask_route_contracts.py tests/unit/test_r18_public_ask_default_app.py tests/unit/test_r05_question_routes.py tests/unit/test_r18_expired_answer_problem.py tests/unit/test_r18_public_bearer_cors.py --no-cov -q` | 0 | 77 passed，15.05s |
| boundary_regression：selector unit/contract/合法输入合同、shared JSON unit/contract、public write unit/contract 共7文件，`pytest --no-cov -q` | 0 | 172 passed，2.17s；1条现有Pydantic警告，非 skip |
| sdk_http：`pytest D:/dz16r1/sdk/python/tests/test_http_transport.py --no-cov -q` | 0 | 66 passed，2.01s |
| r01_offline_retry：`pytest tests/unit/test_r01_migration_engine_disposal.py tests/unit/test_r01_migration_pg_helpers.py --no-cov -q` | 0 | 11 passed，0.12s |
| deployment_negative：`pytest <ownrun>/test_review_deployment.py --no-cov -q --tb=short` | 1 | 1真实业务失败，3.05s，见 Must1 |
| baseline_wheel：own `wheel_probe.py` → `uv build --offline --wheel --out-dir <ownrun>/baseline-wheel D:/dz16r1/backend` → fresh wheel import | 1 | build0 / import1；201 members，见 Must1 |
| identity_audit_negative：`pytest <ownrun>/test_review_identity_audit.py --no-cov -q --tb=short` | 1 | 1passed/1failed，2.05s，旧questions控制通过，新Ask失败，见Must2 |
| backend_types_diagnosis：`mypy` App/question/publicAsk/write/selector/json_output 六源，own cache + `--show-traceback` | 0 | 6 source files，无类型问题 |
| backend_style / backend_format：`ruff check` / `ruff format --check` 同六源 | 0 / 0 | 全通过；没有 --fix 或改源码 |
| batch16_ui_tests：实际 Node/Vitest `run --pool=threads --maxWorkers=1 --no-file-parallelism src/features/questions src/api/client.test.ts src/App.test.tsx` | 0 | XML实查72 passed；只 fixture DOM/HTTP，不是 Edge |
| batch16_ui_types_bounded_gc：Node `tsc --noEmit --incremental false` | 0 | strict TS通过；保护用户 tsbuildinfo |
| batch16_ui_lint_bounded_gc：实际 frontend ESLint `.` | 0 | 全通过 |
| batch16_ui_build_bounded_gc：Vite `build --outDir <ownrun>/frontend-dist` | 0 | 89 modules，构建965ms，真实新产物 |
| plan_validation：`python ... worker_entry.py scripts.verify_plan` | 0 | PLAN_OK，仅计划/状态结构，不是产品验收 |
| freeze_audit：own `freeze_review.py` | 0 | 固定SHA/tree、23源、326离线去重与状态传播实查 |

本批原整合 315 离线用例由新 reviewer 实际完整复跑：77+172+66，不重计 Root/源作者历史通过；另加11个 R01辅助，主回归Python离线去重326。部署负例1红、新身份审计对照1绿/1红及 wheel import红单列，不删、不改 skip。当前已执行独立pytest合计329 distinct：327passed/2failed；wheel另为build0/import1，没有凑入pytest数量。72前端组件单列，不与 Python 或旧 e2e 仪器72混加。

保留控制/环境失败：offline_default 首次 worker_entry 使用相对路径，child cwd=backend 导致文件不存在，exit2且无业务执行；改用同一绝对路径后77通过。R01首次缺 backend package 路径收集1 error/exit2，补 own runner PYTHONPATH 后11通过。PG collect 首次缺 plugin 路径，随后同名 review_checks 导入了外层普通检查器而产生控制递归；两次原红保留，统一改用独立 pg_review_environment 模块名后完整 collect21成功。首次 backend_types 冷 cache 是 mypy INTERNAL ERROR/exit2；原 argv 同 cache 添加 show-traceback 复跑exit0，未改产品/类型规则或放宽资源。未把这些环境/控制错误记业务测试失败，也未删除其记录。

普通检查在 child 前实际设置 512MiB/process、1GiB/job、24核 CPU rate833约2CPU、Native active cap10/完整 Windows cap10、每条≤60s。普通实际 Windows峰4–7，自有残留均0。wheel 和 deploy 的 fresh child 也计入完整树。未读取 DPAPI、.env、KEYS、用户资产或发付费模型/测绘请求。

## 新候选 CBM

Root 独占 ACK 后，09:29:00.362–09:29:40.167（39.805s≤45）使用 Ubuntu-22.04 默认用户，保留 `-d Ubuntu-22.04`，同 cache `/tmp/dianzi-cbm-root-batch15-review1-20261017/defaultWSL`。两个新 project 指向本固定工作树 `backend/src` 和 `frontend/src`，不是0f旧图。

backend 新 index：3013 nodes /17945 edges；frontend 新 index：1181 nodes /5235 edges。两者 not_indexed/skipped/parse_partial/parse_unusable均0。index/schema及3后端、2前端trace的9条 CLI 全 exit0/isError=false；但最后 `submitQuestion` trace实际返回 ambiguous，同名对象为真实client和investigation测试函数，不能算这条追踪通过，原 raw保留，完整函数名定向重查待新独占窗口。

已取得四条真实追踪：`create_application`、`build_public_ask_router`、`build_question_service`、`AuthenticatedQuestions`。它们和源码/rg交叉确认：App共享constructor及两问答router、retriever/generation/semantic/PG链，前端 Workbench→QuestionWorkspace→AuthenticatedQuestions→runRequest→submitQuestion/getAnswer链。provider是否只构造一次仍以实际测试/源码为准；图中兼容 fallback factory caller不会证明运行时重复构造。

Windows峰7 + guest完整至PID1峰7，保守完整双系统峰14≤16。Windows native cap8、guest cap8；process512MiB/job1GiB/rate833；guest两核affinity、RSS采样，GOMEMLIMIT只作为软限制，未宣称guest kernel硬限。每个spawn的tool session按birth匹配关闭，完整guest祖先计数包括shared PID1，未把它当cleanup root。own Windows/guest残留0。资源已归还 Root。

## R01 前置与状态传播

基线已经是 R01 needs_changes、R02–R05 accepted。候选保留 R01 needs_changes，并将当前 R02–R05保守转 awaiting_review；固定 manifest depends_on为 R02→R01、R03→R02、R04→R03、R05→R04。逐JSON核对，四任务原history完整prefix、implementation、verification和能力slices保持，没有改 checker、依赖、历史G-A/G-B冻结SHA或洗掉已证能力。实际 verify_plan exit0。

11个离线释放回归包含迁移成功/connect失败/migration失败、revision missing/head/query失败及PG辅助清理/报告异常保留。真实当前 head0030 的 Engine释放成功、实际42703原异常/事务回滚与默认App数据库健康，已经准备 own PG负例，实际执行前仍 integration not_run。即使这些后续通过，Must1部署问题仍使当前整R01不能accept，R02–R05本次回退应保持。

## Root-only 真实 PG 包与未验证项

Root-only packet：`<ownrun>/pg_support/root_launch_packet.json`；controller raw `f03e415f1a07458af84fbc842f82d7fe280483fbbaa03c7bc3829a5fdff9023f`，admission raw `5f9928f1d96f04da6dba12dff13a1f77a20b4eb4a73cb0c316442ff8f09b53a9`。沿最新typed成熟controller58s总窗/child48s/Rootouter60s、native9、物理2target+1parent sampler、SourceOID10451302/10434264只identity before-after、随机nonce/OID/owner/exact9 COMMENT验证与零连接 exactdrop；只有 Root负责秘密内存注入和逐窗启动，本 reviewer不自行连接真实PG。

6组完整 nodeids `[2,1,5,5,5,3]`：own R01 lifecycle2、own实际默认App1、原public ask18。当前collect21 exit0，不记passed。测试库由controller新建，migration child只在own schema0013装冻结fixture seed→当前0030；不导入0031，不downgrade实际库。新增own DB默认search_path指向own nonce schema是为了测试实际默认build_engine；没有patchApp engine/auth/sharedservice，只替换标记明确的semantic/model IO边界。own App预期真实 health整体503、database ready/cache not_configured，不能把缺Redis/search/worker/scheduler报成allready或live。

Must2另准备独立单窗 `<ownrun>/pg_audit_support/root_launch_packet.json`，没有修改原六窗包任何字节。controller raw `7f94eb7093c73f3abbf10571cb15a95535f854f8085e02c325fee350b3340fa5`；admission raw `dddad2ee67d476f38790f007ae011c081496589d93a0cc49ea34c2bec0b4ee3a`；tag `root-batch16-audit-review1` / label `pg_identity_audit_negative`。同真实默认App和PgAuthAudit，旧route记录作为positive control，新Ask要求相同固定字段记录；当前9d预期新route为红，实际执行后才认PG失败。只1case collect-only exit0，actual PG仍0；58/48/60、2target+sampler1、Source identity和exactdrop均沿成熟控制，不自行开库或取秘密。

真实 Edge/browser/API/普通worker准备与执行尚未取得组合证据。现有U06仪器要求真正answers403；当前四Role都具有READ_PUBLIC，跨owner/tenant按404、expired/revoked按401，未找到合法seed直接产生这一业务403。不会改ROLE_PERMISSIONS、mock403或以collect9/mock143冒称realbrowser；Root需提供可验证的实际拒绝路径或先运行独立匿名/证据/空查询/loading/持久调查状态组。本报告不删原U06验收条件。

尚未检查：完整Docker实际构建启动、修复后wheel、真实PG执行、完整Edge九流程/录像、模型/来源/FOFA/live、6h、性能/Gold/人工双标、全仓覆盖率门、全部公开六工具/插件host ports、完整R01/R17/R18、G-C检查点/阶段或R24-A→R23→R24-B。费用unknown；本次付费调用0。

## 合同、评分证据与下一步

本 reviewer无合同/计划/权限/schema/Gold/分母/阈值变更。三份新CR只作为当前授权/精确pin和异常端口说明读取；实际Source控制迁移、fresh17/ready15s/6h由Root独占执行，当前复核不代签。没有运行任何下载PoC或对第三方资产扫描。

本次证据仅支持 E1/X1输入失败/包布局问题识别、F3/P3共享默认问答和权限组件的局部回归、D2前端构建/严格类型；不提高准确率、P95或正式分母。下一步：Root完成Must1包内schema资源，冻结新source后用原部署负例与actualwheel入口定向复验；Root逐窗执行当前0030 own PG包，再补完整函数名CBM和有真实资源的Edge流程。新源码不复用9d的绿或部署红作为自己的结果。

Verdict：**fix 1 and 2 first。** 当前候选默认部署无法导入，新Ask还漏掉既有身份伪造审计。真实PG/浏览器等not_run保持，不登记accepted。

本次写作证据截止：2026-10-17T09:32:19+08:00。后续真实资源结果另行追加，历史红与本节未运行事实保留。

## CBM 完整函数名定向追加

Root另行授权≤10秒独占窗后，只查询同候选、同cache/project的 `dianzi-root-batch16-review1-20261017-frontend.api.question-client.submitQuestion`，没有重index或取旧图。09:34:05.067–09:34:12.711（7.644秒）新CLI exit0/isError=false，返回18 callees/4 callers；原不限定名称的ambiguous raw原样保留。Windows峰7，完整guest峰6，保守双OS13≤16，自有Win/guest残留0，Native512MiB/1GiB/rate833与guest两核/软内存说明不变。资源即时归还Root；实际完整结果见 `cbm_qualified.command.json`、`cbm_qualified.guest.json`、`cbm_frontend_submit_qualified.raw.log`。
