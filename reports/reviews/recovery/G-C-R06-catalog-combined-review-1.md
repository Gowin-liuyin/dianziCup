# G-C / R06 公共资料持久化与前向迁移夹具最终组合复核 1

What this change does: 本组合固定九个公开来源的身份及八类分类，增加非漏洞资料的原文、修订元数据与只读 DTO，并使用版本化 0013 旧种子恢复前向迁移回归。它保留来源文本和历史身份，不据此创建漏洞结论，也不把内部接口测试当作整张 R06 验收。

**限定结论：Ship。未发现本冻结组合需要先修复的新 Must fix 或 Should fix。** 资料持久化内部切片与测试夹具可供主控装配；本报告不修改任务状态、不签整 R06 accepted、不 push。R06 整卡、七来源 worker/API、真实来源和完整资料工作台的验收保持其现有未完成状态。

## 冻结、授权和独立性

- 被审 SHA：`84301979920bbae7ff0074ebc5a0633f9b31747a`；tree：`54b0d3ee356422e7932e173dbabb452fbfac4281`。
- 基线：`1927eeb00a7e0c1335f76340b0382f46102f08f2`。独立 detached 工作树：`D:/wt/r06-catalog-final-review`。通过 `git worktree add --detach D:/wt/r06-catalog-final-review 84301979920bbae7ff0074ebc5a0633f9b31747a` 创建。
- 我未参与本组合实现。原 `D:/wt/r06-integration`、主仓既有未提交修改及旧独立报告均只读；旧报告只用于定位历史红例，不直接继承其通过意见。
- 审查输出仅本报告、自有 `reports/runs/recovery_r06_catalog_combined_review_1_20261015/`。主控另明确授权本 WT 离线冻结 venv、专用新测试库与仓外归档自己的合成临时文件；未改业务、迁移、旧测试、合同、状态、金标、分母、阈值或分类器。
- 已读 AGENTS、执行地图、R06 卡/恢复计划、03/05 合同、状态/交接、`CR-R04-R06_document_read_api.md`、作者两个任务报告、新版 Ponytail 5.2.0 review skill。当前卡要求来源广度/增量/回补/时效；本次只检查已授权的内部保存与兼容切片，没有删掉整卡其余条件。

审查范围为 `source_catalog`、`catalog_documents`、来源注册、`save_document_revision`/模型元数据、0015、资料 DTO、新 21 项 PG、原 vector/question 35 项及旧 0013 种子。报告初始准备在 2026-10-15T20:10:01+08:00 后开始；正文整理始于 20:24+08:00。精确执行时刻见逐命令记录，最终封存时刻及 SHA256 见 `seal_manifest.json`。

## 已证实的行为与边界

1. **失败页没有可提交的首项资料。** 0015 当前代码在 `catalog_documents.py:179` 开始整页 `session.begin_nested()`，资料、blocks、evidence 与 epoch 均在其中。独立探针使第二成员存储抛 `OSError`，在调用方捕获错误后仍正常提交父事务，再从新连接读取：documents/revisions/text_blocks/evidence/epoch 均为 0；只有调用方在 savepoint 外登记的响应对象仍为 1。原 21 项同类断言也通过。对象存储中可能留下未被数据库引用的内容寻址对象，本断言不伪称外部对象存储支持事务回滚。
2. **URI 和身份边界按冻结规则拒绝。** 整页预校验拒绝敏感 query、字面 DEL、超长 URI、userinfo/fragment/外域与错误类别。独立第二成员负例额外覆盖 percent 解码后的 `%61ccess_token`、大小写 `PASSWORD`、DEL 和恰好 2084 字符；即使捕获错误后提交，资料行仍为 0。2083 字符合法 URI 实际保存成功；含 DEL 的 `source_record_id` 被拒绝，已有合法修订不变。原 21 项的 long_uri/del_identifier/sensitive_query 也通过。
3. **JSON 类型变化与数字重放均正确。** `revisions.py:144–158` 对显式 metadata 用 PostgreSQL JSONB 相等判定；没有自写浮点规范化器。当前 21 项覆盖 true→1→true、1e16、1e20、-0.0；独立探针另在 1e20/-0.0 上组合 true→1→true 与相同输入重放。实际得到三历史版本、布尔/数字/布尔三种原类型、仅末版 current、epoch=3，重复投递新增数为 0。数据库直接把 metadata 更新为数组时拒绝，原对象保留。
4. **历史、权限和并发有实际断言。** 当前 21 项完成 A→B→A、URI/来源发布日期/修订日期变化、重复采集、同一成员两线程投递、viewer/tenant_admin 发布拒绝、原文字节与永久证据 hash/坐标校验。保存证据 `supports_claim=False`，论文没有创建事件。独立来源注册探针确认已存在来源名字冲突和未知 kind 均拒绝，没有覆盖已有身份。
5. **旧 writer 的 head 行为仍可用。** 独立探针直接在 0015 调用原 `persist_source_response`，相同原 vLLM fixture 两次实际经过旧发布链，新增修订数为 `[1,0]`、revision_id 相同、metadata 为 `{}`。旧 `revision_metadata=None` 的语义保持。该结果不要求当前产品代码在旧 0013 schema 上运行。
6. **0015 是前向加列迁移。** 新 JSONB 列非空、默认 `{}`、对象约束；旧正文/hash/证据身份不被重写。未执行 downgrade；其代码明确拒绝删除历史字段。独立迁移检查实际走新 UUID schema→0013→非空旧数据→0015。
7. **DTO 测试通过，不延伸成 HTTP 验收。** 当前纯门包含新 DTO 的日期精度、必需 null、kind、列表/说明/许可边界、证据 revision/data_mode 一致性与总数负例。DTO 没有数据库投影、鉴权路由或游标实现，本报告不把这些单元断言称为资料 GET 已接通。

负例输入和可复跑断言位于自有 `test_independent_probes.py`；最终有效独立 PG 数为 **11 个不同案例**：原边界 9 个、旧 writer 1 个、来源注册冲突/未知入口 1 个。不把修复审查脚本错误后的重复次数累加成更多测试。

## 旧种子、白名单和全表前向等价

独立 `verify_seed.py` 对版本化 seed、旧 writer 五个模块、来源/响应及实际 ContentStore 对象分别校验。旧模块物理 SHA256 与作者 manifest 一致，CRLF→LF 后与 Git 基线 `1927eeb` 对应源码逐字节一致；并未依靠作者口头声明确定来源。原 question PG 文件 Git blob 相对基线不变；vector 全部 `test_*` AST 相对种子修复前 `7b8103e` 不变。相对最初 `1927eeb` 唯一改变的原测试函数是升级测试：要求 head 为 0015 并新增旧 metadata `{}` 断言，原版本/证据检查没有降低。

固定 seed LF SHA256：`6170ce55e63a70a557f62fc79213d20b596222220e2a04d5e050e67b7e188336`。源 fixture SHA256：`f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf`；原响应 body SHA256：`ed8547c71c74f9fe73edef9de024dd8603d76ae1f80b9c8afff53b3aaa874ba9`。内容对象另一个 hash 为 `b0571da15760e3d42c130f3b9662ff4afebfdddd973aaf0b8c696aaecd25910b`。Loader 逐个校验 payload/hash/长度，并在临时 ContentStore 写入与读回真实字节。

实际白名单 **19 个非空表、154 条旧行**：sources1、content_objects2、documents1、document_revisions1、text_blocks126、evidence2、events1、event_external_ids1、event_documents1、claims2、claim_assertions2、claim_evidence2、claim_status_history2、scope_epochs1、change_events2、job_runs2、outbox_events2、publication_receipts2、fetch_attempts1。无 users/auth/session/secret 表；seed 中所有 tenant_id 为空、visibility/scope_key 为 public。

独立运行于 `test_r05_review_seed_bbca599f976c477a994b263a4483ff34`，迁移 search_path 仅该 UUID schema；运行时允许该 schema,public 以解析扩展，且先确认本地 version 表 namespace。升级前后按每表主键排序，对全部 19 表的全部旧列和 154 行逐项相等；旧 evidence 两行非空且 ID/hash 保持；新 metadata 为 `{}`、最终 version 为 0015。另实际证明 public schema、被修改的 seed、被修改的来源、非空旧 schema、已升级 head schema均被 loader 拒绝。8 项自检全部通过，详情见 `seed_independent_verification.json`。

本次未重新执行旧 writer 导出；实际核验了冻结 seed 的来源代码/hash、输入/对象 hash、白名单/范围和当前前向加载/保留行为。作者首次导出漏 job_runs、GeneratedAlways 红例及原失败日志仍保留在目标提交，没有被本报告抹除。

## 独立调用图与源码交叉核对

使用 WSL 官方 `codebase-memory-mcp 0.11.0`，自有 cache `/tmp/dianzi-cbm-r06-catalog-combined-review-1-20261015`、project `r06-catalog-combined-review-1`，只索引本 WT `backend/src`，没有读取作者 cache、测试、holdout 或 vault。fast 索引 **1117 nodes / 5416 edges**；not_indexed/skipped/partial/unusable 均 0；schema 返回 29/29、has_more=false。

三条 both/depth2 trace 覆盖 revisions、catalog persistence、source registration；与 `rg_callers.log` 逐项对照。`save_document_revision` 的直接 caller 是原 `_persist_member` 与新资料保存；旧 `persist_source_response` 为第二跳。注册调用来自原保存函数、source route 与 source job；后两者图工具使用 file-level heuristic，源码确认实际函数。`persist_catalog_documents` **产品 caller 为 0**，`build_catalog_request` 也未装配入产品采集链，因此不能由九个注册项推导九通道工作进程已接通。

保存流程使用既有内容寻址/事务 hash 锁、父文档行锁、不可变修订与证据校验；公开 epoch 使用 PG 原子 upsert。没有新依赖或万能 service/repository。本次负载假设为既定单页≤100成员与普通来源轮询，多线程同一成员实测通过；未认证最大页面或反向成员顺序混合压力性能。

## 实际命令、时刻和结果

除准备只读命令外，完整 argv/cwd、真实开始/结束 `+08:00`、退出码、code SHA、stdout hash 在自有 `commands.jsonl` 及同名 `.json/.log`；JUnit 保留测试数。下表命令均 cwd=`D:/wt/r06-catalog-final-review/backend`。纯门不授予 PG 环境；PG 只显式选受核验文件，没有 umbrella PG 测试。

| 日志 / 核心命令 | 开始—结束 (+08:00) | 实际结果 |
|---|---|---|
| create_review_database / 自有脚本执行固定 CREATE DATABASE | 20:12:32—20:12:33 | exit0；创建唯一 `test_dianzi_r06_catalog_final_review_20261015`，不删库 |
| original_35 / `pytest tests/integration/test_r05_vector_persistence.py tests/integration/test_r05_question_api_pg.py --no-cov -q --tb=short` | 20:12:50—20:13:49 | exit0；35 passed，54.46s，0 fail/error/skip |
| catalog_21_recheck / `pytest tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --tb=short` | 20:13:33—20:13:55 | exit0；21 passed，20.47s，0 fail/error/skip |
| pure_regression_clean / `pytest tests/unit tests/contract tests/security -m 'not real_pg' -q --tb=short` | 20:17:10—20:18:53 | exit0；1450 passed、10 deselected、0 fail/error/skip，98.29s；原 `--cov=ai_intel`/60% 门，实际73.90% |
| probes_independent / 显式自有测试文件，`--no-cov` | 20:19:53—20:20:04 | exit0；9 passed，9.33s |
| probes_compatibility / 显式两个函数，`--no-cov` | 20:22:23—20:22:28 | exit1；旧 writer 1 passed；注册 probe 1 failed（审查脚本导入位置错误） |
| probes_registration_recheck / 仅失败的注册函数 | 20:23:02—20:23:05 | exit0；1 passed，1.92s；只修自有探针 |
| seed_independent_recheck / 自有 `verify_seed.py` | 20:19:53—20:19:58 | exit0；8 自检、19表154行/旧列等价 |
| ruff / `ruff check src tests` | 20:14:31—20:14:32 | exit0 |
| mypy / `mypy src --cache-dir=自有run` | 20:14:32—20:14:41 | exit0；85 source files |
| format / `ruff format --check src tests` | 20:20:34—20:20:34 | exit0；196 files |
| product_diff_check / product/test/seed范围 `git diff --check` | 20:20:34—20:20:34 | exit0 |
| whole_diff_check / 全冻结 diff `git diff --check` | 20:21:37—20:21:37 | **exit2**；作者原 red_one.log/xml 共4处 SQL 渲染行尾空白，未改失败证据 |
| final_scanner / 未修改 scanner、原分类表 | 20:22:22—20:22:35 | exit0；包含自有 artifacts，未扩大豁免 |

PG 连接仅从授权 WSL 私有 connection.json 进入子进程环境，未输出连接串或密码。原 35/seed 用既定 r05 库与 `DIANZI_TEST_RUN_ID=r05_pgvector_20261015`；新 21/probes 用主控明确授权的独立 r06 库和对应 `r06_catalog_final_review_20261015`。每个有效 PG 命令前后使用 **READ ONLY** 事务枚举 public 表 counts/version：r05 保持已有39表及0015版本，r06 始终0业务表/无version；没有新增 public 行，没有清理旧 reviewer 的既有写入。各自 UUID schema 在测试后销毁，未触碰 public。精确快照在各 PG `.json`。

共享解释器用于首轮 PG/static 时有显式 PYTHONPATH 指向当前 WT；最终纯门使用本 WT `uv sync --offline --frozen --extra semantic` 生成的环境。`import_inventory.log` 确认 ai_intel 与六个关键模块全部来自当前 WT/backend/src。锁文件、主版本与 coverage 门未改；没有下载模型/新增付费或执行 PoC。

## 审查执行错误与证据完整性

这些是审查仪器错误，**不是产品新缺陷**，也没有被改成 skip：

- `catalog_21` 首跑把新 r06 库配旧 r05 run ID，exact database guard 在 setup 拒绝；20:12:50—20:12:52，exit1，21 errors，0业务断言，public 空快照不变。对应 ID 修正后上述21项实际通过；保护代码未改。
- `pure_regression` 首跑将 `--basetemp` 放到 reports/runs，security scanner 正确发现测试生成的合成 credential 负例；共享 editable 环境还把主仓未执行源码并入 coverage，实际1 failed/1449 passed/10 deselected/50.79%、exit1。原始 `.log/.xml/.json` 保留。113个临时文件原样打包，逐文件 hash 验证后存到仓外 `D:/wt/r06-catalog-final-review-run-artifacts/pure_regression_synthetic_temp.zip`，SHA256=`f3752283a6a179872e319dfda05d6fc324d8bf99b8f5df6a06f0957495f32ff4`；manifest保留路径与每文件hash。仅删除已验证归档的自有 scratch 目录，未改 scanner、分类或任何用户文件。随后用默认临时目录与当前 WT 独立环境，完整原纯门通过。
- seed wrapper 首次因 Windows 斜杠白名单比较错误，在赋 PG 环境前自检拒绝；没有执行 seed。修正自有路径比较后第一次实际 seed 检查通过。新增注册 probe 的首次 import 指向不存在的模型位置，结果1fail/1pass原样保留；改为实际既有静态 SQL 边界后只复跑失败函数通过。
- `evidence_inventory` 首次在 PowerShell 未引号包围 `HEAD^{tree}`，造成 shell scriptblock 参数，exit128；后续 Python argv 查询与封存使用独立正确值，不引用此失败为身份核验通过。初次报告草稿误抄了该失败输出中的另一个 tree，首次封存实际给出正确 tree 后已更正，初次 seal 的旧报告hash留档。另首选 `D:/dianzi/.venv` 路径不存在，实际通过 `rg --files -uuu` 找到 backend/.venv；未将启动失败计作 pytest 测试。

初始文档阅读、Git现状检查及 worktree 创建发生在日志器建立前，工具会话保留准确命令/cwd/退出码，但未逐条记录秒级开始结束；这里不反填或编造时间。已明确的准备区间为20:10:01之后至首个 ledger 命令20:12:32之前。最终 `seal_manifest.json` 给出代码/seed/原始日志哈希与报告 hash；实际连接串/密码精确字节亦复扫自有文件和外部归档，不写出秘密值。

旧独立 reviewer 曾向 shared r05 public 写入10个 real_pg fixture，错误及无写前快照事实继续以旧报告保留；本次不删除、不改其错误记录，不把既有 public 行全归因于它，也不借当前 r05 public 版本表替代 UUID schema 自有 version。

## 未检查、评分证据和下一步

**已证实缺陷：**本冻结组合无新可复现 Must/Should；旧四个业务红例在本次冻结目标上有独立正向复验。**缺测：**七来源采集 worker/新 GET/游标投影、HTTP/浏览器资料库、真实原文全量许可、持续运行/回补/漏采参考集合、≤6h、最大页负载、生产部署与整体 R06/G-C。**猜测：**没有把无触发输入的担忧列作缺陷；对象存储残留和极限混合并发未据本次测试认证。

E1 可引用真实隔离 PG、旧数据前向等价、拒绝边界和原始日志；F1/R1 只可引用固定类别/来源身份与可追溯版本结构，不能计为八类真实来源已接通；F2/F3 只可引用证据存在与未强造安全结论，不代表论断支持或问答能力通过。本次没有新增 P1/D2/live 得分证据，未取得实际性能分子分母或持续运行时长。

建议主控把此冻结组合装入下一候选，再由独立 reviewer 对新增 worker/API/前端的确切候选执行完整产品闭环。当前审查任务结束，不继续下一张卡。

Verdict: **Ship，仅公共资料内部持久化、只读 DTO 与版本化前向迁移夹具组合。整 R06/G-C 仍须其余验收；不 accepted、不 push。**

Not checked: 真实外部来源、七来源 worker/API、资料库真实浏览器、持续采集/性能与整卡验收。
