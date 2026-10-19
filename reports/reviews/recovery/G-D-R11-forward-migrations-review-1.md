# R11 / G-D 0021–0022 前向迁移 · 第一次独立审查

What this change does: 普通 Alembic 前向链新增六张规则/研判历史表和一张 SBOM sidecar 表，沿用已冻结服务的列、外键、检查、索引和不可变约束。旧数据不回填、不重新解析；不可变历史迁移明确拒绝删除式 downgrade。

**Verdict: Ship — 仅固定生产 0021/0022 迁移及其直属测试/资源适配切片。没有发现需要阻断该切片的可复现缺陷；不签整 R11、T24/T27/T28、G-D 或完整 SBOM 产品链。**

文稿实际开始写作：2026-10-16T07:56:32.5888347+08:00。下述检查日期均为 2026-10-16，时间为 +08:00。本 reviewer 为新非作者，没有参与实现；新建干净 `D:/wt/r11-forward-migrations-review1` / `codex/r11-forward-migrations-review1`，从固定材料提交检出，未审作者活动目录。初始 tracked status 干净；最终保护范围 diff 为 0。仅新增本报告与 `reports/runs/recovery_r11_forward_migrations_review1_20261016/`，不修改业务、作者测试/期待值、公共合同、progress、accepted、锁文件或推送。

## 固定版本、前置与依据

baseline `ed0e14a03a06ed104f23afd0be5407d873ed8edf`；作者 code `2fe903eaff4030b64b3f5789e8027e1e11e41694`；材料/审查 HEAD `569d8a7dc81fcea6b524b4fa172a5c7977388b93`。0021 的六表及五个服务模块逐 blob 等于已限定审查的 `6b10f2c4ed013f4375d51fc31e1cb317409730ac`；SBOM metadata 保持 baseline，即主控冻结 `0532c4f58611e068fc7d5b03da984bc57dbad9f2` 的 seam，不改变导入算法或其 API。解释器仅复用 `D:/dianzi/backend/.venv/Scripts/python.exe`；插件在每次 PG pytest 初始化断言实际 `ai_intel` 来自本 WT/backend/src、MIGRATIONS_DIR 来自本 WT/backend/migrations。

读取 AGENTS、00 执行地图、恢复 R11、T24/T27/T28、03/04/05/06 合同、固定 progress/handoff、作者 CR/任务报告、SBOM seam 和 PG 规则/研判提案，以及 Ponytail Review 5.2.0。固定 progress 的旧 pending 索引不作为源码或测试证据；本轮不代主控更新状态。

0020 前置独审报告 `D:/wt/r12-production-review1/reports/reviews/recovery/G-D-R12-production-migration-review-1.md` raw SHA256 实核为 `89579f9db93b36a48154ef6f8f301ad0fcabe1882e855bd91cad5f06c4559edb`。其实际 `review_manifest.json` SHA256 为 `cb27ac0e914a48a4d49587b144b0d46b855f25d031f324e4bc4f8b8c65ac3bd6`，113 members 逐 raw 核验 0 失败；review_commit=null。副本保存在本 run，Ship 只代表该报告限定的 0020 切片，不代表整 R12/G-D。本次结论来自当前固定树的独立复跑。

## DDL、真实调用与业务边界

`backend/migrations/versions/0021_condition_assessments.py:10` 依赖 0020，`:15` 只创建六张新表；`:57` 保留 rule_id 上 `status='published'` 的 partial unique，`:191`/`:214` 两函数及六 trigger 与冻结 metadata 一致。`:149` 的 asset/tenant/snapshot 复合外键、rule/version 外键和执行唯一键，均通过实际 PG 反射和拒绝输入核验。触发器阻止内容改写、删除、生命周期倒退及已经写入的 published_at/published_by/retired_at 变化；不把触发器误称为完整语义审批或 ACL 检查。

`0022_sbom_sidecars.py:10` 依赖 0021；`:29` 的三列外键精确绑定已有私有快照，`:31`–`:36` 保留版本/租户长度、两个小写64位 hex hash 和 JSON object 检查，`:42`/`:46` 拒绝 UPDATE/DELETE，包括 no-op UPDATE。七表全部无默认值、没有旧表 ALTER/DML、没有业务 metadata 导入；普通生产建表不依赖 create_all。`:53` 与 0021`:251` 明确拒绝删除不可变历史的 downgrade；本轮不执行 destructive downgrade。

生产反射保存于 `seven_table_reflection.json`：七表所有列/类型/nullable/PK/FK/check/unique/index，三函数、七 trigger 的真实定义和 schema。新增 namespace 探针在已存在同名 public 生产表的自有库中，仍确认每个新 FK 的父表都在本例自身 schema，函数/trigger 也落在同一 schema；没有从 public 回退来冒充迁移成功。中间 0021 只增加六表与两函数，0022 后才出现 sidecar 与第三函数，stamp 顺序正确。

连通源码复核 `AssessmentService.commit:198` 与 `read:325`：真实认证上下文、准备收据完全相等、原资产字节/hash、完整 source roster/原文对象/输入摘要、完整 scope map 和资产 current 均保留既有检查。新探针使 tenant epoch 改变而 public epoch 仍为 null，旧结果读取/重放均为 stale，原历史行不改；资产 current 换为修复边界也不会把旧执行身份复活为 current。复杂父链/权限仍由已冻结服务验证，没有通过新增 DDL 静默补强或改写合同。

**默认产品接线仍未完成。** 独立 src 全量 rg 中 RuleService/AssessmentService 只有定义与模块内部使用，没有默认 API/worker 构造调用；sidecar 只在 metadata 模块定义。`api/app.py:124`–`:137` 未挂资产/规则/研判 router；`assets/inventory_routes.py:171/220` 仍调用 JSON/CSV `import_manifest`，该独立 router 尚未挂主 app；`workers/runtime.py:98` 的 handler 未注册规则/研判或 SBOM 消费。新增 DDL 可部署性不能签 SBOM importer、sidecar-only 重判、正式 App/browser 或 worker/API 闭环。这些缺口符合此次 CR 的有界范围，列为未验产品能力，不作为本切片猜测式 Must。

## 独立真实测试与新增输入

入口 `review_checks.py` 记录完整 argv、cwd、精确起止、退出码、超时、stdout/stderr 和实际敏感值扫描；所有 pytest 使用本 WT/backend，明确 `--no-cov`，不冒充全仓覆盖率门。原作者三份生产 adapter 原样运行，`review_resource_plugin.py` 只在内存把 owned fixture 的 DB/run/schema 常量改为 reviewer 自有值，且先验证 host/port/用户名/库/名称上限。原 guard 源码与全部业务函数、原输入、断言字节保持不变。

| label / 实际参数概要 | +08 起止 | exit / 真实结果 |
| --- | --- | --- |
| pg_regression：`-m pytest -p review_resource_plugin tests/integration/test_r11_forward_assessment_regression.py tests/integration/test_r11_forward_hybrid_regression.py tests/integration/test_r11_forward_rules_sbom_schema.py --no-cov -q --tb=short --junitxml=<run>/pg_regression.xml` | 07:48:07.051750–07:49:48.966750 | 0；119 passed，0 failed/error/skip，pytest99.64s |
| pure_regression：新增迁移合同及原 scope/contracts、T26、分支版本、manifest/identity/time、T27、condition schema/security 十文件，完整 argv 在 receipt | 07:48:16.939185–07:48:21.974714 | 0；371 passed，0 failed/error/skip，pytest2.40s |
| independent_pg 首轮：外部新 probe，显式 `-p tests.conftest -p review_resource_plugin` | 07:51:43.474851–07:51:54.193816 | 1；18 passed/2 failed，0 error/skip；两个 probe 假设错误见下文 |
| independent_pg_v2：纠正自有 probe，仅暂不重复已成功的一次性空 public 库输入 | 07:52:42.483851–07:52:54.352050 | 0；19 passed，1 deselected，0 failed/error/skip |
| independent_pg_final：格式/SQL 字符串分行后再跑同19项 | 07:55:43.808363–07:55:57.556808 | 0；19 passed，1 deselected，0 failed/error/skip，pytest11.29s |
| mypy：`-m mypy --cache-dir <run>/mypy-cache src` | 07:52:09.975936–07:52:26.386032 | 0；135 source files 无错误 |
| production_quality / production_format：`-m ruff check` / `-m ruff format --check` 两迁移与五直属测试/fixture | 07:52:09.972935–07:52:10.175629 / 07:52:09.977935–07:52:10.186073 | 各0；七文件通过 |
| material_audit_v2 | 07:50:39.795763–07:51:48.811831 | 0；147 source、115 artifact、393旧文件、9个冻结 PG source/test、113前置成员实核 |
| inspect_final / protected_diff | 07:56:07.134423–07:56:08.227196 / 07:55:53.587215–07:55:53.695240 | 各0；36自有 schemas/80，真实反射和保护范围无修改 |

119=原33+raw修复15+R12原22+新增迁移/历史/安全49；371=原366+新增迁移合同5。本 reviewer 新增20个 distinct case：首轮成功的独占空 public 数据库正常 head 输入1项，加最终19项；空库已形成历史后不清库重跑，所以明确 deselect 该一次性输入，没有 skip 或删题。总共510个 distinct 已通过输入；首轮失败与重复的成功轮次不累计。`test_result_summary.json` 保留每份 JUnit 的真实统计。

新20项覆盖：自有真正空 public 库普通迁移且禁止 metadata 建表；0020→0021→0022 的真实 namespace/FK/function/trigger/order/stamp；正常 Alembic 链执行到 sidecar 表创建后注入中断；candidate 不能跳到 published/retired；published 内容和时间/审批人 write-once；retired 不能复活或改退役时间；第二 published 的真实23505以及旧 retired 与新 published 并存；资产 current/tenant epoch 改变后的历史/重放 CAS；伪造准备收据；他人租户读取；sidecar 版本长度/JSON null；存在的 snapshot 与错误 asset 配对复合 FK。

新中断探针经普通 `run_migrations(head)` 执行，不手工 stamp 成功：在0022建表后抛出显式 synthetic RuntimeError，整个本次 upgrade 的0021/0022表、函数、trigger 和 Alembic stamp 回到0020；旧表全部排序 `to_jsonb(row)::text` 逐行相等。随后正常 forward、重复 head、dispose/新连接后再次比较，保存 `independent_normal_upgrade_rollback_restart_*.json`。原49项的已填0019/0020历史也独立通过，所有旧表 count/hash/rawJSON保持，BYTEA 的 PG 十六进制表示包含在逐行比较中，0020四张派生表实际有行；没有用空表对比替代已填历史。

原48的原文缺失/损坏、Unicode span、来源 roster、ACL/角色/撤销、四态、完整输入当前性、事务失败和并发 publisher 均由未改的函数/断言在新生产 head 下复验。原 R12 22 包含本地已缓存 E5/reranker 的真实小样例，未下载新模型或调用 provider，不计外部 live、正式准确率或完整回答 SLA。PG 与独立 probe 保留第三方 Starlette/httpx 弃用 warning，未为此改依赖。

## CBM 与独立索引

先执行真实 `cli --help`，再用官方 WSL 可执行文件 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 的 `cli --json` 建新 project `dianzi-r11-forward-review1-20261016`。src index 精确指向 `/mnt/d/wt/r11-forward-migrations-review1/backend/src`，fast/persistence=false，07:49:41.706203–07:49:47.911207完成，1701 nodes/9142 edges；工具 excluded assets/cache，因此另建 assets 精确索引，236 nodes/1039 edges。两索引的 not_indexed/skipped/parse_partial/parse_unusable 都为0。

schema、architecture、Assessment.commit outbound/inbound、Rule.publish outbound/inbound、run_migrations inbound 和 Inventory.import_manifest inbound 均实际 exit0，最后 trace 于07:50:18.914121结束。commit outbound48与 publish outbound14支持认证→锁→源文档/CAS核验→PG写入的源码追踪；inbound0本身不证明无默认调用，另以全 src/scripts rg及真实 app/worker/router 源码确认上文接线限制。CBM不索引 migrations 的事实不用于证明迁移；迁移来自真实 Alembic/PG执行。

## 材料核验、原红与 checkout 字节

作者实际 source manifest为 `reports/runs/recovery_r11_forward_rules_sbom_20261016/source_manifest.json`，raw/blob SHA256同为 `2313a8dde79fb36d256601f7c3d8f8cc83d2153b02c4eb7ef34ecac1d00b19b0`，147条逐 code blob、blob ID/SHA核验0失败。actual artifact manifest为同目录 `artifact_manifest.json`，raw/blob SHA256同为 `661680ed977904520c8951377da9592aef5a28b0cd22c7eccf1a3a04397f7b28`，115条逐材料 Git bytes/size/hash核验0失败；没有猜文件名或用作者当前未提交修改背书。

作者任务报告固定 blob SHA256 `b5430e90a233104a1213c71fe0a8ebdc45a4f3c8b6709bdd6007d42ed5c73965`；本 checkout raw SHA256 `839a59a5b6b5d533060a64232269c703d2df30c7044c60f0be5be39668e83519`。源码/新文件有8项 raw表现不同；材料有2项不同（run局部.gitattributes、任务报告），均 CRLF→LF 后精确等于固定 blob。raw、Git blob与LF分别登记在 `material_validation_frozen.json` / `checkout_byte_observation.json`，固定报告blob另存；不误报 checkout115项 raw全同，也未修改作者文件。

baseline已有 backend/src、migrations、tests、backend pyproject/lock、contracts/config 共393文件逐 blob 完全不变，包括旧0019/0020和SBOM metadata；五 PG 服务与四 PG 测试逐 `6b10...`冻结保持。最终 protected_diff exit0再次确认审查未改这些范围。原测试原断言未改、没有gold/holdout读取或阈值/分母变化。

作者 contract_red=5业务合同失败、assessment_pg=48 setup errors、schema_pg_extended=48pass/1fail的原XML/日志都在115份冻结材料中，逐hash保留。assessment红是Table.create guard误拦 Alembic版本表，业务函数未执行；extended红是非法visibility同时触发tenant XOR而期待名过窄。此次119重新通过不抹去这些历史，不计红→绿为额外成功输入。

本 reviewer material_audit首轮错取前置manifest的 entries 字段，实际为 members；已有147/115/393核验并无差异，最后113计数断言失败。保留原脚本 `.py.txt`、exit1日志和receipt；同时修正自有输出文件与command receipt同名的碰撞，最终详细证据单独保存为 `material_validation_frozen.json`，不覆盖原红日志。新 probe首轮误把旧迁移已存在的三函数也当新增、误写scope_epochs.knowledge_epoch（实际epoch），保留v1完整bytes/18pass2fail XML，修正后与最终19项复跑均绿。没有消减业务断言或把错误改skip。

自有审查脚本初Ruff113问题、自动fix后102、format后11，主要排版/import和长SQL字串，原日志保留；后新增封存脚本有1个import顺序问题，同样保留exit1再修正。仅改自有脚本，最终七文件Ruff/format通过，无新增全局ignore。局部.gitignore仅排除可再生mypy-cache/__pycache__；局部.gitattributes只保护review raw材料。初期只读命令误读三个不存在的猜测路径，工具exit1保留，随后经rg找到真实合同/router/app路径；未保存磁盘receipt的早期只读核对不补造时间，也不算测试红。

## 资源、安全与未验范围

唯一自有库 `test_dianzi_r11_forward_review1_20261016`、RUN_ID=`r11_forward_review1_20261016`。私有资源reference经明确pwsh7、`-NoProfile` subprocess capture在内存解密，只读取TEST_DATABASE_URL；先验证原127.0.0.1:25432 / test_dianzi_r01_20261014 / test_用户名，后创建review自有库。库名≤63、RUN_ID≤47，截止2026-10-17T21:49:15+08:00；未复用作者库或硬编码DSN。

PG真实16.14、vector0.8.2；自有schema前缀 `test_r11_forward_review1_`，最终36/80，122231831 bytes，保留供复现。public迁移同样只在此review自有库，不是共享基础库。statement15s、lock5s、connection5s、command300s；没有服务/端口/ACL更改、flush、旧库写入或删除式downgrade。R12回归只用loopback29200的自有随机 `dianzi_test_r11_forward_` 索引且逐例删除200/404；未查全局索引列表，因此不声称他人资源零残留。Redis、源采集库不操作。

所有外部probe显式加载共享 `tests.conftest` failure hook，并逐例注册动态DSN/密码 SecretStr；pytest失败报告和JUnit写前脱敏，runner捕获后再脱敏。最终 `actual_secret_scan.json` 对本review报告/run、作者147源码/115制品、393旧文件的raw以及262固定Git blobs扫描实际授权密码/DSN，必须0匹配才封存。秘密reference内容不进入源码、argv、日志、提示或报告。0付费API/provider/source调用、0第三方扫描/PoC/利用；未知费用上限下没有开启付费批量任务。

unit/contract及上述PG/OS integration/security只对本切片 passed；frontend/e2e/browser/live/manual not_run。未验真实SBOM导入接线和sidecar-only变化重判、正式App/browser、OpenVEX、T36调度、Agent、真人金标、三→五产品真值、正式准确率/召回率、完整问答/吞吐/SLA、连续监测、生产部署和灾备恢复。已测试的事务中断回滚不能充作生产运维恢复或允许删历史。

合同与计划偏差：未发现此次静态DDL偏离冻结合同；上述probe/材料检查修正是审查工具错误，不是产品门槛或业务合同变更。F2/F3/E1仅有规则/资产历史可追溯存储、事务/current边界和可复跑前向迁移证据，不推断官方评分档位、P2真人准确率或A1真实Agent。

下一任务建议由主控另行冻结：SBOM正式InventoryService/importer、sidecar-only变化/new snapshot/epoch/outbox及默认API/worker接线；按原T卡补真实App/browser、OpenVEX与人工/外部实测。本review按单一有界切片停止，任务状态由主控依据本报告登记，reviewer未改accepted。

**Verdict: Ship — 仅固定0021/0022前向生产迁移切片。Not checked：整R11/T24/T27/T28/G-D、SBOM正式产品接线、App/browser/live/manual、OpenVEX/Agent/T36、真人gold和正式性能/评分、生产运维恢复。**
