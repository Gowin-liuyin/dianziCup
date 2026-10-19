# G-C / R06 来源证据批量保存 · 新独立初审

这项改动把已解析来源修订的块与全文证据按最多 500 行批写，保留原文、坐标、归因和历史；NVD/vendor 的支持关系仍由原事实证据入口与发布器核验。**本次未发现需要阻断该保存服务补丁的产品问题，限定服务级 Ship。** 两次原 Windows Job 资源上限下的真实原文离线重放都完整提交，execute_job 为 **1.330 / 1.514 秒**，低于原 35 秒守卫线。

任务范围 G-C/R06，关联 T09/T12/T16/T07；被审状态仍为 awaiting_review，整卡与 G-C 没有在本报告中验收。评审人是新非作者 `/root/r06_bulk_source_evidence_first_independent_review`；工作树 `D:/wt/r06-bulk-review1`、分支 `codex/r06-bulk-evidence-review1`。只新增本报告与 `reports/runs/recovery_r06_bulk_source_evidence_review1_20261016/` 下自有脚本、检查与日志；未改生产代码、旧测试、进度或 accepted，未 commit/push/spawn。

## 冻结身份与依据

| 对象 | 独立核对结果 |
|---|---|
| 代码提交 | `a89e94b66e240a0c958f7b7e2b8dc22e88f79348` |
| 代码 tree | `25bcfe534c447b5b83d4bceed9b1393cfb266109` |
| 基线 | `8a1b04d48346d8550f0326a77f003246a0ebbab5` |
| 作者材料提交 | `bdebeca358f0cfd63630b223dee64647b5280687`，不把材料提交当另一业务版本 |
| 作者报告 | `R06-bulk-source-evidence.md` 原始 SHA-256 `54ca5a36bc464456e2e06a539b4e740bf02b1b4183158f333384a24dde1a8a99` |
| 作者 manifest 原始文件 | SHA-256 `2c0c3fffc1dc078ead919500842859fa63286de86f09477831a6285241fe1aca`，20,265 B |
| 同 manifest 的 Git blob | OID `4f75bbd2579693b0ff343e4a3d765da764ca730e`；SHA-256 `e243c7c6bfed8e068d7fc7ee6a0641d578484e743bf605866aeb6e9dcaf5a35a`，19,802 B；与原文件仅 CRLF→LF 不同 |
| 作者冻结原字节 ZIP | SHA-256 `ddc424412d521948f25c2bb351dced1e3d1a43a7617f4552a027986b0f1ad82b`，94,418 B；86 个成员全部按 manifest 原大小/hash 核对，再核 ZIP 本体，共 87 条 |
| 旧正式诊断 | `D:/wt/r06-release-pg-diagnosis/reports/tasks/R06-large-release-persistence-diagnosis.md`；manifest SHA-256 `d223c872a6844f6419521e7164da2b6fdc9ae0427a5b4085dd2f2bf58048d1cc`，81 个文件逐条复核 |
| 原文 | 仓外 `D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin`，616,865 B；SHA-256 `25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7` |

原文没有 Git blob，也未被输出、索引或复制入本报告/run。以上 Git blob、原始物理字节与 ZIP 成员分别核验；没有把 Git 换行归一后的 hash 冒充原始日志 hash。新工作树源文件也仅有 checkout 换行变化，规范后的实际源码等于固定提交。

已读 AGENTS、00 执行地图、12 中 R06、T09/T12/T16/T07、03/04/05/06、状态与交接、CR-R06_bulk_source_evidence、相关来源集合合同、作者报告及旧正式诊断。采用 ponytail 插件 5.2 review 工作流，先读 diff，再读关联源码、全部调用者、实际事务和测试。主仓原有未提交文件未动；建工作树前确认目标路径和分支无占用，再自行执行 `git worktree add -b codex/r06-bulk-evidence-review1 D:/wt/r06-bulk-review1 a89e94b66e240a0c958f7b7e2b8dc22e88f79348`。

## 源码与调用链核对

生产 diff 恰为 `knowledge/revisions.py`、`ingestion/source_documents.py`、`ingestion/catalog_documents.py`。新入口 `revisions.py:70–179` 在 IO 前检查全部块的范围、Unicode 长度、digest、唯一 ordinal、页码与元数据；一个 savepoint 内对 revision 一次 `FOR UPDATE`、存在/current/精确 visibility/tenant 核验，每批最多 500 个块和 500 条全文证据。块与证据分别 10/15 字段，单批绑定最多 5,000/7,500；没有截原 JSON 字段、减少节点/块、放宽原响应限制、修改 schema 或新增总块数门。

`catalog_documents.py:262` 对每个新修订批写全部块及全文证据，全文 `supports_claim=False`；`source_documents.py:558` 只批写块，随后仍在 `:584–610` 调 `_fact_submissions`、`KnowledgeRepository.publish` 和 `_publish_cvss`。`_fact_submissions:642,679` 仍调用旧 `attach_evidence_span`，先核对字段值及 CVSS authority/vector，再保存独立支持证据。R04 的 `test_quote_mismatch_is_not_saved_as_supported_fact` 原 monkeypatch 实跑通过，不能被新 helper 绕过。

`add_text_block`、`attach_evidence_span`、`save_document_revision`、`register_response_content` 的定义与 8a 基线逐字相同；其 AST 切片 SHA 在 `audit_final_receipt.json`，旧 R04 测试 Git blob 也始终是 `a93f181f94312902dca5d23fb85cc1229b3948bb422f8e8faa5e9ed8b120da68`。UUID 仍独立生成；块→修订、证据→块的对应关系逐字段验证，不用 parser block ID 替代数据库身份。

实际路径为 runtime 注册 → `executor.py:92–125` 短事务认领及业务事务 → `source_jobs.py:435–528` source/cursor、独立 recorder、fetch/normalize、source 或 catalog 保存 → revision/CAS/hash 锁/bulk → `source_jobs.py:560–589` cursor CAS、页收据、release 与必要 continuation enqueue/outbox → executor complete/外层 commit。0016 的响应收据走独立事务；业务页面、FetchAttempt、游标、job 效果仍由原事务提交。保存失败没有业务页或游标残留；CAS 文件可以独立留存，由原 GC/hash-lock 规则追责。

独立 CBM 0.11.0，仅索引本工作树 `backend/src`，cache `/tmp/dianzi-cbm-r06-bulk-review1-20261016`、项目 `r06_bulk_review1_a89_20261016`；1411 nodes / 7144 edges，not_indexed/skipped/partial/unusable 均 0，按工具排除规则排除 `ai_intel/assets`。完成 index/schema/architecture(all)、12 条初始双向 depth=2 trace，以及 `KnowledgeRepository.publish`、`DimensionRepository.publish` 两条消歧后的 qualified trace。初始 `publish` trace 返回 ambiguous，不能当已覆盖两个发布器；qualified 结果已另存。动态闭包/file-level heuristic 与实际 `rg`/源码交叉，不把图边当动态正确性证明。

`all_source_callers.log`、`all_evidence_claim_callers.log`、`r07_model_publication_callers.log` 覆盖 src/tests/scripts/config/contracts。新 helper 的生产调用只有两个来源模块；旧证据写入 API 没有额外 export/config 调用被漏改。当前 a89 的 R07 `model_fields.py`/`field_sources.py` 产生并核验 model hypothesis，不直接写 PG 支持事实；现有 KnowledgeRepository 和 DimensionRepository 继续检查 scope、来源、活动关联、坐标核验及 `supports_claim`。其它分支上的新模型发布模块不属于这个固定 tree，不能由本单宣称已集成验证。

## 两次原资源上限下的真实原文离线重放

每次为全新自有 `test_dianzi_r06_catalog_bulk_review1_<runid>` 数据库、job/key 和仓外 ContentStore；私有 WSL Ubuntu-22.04/root 的 connection.json 只 capture 后在内存解析，验证 loopback:25432、test 基底和 test 用户。DSN 不进 argv/stdout；没有 dev DSN、旧库写入、downgrade、旧 schema/drop、MinIO/API/worker/beat 启动、全局 WSL 操作、依赖安装或秘密 vault 访问。

复用旧冻结诊断的真实 OwnedJob 模块，原模块 SHA-256 `2fb82e49e443b953890abfa6bd20f7a6861be0241cd6654d69821fc3f33891c4`。实际查询确认 CPU rate 2000=20%、每进程 536,870,912 B、总 2,147,483,648 B；本次在 build_engine 和 forward migration 前加入 Job，使重放辅助计时/采样/验证也受限。限额与生产 60 秒 job/source lease 均未改变。

显式 fixture fetcher 仅返回固定 page=1 GitHub URL、同 hash 原字节、空 headers 终页；`execute_job → collect_page` 是原实际业务入口。NetworkGateway HTTP 禁止、socket 只允许本 PG 地址：各轮 fixture fetch=1、真实 HTTP=0、非本地 socket attempt=0。stream_kind=live 只表示原游标分区；这是**真实原文离线 PG 重放，不是 live 分页或 MinIO 证明**。

| 指标 | 重放 1 | 重放 2 |
|---|---:|---:|
| execute_job wall / Python CPU 秒 | 1.3297405 / 1.03125 | 1.5142272 / 1.265625 |
| collect_page wall 秒 | 1.3062975 | 1.4905000 |
| persist_catalog_documents wall / CPU 秒 | 1.1640398 / 0.90625 | 1.3259378 / 1.125 |
| 20 次 bulk helper 累计 wall 秒 | 0.8519082 | 0.9343920 |
| 完整子命令 wall 秒，含迁移/所有辅助核验 | 3.8432219 | 4.0263778 |
| controller 全 wall 秒，另含资源创建/脚本封存 | 4.5456520 | 4.6697418 |
| OwnedJob 最终 CPU 秒 / 峰值 Job 内存 B | 2.484375 / 91,287,552 | 2.671875 / 91,611,136 |
| SQLAlchemy cursor 调用数，enqueue 至业务 commit | 516 | 516 |
| executemany 调用 / 参数行 | 80 / 23,654 | 80 / 23,654 |

两次真正同 raw handler 恰 2 次；controller 合计 **9.215394 秒**，每次 <120 秒、总 <240 秒。没有第三次同 raw handler。峰值内存约 87.1 / 87.4 MiB；CPU 是 Windows Python 进程/采样线程或 Job 记账，不含 PostgreSQL server CPU。各阶段包含下层调用，不可相加当总 wall；小 CPU 值受约 15.625ms 计时粒度影响。

SQL 指标必须保留口径：516 含实际 enqueue 的五次调用（advisory lock、查同 key、job/payload/outbox 三 INSERT）；扣除这段为 511，但这是按实际源码路径划分的 driver 调用。80 次 executemany 分别承载 11,827 个块和 11,827 个证据参数行，**不能称 PostgreSQL 物理语句仅 511 次，更不能直接用 511 对比旧 71,344 物理/逐条执行的全部计数**。旧诊断的 70,962 次逐块六 SQL 已被块/证据批写、每 revision 一次核验及 metadata 一次写入替换；新 driver shape 中无逐块 UPDATE/SELECT。真实 wall 与完整行核验才是本次同资源结果。

`verify_raw.py` 使用标准 json 独立迭代原始 leaf，按 RFC6901 转义路径与原叶值生成期望，没有调用被测 parser/helper 生成期望。各轮完整比对 20 个 canonical member bytes、20 revision 的源响应 hash/URI/可见范围与原 draft/prerelease metadata、11,827 个 ordinal/Unicode start-end/json_pointer/page/block type/hash/quote/locator/scope/supports_claim/verified_at/created_at/coordinate_version 及关联 ID；21 个 CAS 物理对象 hash 全复验。日期精度及其它修订 metadata 的行为来自原相关回归与未改定义检查，没有把它们说成新 raw verifier 逐列比较。最终每库 documents/revisions=20、blocks/evidence=11,827、page receipt/response receipt/FetchAttempt=1、content_objects=21、cursor generation/last_successful_page=1、lease 已释放、job succeeded、initial outbox=1、非法证据=0。outbox=1 是初始 enqueue；终页 fixture 没有验证真实 continuation。

旧诊断的两次 execute 55.656/54.600 秒、保存 55.438/54.433 秒，以及原 35 秒 watchdog 在有效 60 秒 lease 内误杀的 red 均保留。作者第一次 handler 后置短 Alembic ID 错误 exit 1、缺精确 stage 计时；作者第二次成功却未施加 caps，也都保持原记录。本评审用新独立样本补齐同资源门，没有把旧 red 改为 green。

## 真实检查、错误与复验

统一入口为 `D:/dianzi/backend/.venv/Scripts/python.exe -B reports/runs/recovery_r06_bulk_source_evidence_review1_20261016/control.py <mode> ...`，控制 cwd 本工作树；pytest/static 子命令 cwd `backend`。每项 `.command.json` 有 +08:00 起止、完整无 DSN argv/cwd、exit、wall、PID/timeout/wait；stdout/stderr/JUnit 分开保留。下表时间均 2026-10-16 +08:00。

| 检查 label / 实际参数范围 | 起止 | exit / 结果 | wall 秒 |
|---|---|---|---:|
| new_tests / 四个新增文件，importlib、no-cov | 04:31:37.468–04:31:47.448 | 0；17 pass，unit6/contract1/security5/integration5 | 9.980 |
| replay 1 / 原 execute_job | 04:32:06.933–04:32:10.776 | 0；20/11,827 完整核验 | 3.843 |
| replay 2 / 原 execute_job | 04:32:28.687–04:32:32.714 | 0；20/11,827 完整核验 | 4.026 |
| legacy_127 / 旧五文件首轮 | 04:32:35.966–04:32:38.070 | 2；1 collection error，旧非 package import 未入 sys.path | 2.104 |
| r04_adapted / runner 字节前置首轮 | 04:32:41.238–04:32:42.370 | 1；checkout CRLF 与原 Git LF hash 混用，未进旧 body | 1.132 |
| legacy_127_ready / 加入原 integration import 路径 | 04:33:22.474–04:35:28.089 | 0；127 pass，0 fail/error/skip | 125.620 |
| r04_adapted_ready / 原 R04，仅 page_engine→catalog_engine | 04:33:33.257–04:34:08.957 | 0；25 pass，原输入/body/断言不改 | 35.703 |
| t05_t07 / 两原 PG 文件 | 04:33:44.074–04:33:49.355 | 0；21 pass | 5.279 |
| r04_original_resource_red / 不适配旧 fixture | 04:34:49.860–04:34:52.181 | 1；25 setup errors，旧固定库名拒绝新库 | 2.321 |
| Ruff / 三源文件+四新增测试 | 04:35:53.587–04:35:53.789 | 0；all checks passed | 0.202 |
| mypy / 三源文件 | 04:35:56.156–04:36:00.720 | 0；no issues in 3 source files | 4.563 |
| independent_probe / 仓外测试首轮 | 04:38:31.711–04:38:33.561 | 1；4 setup errors，backend conftest 未加载 | 1.850 |
| format / 同三源+四测试 | 04:38:36.154–04:38:36.345 | 0；7 files already formatted | 0.191 |
| independent_probe_ready / 显式 -p tests.conftest | 04:39:28.604–04:39:34.466 | 0；4 pass | 5.862 |
| audit 首轮 | 04:40:07.047–04:40:07.602 | 1；manifest 原物理 SHA 与 Git 归一 blob 混用，未触业务 | 0.555 |
| audit_ready / 原字节 ZIP+Git 分别核验 | 04:41:14.937–04:41:22.560 | 0；87 条作者材料、资源和初始用例核验 | 7.623 |
| independent_probe_final / 增加实际 source/claim updater | 04:42:26.024–04:42:32.006 | 0；5 pass | 5.982 |
| audit_final / 含旧 81 文件、全部 12 自有库 | 04:44:44.331–04:44:51.787 | 0；raw/材料/进程/资源核验通过 | 7.455 |

旧 127 范围是 catalog_documents/source_worker/failed_response、R02 knowledge_revisions/relation_identity；25 为原 R04 source_documents；21 为 T05 persistence/raw_store 和 T07 jobs/outbox。这些分开列示，作者 security_style 的重复 5 个没有再相加。旧 R04 25 setup error 实跑保留；批准的资源适配只替换 runner fixture 为本新库、原 catalog_engine 的自有 UUID schema/forward 0016，测试源码 Git blob、输入与期望不变，没有访问硬编码旧库。

新 17 个覆盖逐条/bulk 每列等价、500/501、digest/ordinal/NUL/页码前 IO 拒绝、missing/noncurrent/跨 tenant、第二块批失败、storage failure 整 job 事务撤销、历史与重复页。自有最终 5 个另外验证：实际第二批唯一约束 SQL 失败，前 500 行及证据一起撤销而旧行保留；第二证据批 SQL 错误导致整 job page/cursor/fetch 回滚且 0016/raw 仍存在；document ACL 冲突拒绝；两个真实 PG PID 的 revision lock/source updater 阻塞由 pg_blocking_pids 观测；两个实际 vendor 来源写进程更新后旧 claim 非 current、旧 evidence 留存且活动关联只指新修订。4 个初始独立 probe 的复跑不再计为另 4 个不同用例。

CBM 首次 `cli --help` 返回 unknown tool（exit1）；architecture 首次多传不支持的 max-output-tokens、第二次 array flag 用 JSON 字符串而 CLI 实际按值解析，两次 exit1 留存；读取该工具专用 help 后使用 `--aspects all` 成功。不是同根因连续两次扩大业务补丁。所有 CBM 正确 index/schema/architecture/trace exit0，逐命令时刻/argv在对应收据；qualified publication 两条为 04:45:26.204–04:45:32.604。前置读/建 WT 的工具结果在会话记录，未补编其准确 +08:00 起止；有业务观察的上述命令均有真实时钟记录。

## 发现、范围限制与交接

**Must fix：无。Should fix：无与本候选服务范围相关的确定问题。** 未发现删原文字段/历史、绕权限或支持核验、部分批残留、游标提前提交、错误吞掉伪成功、租约/CPU/预算放宽或新依赖。无 Lean 删除项。

非阻断记录：材料的原物理字节 hash 与 Git 换行归一 blob hash 需要明确区分，已在本报告和独立 audit 中处理；driver cursor call 与 PostgreSQL 物理语句口径必须保留，未对物理 server 语句数作新实测。原 watchdog 工具 owner 的修复以及新真实边界仍需各自审查/运行；不能用此服务通过替代它们。

| 验证层 | 本次状态 | 具体范围 |
|---|---|---|
| unit | passed | 新6个前 IO 负例；非全项目 unit |
| contract | passed | 500/501 有界写入及全文证据非 supporting fact |
| integration | passed，限定服务 | 新5 PG、旧127、资源适配25、T05/T07 21、自有5 probe、两次原 caps 原文重放 |
| security | passed，限定边界 | 新5 scope/current/missing、旧租户/quote/identity及自有 doc ACL；非全项目安全审计 |
| frontend | not_run | 无前端/UI 变更与浏览器运行 |
| e2e | not_run | 未跑 API/Celery/MinIO/浏览器部署链 |
| live | not_run / blocked_live | 无原 Link headers、真实 HTTP、MinIO 或新真实采集段 |
| manual | not_run | 没有人工评分、标注或正式验收；本次为独立代码与服务实跑评审 |

F1/E1/R1：提供完整来源原文/证据、历史、事务、权限与可追溯保存证据。P1：提供固定同 raw、同原 Job caps 的限定保存负载耗时；不签正式 ≤6h、独立漏采参考集合、来源八类 live、连续运行或完整 R06/T09/T12/T16/T07。W01/T16 要求的原始采集与异步解析完整切片仍不由这项同步保存优化验收；冻结 CR 对本次窄保存合同的授权没有删除该整卡要求。

04:44:51.675 +08:00 的最终 audit：两个实际 replay Python PID 16232/24752 按 creation time 校验已退出，controller 子命令均已 wait；sampler 已停，12 个自有数据库只读复核均无其它 session、无残留 test_r06 UUID schema。数据库与仓外 CAS 保留复查；未删旧库/原响应/用户文件。原 raw 精确 bytes、捕获的 test 基底 URL/credential 在本 run 扫描命中0；该范围没有冒称读取供应商/vault 秘密。后续只读 CBM 命令也已退出。两次 replay 的脚本 hash 在启动前记录；随后添加其它检查 mode 的 controller 已按该记录重构出原执行字节并核 hash，相同 replay/verify_raw 原字节也已封存，见 executed 快照和 provenance。

计划偏差仅评审 harness 的导入、fixture/换行和 CLI 参数前置错误，全部记录及复验；产品合同与门槛没有偏差。下一步建议 root 按固定 a89/tree 整合该服务补丁，并另开新、固定同版本、有界的真实 MinIO/live 采集段，保留旧失败段；实际 continuation、自动恢复、完整覆盖和时效继续分别验证。本报告不更新 accepted，也不签 G-C。

**Verdict: Ship，仅限本次来源块/证据批量保存服务及所列固定版本。**

Not checked: 真实 Link 分页、生产 MinIO/API/Celery/browser、来源八类 live、停机后真实补采、持续运行与正式 ≤6h 指标、其它分支新模型发布模块的同版本集成。
