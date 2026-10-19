# G-C / R06 资料目录、修订与只读 DTO 独立审查 1

What this change does: 固定九个公开来源的身份、八类分类和有界请求构造，增加非漏洞资料的 PostgreSQL 修订保存与证据定位，并冻结资料只读 DTO。资料没有因此成为漏洞事件，核对原文存在也没有被当成支持安全论断。

当前结论：**45 四项修复的定向行为复核通过；整内部切片仍 awaiting_review，不能 accepted 或作为最终组合通过证据。** 最终固定代码 `45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b`，tree=`82e588b929f91de2c12df22690da55c3db04bbda`，新干净 detached WT=`D:/wt/r06-catalog-review-jsonb`。原7探针和后补3数值探针均 exit0；catalog 21/21 断言通过。21项定向 pytest 的覆盖率25.96%低于原60%门，命令实际 exit1；不将其当成功命令，也不将定向低覆盖称为功能失败。

以下保留 `622ac77a25fbd3b9c1be273489eb18fab9ba2de8`（tree=`fb1e89f7a2954227ae044918964681ec97667746`）初审 **needs_changes** 与 `7b8103e6d91a7274bcfb661d8e6f1d5b7180be17` 修复轮的真实红灯。225 只作初始阅读；163 的差异先阅读、后在7b继承候选中复验，未给163单独签字。旧35兼容门仍未通过，最终真实0013种子/合并候选将由其他独立审查者完成；本报告不背书尚未冻结或运行的种子修复。

## 范围和前置

基线 `1927eeb00a7e0c1335f76340b0382f46102f08f2`。初始 detached WT 为 `D:/wt/r06-catalog-review`（225）；收到版本变更后另建干净 detached WT `D:/wt/r06-catalog-review-final`（622）。主仓库原有修改未动，审查没有修改业务、合同、迁移、测试、分类或扫描器；只有本报告及同名 review run 目录是自有产物。未 commit、push、联网、付费、下载模型、执行 PoC、读取产品 vault 或 holdout。

已读取项目 AGENTS、执行索引、恢复计划 11、恢复任务卡 12 的 R06/R09/R17、03/05 合同、04/07 相关语义、新 `CR-R04-R06_document_read_api.md`、原 T05/T09/T11/T14/T15 以及状态/交接。工作方式为 Ponytail 5.2 full/review。R06/R09 整卡在冻结状态仍为 pending，R17 为部分进行中；本内部切片没有越权将其改成 accepted。

本次可签范围仅为目录身份/请求、资料写入、修订兼容与只读 DTO。`persist_catalog_documents` 无产品 caller；新 GET、source worker、cursor/outbox 接线、前端、真实来源采集、持续运行、时效及整个 G-C/R06/R09/R17 均不能据此签通过。

## 622 初审 Must fix（45 定向已关闭）

1. **页中途失败仍可提交首条修订**（`backend/src/ai_intel/ingestion/catalog_documents.py:175–178`）。
   - What this is: 新函数宣称整页 savepoint，旧 `persist_source_response` 也确有 `session.begin_nested()`；新实现直接在父事务循环写入。
   - Problem: 两个合法不同成员中，第二个 `ContentStore.store_bytes` 抛 `OSError`。调用方捕获异常后正常结束父事务，独立 schema 中实际提交了第一成员的 1 条 revision 和证据，失败页部分成功。
   - Fix: 整页数据库写入包入 `session.begin_nested()`，仍由调用方负责外层提交及 cursor/outbox，不添加新事务体系。
   - If we skip it: 将来调用方为保存失败状态而捕获存储错误时，可能提交没有完成的页。当前未接产品 worker，因此不声称线上已有错误页。
   - 复验：`test_caught_midpage_storage_error_does_not_leave_committable_first_member`；已实测父事务提交后从新 Session 读取，实际 1，期望 0。

2. **JSON 布尔值和数字变化被吞成同一修订**（`backend/src/ai_intel/knowledge/revisions.py:148–151`，622 行号）。
   - What this is: 显式 metadata 参与末版身份，但比较使用 Python 字典相等。
   - Problem: 相同原文字节的 metadata `{"upstream_flag":true}` → `{"upstream_flag":1}` 均为合法 JsonValue，Python 将二者视为相等；第二次 `new_revision_count=0`，历史没有保存来源 JSON 类型变化。
   - Fix: 采用保留 JSON 类型的稳定比较，至少区分 bool 与 number；旧 `revision_metadata=None` 的复用语义保持。
   - If we skip it: 来源字段类型发生变化时，历史仍显示旧值，破坏显式元数据不可变修订合同。
   - 复验：`test_json_boolean_and_number_are_distinct_revision_metadata`；第二次期望 1 条新修订，实际 0。

3. **公开 canonical URI 可保存敏感 query**（`backend/src/ai_intel/ingestion/catalog_documents.py:87–105`）。
   - What this is: 写入校验固定 HTTPS 发布者、端口、userinfo、fragment、长度和控制字符，但不检查敏感 query；新 DTO 明确拒绝它们。
   - Problem: `https://arxiv.org/abs/2601.00001?access_token=synthetic` 被资料保存入口接受，不抛 `SourceCatalogError`，与冻结的安全 HTTPS URI 合同及 `DocumentSummary` 边界不一致。
   - Fix: 在整页预校验复用既有 `SENSITIVE_QUERY_KEYS` 和 `parse_qsl` 检查，拒绝后不写部分文档。
   - If we skip it: 凭据形态链接可能进入公开修订账本，后续 DTO 投影拒绝该文档或被错误暴露。本例只使用合成值，没有实际密钥。
   - 复验：`test_sensitive_canonical_query_is_rejected_before_public_persistence`；期望拒绝，实际接受。

三个输入和完整断言位于 `reports/runs/recovery_r06_catalog_persistence_review_1_20261015/test_review_pg_probes.py`。最终有效原始输出是 `independent_pg_assertion_probes_schema_only_confirmed.stdout.log`：**7 项，4 passed / 3 failed，exit 1**。其中四项真实正例是预校验失败后整页无文档、旧位置参数调用在 head 复用、原文及 source-response 的 GC 引用保护、数据库拒绝非对象 JSONB。独立断言驱动不测覆盖率，60% 完整 pytest 门另有记录，未替换或降低。

## 7b 新发现及45限定复核

4. **JSON字节比较把JSONB数值规范化当作新修订**（7b `backend/src/ai_intel/knowledge/revisions.py:157–169`）。
   - What this is: 为修复true/1的Python相等问题，7b改用排序JSON bytes比较末版与输入。
   - Problem: metadata `upstream_number=1e20` 或 `1e16` 经JSONB读回为整数，`-0.0`读回为`0.0`。相同字节、相同输入重复投递，三项真实PG均 `new_revision_count=1`，制造重复修订和epoch。
   - Fix: 45在显式metadata的tip SELECT中计算PostgreSQL JSONB `source_metadata == incoming_dict`，读取该bool；旧None不访问新列。没有自写数值canonicalizer。
   - If we skip it: 上游数值表示不变仍会每次轮询制造历史版本；这个问题不等于原bool/number区分已经解决。
   - 复验：`numeric_metadata_probe.py`原三输入；7b `3 failed / exit1`，45相同三个输入均 `second_new_revision_count=0 / exit0`。

45是新建 clean detached WT，离线 frozen+semantic venv；源码检查确认：敏感query预校验复用既有敏感键；整页写入及epoch都在savepoint中；JSONB比较仅在显式metadata时访问新列。原7个独立探针的输入和业务断言未随修复改变，严格UUID schema-only；45全部7/7通过。后补3个数值回放也严格schema-only，全部通过。

45显式只跑 `tests/integration/test_r06_catalog_documents_pg.py`：**21 passed，0 fail/error/skip，20.91s；原60%门因25.96%覆盖率退出1。** 已区分行为与覆盖门，不降门、不为变绿重复跑。45未重跑纯门、旧35或任何contract/security混合命令。主控明确收窄后，本审查停止混合测试并把旧混合模式从自有runner禁用。

## 已知作者发现与兼容变更

作者先发现 225 的 catalog URI 上限仍为 4096，DTO 已是 2083。622 只将该上限改为 2083、record_id 拒 DEL，并新增真实 PG 负例；这些是作者已发现问题，不列作本审查新发现。622 的 15 项 catalog PG 在独立组合门中全部通过，包括 long_uri 和 del_identifier。

作者另通知 622 的旧 0013→保存种子→head 测试遇到新列 `source_metadata`。163只在显式metadata时读写新列；旧None选择旧tip三字段，INSERT省略新列，head由server default填`{}`。原位置参数调用在head的独立正例已通过。

7b修复了旧fixture迁移URL为schema-only，并实际断言`alembic_version`解析属于新UUIDschema。独立旧35仍全部setup error：到达`source_documents._persist_member → EventRepository.publish_events`后，`event_linking.py:155–156`的宽`select(document_revisions)`在0013读新metadata列失败。源`rg`另找到`knowledge/persistence.py:762`同类宽select。它说明“当前model作为旧schema种子writer”的兼容门未过，未到35业务断言；不能称head产品业务35回归失败，也不能声称迁移已通过。主控决定用test-only、真实0013版本化种子保留原前向升级与旧身份断言，未扩大产品支持旧schema。本审查未继续运行尚未交付的种子修复。

## 源码、调用和最小设计核对

官方 WSL `codebase-memory-mcp` 0.11.0，独立 cache `/tmp/dianzi-cbm-r06-catalog-review-1-20261015`，项目 `r06-catalog-review-1`，仅 index 622 WT 的 `backend/src`。fast 索引 **1117 nodes / 5414 edges**，not_indexed/skipped/partial/unusable 均 0；graph schema 返回 29/29、has_more=false。七条双向 depth=2 trace 和源码 `rg` 相互核对，无测试索引、无作者 cache、无 holdout。

最终45另用独立cache `/tmp/dianzi-cbm-r06-catalog-review-45ee-20261015` 和项目 `r06-catalog-review-45ee`，仅索引45 WT/backend/src：**1117 nodes / 5416 edges**，四种缺失计数仍0，自动排除生成的`__pycache__`。schema与三条共享函数/注册/catalog双向trace均exit0，与最终源码rg相符；caller数量与原登记一致，新catalog仍无产品caller。最终45 tracked status为空、diff check通过。自有run的原始日志和测试库连接/密码精确值使用未修改的既有scanner复扫，exit0；未改分类表或扩大豁免。该扫描在承载自有run的622 WT执行，不能称45全产品安全验收。

`save_document_revision` 的产品直接 caller 为旧 `_persist_member` 和新 `persist_catalog_documents`；旧 `persist_source_response` 为第二跳。注册调用来自旧保存函数、`source_jobs.collect_page`、`source_routes.collect_source`；图对两个嵌套函数只给 file-level heuristic，已读取源码确认。新 catalog 保存函数 callers=0。旧 source route 与 source worker 仍由原两源的 `SourceKind`、固定 JSON 请求路径和旧保存函数处理，没有因注册表扩九项而获得新源自动采集能力。

九 UUID 唯一，NVD/vLLM 的旧 namespaced ID 保持；类别仍为八值，OSV 不另凑社区类别。请求只接受固定来源与有界 page/token/blob SHA，不把 cursor 当 URL。非漏洞资料未创建 CVE/Event/Claim；保存的 spans 为 verified text，`supports_claim=False`。A→B→A、URI/来源日期变化、元数据变化、重复轮询、同一成员并发和 PUBLIC/SYSTEM_ADMIN 权限在新增 PG 测试中有断言。

source response 与成员原文先经内容寻址登记，修订持有 FK；GC 使用既有 hash 事务锁检查正文、response 与 fetch 引用。坐标预校验要求 ordinal/连续 Unicode 范围/规范正文拼接一致；`attach_evidence_span` 再核对块与 quote。无新全能 service/repository、无依赖新增。每页最多100成员、每成员2000块；没有做此上界的性能认证。

0015 是 additive JSONB object 列、默认 `{}`、object 检查约束；downgrade 明确拒绝，需要前向恢复，没有删除历史。DTO 禁资产 kind、必填 null、限制列表/来源说明/许可、日期精度，详情拒跨 revision/mode 证据及小于页面长度的总数。它没有授权过滤/稳定游标/数据库投影的实现，不能把 DTO 单元测试算 HTTP 权限或分页已经完成。

## 实际命令、结果与审查执行偏差

可复跑的完整 argv/cwd/起止秒级 `+08:00`/exit/原始 stdout、stderr hash 在同 run 的 `commands.jsonl`，原始输出和 JUnit 均保留。下列为重要结果；最终报告交付时附全 ledger 摘要。

| 命令/门 | 622 实际结果 |
|---|---|
| `uv sync --offline --frozen --extra semantic` | exit0；独立 Windows venv，仓外既有 cache，无模型或网络下载 |
| Ruff `check src tests` / `format --check src tests` | 均 exit0；196 files formatted |
| `mypy src` | exit0；85 source files |
| `pytest tests/unit tests/contract tests/security tests/integration/test_r06_catalog_documents_pg.py -q` | exit0；1475 passed，0 fail/error/skip，118.46s；coverage77.80%，原60%门保留；包含10个public PG fixture，不作为最终干净组合证据 |
| CBM index / corrected schema / 7 traces | 全部 exit0；首次 schema 错传不支持的 `--max-output-tokens` 为 exit1，已保留后更正 |
| 严格 schema-only 独立 PG 断言 | exit1；7 中4pass/3fail，三个 Must fix 均复现 |
| `git diff --check` / tracked status | exit0；tracked status 空，无审查业务修改 |

**审查执行错误必须保留：**初版组合没有`-m`过滤，1475实际组成是1450纯unit/contract/security + 10个原有real_pg + 15catalog；不是1475纯测试。10项精确为两个security模块9项，以及`tests/contract/test_t07_jobs_outbox.py`1项。它们在本次新建`test_dianzi_r06_catalog_review_814d44cd`的public运行；catalog自身fixture是schema-only，因此15个catalog行为结果有效，但整门不作最终干净组合背书。一次通过不关闭已知Windows native CPU-limit基线问题，也不将其称环境原因或删门。

初版独立 probe fixture 错用了 `schema,public`，与上述安全测试在新专库 public 的 head 发生回退，导致额外的预校验计数失败。`independent_pg_probes.*`（3 failed /1463 passed）及首次 direct driver（4fail/3pass）为 **review harness invalid**，不当成第四个产品缺陷。改为严格 UUID schema-only 后，预校验正例通过；7项有效结果只保留上述3fail/4pass。

更严重的范围偏差：旧vector/question组合也误带这10个real_pg，在指定旧测试库`test_dianzi_r05_pgvector_20261015`的public执行了迁移与合成用户/认证状态、任务/来源写入，而授权本应限新UUIDschema。没有生产、downgrade或删除，但仍是审查者执行范围错误；已立即告知主控，没有擅清理共享public。此组合原始 **1failed/1468passed/26errors、coverage80.62%、exit1** 留作 **review harness invalid**：旧fixture的schema,public可借public版本表，并造成部分vector种子/事实与测试状态落到public；既不证明兼容成功，也不证明业务回归，不覆盖作者原35个setuperror。

7b第二轮错误地只排除两个security模块，仍漏筛1项T07 public fixture。catalog+7probe组合实际`1476passed/76.36%/exit0`，构成为1450纯+1 T07+18catalog+7probe。旧35组合实际`1451passed/35errors/75.56%/exit1`，其中1项T07仍写shared public，是重复的审查仪器范围错误；已明确报告，不能将整组合称为仅UUID或最终通过。此轮旧35严格schema身份断言已通过，因此其EventRepository旧schema setup红的具体根因有效。最终纯门应单独`-m 'not real_pg'`；PG只显式选schema-only文件，不能再靠枚举排除公共fixture。

发生写入的准确窗口、argv与原始输出在ledger的`old_vector_question_combined`及`final7b_old_vector_question_pure`，新专库则另含`catalog_pure_combined`、`independent_pg_probes`、`final7b_catalog_probes_and_pure`。没有写前public快照，所以不能把现存所有行都归为本审查新增。主控收窄后仅在2026-10-15T19:53:02+08:00做了一次**READ ONLY** public逐表count/版本快照（`shared_public_read_only_snapshot.json`），不含行值或凭据，未清理、更正或删除旧public。后续复核由新独立身份接手。

## 未检查、评分证据与下一步

未检查：真实外源、模型、MinIO现场、最终新 GET/游标与投影、真实 API 浏览器/前端、持续采集/回补/漏采参考集合、≤6h、并发混合100成员上界、生产部署、整个 R06/G-C 和原T整卡。无凭据的外部 live 仍 blocked/not_run，不计通过。

F1/R1 可引用固定身份/分类与版本证据结构，但不能引用为八类来源已产品接通。F2/F3 仅引用可定位原文与未强造安全结论；没有知识卡、语义支持或真实问答验收。E1 可引用真实 PG、原始日志、迁移设计和源图；失败与审查错误均公开留档。P1/D2 没有本次新增通过证据。

下一步：本审查停止并释放槽。由新独立审查者对最终test-only真实0013种子与产品冻结候选执行干净旧35、新catalog、原1450纯门及相关安全门；保留本报告所有历史红、scope错误、合同、分母、原旧断言和外部阻塞。不得用本次45的限定行为复核替代最终组合。

Verdict: **Ship，仅45对1–4的定向行为修复；整资料内部切片仍 awaiting_review，不 accepted、不 push。**
