# G-C 集成 e310 · 新非作者独立回归验证

What this change does: 固定集成版本把来源块/证据批量保存、全来源富化发布、聚合历史及 TTL、私有资产历史、图指针选择放在同一树中。本报告核验它们的组合事务、权限、回归与真实默认来源入口，保留首次失败。

任务状态：`awaiting_review`；业务实现未改。本轮是新非作者 `/root/r06_r07_e310_integrated_regression_validation` 的限定集成验证，**不是正式 G-C、整 R、原 T 卡、live 或生产迁移放行**。已合业务服务组合可作为下一段有界、独立留证的受控采集代码基线；原 Windows CPU 四红仍未关闭，不能由本轮宣称整体工程门通过。

## 固定身份与授权范围

- SHA：`e310f7735bd499c4d9fbcefe8a644e2309a16a62`；tree：`886e5132c9d723bbc5d442614ab0c54f8e1208c1`。
- 首 cwd `D:/dianzi`，确认主仓有已有未提交文件、目标目录不存在。执行 `git worktree add -b codex/gc-e310-regression D:/wt/gc-e310-regression e310f7735bd499c4d9fbcefe8a644e2309a16a62`，exit0。只写本报告与 `reports/runs/recovery_gc_integrated_e310_validation_20261016/`；自有离线 venv 最终位于 Git ignored 的 `backend/.venv`，自有 node_modules 亦 ignored。没有 spawn、commit、push、progress/accepted 更新。
- 已读 AGENTS、00、恢复11/12中的 R06/R07/R08/R11/R17、03/04/05/06相关合同、冻结 task_state 与交接、各已合作者及独立报告、bulk/publication/typed候选/aggregate/asset/pointer CR。使用 [Ponytail review 5.2.0](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，先追真实入向/出向与跨模块调用，再验证可观察结果。
- 整合收据为主仓 `reports/runs/recovery_r06_integration_20261015/persistent_slices_integration_receipt.json`，五份目标材料分别 pub `9e722c944cf83086ffd30ad24a708172c13da189`、bulk `bdebeca358f0cfd63630b223dee64647b5280687`、aggregate `a76374ca9200945441a83421050eceef00db47d8`、inventory `bc8798cf5efc81e210a429884930ca545af43ad8`、pointer `65497b14cb5c24c6d780f675a70af3ee4019d8db`。各切片原 Ship 只作待核背景，没有替代本次组合检查。

## 组合语义与源码身份

新官方 WSL CBM 独立 src 索引为 `gc-e310-validation-src`：117 files、1642 nodes、8541 edges，not_indexed/skipped/partial/unusable均0；实际 schema、architecture 和 bulk/source/catalog/handler/publication/inputs/detail/runtime 八条双向 qualified trace 均 exit0。assets 另建独立 `gc-e310-validation-assets`：12 files、198 nodes、825 edges，同四项计数均0；单独 schema/architecture 已读。缓存仅 `/tmp/dianzi-cbm-gc-e310-validation-20261016`，root仅本树 backend/src，不索引报告、秘密、gold/holdout。CBM动态闭包仍出现 file-level heuristic，逐一用源码、rg、原测试及实际默认 API/worker 交叉，未把图边当事务正确性证明。

`integrated_source_identity_v2.json` 证明 signals.py、两份 public-signals 回归、inputs.py、publication.py 与 pub9e **五份 Git blob 精确相同**。CVSS add/add 解决确实含 `signals.py:552` 的 `(target, standard_version, authority)`；不同机构并列、同机构真实分歧冲突的正负例在本树运行。bulk 三源及其测试、aggregate TTL、inventory、pointer源文件与各冻结材料也无漂移。`attributes_audit_v2.json` 未发现 Git virtual merge-base 冲突标记；没有增加全局检查豁免。checkout CRLF raw hash与Git LF hash分开保存，不用工作树 hash替代Git对象身份。

来源真实路径：`api/app.py:122` 的默认 source router → PG enqueue/job/outbox → `workers/runtime.py:98/131` 固定 registry/execute_job → `source_jobs.build_source_page_handler` → source/catalog 保存 → `knowledge/revisions.py:70` bulk → 游标CAS、page receipt、commit。批次500，Unicode/hash/唯一ordinal/page/metadata在IO前校验；savepoint锁精确current revision和scope。catalog全文证据 `supports_claim=False`；source仍调用原 `attach_evidence_span`、事实发布与支持核查。原逐条 API、原文CAS/GC、0016独立失败响应收据与主事务的边界保持。

富化读取先核 source/document/revision 全roster权限，首次对象IO前完成整个名单检查；发布与历史回放再核父级ACL。真实源来源锁 → document/revision → publication scope → event顺序共同使用，来源父行 FOR SHARE兼容FK KEY SHARE。全来源集合、事件版本、current修订、原文字节/块与规则上下文校验，模型候选保持 unverified/pending，合法单维失败不会抹掉其它成功。PG历史回执和旧引文不被当前原文修订覆盖。

默认 app 的 `app.py:118–135` **仍未装配 inventory/aggregate/enrichment 新接口**，默认 worker registry仍无富化publisher/资产变化重判 handler；publisher CBM零入向又经全src rg确认。`frontend/src/App.tsx`仍没有图入口，生产build维持原53modules。405前端测试证明当前组件回归，不能据此称 graph→真实API→默认App 已接通。

## 真实执行与数量

运行目录简称 `R=D:/wt/gc-e310-regression/reports/runs/recovery_gc_integrated_e310_validation_20261016`，后端 `B=.../backend`，前端 `F=.../frontend`。每条 `<label>.command.json` 保存实际完整argv/cwd、start/end `+08:00`、exit、code SHA、runner hash；stdout/stderr、JUnit和逐实例 roster 原文件均保留。`test_rosters.json` 按真实 collected testcase 分组，子集与复验不叠加成新总分母。

离线 `uv sync --project backend --frozen --offline --all-extras` 在05:15:00.902–05:15:10.180+08 exit0，CPython3.12.13；新树editable安装，锁文件不变。先置自有run/.venv，后移至标准ignored B/.venv。`runtime_origin.stdout.log`独立核对 source_jobs/source_documents/revisions/publication/signals/inventory/aggregate七实际module.__file__均来自本树src，无作者/主仓模块污染。npm ci `--offline --ignore-scripts --no-audit --no-fund`自有F目录exit0。

| label / 实际核心命令 | +08窗口或pytest时间 | exit / 真实结果 |
|---|---|---|
| backend_directed_pure / `pytest` R06/R07/R08/R09/R11/R02、T05/06/07/19/21/24/26相关unit/contract/security；`-m "not real_pg and not real_services and not real_search_tls" --no-cov` | 05:16:26.980–05:17:48.066；76.43s | **1；1492 pass、1 fail、12 deselected、0 error/skip**。单失败为自有venv扫描污染，下文保留复验 |
| security_scan_resource_recheck / 原T06-C06精确节点、`--no-cov` | 22.06s | 0；1 pass。仅迁移自有venv，不改scanner/classification/原测试 |
| shared_generation_regression / 原generation/review-fixes/predispatch/wire/T18 + 原跨R07 `_generate_field→GenerationClient`探针；`--no-cov` | 05:27:41.529–05:27:46.586；3.14s | 0；156 pass，0 fail/error/skip；四provider到期均FAILED/model_network_timeout、空candidate、0DNS/POST、slot释放 |
| pg_publication_95 / 原9文件；`--no-cov` | 05:17:54.034–05:19:40.172；102.91s | 0；95 pass，0 fail/error/skip |
| pg_independent_lock_roster / 原reviewer独立v2探针精确新副本；`--no-cov` | 05:19:40.174–05:20:11.013；29.10s | 0；17 pass，0 fail/error/skip |
| pg_sources_bulk_failures / 原7文件；`--no-cov` | 05:20:40.139–05:23:31.287；166.91s | 0；165 pass，0 fail/error/skip |
| pg_t05_t07 / 原T05/T07；`--no-cov` | 05:24:46.063–05:24:50.004；2.15s | 0；21 pass，0 fail/error/skip |
| pg_bulk_auth_security / bulk原scope安全5+原PG auth安全6；`--no-cov` | 14.36s | 0；11 pass，0 fail/error/skip；这5补齐bulk17，保持PG安全层分类 |
| pg_t07_retry_contract / 原T07真实PG retry_wait合同；`--no-cov` | receipt | 0；1 pass，0 fail/error/skip；与上述11一起独跑首pure的12个PG deselected实例 |
| pg_original_r04_fixed_resource / 原正常节点2参数实例、不改旧fixture | 0.41s | **1；2 setup error**；旧固定库断言拒绝新库，未进body |
| pg_original_r04_resource_adapted / 原全部25 body；仅page_engine→catalog_engine安全资源adapter | 23.72s | 0；25 pass，0 fail/error/skip；原source/testblob与期望不变 |
| pg_inventory / 原T24，0016基底显式三表proposal | 05:22:04.357–05:22:11.417；4.75s | 0；46 pass，0 fail/error/skip |
| pg_aggregate / 原PG20+TTL PG10，0016基底显式单表proposal | 05:22:14.136–05:22:18.918；2.71s | 0；30 pass，0 fail/error/skip |
| pg_default_product_path_v2 / 默认认证/app/API及runtime registry；显式fixture transport | 4.01s | **1；正常1 pass、负例1 fail**，负例自有probe错列名，未执行worker |
| pg_default_product_path_v3_negative / 只负例、真实cursor字段；新独有库 | 3.97s | 0；1 pass、1 deselected、0fail/error/skip |
| backend_ruff / `python -m ruff check src --no-cache` | receipt | 0；全src含assets |
| backend_format / `python -m ruff format --check src --no-cache` | receipt | 0；117 files |
| backend_mypy / `python -m mypy src --cache-dir R/mypy_cache` | receipt | 0；117 source files |
| frontend_test / `npm test -- --reporter=json --outputFile=R/frontend_vitest.json` | 05:16:22.812–05:17:00.388 | 0；405 pass，0fail/skip/pending |
| frontend_typecheck/lint/build / 原npm scripts；build输出R/frontend_dist | receipts | 全exit0；严格类型、lint及实际production build一次 |

纯定向内 bulk新unit6/contract1，PG165内bulk5；原security5标记real_pg，因此属于首pure的12 deselected，在独立真实PG安全命令另跑，不能冒称pure通过。这些构成原新增**17个实例**，不将这17再累加到各suite。R09 unit38/contract10/security12、manifest parser unit32+identity36/contract1/security32共101实例实际覆盖；公共信号unit51+fix13、模型字段unit56+root-causes46及对应合同/安全亦在roster。新 Generation156与前述pure没有文件重复；重复的T061只作修复仪器复验，不增唯一case数。本轮所有pytest显式`--no-cov`均为行为验证，**没有关闭、放宽或重新宣称原60%全仓门passed**；全pure/default覆盖、CPU四例没有重跑。

PG95文件数量：inputs12、composed6、publication18、signal-values13、literature-target7、catalog21、ACL/lock15、CVSS2、provenance1。PG165：bulk5、source-worker33、failed-response43、source-boundary6、R04-source-jobs19、source-worker-API39、document-API20。T05/T07为15/6。完整实例名单及原始outcome见roster，没有以import数量或作者口述替代collected计数。

## PostgreSQL与产品路径实证

唯一读取的私有配置是授权WSL `/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json`，subprocess capture到内存，验证loopback25432/test用户/test库；DSN只经环境或受控内存参数，不进stdout/argv/报告。测试库保留，没有连接dev/生产DSN、downgrade、删旧库或跑已知破坏性命令。

自有库：`test_dianzi_r06_catalog_gc_e310_20261016`，run_id严格匹配；catalog/source各例自有UUID schema、实际数据库核对、原statement/lock timeout、前向0016。T05/T07使用该新库public基底。R11为 `test_dianzi_r11_inventory_gc_e310_20261016`，R08为 `test_dianzi_r08_aggregate_gc_e310_20261016`；前向0016后显式创建自身三表或单表/trigger，receipt明确 **create_tables_not_production_migration**，不是0018/0019通过。

默认product正/负各给新public-schema库 `test_dianzi_r06_catalog_gc_e310_20261016_default_p` / `_default_n3`，保持原默认build_engine而不注入认证服务或替换PG引擎。默认登录 → `/v1/sources/vllm_vendor/collect`202 →实际PG job → `runtime.consume_job`默认registry中的同一source handler（只注入固定fixture fetcher）→ succeeded → `/api/v1/jobs`、`/v1/events`、event-detail及精确revision evidence重读全部成功。负例同入口送固定网络timeout，得到retry_wait；cursor JSON/watermark/last_successful_page前后相同、page receipt=0、document revisions=0、events为空。没有实际broker/Redis传递或外网，ASGI TestClient真实路由不是部署HTTP/browser/live证明。

实际source父ACL、解析失败/非2xx/timeout的独立raw留证、主页面/游标回滚、重放/并发/CAS、A→B→A原文修订及旧事实失效、旧证据仍打开在原PG回归中通过。bulk批次故障全部savepoint撤销，不把引用存在当支持事实；原quote-mismatch monkeypatch仍拒绝伪supported。

新独立17精确复跑全roster source/document/revision撤权（包括无candidate的FAILED和历史replay）、零对象IO与14表完整内容快照；真实writer-first/publisher-first、单双源和反序loaded清单四种时序，通过pg_locks/pg_blocking_pids识别精确source advisory等待，释放后源→文档→scope顺序、无40P01/55P03/隐式retry。writer-first拒绝旧快照无部分结果；publisher-first均提交，旧请求重放保持历史ID，新请求旧快照拒绝。原来源修订不覆盖历史支持引文；新workflow schema2可读context/rule_version/event版本/完整revision名单真实PG重读。

R11原46检查不可变snapshot、current/previous/receipt复合FK、权限/角色/CSRF/Origin、同请求/异请求并发、原文仅private PG、发布故障rollback及历史重放；R08原30检查0/未知/失败分离、历史不可改、scope/policy/mode、future/乱序、UUID collision与并发、最新失败不代以旧总量、cache半秒TTL不超PG剩余期。全部provider/模型/测绘请求0，费用unknown，不将fixture live标签当在线结果。

## 首次失败与仪器修正

1. 首pure1492/1失败原bytes保留。T06仓库扫描将误置R/.venv第三方site-packages视为仓库材料；严格确认绝对源/目标后Move-Item自有venv至B/.venv，文件bytes完整保留，原scan精确节点1pass。没有增secret allowlist/fixture分类或改测试。
2. 原R04固定库2setup errors保留，只读确认拒绝发生在创建schema/写事务前。新`run_legacy_r04.py`通过pytest collector只换resource fixture，仍原25body/input/assertion与原blob，realPG/0016/UUID schema/timeout护栏均保留。原2红没有改记green。
3. 默认product初版两个login503，尚未进入业务；原schema-URL资源与默认build_engine自有connection options不相容。v2使用各自新public-schema数据库，正常路径通过；负例错读并不存在的last_success_at列，原1红保留。v3只修自有probe到实际watermark_published_at/last_successful_page，负例通过。没有改业务/原fixture/金标/计分规则。
4. 作者字节首audit把raw hash直接比Git，bulk70/graph13显示表示差异；首JSON和脚本保留。v2分别按bulk ZIP原raw、graph manifest冻结LF/hash、inventory gzip原raw核验；没有降低字节校验，也不把换行表示差异当源码语义修复。
5. frontend build生成tracked tsconfig.tsbuildinfo；将生成bytes保存在R，精确恢复HEAD Git blob，`frontend_build_generated_restore.json`记录hash，最终tracked diff空。原弃用/未知mark warnings保留；新报告no-index diff --check exit1为新增文件差异返回码，stdout无空白错误，stderr仅LF→CRLF提示，不改写原输出。上述是验证仪器/资源记录，不伪装成产品修复、skip或完整首回归全绿。

## Must fix（继承的安全门，未在本轮复测）

1. **Windows原CPU短任务/guardian硬退出门仍未关闭**（`backend/src/ai_intel/infrastructure/process_limits.py:157/234/254`；`backend/tests/unit/test_r20_native_cpu_guard.py:81/99/154`）。
   - **What this is:** 受限worker应保留短任务结果，在guardian退出时清理进程树，并满足原累计kernel+user CPU `<1s`断言。
   - **Problem:** 原8a完整实跑四red：短任务exit3221225540且空stdout；python-gil-held没有TREE；native-idle实测1.0s、native-cpu1.3125s不满足严格<1s。本轮两相关source/test Git blobs仍与8a完全相同；原JUnit hash、四failure原文保存于`inherited_8a_cpu_failures_v2.json`。这是**历史已复现、e310未重测且未修的门**，不是新测量，也不推断空stdout精确耗尽时点。
   - **Fix:** 沿原边界继续独立根因诊断/有界早期启动监督修复，再由新冻结独立复跑原四例；保留累计口径、ready/wall/原阈值，不改预算到碰巧通过。此review不扩大业务补丁。
   - **If we skip it:** 不能给Windows短CPU安全保证、全工程passed、R20或G-C放行。

组合的bulk/来源/发布事务未发现新的Must。本轮JSON/Catalog批量SQL与PG服务检查不依赖上述1秒native worker，故旧门**不阻断独立sourcebulk正确性开发/限定服务验收**；但新受控live必须沿已授权外层OwnedJob CPU/内存/watchdog约束及自身预算留证，不能以本轮PG绿替代安全门或继承先前大页1.330/1.514s为e310新性能实测。原大页caps独立report保留，本轮没有再跑大页/raw handler。

## 材料、边界与交接

`author_frozen_material_audit_v2.json`独立核对五包：bulk86 entries及ZIP本体，publication47、aggregate32、inventory103（94 gzip artifact与9source proof；另93原raw解压）、graph173（6source+167evidence）。所有声明raw/archive/冻结Git basis匹配、source漂移0。bulk70个Git表示差异由原ZIP精确bytes证明，graph13由声明LF/frozen_blob hash证明；不将Git过滤视图当原日志。各manifest的Git/checkout SHA分列。信号五精确blob与整合收据的CVSS冲突解决吻合；attrs virtual marker清理没有改测试门。曾引用的两单独ACL/CVSS CR并未出现在pub9e/main树，其行为已在当前multisource publication CR明确记录；本轮没有凭这些缺失路径修改权限或合同。

八层：unit/contract/security在所述限定行为范围有证据，首pure扫描红与复验分别保留；完整unit/contract/security/default覆盖门 **not_run**，继承CPU门未关闭。integration上述真实PG与默认ASGI/handler限定passed；全部署Redis/Celery/MinIO/生产迁移与端到端not_run。frontend405/type/lint/build passed；本轮browser/e2e/manual not_run。live/正式≤6h/模型或provider/完整来源覆盖、准确率与人工金标均not_run/blocked_live，不涂绿。

评分证据仅F1/E1/R1来源原文及失败/游标/事务，F2/P2支持/未知/权限/修订，F3共享模型typed故障传播，D2前端组件回归；没有新分数、准确率/召回、吞吐、连续时长或费用结论。原整R06/R07/R08/R11/R17/T卡、G-C门与0018/0019生产迁移不由本报告签收。

改动文件仅本报告与R内脚本/日志/roster/sourcehash/归档审计。`scoped_diff_identity`/`final_status`确认业务、原tests、migrations、locks、contracts、progress、docs、frontend源码和生成tracked缓存无diff；HEAD始终固定，无push。报告raw SHA与独立manifest/sidecar在本run封存；manifest不自引用，原red全部另名保留。下一任务建议：主控以e310固定组合另开有界受控采集，单独核实际来源/MinIO/分页/恢复/持续窗口；并行完成富化作业、资产/聚合生产迁移与默认图接线，各新冻结仍须独立review。严格CPU门继续单独处理。

Verdict: **已合业务服务组合限定 Ship，可作下一受控采集代码基线；完整安全/工程门先修上述1。**

Not checked: 全pure/default60覆盖/四CPU复测、大页新性能、生产0018/0019、真实broker/MinIO/外部来源/模型/provider、新图默认App及真实API浏览器整合、完整R卡/阶段/≤6h/人工终验。
