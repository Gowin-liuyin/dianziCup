# G-E / R18 component selector 非作者最终fixture复核

当前结论：**LimitedShip，仅内部component selector业务source4c35＋source36两个合法fixture输入修复切片**。retry4原PG7实际7passed/0failure/error/skip，source/own native身份、全窗口、资源/清理与秘密扫描均独立核验；不accepted，不签默认producer/整R18/G-E，不授权stage/push。此前本报告prepared/not_run节点另存ownrun `report_pre_retry4_receipt_review.md`；原4c报告/首prepare失败0业务、Retry1 URI红+wrapper124、source1e retry3 expired CK红全部保留，不改写为历史全绿。

## 1. 当前fixed source与AST范围

source=`36b969bd9b98dcbb53f9eb3a4ffcb4d74cc77df9`，parent a910含URI1e输入。干净新worktree=`D:/wt/r18-selector-expiry-review1`、branch=`codex/r18-selector-expiry-review1`，HEAD/commit object=36b969bd，tree=`aea9e307d59d9b601987f08eb6e26b19363a2d55`。相对selector业务source4c35，业务、迁移、schema、旧seed、原离线unit/contract无变化；本非作者仅reports下新报告/ownrun，无本地tracked业务或测试修改。

原PG6函数/7参数化案例，仅两输入修复：create_assessment在same revision+document补same源origin URI后再publish；expired分支单次fixture_now=datetime.now(UTC)，同时issued_at=now−2s、expires_at=now−1s。真实字段是issued_at；保持session hash WHERE、role_downgrade分支、原SessionExpiredError/PermissionDeniedError断言、0006 expires_at>issued_at约束和共享clock gate，无sleep。

`prepare_retry4.py`分别验证新增expiry输入AST精确值、单次时钟调用、原hash WHERE AST，规范化expiry inputs后等1e；再仅移除URI helper/input与document_revisions import后，全原PG module AST等4c35。全部原assert/decorator保持。原URI合同的5个函数源码段/AST相同，对应4cases；整contract文件因imports与新增6cases变化，不能称whole-file byte/hash相同。原URI4不重复运行或升count。辅助只读核查无finding；其纯内存初检查器遍历顺序错误已纠正、最终exit0，没有测试/PG/WSL执行。

## 2. retry4 ownharness身份与固定边界

RUN=`reports/runs/r18_component_selector_review1_pg_retry4_20261017/`；`prepare_retry4.py`实际exit0、PG/WSL0。复用retry3direct controller，只有四helper的ROOT/src路径和sourceSHA常量变更，另外五helper raw不变；9helper、234current source/migrations/tests、3external helper逐项hash核验。原hash map只PG输入+contract两文件变化。六项source/关键assert/原seed/CK材料按raw base64/长度/SHA256与Git blob OID/hash归档复验，见 `current_source_assert_bytes_archive.json`，原材料不覆盖。

| 文件 | 最终raw SHA256 |
|---|---|
| run_pg_review.py | 0538315b330780b0a6be0472d35c7885f487f043f78c22b5542d57de860c9f2f |
| pg_prepare_worker.py | 67fab0f28a64bc9f61294c195a228156a1238fe5380c8d0f0a59d5f33c13563b |
| worker_entry.py | b4c36aa5d23a7a3ff207c07cf1ecba87170849950636f911678a38ec212a4ad7 |
| pg_controller_admission.json | aa5fe61cf6320640957ef3e196c9d52d2786fcb6371e477846e4bd0cc4b779e0 |

direct pytest仍为same base worker_entry.py pytest -p reviewer_pg_identity 原PG test整组、same pg_actual_7.xml；旧pg_entry作为未调用4c归档输入保留，不导入/调用。ROOT固定新WT，RUN从本目录派生。native marker exact9及新source36/current ownDB only HEAD0030、真实nullable role COMMENT、Source OIDs10451302+10434264完整身份前后、OID/owner/exact COMMENT/zero sessions drop、secret扫描保持。

总58秒/prepare+pytest共同48秒子截止/Root外层60秒、Windows10、target2+parent sampler1物理3、native9/15固定Job512MiB每进程/1GiB总/~2CPU均保持，不加时或延长native资源、不改角色。Root memory注入原四变量：R18_REVIEW_PARENT_DATABASE_URL、DIANZI_REVIEW_RESOURCE_AUTHORIZED=r18-component-selector-review1、R18_REVIEW_BATCH_ALLOWLIST=[pg_selector_7]、aware UTC R18_REVIEW_AUTHORIZED_UNTIL_UTC；值不入报告、不读DPAPI/private。新launcher须新RUN worker_entry再调用新controller。

## 3. 实际命令与计数

| 当前point实际命令 / 检查 | 结果 | 证据 |
|---|---|---|
| git worktree add -b codex/r18-selector-expiry-review1 D:/wt/r18-selector-expiry-review1 36b969bd9b98dcbb53f9eb3a4ffcb4d74cc77df9 | exit0，新HEAD/tree如上 | 工具实际输出 |
| D:/dianzi/backend/.venv/Scripts/python.exe <RUN>/prepare_retry4.py | exit0，只AST/bytes/identity准备、PG0 | prepare_retry4.command.json/stdout/stderr |
| D:/dianzi/backend/.venv/Scripts/python.exe <RUN>/run_expiry_contract6.py；内层python -m pytest --no-cov -q tests/contract/test_r18_selector_canonical_uri_fixture_input_contract.py -k "expired_fixture or shared_auth_accepts or fixture_session" --junitxml=<RUN>/expiry_contract6.xml | exit0，6passed/4deselected/0failure/error/skip，JUnit0.631秒 | expiry_contract6.command.json/stdout/stderr/xml |
| 原PG7 retry4 | **passed**；实际7passed/0failure/error/skip，prepare0/pytest0/outer0，JUnit3.630秒 | pg_selector_7.*、pg_actual_7.xml、native before/after、Rootretry4launcher；见第5节 |
| front/e2e/live/manual/default REST/MCP/RiskSummary/full CI | **not_run** | 内部selector切片证据不代整R18/G-E |

新6合同：合法expired输入真正进入共享auth拒绝；原未过期输入共享auth接受；issued/expires各自NULL数据库拒绝两例；expires=issued和expires<issued两例。都是显式SQLite/mock fixture、非真实PG或live。复用成熟Root batch13 checker+fixed native Job，无新运行框架；timeout25、Win10，实际峰6/owned残留0，Job24CPU rate833≈1.9992cores、峰111550464B/CPU4.0秒、active_processes=1为checker。离线占用结束、PG/WSL0。

原4c非作者127+own5、1e URI4、36新增6是不同版本固定输入上的不同用例记录，不能称本source一条命令全跑142或借作者137通过为本非作者当前全绿。原4c CBM17indexed/18snapshot只能历史关系参照，当前fixture由36源码rg/Git/AST/raw核查，不冒称新完整索引。

## 4. 当前问题与结论

1e retry3原URI/exact_current已实际passed，原URI问题已关闭；retry4原7整组中的exact_current与expired共享认证拒绝均真实passed，source36输入合法化后新expired CK输入红已闭合。旧wrapper124在retry3/retry4均未重复，旧25.56至48时差唯一根因仍unknown，不因去nested监督确认sole cause；初prepare URL编码错误、URI红、expiry红与旧收口124分开记录并保留各原始日志。

当前 **LimitedShip**，限定内部选择器和两个明确fixture输入修复，没有未闭合selector业务Must。调用方仍须同txn/engine预锁当前认证（尤其空结果）、保留unknown/ambiguity/stale原因与finalauth/current proof；selector不是独立producer。默认REST/MCP/RiskSummary接线及全R18/G-C/G-E/完整CI/front/e2e/live/manual未在本切片验证，仍partial/not_run，不accepted/stage/push。原限额、oracle、分母与所有红日志保持。

## 5. Root实际retry4原PG7与独立关闭证据

Root外层窗口07:35:25.6948531–07:35:34.9276899+08、exit0、outer_timeout=false、timeout60；Root收据为 `D:/dianzi/reports/runs/recovery_reviewed_integration_20261016/r18_component_pg7_retry4_launch.json`。controller窗口07:35:26.383–07:35:34.858+08、8.468秒、exit0/error=null、prepare0/pytest0，实际执行source36/new ROOT/RUN和原7整组；executed9helper/234source hashes逐项等admission。内层真实argv保持base worker_entry.py pytest -p reviewer_pg_identity tests/integration/test_r18_public_component_selector_pg.py -q --no-cov --junitxml=<RUN>/pg_actual_7.xml，cwd为newWT/backend。

JUnit真实7 distinct/7passed/0failure/error/skip，3.630秒：exact current typed source URI/citation；wrong/unknown version不得借结果；foreign tenant同组件不可见；新asset snapshot排除旧current；knowledge epoch失效不可只借database freshness列；expired空结果认证拒绝；role_downgrade空结果权限拒绝。最后两例保留原SessionExpiredError/PermissionDeniedError oracle，expired本次已越过合法UPDATE进入共享auth拒绝，而非CK错误冒充拒绝。原URI的NULL/wrongrevision/wrongdocument拒绝合同在1e真实跑4passed、36原函数源码/AST相等；新增expiry6在36真实全绿。没有重复计原4或重试PG7为新distinct。

native nonce=68b3410ebfbf，数据库 `test_dianzi_r18_component_selector_68b3410ebfbf` OID10727979、schema `test_r18_component_68b3410ebfbf` OID10728308、role OID10。before/after DB/schema/role OID/owner/exact COMMENT相等，DB/schema marker为exact9/source36/max58，role COMMENT真实NULL，未伪造marker或创建role；only ownDB HEAD0030，prepare独立child退出后才pytest。drop前exact native identity与零目标连接已核，实际ownDB剩余0/target0/sampler0；Source OIDs10451302和10434264完整身份前后相同；本审查没有再次打开PG或任何Source。

实际target峰1+parent sampler1=物理2≤3（任务门为target2+sampler1），Windows全树峰4≤10/owned残留0/sample_errors0。parent Job native9/15在spawn前验证每进程536870912B/总1073741824B、24CPU rate833≈1.9992cores；usage峰145244160B/CPU9.359375秒，active_processes=1为controller自身。秘密扫描13原artifacts passed；没有服务密码/DSN值入报告，Root parent URL只内存注入，Root外层没有超时或擅延资源。

非作者 `review_retry4_actual_receipts.py` 实际exit0，只读已结束收据/原raw；严格核7cases、当前source/entry hashes、native marker/nonce/OID/head/NULLrole、cap、Source/精确drop/secret/两修复oracle。输出 `retry4_actual_review_summary.json`，另将28项actual原材料、9helpers、source/assert byte包和Rootlauncher按base64/长度/SHA256归档逐项解码复验，见 `retry4_actual_bytes_appendix.json`；28是文件数不是测试数，封包命令/退出码/输出为 `review_retry4_actual.*`。原执行日志/所有旧封包/未测层级未覆盖或改绿。

B资源已向Root明确归还，当前本审查0PG/0WSL/0业务子进程，只归档报告；Root可继续其public ask限定窗口，无需等待本材料commit。单切片复审结束，后续默认producer仍由新独立审查承担。
