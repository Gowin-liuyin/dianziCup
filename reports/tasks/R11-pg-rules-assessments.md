# R11 / T27–T28 · PostgreSQL 规则与资产证据包内部切片

记录时间：2026-10-16 Asia/Shanghai；状态 awaiting_review，内部切片实现 complete；整 R11/T27/T28 仍 partial，不自签 accepted/G-D。作者 worktree `D:/wt/r11-pg-assessments`，分支 `codex/r11-pg-assessments`，冻结代码 **d56a1ed306d975be408a2f6f8fbe3e905d940643**。材料目录 `reports/runs/recovery_r11_pg_assessments_20261016/`；禁止推送，实际没有 push。

## 范围与依据

已读取 AGENTS、执行地图/恢复 R11 与 U04/U05/U08、03 §3.6–3.8、04 W06/W07、05/06、真实 T27/T28、完整条件提案、当前状态/交接、实际 asset/knowledge/auth/input roster 源码及最新 Ponytail 5.2.0 full。基线 e310f7735bd499c4d9fbcefe8a644e2309a16a62；仅依赖冻结纯函数 328ed7a933a9a81ec715f447235f4b933e0ed506 + 生命周期修复 ddfbf8c。既有正向迁移采用 c842333fe56a4ab3018a3216a8ddcd6a34639ae1 和 281371b072a696d972aa3c38519b8646393c98e2；作者未改迁移。不能把本切片自检等同 pure 独立审查通过。

首次业务代码前执行 CBM 当前 src 独立 fast index（1511 nodes/7815 edges，assets 排除）、assets 独立 index（198/823），并读 schema/architecture/trace 与 `rg` 实际调用者；没有用旧图代替当前源码。初次 CLI 参数错误（遗漏 cli、schema 漏 project、trace 错用 source）修正后读取成功，均为工具使用问题。最终 fresh src/assets 图、完整 qualified 方法 trace 和 callers rg 已保存；首次短名 AssessmentService.commit 找不到的红日志保留于 first_final_assessment_trace，修正后 final_cbm_fixed exit0。图不是源 ACL、事务锁序或测试的替代证明。

主任务明确冻结 [内部兼容提案](../../docs/decisions/CR-R11_pg_assessments_proposal.md)。修改仅九个新增文件：五个 assessment 内部模块、三个直属新测试、提案。未改 pure conditions/rules/version、assets、API、worker、认证、公共 DTO/schema、依赖、既有测试/金标/门槛/holdout、全局 progress/config；用户与主任务现有未提交修改在主目录保持。

## 实现及调用者

- RuleService 的 create/validate/review/publish/retire 都使用实际 auth session 和 PG users 行构造 AccessScope，不收 tenant/role/policy/approver 自报参数。固定 SERVER_RULE_VALIDATION_POLICY 自动发布关闭，未知/无语义审核明确 pending_semantic_review。
- 六表共用既有 PG metadata；业务路径不建表。规则版本内容不可变、candidate→validated→published→retired 单向，验证收据追加；发布、退役和现有 change/epoch/job/outbox 同事务。每个 rule family 保持 event/scope/kind 身份；foreign family 任意新 version 404；partial unique index 与 family 事务锁保证至多一个 published。新版本先显式退役旧版，不能悄悄更替。
- 已有 claim_evidence.validated 与坐标核验只作为必要前置；必要性与 range_complete 必须由精确叶/claim/span/源摘要绑定的独立、有实际 PG 管理权限审核者收据确认。模型 claim 保留 unverified，不可自行 publish。所有本次审核身份与理由均 **synthetic fixture**，人工标签 0，不计 manual/live。
- 来源必须与 document/revision/assertion/event 配对；当前文档 content_hash 对应当前 revision。每个 block/quote 的 Unicode code point 左闭右开坐标与 SHA256 重验。prepare/create/validate/publish 读取 PG 指定 content hash 的原文对象并校验 hash/大小；单对象 2 MiB，总 8 MiB、20 来源、64 支持绑定。没有任意 URL/SQL/shell 产品工具或 PoC 执行。
- Assessment prepare 固定资产快照、发布规则版本、全部事件来源（含未命中的来源）、审核/证据输入、逐分区 epoch、资产/规则 fingerprint，写 PG preparation receipt。commit 比较 receipt_id+actor 与完整准备对象，拒绝伪造输入；短事务再锁认证/资产/source/document→publication/family/event→claim/evidence/assertion/link 并重查。实际 source、InventoryService、KnowledgeRepository 写方锁序已按源码核对，等待 publication 时不持 claim 锁。
- 源、资产、知识或规则变化保留 stale，旧结果/unknown/negative/history 不覆盖；角色、撤销或 ACL 改变拒绝且无新输出。重放返回原 assessment 身份且实时刷新 freshness，不会恢复旧 current。历史访问同样检查原来源 parent 最新 ACL。
- 证据包保存四态、完整树、每叶 span ID、原文 quote/位置/hash、精确资产 field refs、全部来源/规则版本/epoch/digest、限制与独立 exposure_result；网络路径不会改变软件适用性，未发布规则返回 insufficient_evidence。mitigation 没有资产关联的既有确认通道时保持 unknown，不编造资产缓解事实。
- knowledge_epoch **仅表示已有 public epoch 的投影**，不是 global counter；缺 public 行保留 null，scope_epoch_map 缺分区也为 typed null。有效性只比完整 map/source/asset/rule/审核 digest，不只比 scalar。scope watch 保留事件、规则包、资产包和空 published 结果范围，配额兼容已有 10000 components/4096 字符清单，不缩成 128/200。

`callers_rg.stdout.log`：目前只有新内部服务/直属测试直接调用，现有生产 API/worker 未接线。完全没有 rule 行的任意查询空结果生成未实施；已知 candidate 但无 published 的真实 PG 输出会保存显式 no_published_rule watch。T36 反向候选索引、调度、默认 latest 选择 API 仍未实施。

## 实际验证

所有完整命令、工作目录、秒级开始/结束、耗时和退出码见 commands.jsonl；pytest 原始 stdout/stderr/JUnit 与测试数量见 test_counts.json。执行器 `run_checks.py` 只在内存读取 WSL root-owned connection.json，把 TEST_DATABASE_URL 放环境，不进 argv/日志；专用数据库 **test_dianzi_r11_assessment_20261016**，随机 schema。两次都由空 schema **正向实际 Alembic 升到 0019**，再显式创建六个本切片局部 Table；没有 downgrade/drop/删除既有数据库。先前 schema 与 receipt 保留。局部 create 不能计作生产 0021 迁移通过，0021 not_run，由主任务独占。

以 `D:/dianzi/backend/.venv/Scripts/python.exe` 在本 WT backend 执行：

| 检查 / 实际命令 | 时间 +08:00 | 退出 / 数量 | 原始证据 |
|---|---|---|---|
| `-m pytest tests/integration/test_r11_pg_assessments.py --no-cov -q`（frozen_pg；冻结代码后） | 06:26:54–06:27:06 | 0；33 passed，0 fail/error/skip；pytest10.25s | frozen_pg.stdout.log / .xml |
| `-m pytest tests/unit/test_r11_pg_assessment_scope.py tests/contract/test_r11_pg_assessment_contracts.py --no-cov -q`（scope_limits_final） | 06:22:53–06:22:55 | 0；7 unit + 5 contract =12 passed；0 fail/error/skip | scope_limits_final.stdout.log / .xml |
| `-m pytest tests/unit/test_t26_version_engine.py tests/unit/test_r11_version_branch_context.py tests/unit/test_r11_manifest_parser.py tests/unit/test_r11_manifest_parser_identity_time.py tests/unit/test_t27_condition_rules.py tests/contract/test_r11_condition_schema.py tests/security/test_r11_condition_security.py --no-cov -q` | 06:15:48–06:15:54 | 0；354 passed；0 fail/error/skip | relevant_pure.stdout.log / .xml |
| `-m mypy src`（frozen_types） | 06:26:54–06:26:55 | 0；126 source files | frozen_types.stdout.log |
| `-m mypy` 五个新增 src（internal_types_frozen） | 06:22:56–06:22:57 | 0；5 files | internal_types_frozen.stdout.log |
| `-m ruff check` 八个新增代码/tests；`ruff format --check` 同文件 | 06:26:54、06:27:40 | 0；8 files formatted | frozen_quality / frozen_format.stdout.log |
| `cbm_audit.py`（frozen_cbm） | 06:26:54–06:27:18 | 0；23.484s，冻结源码/资产 index+schema+architecture+trace+rg | frozen_cbm + final_*.log |
| `inspect_evidence.py` | 06:27:36–06:27:39 | 0；六表反射、15 JUnit、12源码hash/blob；真实 test password匹配0 | inspect_final + reflection/hash/manifest/scan JSON |

33 个最终 PG case 中，23 integration +10 security；security 初扩展单独实际跑10 passed，integration 初扩展21 passed（之后追加2 family case）。含来源/Unicode quote/hash、必要性待审/独立 review、range completeness/refutes、三版本/三配置/版本冲突、软件与网络分栏、unpublished/model、跨租户/低权限、角色/来源 ACL 并发、会话撤销、全部 source roster/资产/原文并发变化、重放、伪造 preparation、结果和生命周期不可变、发布/证据包事务回滚，以及两 publisher 竞争和 partial unique 的数据库负例。

原红不删：pg_red exit2 是 fixture import 名称错误，0 业务测试执行；pg_red2/pg_red3 各15 fail 是 SourceRevisionBlock/register_source_revision_blocks fixture 必填参数遗漏，不是环境或业务算法失败。两次后停止扩大业务补丁，按完整现有签名定位并单用例验证 seed_targeted1 pass；pg_initial14 pass/1 fail 是 seed 违反既有“model_hypothesis 必须 unverified”合同，修复新 fixture 后 pg_baseline15 pass。后续26/31/33均真实通过。Ruff/mypy 初稿问题仅本次新增代码，类型逐项改正未禁用检查；CBM 首次短名 trace exit1 保留，修正实际 qn 后 exit0。

本切片定向 pytest 使用显式 --no-cov，不报告全局覆盖率、全部后端测试、性能门槛或外部对照通过。既有原始 T24 PG suite 的独立 DB naming guard 不在本专用库改写；当前新 PG cases 直接使用实际 InventoryService，相关既有 pure 回归已执行。

## 制品、未运行、偏差与下一项

six_table_reflection.json 对应当前新 schema 的实际 constraints/FK/index；asset_snapshot_hash_checks.json 校验真实持久化 raw bytes SHA 与 canonical snapshot hash。assessment_evidence_fixture_rows.json 保留本次实际 PG 输出/树/引用/epochs，明确 fixture_data=true、human_labels=0。source_manifest.json 保存工作树 SHA256、Git blob ID、实际 blob SHA256并核对 HEAD；artifact_manifest.json 保存所有原始文件大小/hash，排除可再生且未提交的 __pycache__。日志/XML局部 -text/-diff、JSON/脚本/属性文件的局部 -text 与 cr-at-eol 仅保护该 run 目录的原字节及正常 Windows CRLF，不忽略业务静态/类型测试，不修改原红字节。首个材料 diff 把保留的 CRLF 误报 trailing whitespace，原始 material_diff_red.log 保留；限目录精确属性后复核，不重写红日志。源码和工作树换行形式分别由 blob 与 raw hash 标识。

unit/contract/integration/security：本内部切片 passed，未替代独立 review 或整卡状态。frontend/e2e/live/manual：not_run；生产0021/API/worker、完全无 rule 行的空查询流程、T36重判、OpenVEX、真人金标与至少3→5产品可靠真值：未完成。外部 model/provider/source **0 calls**；费用上限 unknown，未启动付费任务。无来源 live、人审核或性能数据伪装成功；原红和其他 R11/阶段阻塞保持。

合同偏差：公共合同不改；内部 public epoch 投影/null、一个 published family 和 scope watch 配额已由主任务冻结记录。没有改变指标分母/阈值。评分证据仅支持 F2/F3 的可追溯内部资产/条件计算与 F3 结构化证据包；P2 人工准确率/召回率、F3完整产品页面、A1九职责真实 Agent 工作流均无本次验收证据，不登记已达标。

下一项建议：主任务安排新的非作者独立审查此冻结代码与材料；有 Must 先改再复核。审查通过后主任务独占0021正式迁移和相应正向/保留数据验证，再分别接 REST/jobs/worker、真人来源/审核与 U05 浏览器证据。此作者停在单切片，不继续 R12 或签 G-D。
