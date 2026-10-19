# R12 / T30 混合检索内部批次 · 独立初审 1

What this change does: 本批次为当前 PG 已支持事实建立 OpenSearch BM25 与 pgvector 双路检索，经固定 RRF 和真实重排返回可追溯证据。它新增版本化索引、outbox 消费收据和返回前事实校验；现有 R05 单事件服务及产品 API 未改。

**结论：needs_changes；Must fix 1 后复核。** 原 64 个 fixture/合同/安全回归与 22 个真实 PG/OpenSearch 集成例独立复跑全部通过，但四个使用合法知识发布事务的最终读取窗口反例全部失败。本报告不能签 G-D、完整 R12/T30、多跳、正式 live 或 SLA。

## 固定版本与改动边界

被审代码 `f316a7aa432d6f730fa49189814c2559be8b6db4`，材料 `a43d25e64dd00eaec63521c9457c7fa2228b8799`，基线 `e310f7735bd499c4d9fbcefe8a644e2309a16a62`。独立工作树 `D:/wt/r12-hybrid-review1`，分支 `codex/r12-hybrid-review1`，首次从材料 SHA 创建，实际测试的 PYTHONPATH 指向此工作树 `backend/src`。解释器为已存在的 `D:/dianzi/backend/.venv/Scripts/python.exe`，没有下载、安装或改锁。

已读 AGENTS、00 执行图、恢复 R12 卡、T30、03/04/05/06、manifest 的 R12 能力前置、task_state/handoff、作者报告及索引提案、新版 Ponytail Review 5.2.0。本 reviewer 没有参与实现、spawn、业务修复、状态更新、accepted、提交或 push；只新增此报告及 `reports/runs/recovery_r12_hybrid_review1_20261016/`。清理核验确认 `backend/src`、原 `backend/tests`、依赖/锁、config、progress 的 diff 为空；主工作区原有未提交修改保留。

正式 0020/authority FK 尚未实现。现有独立 `hybrid_metadata` 是迁移输入，测试在独有 schema 创建提案表，不作为正式迁移通过证据。worker 注册、settings、全库初建、API/回答/UI 与 graph 产品接线仍待主控集成。

## 安全独立理由和静态调用链

本服务只消费既有 source-supported PG 事实、已核验永久 EvidenceSpan，以及既有 E5/pgvector/重排接口；它不执行资产四态条件、不产生多跳结论、不调用 FOFA。因此尚未完成的资产四态与 graph 产品接线不阻断此内部检索审查，但仍阻断完整 R12 和阶段过门。正式鉴权由后续调用方构造 AccessScope，本 query 没有 tenant/permissions 字段。原 R05 `service.py`、共有 models/settings/runtime/锁保持冻结。

业务源码版本核验完成后，实际对本工作树 `backend/src` 建立独立 CBM fast 索引：`dianzi-r12-hybrid-review1-backend`，cache `/tmp/dianzi-cbm-r12-review1-20261016`，工具 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 0.11.0。index/schema/retrieval architecture 和 fully qualified `HybridRetriever.retrieve`、`HybridIndexer.refresh_scope`、`HybridIndexer.prepare_generation` outbound depth 3 traces 均 exit 0，1533 nodes / 7975 edges，not_indexed/skipped/partial/unusable 均 0。fast excluded 摘要含 assets 与缓存，不能据此断言资产能力已审完。`rg_callers.log` 交叉确认新服务当前只在 retrieval 内定义/互调，生产 answering 仍使用旧 EventEvidenceRetriever；CBM 对协议动态调用的缺边没有被当作未接线证明。

实际连通审查覆盖五个新 retrieval 文件、其调用的 R05 分块/embedding 校验、KnowledgeReadService 的源/文档/修订 ACL 与 quote hash/坐标校验、KnowledgeRepository 发布及 epoch 路径、直接测试与回归。BM25 查询预过滤 generation/model、scope、public/tenant XOR、可用时间；PG 384 维向量分支也预过滤同一权限/时间/模型空间。精确 CVE 的 PG 子查询同时关联 event_id 和 scope_key，RRF 固定 k=60，重排后精确事件仍优先。永久 evidence_id 与派生 chunk_id 分开。

facts_query 回查 active event/association、当前 revision/parse、支持 claim/current/freshness、validated supports、supports_claim、来源撤回与每层 ACL。Evidence 读取还验 block、hash、Unicode 坐标和安全 source URI。index_lag、无支持证据、graph_not_configured 和搜索失败均明确 partial；未将空结果写成“无风险”。其中最终 epoch 校验存在下列实证窗口。

## Must fix

1. **[P1] 最终事实读取以后没有锁定并重读 epoch，可把已经变化的证据标为完整**（`backend/src/ai_intel/retrieval/hybrid.py:460`、`:483`、`:488`）。

   **这段代码做什么：** 重排后先读取 `final_epochs`，随后逐项重新读取 PG facts 与永久证据，再用此前的 epoch 值决定能否返回。当前事务为默认 READ COMMITTED，最终 epoch 没有取锁，HybridSelection 在事务结束后构造。

   **问题和输入：** 自拟 `resource_copy/test_legal_publication_window.py` 在“最终 epoch SELECT 完成后、facts SELECT 前”和“最终 candidates 读取完成后、epoch 比较前”两处安排合法 `KnowledgeRepository.publish` 提交。初始化只用显式 synthetic 资料；发布者为服务端 system_admin scope，提交有 source/revision、validated supports、当前观察时间。每个发布实际通过现有校验并生成 source_verified/supported claim、publication receipt、change、job、outbox；同一事务将 public epoch 由 1 升到 2，**没有恢复 epoch 或绕过发布协议**。

   | 合法发布内容 / 提交窗口 | 实际 PG after | 返回 epoch / partial | 可观察结果 |
   | --- | --- | --- | --- |
   | 新匹配事实 / final epoch 读后 | epoch=2、claims=2、receipt epoch=2 | 1 / false | 只返回旧事件，漏掉新可用事实且仍声称完整 |
   | 新匹配事实 / final candidate 读后 | 同上 | 1 / false | 同上 |
   | 支持的 source_status=withdrawn / final epoch 读后 | 同上 | 1 / true | 旧 hit 被过滤，但返回 epoch 仍是 1，未识别 scope 改变 |
   | 支持的 source_status=withdrawn / final candidate 读后 | 同上 | 1 / false | 被撤来源旧 hit 仍返回，reasons 为空 |

   `legal_publication.log/.xml/.command.json` 保留每例 before/after/result、source/evidence/event IDs 及真实 receipt epoch。四例均 `expected partial + empty hits + scope_changed_during_retrieval`，实际 4 failed、0 error/skip。底层权威路径实际为 `KnowledgeRepository.publish`（`knowledge/persistence.py:459`）→ `_validate_submission`/`_save_claim` → `save_change_publication`（`:249`）→ `bump_scope_epoch`（`knowledge/revisions.py:463`）；来源接入本来就在 `ingestion/source_documents.py:704` 创建受支持来源事实，包含 source_status/source_withdrawn_at。本问题在正常新增/撤回发布并发下可触发。

   **最小修复：** 在最终完整 facts/evidence 回查结束后，重新读取并共享锁定有权 scope epochs，比较初始值；改变时清空 hits 并返回当前 epoch/明确 partial。在同一事务、持锁期间构造不可变选择，避免使用第 460 行早先读到的值作最后围栏。不要把锁延长到 embedding/重排。若还加强直接父级变化的锁，应遵循已审 R10 的父输入→epoch 锁序；后续产品发布/序列化仍须自己的当前身份和提交围栏。本 reviewer 不改业务实现。

   **不修的影响：** 当前来源已撤回时仍可能把旧引用交给下游作为完整当前证据；新事实晚到也会漏召回并隐藏索引落后。原 64/22 的绿色不能覆盖该窗口。复验需保留本次四例原红，在新冻结版本验证它们；再补 reader 持锁期间正常 writer 等待、释放后提交、无死锁的并发对照，并回归原 64/22。

## 实际命令和结果

run 根 `D:/wt/r12-hybrid-review1/reports/runs/recovery_r12_hybrid_review1_20261016/`。所有下列校验都有 `.command.json` 完整 argv/cwd/+08 起止/exit/code SHA，以及 `.log`；pytest 数量从独立 JUnit 读取，重复组不累计成新案例。`review_runner.py` 是收据入口，表中的 pytest/mypy/Ruff 参数是其实际子命令；PG 准备在测试子命令之前，未把准备耗时混入 pytest 耗时。

| label / 实际命令 | +08 起止（2026-10-16） | exit / 结果 |
| --- | --- | --- |
| freeze_audit：`project-python review_runner.py audit` | 05:50:47.190456–05:50:56.989924 | 0；14 source blob、139 material、126 raw entries、16 originals 核验 |
| fixture_regression：`-m pytest tests/unit/test_r12_hybrid.py tests/contract/test_r12_hybrid_contracts.py tests/security/test_r12_retrieval_boundaries.py tests/unit/test_r05_evidence_chunks.py tests/unit/test_r05_embedding_boundaries.py tests/contract/test_r05_semantic_contract.py -o addopts= -q --junitxml=<run>/fixture_regression.xml` | 05:51:06.245233–05:51:09.159866 | 0；64 passed，0 failed/error/skip；pytest 1.23s |
| integration：`-m pytest <run>/resource_copy/test_t30_hybrid_retrieval.py -o addopts= -q -s --tb=short --junitxml=<run>/integration.xml` | 05:51:24.461815–05:52:14.663705 | 0；22 passed，0 failed/error/skip；pytest 48.53s，命令墙钟50.2032s |
| negative：`-m pytest <run>/resource_copy/test_review_negative.py ... --junitxml=<run>/negative.xml` | 05:52:15.914898–05:52:27.308198 | 1；5 passed/2 failed；两个失败为 reviewer 首版读取计数错误，不能算业务反例 |
| negative_final：同独立 probe，正确 final candidate 窗口 | 05:53:03.025792–05:53:15.984456 | 1；5 passed/2 failed；新事实和撤回窗口业务红 |
| negative_epoch_read：同 probe，final epoch 读后窗口 | 05:54:08.133870–05:54:21.553180 | 1；5 passed/2 failed；新事实完整错误、撤回的旧 epoch 围栏红 |
| legal_publication：`-m pytest <run>/resource_copy/test_legal_publication_window.py -o addopts= -q -s --tb=short --junitxml=<run>/legal_publication.xml` | 05:56:05.821017–05:56:16.989370 | 1；4 failed/0 passed，0 error/skip；四例通过合法 publish 的前置断言后在最终期望断言失败 |
| mypy：`-m mypy --cache-dir D:/wt/r12-hybrid-review1-mypy-cache src` | 05:54:34.129079–05:54:47.829080 | 0；122 source files 无错误 |
| ruff：`-m ruff check <五新源码、五直接tests、三作者run脚本>` | 05:54:34.088830–05:54:34.427030 | 0；无错误，完整13文件 argv在收据 |
| format：`-m ruff format --check <同13文件>` | 05:56:25.955272–05:56:26.146182 | 0；13 files already formatted |
| cleanup_verification：`project-python verify_cleanup.py` | 05:57:05.725981–05:57:20.237894 | 0；自有 schema/index剩余0，business diff空，材料复核仍通过 |

CBM 实际命令为 `wsl --exec /usr/bin/env CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-review1-20261016 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r12-hybrid-review1/backend/src --name dianzi-r12-hybrid-review1-backend --mode fast`；05:51:06.245233–05:51:12.251422，exit0。schema 05:51:12–15、architecture 05:51:15–18、retrieve trace 05:51:18–22、refresh_scope trace 05:51:22–25、prepare_generation trace 05:51:25–28、源码 rg 05:51:28 均 exit0，毫秒/完整参数各自保留。

五个独立通过的新增负例是：目标 CVE 不被邻近事件和其他 tenant 抢排；真实 OS bulk/refresh 已成功、后续清理失败时 PG水位/receipt不推进且返回 index_lag/partial；HTTP401、403、timeout在真实PG检索流程里分别保留权限/超时原因，不回显模拟认证文本。HTTP失败使用明确 MockTransport，不当成真实OS鉴权实测。

## 原合同覆盖与尚未通过

| T30 原案例 | 独立覆盖 | 当前判断 |
| --- | --- | --- |
| C01 精确 CVE | 原例及新目标/邻近/跨tenant例 | 已复跑通过 |
| C02 中英文同义 | 真实本地 E5/PG余弦top1/真实重排；三条 synthetic 正文 | 小样本接线与行为通过；正式质量 not_run |
| C03 两tenant同词 | 真实两分支 public/own/other/future；viewer/analyst | 原例及新精确跨tenant例通过 |
| C04 撤回仍留索引 | 原七类撤回/旧修订/stale/失效关联/ACL例；重排撤回 | 原例通过，最终合法发布窗口 Must1 未通过 |
| C05 模型/维度变化 | 固定模型空间合同、错误384维投影事务、generation验证 | 原例通过；0020正式迁移未运行 |
| C06 尚未索引新事实 | PG精确补查+index_lag、失败水位、图未配 | 原例通过；最终新增窗口 Must1 未通过 |

outbox authority ref/scope 验证、乱序完整快照、重放与双 writer 同消息原子收据、embedding期间epoch变化、模型维度失败不提交，以及 OS写入中间态明确lag均有实际复跑。未从 proposal 表或测试 create_all 推断正式 worker/live全库重建已实现。

## 资源、模型与真实性

私有 connection.json 仅在 WSL 子进程 capture 到内存，核对已授权 loopback:25432 的原资源身份后创建独占 `test_dianzi_r12_review1_20261016`；DSN只环境传递，未进 argv/报告。复用冻结 `scripts/dev.py` 真实 guard。原22例硬编码作者资源名称，故保留原字节 `resource_copy/original_test_t30_hybrid_retrieval.py.txt`，只在自有副本改测试DB、schema/index前缀，业务期望全部不变，替换与 SHA 见 `resource_copy_audit.json`。副本用既有 tests.conftest 的 guard/失败脱敏；原 tests 文件未改。

PG 实读 16.14，vector extension 0.8.2；OpenSearch版本2.17.0引用已封作者 probe，未重复全局 GET `/`，本 reviewer 对自己的 index实际创建/search/bulk/refresh/delete。索引 `dianzi_test_r12_review1_<uuid>`、schema `test_r12_review1_<uuid>`，只清理当例创建的确切对象，最终 scoped GET/PG names查询剩余0。测试数据库保留供复现；没有 flush/drop其他索引、修改生产库、重启服务或续期资源。

模型 cache `C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime`；E5 `intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`，rerank `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1@1427fd652930e4ba29e8149678df786c240d8825`，固定已有 model-space fingerprint和384维。runtime实读 Python3.12.13、SQLAlchemy2.1.1、psycopg3.3.6、Python pgvector0.5.1、httpx0.28.1、onnxruntime1.24.4、tokenizers0.22.2、numpy2.4.2、pytest8.4.2、Ruff0.16.9、mypy1.20.2。没有付费 API、新模型下载、测绘、PoC执行、holdout或真人金标。

真实模型例为提示注入中英文与煮米饭三个合成正文，其余集成/负例为显式 FixtureSemanticModels，只证明SQL/REST/合同。实测中文完整retrieve 5.0653s、英文4.6052s；BM25 0.0335/0.0195s，vector含query embed 2.5487/2.0452s，rerank2.4068/2.4763s。它们不是官方5秒问答SLA、吞吐、准确率或召回率；没有因为中文超过5秒改门槛或删题。

## 材料核验与失败保留

作者 materials_manifest raw SHA256=`34fd3a94edf158944f5217caa1a28cec83d9cf70c09e3f21b91d57199a718b40`。14 source blob在code/materials/current源码逐项一致；139提交材料Git内容与raw/LF记录核验；126 synthetic raw entries的hash/size/标记对应16 distinct originals。没有改作者 manifest。raw/LF差异按其合同核对，本run `.gitattributes -text` 只保留日志/JSON/XML/blob字节，不豁免源码检查。

作者旧 integration_first 6 failed/9 passed、integration_seed_fix 2 failed/13 passed和后来22green的JUnit/日志均核验保留。旧 HTTP409/可见性原因只是作者推断，因为响应状态原来未独立保存；不把推断升级成实测。旧 collection error、静态入口路径错误及修复记录也未隐藏。

reviewer 初版 probe误把空 exact读取忽略，实际candidate调用3次却断言2次，原版本 `initial_probe.py.txt` 与 `negative` 红日志保留；它不是业务失败证据。纠正计数后原版本 `post_candidate_read_probe.py.txt`、`negative_final` 留存，再改 final epoch读后位置另存 `negative_epoch_read`。最终采用独立新文件的四个合法 publish 例确认 Must1，不改旧断言/金标/分母/skip。

首两个 reviewer 输出曾将完整DSN的8字符片段也作脱敏，过度遮蔽日志中自有资源前缀；没有泄漏秘密，也没有改测试结果。之后收据入口改为完整连接串整值脱敏、只有密码做片段脱敏；旧log原样保留，最终合法publish/cleanup日志保存准确自有对象名。测试失败redaction只是隐藏认证信息，outcome/count保持原值。独立raw manifest、report SHA及真实秘密值零命中检查见本run `review_manifest.json` / `seal_receipt.json`。

## 性能和复杂度建议

没有实际大语料或并发SLA负载，故不报告加速比。源码可见全scope刷新上限10000 chunks，每8条调用模型、每64条OS bulk、PG每chunk一次insert；facts候选每行读一次完整EvidenceSpan，同一span支持多claim会重复读/分块。下一轮扩大真实语料前，可在一次请求内按evidence_id复用验证结果、批量PG插入，并用真实语料记录SQL/模型批次数，先证明耗时来源再优化。

`indexing.py:156`先对worker可见 public+tenant rows施加10001上限，再在`:173`筛出目标scope；因此租户刷新容量目前也受公共可见语料影响。未执行10001条压力，不把静态容量边界称为本轮生产故障。正式全库扩展应先在SQL中过滤有效目标scope或明确该共享上限，不新增通用仓储层，不改验收阈值。此建议不增加本轮Must编号。

## 评分证据、偏差与下一步

F3/P3 仅有双路检索、精确优先、真实小样本语义接线和已复跑权限/历史有效性证据；最终当前性围栏失败，不能提升评分档位。unit/contract及原integration回归passed；新增关键并发验证failed。frontend/e2e/manual、正式多跳/图扩展、历史真值查询、资产结构化补查、0020迁移/worker/API/UI和真人gold/正式评测/live均not_run，保持既有阻塞可见。

本轮偏差只有安全资源副本和reviewer probe修正，均在自有run记录，未改公共合同/主版本/认证/阈值/金标/分母。主控可将 Must1 交作者作最小修复；新code/materials冻结后本reviewer定向复核四红、持锁writer并发以及原64/22，不把作者自检替代独立核验。之后才继续主控0020与产品集成；此轮到独立初审交付即止。

**Verdict: fix 1 first. Not checked：正式迁移、产品worker/API/UI、多跳/graph、真实来源/资产、人工金标、正式性能与整个R12/G-D。**
