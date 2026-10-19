# R11 集成 API / 迁移 · 原独立 reviewer 定向复核

What this change does: 修复未知字段定位中的相对路径展示和 schema2 占位段的整串绕过。当前 reader 逐段验证全部 typed 来源定位与脱敏 marker，同时保留合法 PURL/Unicode、引用拓扑、不可变历史和原始摘要。

**Verdict: Ship，限本次 M1/M2 locator 展示修复及其默认 API、历史和相关回归范围。** 原25个输入与断言在新冻结树独立25/25通过，原三个真红全部关闭；补充39项历史/typed定位验证也通过。未发现本次修复的遗留可证 Must。旧HEAD oracle和先前R07已知红不被本意见关闭，不签整R11、G-D/G-C、browser/live/manual、OpenVEX/Agent或正式评分。

本 reviewer 仍为非作者 `/root/r11_integrated_api_migrations_independent_review`，未参与修复业务。新建独立 `D:/wt/r11-integrated-api-review1-fix1`，分支 `codex/r11-integrated-api-review1-fix1`；材料HEAD `54f17c9a61d55af5ffe43e58d9252efad6317646`、tree `905511223ab99e15b51f515a51b95f3bd1bb08c6`，业务source `dcbc3d928b26f6755a5bfa71a3b70f71527bd832`。中间9b版本的作者绿不作本复核对象。初始/最终tracked与staged均0；只写本报告和 `reports/runs/recovery_r11_integrated_api_migrations_review1_fix1_20261016/`。未修改业务、母测试、合同、progress、attrs、locks，没有commit/push/accepted或再次spawn。

## 两个 Must 的同输入关闭

1. **M1 相对内部路径键泄漏，已关闭。** 原 `../../private/sbom.json` 与 `..\\..\\private\\sbom.json` 作为合法CDX未知组件键仍通过真实默认POST201。GET200返回稳定 `redacted-field:<原键SHA256>` 和精确 `unsafe_uri_or_path`/None，private/sbom.json不出响应；原raw/所有摘要不改。
2. **M2 schema2单占位段跳过后续危险URI，已关闭。** 原同scope、外层hash/FK完整的新合成历史payload，完整locator为 `/redacted-field:<64个a>/postgresql:~1~1synthetic_user:synthetic_password@db.internal~1private` 且同位置None marker。默认GET现在503，固定错误不回显URI/合成凭据，不关闭trigger、不更新旧历史；不是声称远程用户可任意写PG。

原探针文件 `original_probe_frozen.py` 与旧审原文件逐raw完全相等，SHA256仍 `7e26ef18e236f915447e413784adf8b650b69d257db31afd004a2bebedebd62d`。新wrapper直接导出原test function对象、复用原api fixture，只换自有default_engine fixture为新库/NullPool，保留原所有输入、assert和参数化。`frozen_material_validation.json` 另核母测试函数AST相等；原25没有重新生成或把预期503改200。

`sbom_inventory.py:128` 的JSONPointer分段只接受规范~0/~1转义；`:135` 的字段判断复用最多四轮严格percent/UTF-8，并拒绝dot段、相对/绝对路径、userinfo、控制与URI scheme；合法PURL特判同时拒绝namespace中的 . / ..。`:183`–`:210` 实际枚举当前DTO的7类typed source locator，`:211`–`:222` 校验所有marker定位，`:265`–`:295` 对已绑定占位只跳过该段并继续验证其余段。源码和真实GET支持这个关闭结论，不只依赖作者unit绿。

本审补充21项真实默认HTTP探针，和作者18项历史输入一起39/39通过：component、field_source、checksum、edge、composition、external_document、external_checksum七位置各两种私有路径/数据库URI均503；原current/safe历史仍200且坏行未改；schema1与schema2的同串双占位段保留安全父字段/numeric/Unicode并二次读取幂等；安全PURL两个、Unicode、普通~字段、数字键五阳例保持可见与raw hash。作者18项函数AST原样，仅import指向本审资源fixture，覆盖新/schema1路径、坏schema2先/后危险段、重开读取、幂等、跨租户、raw/hash与日志否定。没有删母测试或把失败改skip。

## 真默认应用与串行资源

测试使用当前 `create_application(settings=...)` 的默认App/build_engine/auth/Inventory router，未patch默认engine或注入业务服务。bootstrap只创建合成用户，之后通过真正 `/v1/auth/login` 验密码取得cookie/CSRF；全为显式synthetic/data_mode=fixture。原权限竞态probe沿用其auth-scope hook，在初次读取后实际改PG角色，用以验证事务入口重核；不是替换engine。首审报告“不替换业务方法”的表述过宽，此处将边界明确为未替换App/engine/Inventory计算路径，认证竞态注入的原输入保持。

所有fixture engine为NullPool，原迁移wrapper只在test模块内替换 `create_engine` 资源池，移除pool_size/max_overflow，不改业务factory。autouse共享failurehook登记真实DSN/password SecretStr及原api随机密码/session/CSRF；测试结束捕获过的自有engine全部dispose。默认生产factory自身池配置未改。默认真API在自有空test DB public正常forward head；其他服务/迁移使用自有随机schema，禁止业务create_all/Table.create，只允许Alembic版本表。没有执行downgrade。

获主控一个重PG槽后，四组**严格串行**：25→39→105→119。每个子进程结束后runner以NullPool只查本库pg_stat_activity、排除本查询连接，剩余连接均0；09:35:23+08:00最后119组退出后已向主控release，不再占PG槽。没有改max_connections、终止他人连接或以FATAL为理由补产品代码。

自有API库 `test_dianzi_r11_int_rev1_fix1_20261016`，迁移空库同名 `_mig`，owner marker和实际创建时间存在本run；随机schema前缀 `test_r11_int_fix1_`。PG16.14/vector0.8.2，授权截止2026-10-17T21:49:15+08:00。仅通过明确pwsh7 subprocess capture在内存解密授权reference的TEST_DATABASE_URL；校验原loopback25432/test_身份后派生新库，DSN/密码不进argv或日志。R12原22用loopback29200随机自有test索引及已缓存本地模型，未下载模型、访问外部来源/供应商/第三方资产、调用付费API或执行PoC。真实外部产品live不因PG通过而通过。

## 本审实际执行记录

日期均2026-10-16、时间+08:00。解释器 `D:/dianzi/backend/.venv/Scripts/python.exe`，cwd本WT/backend，PYTHONPATH/import与MIGRATIONS_DIR断言来自本固定树。完整argv、秒级起止、exit、HEAD/tree、own conn0和secret scan在同label.json；日志与JUnit原件相邻。pytest明确 `--no-cov`，未冒称全仓coverage门。

| label / 实际范围 | +08起止 | exit / 分母与结果 |
|---|---|---|
| original25：`-m pytest -p tests.conftest -p recheck_resource_plugin <test_original_default_api.py> --no-cov -q --tb=short --junitxml=<run>/original25.xml` | 09:29:56–09:30:09 | 0；25/25，0fail/error/skip；own conn0 |
| history_and_independent：母历史18+独立21 | 09:30:55–09:31:16 | 0；39/39，0fail/error/skip；own conn0 |
| original_inventory105：四母source函数的生产0022 wrapper | 09:32:11–09:32:53 | 0；105/105，0fail/error/skip；own conn0 |
| production119：原 forward_assessment、forward_hybrid、forward_schema三个wrapper | 09:33:23–09:35:23 | 0；119/119，0fail/error/skip；own conn0 |
| locator117：新增58＋原privacy33/26三个unit文件 | 09:32:20–09:32:22 | 0；117/117，0fail/error/skip |
| related616：固定作者recipe只换本审JUnit路径，27个原相关文件 | 09:33:51–09:35:43 | 0；616/616，0fail/error/skip；母文件/断言未改 |
| legacy_head_oracle：原 `test_production_chain_has_single_forward_head` 单例 | 09:34:01–09:34:02 | 1；1fail，0pass/error/skip，原HEAD0019期待保留 |
| source_types：`-m mypy --cache-dir <run>/mypy-cache src` | 09:34:09–09:34:29 | 0；146 source文件无错误 |
| source_style / source_format：Ruff check / format --check变更业务+58unit | 09:34:05–09:34:05 / 09:35:21–09:35:21 | 各0 |
| material_audit / material_audit_v2 | 09:31:47–09:31:48 / 09:32:51–09:32:52 | 首1/后0；首轮raw/LF强假设错误，见下文 |
| cbm_audit / cbm_audit_v2 | 09:31:51–09:32:09 / 09:33:12–09:33:57 | 首1/后0；v2十二命令全exit0/isError=false |
| source_evidence：全caller/default/DTO/protected diff/hash | 09:35:16–09:35:17 | 0；保护范围及staged0 |

117与616共享旧59，不能相加为733个新输入；PG各组也不汇总成评分或整R11分母。105包含既有privacy与JSON/CSV导入/历史/权限、10000组件原输入；119=原48assessment+22R12+49schema/history，实际前向0/已填0019/0020→0021→0022、完整FK/trigger/partial unique、immutable历史、rollback/replay/concurrency与原文/current核验，不把局部metadata建表当生产迁移。新修复无DDL，七表源码和迁移与6a无变化。

旧硬编码HEAD合同 `test_r11_r08_forward_migrations.py:49` 仍期待0019，而批准迁移head为0022；本审单独实际复跑仍红，没有修改/skip或算进616通过组。首审原R07 NVD oracle partial vs failed及3次离线mock wire的观察，连同旧报告/200制品原样保护，本定向复核未再跑R07，不以privacy Ship关闭其失败或签G-C。原R07验证仍是首审记录范围。

## 冻结材料、AST和源码身份

作者artifact_manifest的188项逐size/raw SHA全部核验；其中187项从 `evidence_exact_raw.tar.gz` 的原字节只读核对，剩余项为archive文件本身，未解压到作者目录或运行其封存runner。manifest raw SHA256 `39feefefb9c3884b911f4c50ed442276a26256f1c3b015a504fbf49ca3c30cfe`，tar SHA256 `37f993007648b6bdebe436aee68ed5e0a2239821d1f181194f3fe7e5a5f2873c`，报告原文 `fc711954f276b0d16676249991bb90a8f800c3c058635047d44a1a1d64ed2684`。所有FATAL/首红、作者修正与串行最终绿均保留在该原包，没有用最终绿抹去资源失败。

业务只改 `sbom_inventory.py`、新增58unit；dcbc与54f这两source/test Git blobs逐byte相等。源码Git LF SHA256 `416a166f46237513761db0dc1952af4a272fc0bdfdabdefc81a3d2597507a19d`；作者实际源码raw CRLF SHA256 `8cbf5e41291cd1e2830498c82041d8d6e89dafeb1b6b9b5d4619bda77f59a2ee`，455个CRLF，LF规范化后精确相同。新unit raw/Git均 `baf2a45b9b14d408dd8ab01ff1990898d8940d3cc00b4cb9727db44a120276a4`。不把raw和GitLF说成同一hash；本审fresh checkout执行的源码与归档raw/提交语义均有独立绑定。

本审material_audit首轮自行错误地要求rawarchive源字节直接等GitLF，在188原成员已核成功后该断言失败；保存v1 script/log/exit1，依据实际source_proof的两种字节表现修正为分别记录raw/Git并核LF相等，v2全部成功。这是审查工具假设错误，不是作者偷偷改业务或放宽产品断言。

旧审 `D:/wt/r11-integrated-api-review1` 的200manifest成员逐raw重新核验，旧报告 `b8bb314bfe19ca6f70038e4302b05b376de0ba02b5e63c2335ffe7ccd1fb13ca`、旧manifest `9a2d2cb51f4cc78b46fc1afb0b625a308b3114522afc55d9f7e49f9c41cf3fd0` 与原seal相等。旧25probe、3真红、审查工具红、原R07/旧HEAD红全部未覆盖。母25、作者历史18与原库存wrapper三组的test函数AST相等，实际输入/期待来自母文件，不用被测输出生成预期。所有保护范围diff为空，没有改金标、阈值或计分分母。

## CBM、typed DTO与兼容

在本固定工作树建独立project `r11-independent-fix1-54f17-dcbc-src-20261016` 与 `...-assets-20261016`，schema、architecture及trace均保存命令/原输出。source1819nodes/9955edges，明确默认excluded assets，另窄assets263/1180，not_indexed/skipped/parse_partial/parse_unusable均0。v2实际十二命令exit0/isError=false，trace核default create_application、inventory router、safe sidecar/field/snapshot/history。第一轮错误在默认source索引查询被排除的assets工厂，function not found；原输出保留，移动到窄assets后同caller得到trace。没有以图缺边声称caller不存在。

当前完整 `sbom_inventory_contracts.py` 与source/route均保存到 `current_typed_dto_and_locator_source.txt`；全source/scripts/frontend rg确认import/freeze、新current比较、历史GET及所有snapshot/list/history安全投影caller。七类typed locator和redaction、unmapped域都独立检查，没有新增DTO/公共schema/认证字段。非SBOM `safe_sbom_snapshot` 仍原样返回；JSON/CSV原导入、响应、历史和PURL兼容由原105及原25直接复验。没有借此次新增文件export/OpenVEX、规则API、worker重判或前端SBOM能力。

新增业务helper都有类型及职责docstring，未引入Any/cast/ignore、依赖、万能抽象或原文重解析。原raw/fullJSON/combined/projection摘要、immutable payload、current选择与typedreason未改；旧schema1安全展示，坏schema2固定503，合法schema2双占位幂等。这些是展示边界限定结论，不扩大成任意业务自由文字的秘密检测。

## 安全、状态及未检查

真实DSN/密码原字节扫描覆盖本run/报告和封存source/author归档原成员/旧review包，结果0匹配；登录秘密通过原共享failurehook登记，JUnit/失败报告不暴露真实授权值。可再生mypy/__pycache__不作为交付材料；manifest成员逐size/raw SHA复核。自有resource marker、prefix与固定版本已记录，未改他人资源或全局连接上限。

任务编号R11定向独审；审查建议limited Ship，状态由root登记，reviewer不改accepted。评分证据仅F2/F3的历史/定位/hash/权限与E1/D1真实回归/材料绑定；无P2/P3正式指标、真人产品真值或全阶段评分。

未检查：整个R11/T24/T27/T28/G-D/G-C、真实外部来源/模型/FOFA、UI浏览器、live/manual、OpenVEX/Agent/T36调度、人工资产完整性/金标、正式准确率、吞吐/SLA/持续运行和生产恢复。当前root后续集成树需自行重核source/blob一致及相应有界回归；本意见不代替阶段验收。

下一步建议root按固定dcbc/54f证据集成该最小修复，保留旧HEAD/R07与所有资源首红，再安排尚未验的真实工作台/API全链。不重开旧children或推进下一任务。

本review run manifest SHA256 `583f2188448c18f22d41d75853c3262a72739d77702082e316777ea6e89b6540`；本报告raw SHA与真实+08写作起止由 `review_seal.json` / `report_write_receipt.json` 单独记录，避免控制文件自引用hash。

**Verdict: Ship — 仅M1/M2 locator修复和本报告实际默认API/历史/PG回归切片。Not checked：整任务/阶段、browser/live/manual、真实模型/来源、人工/正式指标、OpenVEX/Agent/T36及生产运维恢复。**
