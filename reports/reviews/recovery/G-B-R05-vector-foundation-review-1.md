# G-B / R05 向量基础批独立审查 1

What this change does：本批新增共享原生内存/CPU限额与PDF委托，集成本地官方ONNX E5和mMARCO接口，强化共享embedding校验，并增加384维pgvector检索块、用户拥有的答案/audit JSON增量迁移与依赖锁。固定代码尚未把语义、检索、引用问答接入API；本报告只审这个基础批，不签整R05、原T18/T30/T31或G-B。

初审状态：`needs_changes`，必须先修复下方1、2。最新定向复核固定`3ab2357`已关闭1、2、3，最终意见为**Ship（仅本批范围，见末尾）**。审查者`/root/r05_vector_foundation_review`未参与本批实现。作者日志及此前semantic独立审查用于定位，不作为本次复跑结果。

## 固定范围与方法

- 基线`afe490ce15e567bf916d2e7b970354ddff3e193e`；初审代码`fd01ea3e0205361c1f446d6fb97694aa3aa715cf`，14文件，新增1684/删除77行。独立worktree：`C:/Users/yinha/.codex/worktrees/recovery-r05-vector-foundation-review-1/dianzi`；分支`codex/r05-vector-foundation-review-1`。初审最终snapshot的Git状态为空，源码模块路径全部断言位于此worktree，未对作者活跃主仓判通过。
- 阅读AGENTS、00执行索引、R05恢复卡、T18/T30/T31、03/04/05/06合同及02/07和CR-R02相关条款；采用Ponytail5.2的ponytail-review。没有修改业务、共享状态、合同、锁文件、金标或分母，没有push或写accepted。仅写本报告和`reports/runs/recovery_r05_vector_foundation_review_1_20261015/`；独立worktree及仓外CBM缓存另行隔离。
- CBM0.11.0：先看help/CLI参数，初次无project的schema命令报缺参数后改正；以独立`XDG_CACHE_HOME=/tmp/dianzi-cbm-r05-vector-foundation-review-1-20261015`索引本worktree的`backend/src`，1000节点/4725边，75源码文件，无未索引/部分解析文件。schema和inbound/outbound trace与源码rg交叉核对，索引不替代源码结论。
- `validate_embedding_batch`唯一业务调用者是`LocalSemanticModels._embed`；`bound_process_resources`用于semantic worker和PDF worker。检索/答案Table只有映射与测试引用；API没有新模型/检索/问答调用路径。upstream semantic/helper/PDF与独立复核的`1e77c0d`业务字节相同，本次仍独立跑unit、contract和一次真实live批次，不借用上次日志。
- 本机Python3.12.13，pgvector Python0.5.1、SQLAlchemy2.1.1、psycopg3.3.6、numpy2.4.2、onnxruntime1.24.4、tokenizers0.22.2。复用已有解释器，`PYTHONPATH`固定到审查worktree；版本与源码origin写入snapshot。PG使用已授权25432专用`test_dianzi_r05_pgvector_20261015`、UUID schema；connection.json通过`wsl -u root ...`和subprocess capture读取到childenv，未打印/留档DSN或密码。未重启PG、改其他库或做降级。

## Must fix

1. **Python非零在float32持久化后变成零向量**（`backend/src/ai_intel/infrastructure/models/clients.py:110–118`，P2）。

   - **职责/预期：**共享校验宣称返回可安全入pgvector的有限float32非零向量；非法输入应在入库前报`ModelContractError`，不能留下余弦距离无定义的零向量。
   - **输入/实际：**`validate_embedding_batch([[1e-50]*384], 1, 384, 'review-underflow-v1')`被接受。通过本批Table与真实pgvector插入，读回384坐标全为`0.0`，`cosine_distance([1.0]*384)`为`NaN`。原因是非零检查使用Python双精度原值，未检查float32下溢。两项独立红例见`independent_negative_v2.log/XML`：两维拒绝测试未抛异常，384维真实入库测试实际零向量。
   - **最小修复：**使用与PG持久化一致的float32表示检查全部坐标转换后是否为零，再拒绝该向量；不要把合法非零subnormal一概拒绝。可使用标准库float32转换，无需新依赖或层。
   - **影响/复验：**不修会把校验通过的无定义向量交给索引/余弦排序。当前固定E5调用另有L2检查，因此本例不是宣称已经发生在线E5错误；它确证本批共享边界合同不成立。复验必须保留`1e-50`正负下溢、`2**-149`可表示值、原finite/类型/维度/空间边界，以及真实PG不写入全零向量的断言。

2. **新增迁移没有协调已有升级回归的迁移头期望**（`backend/tests/integration/test_r02_schema_migration.py:87`，P2）。

   - **职责/预期：**空schema与0006旧数据均升级到当前合法head，并继续验证旧列、旧事实、unknown语义及时间保留。
   - **输入/实际：**原文件不改动复跑，`previous_revision=None`与`0006_auth_state`两项均失败：实际`0014_grounded_answer_vectors`，断言仍为`0013_revision_source_metadata`。同批另外7项通过；不是迁移业务崩溃，也不是资源缺失。
   - **最小修复：**将head断言协调到本批正式Alembic head（或从官方ScriptDirectory取得当前head），保留所有历史数据/列/时间断言；不能删例或skip失败。
   - **影响/复验：**不修相关真实PG回归一直为红，且该断言后的旧事实检查未执行。需不改原验收语义地完整复跑原R02三项；本审查另外独立确认0006旧事实的值、unknown、freshness和时间可保留，但不拿独立探针替代原回归。

## 独立初审命令与结果

以下时间均为2026-10-15，Asia/Shanghai（+08），秒级原始时间、逐字argv/cwd、退出码见同名`*.command.json`，stdout/stderr见`*.log`，pytest数量来自JUnit，不合并重复复跑数量。所有Python/pytest/mypy/Ruff/uv命令cwd均为独立worktree的`backend`。证据根：`D:/dianzi/reports/runs/recovery_r05_vector_foundation_review_1_20261015/`。

| 日志名 / 实际命令要点 | +08起止 | 退出与真实结果 |
|---|---|---|
| `full_unit`：`python -m pytest tests/unit -q --junitxml=.../full_unit.xml` | 16:13:21–16:13:59 | 0；778 passed，0fail/error/skip；原60%门保持，66.26%，1条既有warning |
| `vector_pg_actual`：原`pytest tests/integration/test_r05_vector_persistence.py tests/integration/test_r02_schema_migration.py -q --no-cov` | 16:14:35–16:14:47 | 1；7 passed/2 failed；新6项均通过，R02两个head期望失败 |
| `semantic_live`：原`pytest tests/live/test_r05_semantic_live.py -q -s --no-cov`，显式`R05_SEMANTIC_CACHE` | 16:14:35–16:14:49 | 0；3 passed，0fail/error/skip；一次真实中英embedding、重复index稳定重排及token超限回归 |
| `independent_negative`：原T18合同+独立v1探针 | 16:15:55–16:16:08 | 1；12 passed/5 failed；2下溢业务红例，3为审查者自有viewer fixture缺tenant的准备错误，未判业务缺陷 |
| `semantic_contract_actual`：原semantic/T18/T09合同3文件 | 16:16:56–16:16:59 | 0；17 passed，0fail/error/skip |
| `mypy_src`：`mypy --cache-dir <本证据根>/mypy_cache src` | 16:16:56–16:17:08 | 0；75源码文件通过 |
| `ruff_changed` / `format_changed`：本批12个Python源码/迁移/测试文件 | 16:16:56–16:16:56 / 16:17:33–16:17:33 | 各0；lint和格式通过 |
| `uv_lock`：`uv lock --check --offline` | 16:16:57–16:16:57 | 0；82 packages已锁定，不安装/下载模型 |
| `frozen_diff_check`：`git diff --check afe490... fd01ea...` | 16:17:33–16:17:33 | 0 |
| `independent_negative_v2`：原T18合同+自有v2探针 | 16:19:30–16:19:43 | 1；16 passed/2 failed，0error/skip；修正自有fixture的tenant，新添0006历史检查；两项业务红断言未改变 |
| `missing_extras`：`python -S probe_without_semantic_extras.py` | 16:19:30–16:19:31 | 0；标准库解释器确认3推理库不可导入，明确`ModelNotConfiguredError`，无伪成功/残留active child；这是缺库模拟，不是另做非extra安装验收 |
| `linux_limits`：WSL stdlib-only自有child probe | 16:19:31–16:19:33 | 0；memory子进程exit1/MemoryError、CPU子进程exit-9；0.256/1.082秒；Python3.10.12，仅共享限额，非Python3.12全栈Linux验收 |
| `cbm_index/schema/validator_trace/pdf_trace` | 16:14:03–16:17:05（分命令） | 各0；完整索引和两条真实调用路径核对，详细分段时间在receipt |
| `frozen_snapshot_actual/source_scan` | 16:21:17–16:21:19 | 各0；源/测试SHA256、Git tree与空status、origin和JUnit数量封存 |

前置失败均留档：首次普通WSL用户读取root600配置失败，未启动PG测试；改为root后才执行。`semantic_contract`首次用了不存在的T09文件名，exit4/0tests；改正实际文件名后17项通过。`frozen_snapshot`首次Git diff文本解码用了Windows默认GBK，exit1；保留初始partial snapshot和失败日志，v2只固定UTF-8后成功。没有把这些准备错误计为业务测试失败，也未伪造首次未独立记录的墙钟时间。

独立v1/v2测试及diff不覆盖；最终snapshot包含全部14变更文件hash、审查探针hash和每个XML计数。v1 SHA256=`cf5044827a20035af84d852f87209cd31a77a80017fd77d417b68f3a5de9f81c`，v2=`08f43785a142b80a848a6e54c0f689e8082003f33197cc7cf45f051f0aac817d`。

## 已验证边界与未覆盖范围

真实PG确认：0013→0014保留既有immutable evidence ID/hash；固定vector类型、余弦roundtrip与model-space过滤；错误维度/NaN/Inf拒绝且事务回滚；相对坐标长度拒绝；migration replay不覆写已保存chunk/答案owner/audit；3个JSON audit字段拒绝array；孤儿owner FK拒绝；两线程同evidence/坐标/model_space只有一条提交，另一条唯一约束明确拒绝。这里是数据库约束并发证明，尚无业务幂等upsert服务。合成向量及recorded来源只记integration，不计真实embedding入库live或来源live。

只含自有schema的search_path能够空库/旧库升级并重复迁移，表仍落自有schema，没有改为public业务表。另以新连接只含该schema做`embedding <=> ...`，实际SQLSTATE42883：extension operator位于public而连接看不到它。当前无产品调用路径，因此不把它报成当前在线检索故障；后续检索接线必须显式配置extension operator/schema可见性并测试这种连接路径。迁移内的事务局部set_config不会永久改变所有应用连接。

资源方面，full unit包含真实Windows内存/CPU负例与PDF解析回归，PDF仍512MiB/CPU15s、semantic仍2GiB/CPU30s；独立Linux限额负例另外通过。默认extras缺失fail-closed，无fixture后备。固定官方仓外权重校验及真实推理3项通过；没有新下载、付费调用或新服务启动。一次暖缓存调用约2.4–2.6秒，不据此宣称冷启动、吞吐或问答SLA达标。

尚未检查/仍`not_run`：真实模型向量与PG写入的产品整链、API/租户前过滤/epoch回查、问答owner读取拒绝与会话重授权、唯一证据删除后引用回答、索引落后/失效事实过滤、业务发布/幂等与跨进程并发、答案更正历史流程、正式检索质量/性能、长时间资源与全栈Linux、人工/盲测。新表FK与JSON约束不等于已经有这些权限和历史服务。没有发现本批需要抽象层或删行的复杂度问题。

评分证据限于R05②的迁移/空间/边界、③的本地重排和T18相关unit/contract及小批live；Must1使共享float32非零合同仍不完整。没有F3/P3整体验收、真实引用回答或G-B过门证据。

下一步建议仅冻结并修复1、2，再由本独立审查者定向复跑原输入与相关回归；retrieval/QA/API应另冻结并另找新独立review，不能沿用本批意见签整R05。

**初审 Verdict：fix 1 and 2 first（needs_changes，仅本批范围）。**

## 8dd 定向复核附录 · 2026-10-15T16:30+08:00

主控授权后，干净独立WT切到新分支`codex/r05-vector-foundation-review-1-recheck`的固定`8dd9c73ca4494068e0d83ef5f8db66a1ab409c13`。fd01之后另有文档/日志留档提交，不能把整树差异说成只有三文件；后端业务/测试差异确实只有clients、embedding unit与R02原集成测试，17新增/3删除行。未读取主仓未提交retrieval草稿。新snapshot与初审snapshot分别保留。

**Must1（float32转换后零）：closed。** 标准库`array('f')`与所用pgvector Python0.5.1内部list的float32表示一致；校验已拒绝原`1e-50`输入，保留返回原值/顺序。原独立两维红例逐字复跑通过；原384维PG诊断函数未修改，通过外层`pytest.raises(ModelContractError)`确认其在原validator调用处中止，随后真实PG仍0行。这个诊断在初审先假定校验返回再检查入库结果，修复后直接抛出预期错误是正确结果；它不能作为一个仍然失败的产品断言，也没有改成skip。

**Must2（R02head期望）：closed。** 修复使用Alembic官方ScriptDirectory当前head，所有旧列/unknown/时间/旧事实断言字节保留；原R02三项完整独立复跑通过，不用作者日志替代。

### 新 Must fix

3. **非零float32向量仍能因平方范数退化得到NaN余弦**（`backend/src/ai_intel/infrastructure/models/clients.py:110–119`，P2）。

   - **职责/预期：**共享校验是余弦索引边界。能够保存为非零float32不保证PG余弦距离可计算；不能把会使距离成为NaN的向量交给检索排序。
   - **输入/实际：**修复SHA仍接受`[[2**-149]*384]`和`[[1e20]*384]`。两个值都是有限且可表示的float32，真实PG0.8.2都保存为非零向量，但对自身做`<=>`均返回`NaN`。严格拒绝负例2项实际失败，另外2个直接PG诊断例实际断言非零存储和NaN成功，见`recheck_pg_actual.log/XML`。`[2**-149,1.0]+[0.0]*382`则保存极小坐标的float32位并得到有限0距离，不能一概禁用subnormal坐标。
   - **最小修复：**维持原值/順序，新增对实际float32平方范数退化的输入拒绝；覆盖极小/极大整体尺度与mixed subnormal正例。不静默改为另一模型/空间或归一化返回值。只把double精度平方和转float32未必等价于每个float32乘积先舍入，需用实际PG负例验证。
   - **影响/复验：**不修共享校验通过但余弦排序仍可能出现未定义距离；当前L2 E5输出不是这个异常输入，仍不虚构在线事故。最小复验保留两个明确输入、原下溢输入、mixed subnormal可用和实际PG结果，再跑共享模型/原迁移回归。

定向命令仍由同一证据根封存，所有cwd为固定独立WT的backend，Asia/Shanghai时间：

| 日志名 | +08起止 | 退出/结果 |
|---|---|---|
| `recheck_unit`：原`pytest tests/unit -q` | 16:25:32–16:26:03 | 0；782 passed，0fail/error/skip；60%门保持，66.26%，1既有warning |
| `recheck_pg_actual`：原新vector6+R02三项+T18六项+原独立两维红例+自有修复/scale/PG探针 | 16:27:57–16:28:18 | 1；24 passed/2 failed，0error/skip/deselect；原Must均绿，新Must3两负例红 |
| `recheck_static` / `recheck_mypy` | 16:27:57–16:27:57 / 16:27:57–16:28:08 | 各0；修复三文件lint与75源码mypy通过 |
| `recheck_format` | 16:29:48–16:29:48 | 1；两文件格式通过；embedding unit新两处指数运算空格需按Ruff0.16.9格式化，这是既定检查未过，非业务缺陷 |
| `recheck_cbm_index` / `recheck_snapshot` | 16:29:47–16:29:52 / 16:29:47–16:29:48 | 各0；独立索引1000nodes/4725edges，8dd空Git状态、变更字节与探针hash封存 |

首次`recheck_pg`保留：exit1，29passed/3failed。指定的deselect因外置测试rootdir/nodeid未匹配而没有排除该函数，原诊断正确抛出的异常和两项错误的审查者双精度读回等号比较均失败；未计其为新业务缺陷。查已安装pgvector0.5.1源码确认text decoder保留服务器短十进制`1e-45`，标准库重新表示为float32后的位是`00000001`，存储并未丢值。新的探针v2改用固定IEEE754位比较，并用单独严格scale拒绝红例验证新Must；最后正式命令无deselect/skip，原失败日志未覆盖。

本轮未再次调用真实权重：初审一次真实smoke属于fd01，semantic/helper/PDF在8dd未改变，最新共享validator的unit/contract经过新复跑；不把前一SHA live冒称新SHA live。检索/QA/API、正式质量/性能等未覆盖项仍同初审`not_run`。

**8dd Verdict：fix 3 first（needs_changes，仅本批范围）；原Must1、2关闭，格式检查也须恢复通过。**

## 3ab 最终定向复核 · 2026-10-15T16:34+08:00

收到主控明确授权后，干净独立WT切到`codex/r05-vector-foundation-review-1-final`上的固定`3ab23574298d872350587f273c739397e114c2d9`。相对8dd只有clients与直接embedding unit两文件，20新增/6删除行；其余业务字节不变。仍不读取主仓活跃retrieval/扩充PG草稿，也不签其通过。

**Must3：closed；8dd格式检查：closed。** 代码先把坐标、每个平方表示为float32，再用fsum累计，拒绝非有限/零平方范数及接近上界的危险尺度；使用随维度保守累加裕量。返回仍保存原始值/顺序，没有静默归一化或改变模型空间。原两个严格拒绝红例不改字节复跑通过；`1e-23`逐坐标乘积下溢、原1e-50正负下溢和平方舍入零边界另外拒绝，真实PG均0写入。合法`2**-74`、1、1e17、1e19的单坐标向量读回非零，自余弦都为有限0；mixed`[2**-149,1.0,...]`保留最小float32位且自余弦0。新的限制针对可计算性，未改官方评分/金标/分母或性能门槛。

| 最终独立命令 / 日志名 | +08起止（2026-10-15） | 退出与结果 |
|---|---|---|
| `final_pg`：原vector6、旧独立Must3红例、原PG诊断安全中止、mixed subnormal及新10项scale/零写入/实际余弦 | 16:32:40–16:32:59 | 0；20 passed，0fail/error/skip/deselect |
| `final_contract_unit`：共享边界、semantic unit、T18与semantic合同、既有PDF解析unit | 16:32:39–16:32:45 | 0；126 passed，0fail/error/skip |
| `final_format` / `final_lint`：两次修复涉及的三文件 | 16:32:39–16:32:40 / 16:32:40–16:32:40 | 各0；3文件格式和lint通过 |
| `final_mypy`：独立新cache全src | 16:33:24–16:33:36 | 0；75源码文件通过 |
| `final_code_diff`：`git diff --check 8dd... 3ab... -- backend` | 16:33:36–16:33:36 | 0 |
| `final_cbm_index`：独立cache固定WT backend/src | 16:33:24–16:33:31 | 0；1000nodes/4725edges，无未索引或部分解析文件 |
| `final_snapshot` | 16:34:17–16:34:18 | 0；3ab空Git状态、源码origin、修复diff与独立探针hash封存 |
| `final_e5_target`：主控最新明确要求的单次真实E5 query | 16:35:56–16:35:58 | 0；真实384维1条输出通过修复校验，L2=0.999999957，2.204秒；调用前后active children均0 |

最终逐字argv/cwd、时间、exit、stdout/stderr与XML仍位于同一证据根。`final_recheck_snapshot.json`与`final_recheck_code.diff`分开保留；初审fd01、8dd的snapshot及全部红日志未覆盖。最终只按修复影响范围复跑，没有重复不相关全unit；8dd全unit782/66.26%与原R02三项通过是其明确SHA的既有独立证据。LocalSemantic._embed在共享校验前已有L2≈1检查，该范围离新零/溢出范数边界很远，正常调用路径的126项回归通过。fd01真实权重3项仍只归fd01；最后按主控追加的明确指令，3ab另执行一次真实E5 query target，使用同官方只读缓存、无下载/付费/重排批处理，真实输出通过新范数校验，active child回到0。新增target脚本及receipt hash单独封存在`final_e5_snapshot.json`，不冒称3ab重跑了原整组live。

原Must1、2在8dd关闭且本次未改其迁移/历史逻辑；Must3及format在3ab关闭。没有剩余本批Must/Should/删行建议。检索、QA、API、正式模型质量/性能、人工与全链权限等`not_run`范围同前，本意见不能替代这些后续验收。

**最终 Verdict：Ship（固定3ab23574298d872350587f273c739397e114c2d9，仅本地semantic/shared limits、共享向量边界、0014表基础及依赖锁的本批范围）。** 不写accepted，不push；主控可以据固定SHA/报告登记这一批意见。整个R05和G-B仍须完成真实检索引用回答及另一次独立冻结审查。
