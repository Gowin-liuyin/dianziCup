# R12 / T30 混合检索内部批次 · Must1 定向复核

What this change does: 修复把最终事实重读、当前范围版本校验和结果构建放在同一 PG 事务内。它按实际可见输入锁住相关父行和支持关系，再共享锁定并重读 scope epochs，保护正常发布与撤销期间的当前快照。

**结论：限定 Ship。初审 Must1 已由独立复跑关闭；仅签本内部 retrieval 服务与 Fix1 当前性围栏，不签完整 R12/T30/G-D。** 原 64 fixture 回归、原22真实PG/OS、原四个合法发布红例及五个线程/ACL对照本轮均通过，合计95个不同用例。初审报告、原红、作者历史失败和性能限制保留。

## 冻结版本、审查人和范围

代码 `ba1548d591d2b341e61a230f1cdd5bd387f3235b`，材料 `d3f55300c34760bd97d9a85c710fc23b4a480b66`；上一轮 code `f316a7aa432d6f730fa49189814c2559be8b6db4`、materials `a43d25e64dd00eaec63521c9457c7fa2228b8799`。独立新工作树 `D:/wt/r12-hybrid-review1-fix1`，分支 `codex/r12-hybrid-review1-fix1`，首次从新材料SHA创建；实际导入 PYTHONPATH 指向该树 backend/src。解释器复用 `D:/dianzi/backend/.venv/Scripts/python.exe`，无新安装或锁变动。

本 reviewer 仍是未参与实现的初审人，按主控已授权的新冻结定向复核继续，没有spawn、业务修改、进度/accepted、commit/push。本轮仅新增本报告和 `reports/runs/recovery_r12_hybrid_review1_fix1_20261016/`。旧初审 `D:/wt/r12-hybrid-review1/reports/reviews/recovery/G-D-R12-hybrid-retrieval-review-1.md` 与旧run保持原样；已逐一重验旧review manifest的83件文件SHA。

沿用已读 AGENTS、00/R12/T30、03/04/05/06、冻结状态/handoff、新版 Ponytail Review5.2.0，新增阅读 Fix1报告和源码/测试。实际 code diff相对a43只有一个业务文件 hybrid.py、两直接测试、三个run文件；旧R05/权威发布/修订/事件/catalog/read/auth/原T30测试等八个共享输入与a43逐blob一致。没有修改migration0020、worker、共有model/settings/runtime、依赖主版本、认证、gold、阈值或计分分母。

内部安全独立理由保持：只消费已有 source-supported PG事实、已核验永久span和已核验本地E5/pgvector/rerank能力，不执行尚未完成的资产四态或生产graph、多跳回答。内部服务可以单独验收，正式资产/图/多跳/产品接线缺口继续阻断完整R12和G-D。

## Must1 关闭的实证

初审根因位于旧 hybrid.py:460/483/488：最终事实查询之前读取epoch、查询后没有锁定重读，结果又在事务结束后构建。合法 KnowledgeRepository.publish 能提交受支持新事实或来源撤回并把epoch1升到2，旧实现却返回epoch1/partial=false，撤回窗口还会留下旧hit。

本轮把**初审四例原文件字节直接复制**至自有 resource_copy，SHA仍为 `b55f8ca4e2060d5ee541351b92cd7c0653a6d988bb23cac877390864f7efe852`，输入、发布阶段、预期与断言未改。新服务保留原早先无锁观察，四个钩子仍照原时序提交，而不是把钩子阻塞/timeout算修复。

| 原合法发布案例 | 真实PG before→after | 本轮返回 | 结果 |
| --- | --- | --- | --- |
| 新supported事实 / 最终epoch观察后 | epoch1/claims1→epoch2/claims2；receipt2；source_verified | scope epoch2、indexed epoch1、partial=true、空hit、scope_changed_during_retrieval | passed |
| 新supported事实 / 最终candidate观察后 | 同上 | 同上 | passed |
| supported source_status=withdrawn / 最终epoch观察后 | 同上 | epoch2、partial/空hit、facts_changed与scope_changed原因 | passed |
| supported source_status=withdrawn / 最终candidate观察后 | 同上 | 同上，不再返回被撤来源证据 | passed |

正常发布确实经过 `KnowledgeRepository.publish → save_change_publication → bump_scope_epoch`，同一事务保存claims/support/receipt/change/job/outbox，**没有手动恢复或跳过epoch**。每例before/after/result及synthetic source/evidence/event身份在本run `whole_integration.log`，对应JUnit case IDs与初审四红一致。

新增五例也独立复跑：两例正常新claim/来源撤回在RetrievalTrace构建时启动真正后台writer，查询pg_stat_activity观察到 `wait_event_type=Lock`、future未完成；读取事务退出后writer正常提交receipt epoch2，下一次读取显式index_lag，撤回没有hit。visible source ACL更新也实际等锁，释放后下一读取排除。final candidate观察后、加锁前把doc变为tenant-b、不手改epoch，完整fresh读将hit排除。hidden tenant-b的正常publish在public构建期间直接成功，public返回仍只有public，未锁住他人数据。2秒writer lock_timeout和有界future保持，不以锁超时当通过。

## 连通调用和保证边界

新 `hybrid.py:539`显式 READ COMMITTED事务，先无锁epoch/candidate观察；`:543`调用 `lock_candidate_authorities`，按 source→document→revision→event→claim→evidence→block→event-document→claim-evidence锁原可见身份，各表ID排序。带ACL表每个查询仍按服务器AccessScope过滤；支持/关联只锁命中候选的精确组合，没有全表锁或全租户集合。

`:544`在这些锁之后完整重执行facts_query和永久EvidenceSpan hash/坐标/父级ACL验证，锁身份没有替代当前查询。`:545`最后按scope_key排序FOR SHARE读取epochs，比较初始和observed值；`:557`起在同一事务持锁构建HybridSelection和trace。异常仍向上传播并释放事务，没有假空成功。范围版本变化清空全部hit；事实变化过滤对应hit并明确partial。

静态复查正常知识发布、事件publish/merge/undo、source_documents与catalog路径：知识/事件提交经同事务epoch helper，catalog新修订另有事务内epoch upsert。source/doc等当前基线没有新增产品ACL写API；直接ACL线程例是明确raw PG安全负例，不冒称生产ACL操作已接线。参照已审R10的父输入→epoch和fresh读范式，未发现本次窄锁新增反向锁序或隐藏tenant的全局锁。已经运行的五并发例没有40P01、55P03或writer超时。

**当前性保证止于持锁构建的快照。** 锁释放后新事务可合法提交，返回对象不能永久代表当前事实；后续API/回答发布必须再次核认证、关键事实和epoch。正常写入须保持同事务epoch协议。本复核没有宣称旧身份行锁能阻止任意无epoch的未来插入，也没有新增所有DB篡改时序的容错保证。

BM25/向量预ACL与可用时间、exact CVE关联/优先、固定RRF60、真实重排、generation空间隔离、outbox来源/乱序/幂等/失败水位仍是初审批次的行为；其原64/22此次完整回归，不仅仅读修复diff。0020表/FK及正式初建仍未实现；自有schema中的proposal表创建不能算正式迁移通过。

## 独立CBM与材料核验

在源码冻结核验成功后，新WT backend/src独立fast索引 `dianzi-r12-hybrid-review1fix1-backend`，cache `/tmp/dianzi-cbm-r12-review1fix1-20261016`。工具0.11.0实际命令为 `wsl --exec /usr/bin/env CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-review1fix1-20261016 /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r12-hybrid-review1-fix1/backend/src --name dianzi-r12-hybrid-review1fix1-backend --mode fast`。1535 nodes/7994 edges，not_indexed/skipped/partial/unusable均0；fast摘要排除assets/cache，不能据此声称资产已审。

新schema/architecture、fully qualified retrieve、lock_candidate_authorities、refresh_scope、prepare_generation outbound traces和KnowledgeRepository.publish outbound/bump_scope_epoch inbound depth3均exit0。源码rg交叉确认实际callers和生产answering仍走旧EventEvidenceRetriever；没有拿CBM动态协议缺边推断不存在调用，未索引秘密、附件、holdout或run。

Fix1 manifest raw SHA256=`5afd7a75e86afd0635bb0b4befa216244931775a2e48fd71224ad10d75d32b50`；6source blob/8 unchanged shared sources、92 committed material逐项Git/raw/LF验证，110 synthetic raw entries对应19 distinct originals。原作者143件在a43和d3逐blob保持，初审83件SHA保持。作者must1_red4failed、未提交draft receipt及静态初红保留；未把当时HEAD=a43的draft绿充作ba1548d代码证据。

## 实际检查命令与结果

run根 `D:/wt/r12-hybrid-review1-fix1/reports/runs/recovery_r12_hybrid_review1_fix1_20261016/`；test/static cwd均为此WT/backend。入口 `review_runner.py` 每个子命令保存完整argv/cwd/+08起止/exit/code/materials SHA和日志；下表时间为2026-10-16。pytest数量直接取新JUnit，31=原22+原红4+线程5，不与作者或初审重复执行相加。

| label / 真实命令 | +08起止 | exit / 实际结果 |
| --- | --- | --- |
| freeze_audit：`project-python review_runner.py audit` | 06:18:58.969661–06:19:24.600154 | 0；上述材料/源/历史核验通过 |
| fixture_regression：`-m pytest tests/unit/test_r12_hybrid.py tests/contract/test_r12_hybrid_contracts.py tests/security/test_r12_retrieval_boundaries.py tests/unit/test_r05_evidence_chunks.py tests/unit/test_r05_embedding_boundaries.py tests/contract/test_r05_semantic_contract.py -o addopts= -q --junitxml=<run>/fixture_regression.xml` | 06:19:36.827457–06:19:40.828743 | 0；64 passed，0failed/error/skip，pytest1.68s |
| whole_integration：`-m pytest <run>/resource_copy/test_t30_hybrid_retrieval.py <run>/resource_copy/test_legal_publication_window.py <run>/resource_copy/test_r12_final_snapshot_fence.py -o addopts= -q -s --tb=short --junitxml=<run>/whole_integration.xml` | 06:19:38.126676–06:21:03.381964 | 0；31 passed，0failed/error/skip；pytest83.08s，命令85.2559s |
| mypy：`-m mypy --cache-dir D:/wt/r12-hybrid-review1-fix1-mypy-cache src` | 06:20:07.017222–06:20:24.884799 | 0；122 source files无错误 |
| ruff：`-m ruff check src/ai_intel/retrieval/hybrid.py tests/integration/test_r12_legal_publication_window.py tests/integration/test_r12_final_snapshot_fence.py ../reports/runs/recovery_r12_hybrid_fix1_20261016/fix_checks.py ../reports/runs/recovery_r12_hybrid_fix1_20261016/fix_cbm_checks.py` | 06:20:07.234259–06:20:07.593325 | 0；无错误 |
| format：`-m ruff format --check <上述5文件>` | 06:20:45.105864–06:20:45.372353 | 0；5 files already formatted |
| cleanup_verification：`project-python verify_cleanup.py` | 06:21:19.203875–06:21:49.637853 | 0；自有schema/index剩余0、business diff空，材料复核通过 |

CBM index06:19:36.995502–44.465821，schema06:19:44.551834–48.353845、architecture06:19:48.427107–52.214973、retrieve06:19:52.309743–56.530095、locks06:19:56.622960–06:20:00.526830、indexer06:20:00.593912–11.542507、prepare06:20:11.610943–15.426933、publisher06:20:15.626229–19.427609、epoch writers06:20:19.501927–24.023893、源码rg06:20:15.498447–15.568430，全部exit0，完整参数和日志各自保存。

## 资源、性能与未检范围

专用testDB `test_dianzi_r12_review1fix1_20261016`、runid同名去test_dianzi前缀；通过既有真实guard校验。私有connection.json只WSL capture到内存、核原授权loopback:25432资源身份后派生env，不在argv/报告。PG16.14/vector0.8.2实读；OpenSearch2.17.0引用已封作者probe，无重复全局GET `/`。只创建/清理自有 `test_r12_review1fix1_<uuid>` schema和 `dianzi_test_r12_review1fix1_<uuid>` index，最终对自有prefix的scoped GET和PG查询剩余0；testDB保留复现，未flush/drop别人的索引或修改生产库。

原T30文件保留字节原件，自有资源副本只替换DB/schema/index守卫；业务输入/期望不变。五线程文件自有副本只改fixture import到本资源副本；原作者文件未改。原四红直接原bytes复制。所有src/原tests/config/progress/pyproject/lock diff为空，资源副本和封存说明不改变公共合同或评分分母。

实际本地模型与初审一致：cache `C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime`，E5 multilingual-e5-small固定revision614241f6、rerank mmarco-mMiniLMv2-L12-H384-v1固定revision1427fd65，原精确fingerprint/384维。只有三条中英提示注入/米饭synthetic正文使用真实E5/PG余弦与重排；其余30集成用显式FixtureSemanticModels，不作为正式semantic live或金标。无新下载、付费API、测绘、PoC、holdout或人工标注。

本次中文完整retrieve **7.0522s**、英文 **5.5004s**；BM25 0.0383/0.0359s，vector含query embedding2.7553/2.2260s，rerank4.1199/3.0856s。两条都超过5秒，保留慢例，不改门槛。此为同资源段上一次synthetic小样本，无冷/热/并发控制，不能归因整个差异为锁开销或模型回归，也不能签完整QA SLA/吞吐/准确率。源可见新增两次当前读和有限身份锁；扩大语料之前应记录实际SQL/模型批次数，按初审已列的重复span验证、全scope重建批处理等建议测量后优化，没有必要建立通用BaseService。

F3/P3此次仅补上内部检索当前性证据，未给评分档位。unit/contract/security和上述真实integration通过；live仅一个已冻结本地模型synthetic接线例。正式0020迁移/FK、worker/settings/API/回答/UI、graph、多跳、历史真值、资产四态补查、真实来源题集/人工gold、正式性能与完整R12/T30/G-D仍not_run或既有未完成，不升级为accepted。

主控下一步可依据本限定结论推进0020/worker的单独冻结和新审查，再按正式前置恢复产品检索/回答链。调用方仍须其最后身份/事实发布围栏。本review到此停止，旧初审材料与新复核raw manifest/report SHA分开封存，不覆盖失败记录。

**Verdict: Ship — 仅固定内部retrieval服务及Must1修复。Not checked：正式迁移、worker/API/UI、多跳/graph、真人gold、完整QA/SLA与整R12/G-D。**
