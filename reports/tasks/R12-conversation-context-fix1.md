# R12 · conversation-context boundary fix1

任务状态：`awaiting_review`；实现状态：`complete`（限定四项边界）；unit / contract / integration / security：`passed`；frontend / e2e / model live / manual：`not_run`。作者不登记 accepted，不 push，不改进度。

工作树 `D:/wt/r12-conversation-context-fix1`，分支 `codex/r12-conversation-context-fix1`。输入作者 code `6259db6d98d67c1be274370ce20775133a8b0520`、材料 `f557df069a0e0eb74194557ebdb9be338d9a5b0e`；新独立 reviewer 材料 `6383926b169e7f9ac657e9a32a5802f116937d25`。本轮代码冻结 `1e210090d74d1444101330f0c8b8637ad1dd50a3`，6 文件；代码提交后没有再改源码/直属测试。最终测试 receipt 的 source_ref 是当时 HEAD f557（修复尚未提交），其工作树源码随后原样冻结为上述 code；`fix1_source_manifest.json` 同时记录 raw SHA 与 clean Git blob。

## 范围与实现

已读 AGENTS、00执行地图、R12恢复卡、T30/T31/T35、03–06合同、state/handoff；使用 Ponytail5.2 full。仅改 `conversation_context.py`、`conversation_contracts.py`、`evidence_bundle.py`、必要 `conversation_models.py` turn guard，以及新增 `test_r12_conversation_boundary_fix1.py` / `test_r12_conversation_boundary_fix1_pg.py`。API、worker、公共schema、grounding、hybrid、认证、共享锁/依赖、进度、金标及原9测试不改。

| 评审 Must | 根因修复与可观察行为 |
|---|---|
| 无成功父轮或对象的“它的修复是什么” | resolver 在无 event/asset/显式标识绑定时返回 `reference_ambiguous`，无派生查询；PG不预留答案。失败父轮与完成但未绑定对象的父轮均不能提供对象。显式标识、显式event以及普通首问保持准入。 |
| 过期轮遇新 nonce / 旧 version 409回滚恢复 | `admit` 在独立短事务中重新认证、owner会话行锁、读取当前active turn，再执行既有reservation/state CAS与终态保存；该事务退出后才检查新准入。后续CAS/clarification拒绝不会回滚expired历史/清槽。准入事务重新认证并重锁会话，仍保留版本CAS、单active、幂等与原answer ID；不创建额外付费记录。 |
| 子轮绕过已保存父context hash | 成功父轮选择同时要求 completed response与completed workflow；只选turn ID，再走共享 `_turn` 完整性入口。typed context的canonical digest、DBdigest、conversation ID、base version和原问题列都匹配，所有父消费重新核当前ACL。bundle复用同一digest validator；损坏数据返回固定安全503code。 |
| 完成历史因当前eventinactive被拒绝 | 历史/replay按当前事件ACL和当前asset read权限授权，不把active资格当历史权限；原context/hash/版本/快照不变。inactive event或快照改变返回 `reference_freshness=stale`，其余为unknown（未证明事实当前性）。新问题仍重新加载active事件、当前快照和当前PG事实；撤回/合并身份新问返回clarification，不能继承旧结论为真。 |

metadata只追加 `prevent_qa_turn_changes` / `qa_conversation_turns_immutable` BEFORE UPDATE OR DELETE。与唯一0024作者批准statement strip UTF8 SHA完全一致：函数 `579d7b1a844c6c3efc295bbb5ae41a6a2096693e09af275fa4d5416d1f460d43`，trigger `76472dea4ba24248e49eacc50897f7903dd8cbfd38f402eac138ed3808a9c585`，见 `metadata_0024_guard_match.json`。保留deferred ownership；生产0024及ownership函数固定部署search_path由唯一迁移Agent负责，本轮未改migration。

旧损坏数据的应用拒读不能被新guard遮住：owned fixture仅对原same7父篡改、原security摘要篡改和新身份错配3个精确case，显式 DISABLE本schema guard并打印 `explicit_legacy_corruption_fault_injection`。其他case保留guard，新测试实际证明UPDATE/DELETE拒绝。原probe、原断言、原9测试字节不被编辑。

## 冻结输入与调用/锁序

same7输入绝对原路径 `D:/wt/r12-conversation-context-review1/reports/runs/recovery_r12_conversation_context_review1_20261016/test_review_negative.py`，SHA256 `9e813862bbf5def30138a7ea67ae140a4ad5c599c6362f142f91f88d8401e9d7`、原Gitblob `e4214bb50966ce53ef8fb9d34899d4225a14eb05`。本run保留执行用同字节 `.py` 和受精确binary规则保护的 `.py.raw`；强合法merge probe也保留原字节。先未修复执行same7，真实5failed/2passed；修复后原7断言全通过。

`source_protection.json`核验原作者WT的173材料、50caller、13source原raw全部匹配；本WT原173 raw完全匹配、50caller与原9测试 clean Gitblob完全匹配。新checkout把原9作者LF转为CRLF，所以原raw不同；没有为核验改写旧测试换行，同时保存实际checkout SHA与cleanblob双证明。四个源码是明确授权修改。首次audit误把checkout原raw必须相等作为断言，失败原因已诊断为换行，保留 `audit_fix1_checkout_eol_red.py.raw` / `audit_eol_red`，改成原作者raw + 本WTcleanblob验证；没有修改输入manifest。

独立CBM project/cache：`dianzi-r12-conversation-context-fix1` / `/tmp/dianzi-cbm-r12-context-fix1-20261016`；最终backend/src1708nodes/9063edges，asset子索引236/1039；parse_partial/unusable均0。保存schema/architecture/admit/read_bundle/ack trace；工具排除的assets由独立索引和rg补读，不称全仓覆盖。自己的未冻结初始CBM日志因runner复用标签被最终重索引覆盖，只引用最终CBM；原作者材料和所有测试红/绿raw未覆盖。runner现拒绝已有输出标签，该材料偏差明确保留在 `artifact_limitations.json`。

`rg_current_callers_and_locks.log`记录当前真实auth、全部相关publisher和旧caller。公共路线仍是question_routes→GroundedQuestionService→旧retrieval/grounding；未接新内部多轮能力，R05 unsupported scope拒绝保持。auth→conversation；bundle继续source→document→revision→event→claim/evidence/support→scope epochs，不提前锁event再等document。历史身份授权只持有必要event/asset锁，不再读取source/doc；新问当前事实仍经原bundle authority fence。原source/document/enrichment等待、反向合法writer等待、hidden row对照和两进程重启测试真实通过；`merge_events`合法发布后历史仍可读。

## 真实执行结果

所有正式检查cwd均 `D:/wt/r12-conversation-context-fix1`。同名 `.command.json` 保存精确argv/cwd/+08开始结束/exit/wall/source_ref，完整输出和JUnit原样留档。最终只计 `unit_final`37、`regression_fix1`156、`pg_final`70，共263个不同最终case ID；不叠加早前重复绿。70中原41 +新增11 + reviewer boundaries4 +same7 7 +R05 PG7（R05所选6函数有1参数化）；same7中1纯函数，故该命令69真实PGcase+1pure。所有最终case0fail/error/skip。

| receipt | +08开始→结束 | exit | 实际结果 |
|---|---|---|---|
| `pg_same7_red` | 2026-10-16T09:41:13.621063+08:00 → 2026-10-16T09:41:24.881554+08:00 | 1 | 7 tests / 5 failures / 0 errors / 0 skipped |
| `pg_same7_fix1` | 2026-10-16T09:43:54.872943+08:00 → 2026-10-16T09:44:06.068206+08:00 | 0 | 7 tests / 0 failures / 0 errors / 0 skipped |
| `unit_fix1` | 2026-10-16T09:45:13.262310+08:00 → 2026-10-16T09:45:15.701930+08:00 | 1 | 37 tests / 6 failures / 0 errors / 0 skipped |
| `unit_fix1_corrected` | 2026-10-16T09:45:51.196261+08:00 → 2026-10-16T09:45:53.181960+08:00 | 0 | 37 tests / 0 failures / 0 errors / 0 skipped |
| `pg_new_fix1` | 2026-10-16T09:45:33.177090+08:00 → 2026-10-16T09:45:59.157035+08:00 | 0 | 13 tests / 0 failures / 0 errors / 0 skipped |
| `pg_original41` | 2026-10-16T09:46:14.288434+08:00 → 2026-10-16T09:47:30.849960+08:00 | 0 | 41 tests / 0 failures / 0 errors / 0 skipped |
| `unit_final` | 2026-10-16T09:48:28.227957+08:00 → 2026-10-16T09:48:29.952853+08:00 | 0 | 37 tests / 0 failures / 0 errors / 0 skipped |
| `regression_fix1` | 2026-10-16T09:46:31.546603+08:00 → 2026-10-16T09:46:42.982897+08:00 | 0 | 156 tests / 0 failures / 0 errors / 0 skipped |
| `pg_final` | 2026-10-16T09:48:08.408028+08:00 → 2026-10-16T09:50:11.177747+08:00 | 0 | 70 tests / 0 failures / 0 errors / 0 skipped |
| `ruff_first` | 2026-10-16T09:45:17.295782+08:00 → 2026-10-16T09:45:17.559905+08:00 | 1 | 非 pytest 检查 |
| `ruff_fix1` | 2026-10-16T09:45:54.520426+08:00 → 2026-10-16T09:45:54.707693+08:00 | 1 | 非 pytest 检查 |
| `ruff_final2` | 2026-10-16T09:48:30.936195+08:00 → 2026-10-16T09:48:31.086015+08:00 | 0 | 非 pytest 检查 |
| `format_final2` | 2026-10-16T09:48:32.131132+08:00 → 2026-10-16T09:48:32.285685+08:00 | 0 | 非 pytest 检查 |
| `mypy_final` | 2026-10-16T09:48:33.347223+08:00 → 2026-10-16T09:48:34.419159+08:00 | 0 | 非 pytest 检查 |
| `audit_eol_red` | 2026-10-16T09:51:16.166879+08:00 → 2026-10-16T09:51:20.523810+08:00 | 1 | 非 pytest 检查 |
| `audit_inputs_final` | 2026-10-16T09:51:32.025836+08:00 → 2026-10-16T09:51:40.562486+08:00 | 0 | 非 pytest 检查 |
| `rg_current_callers_and_locks` | 2026-10-16T09:52:27.909876+08:00 → 2026-10-16T09:52:28.165414+08:00 | 0 | 非 pytest 检查 |

新增test首轮漏填原QuestionRequest必填mode导致6failed/31passed，纠正测试输入后37passed；未改合同或断言。Ruff初次7条，修格式后只余一个nested-with警告，按既有风格合并后最终0；mypy项目配置4source通过。两个辅助PowerShell读取命令误将数值参数写为单词，及一次辅助probe误传 `-m this`，均未用于验证/计数；后者原输出保存为 `auxiliary_wrong_probe_parameter`，实际rg单独正确运行。

真实PG16.14，使用获准现存25432服务、fresh marked `test_dianzi_r12_ctx_fix1_20261016`和精确随机 `test_r12_fix1_<uuid>` /必要 `test_r05_fix1_<uuid>` schemas。CurrentUser DPAPI引用仅Python子进程捕获至内存，原敏感失败hook先加载；不在argv/日志写DSN密码。自己仅一个pytest串行，NullPool与显式dispose，只清自有schema，不kill其它连接、不增连接上限。最终release receipt为own schema0 / other ownDBsessions0，数据库保留供复跑。生产migration、OpenSearch、真实外部模型调用均未运行。

最终实际命令（完整argv也见各receipt）：

`unit_final`：

```powershell
D:/dianzi/backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_r12_conversation_context.py backend/tests/contract/test_r12_conversation_contracts.py backend/tests/unit/test_r12_conversation_boundary_fix1.py -q --override-ini=addopts= --junitxml=reports/runs/recovery_r12_conversation_context_fix1_20261016/unit_final.xml
```

`pg_final`：

```powershell
D:/dianzi/backend/.venv/Scripts/python.exe -m pytest reports/runs/recovery_r12_conversation_context_fix1_20261016/test_r12_conversation_boundary_fix1_replay_test_r12_conversation_assets_pg.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_r12_conversation_boundary_fix1_replay_test_r12_conversation_context_pg.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_r12_conversation_boundary_fix1_replay_test_r12_conversation_lock_pg.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_r12_conversation_boundary_fix1_replay_test_r12_conversation_process_pg.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_r12_conversation_boundary_fix1_replay_test_r12_evidence_bundle_pg.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_r12_conversation_boundary_fix1_replay_security.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_r12_conversation_boundary_fix1_replay_new.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_review_boundaries.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_review_negative.py reports/runs/recovery_r12_conversation_context_fix1_20261016/test_review_r05_pg.py -q --override-ini=addopts= --junitxml=reports/runs/recovery_r12_conversation_context_fix1_20261016/pg_final.xml
```

`regression_fix1`：

```powershell
D:/dianzi/backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_r05_grounded_answer.py backend/tests/unit/test_r05_question_routes.py backend/tests/contract/test_r05_question_contracts.py backend/tests/contract/test_r05_grounded_answer_contract.py backend/tests/unit/test_r12_hybrid.py backend/tests/contract/test_r12_hybrid_contracts.py backend/tests/security/test_r12_retrieval_boundaries.py --override-ini=addopts= -q --junitxml=reports/runs/recovery_r12_conversation_context_fix1_20261016/regression_fix1.xml
```

`ruff_final2`：

```powershell
D:/dianzi/backend/.venv/Scripts/python.exe -m ruff check --config backend/pyproject.toml backend/src/ai_intel/answering/conversation_context.py backend/src/ai_intel/answering/conversation_contracts.py backend/src/ai_intel/answering/conversation_models.py backend/src/ai_intel/answering/evidence_bundle.py backend/tests/unit/test_r12_conversation_boundary_fix1.py backend/tests/integration/test_r12_conversation_boundary_fix1_pg.py
```

`format_final2`：

```powershell
D:/dianzi/backend/.venv/Scripts/python.exe -m ruff format --check --config backend/pyproject.toml backend/src/ai_intel/answering/conversation_context.py backend/src/ai_intel/answering/conversation_contracts.py backend/src/ai_intel/answering/conversation_models.py backend/src/ai_intel/answering/evidence_bundle.py backend/tests/unit/test_r12_conversation_boundary_fix1.py backend/tests/integration/test_r12_conversation_boundary_fix1_pg.py
```

`mypy_final`：

```powershell
D:/dianzi/backend/.venv/Scripts/python.exe -m mypy --config-file backend/pyproject.toml backend/src/ai_intel/answering/conversation_context.py backend/src/ai_intel/answering/conversation_contracts.py backend/src/ai_intel/answering/conversation_models.py backend/src/ai_intel/answering/evidence_bundle.py
```

## 验收边界与交接

F3/R1的会话绑定、重新授权、永久context、撤回历史与当前事实分离已有上述fixture/真PG证据；E1的owner/permission/CAS/idempotency/不可变与进程恢复已有真实回归。无真实模型、多跳题集、性能或标注验证，不登记F3/P3/R1分数。未知状态不当否定，fixture completion始终明确synthetic，不当在线答案。

frontend/e2e/model live/manual均not_run；原R12最终图路径、规则/Assessment、历史证据包、semantic recall、grounding双调用、付费预算与公共API接线继续归root，不因本slice通过视为整R12/T30/T31/T35完成。当前性标记只说明引用资格/快照变动，active历史事实仍unknown，不冒充current。过期回收在准入前有独立提交和认证/会话重新锁定，业务计费/generation未触发。

首材料提交 `a7e3a10a5bc508e9d84752789a798112af324cd6` 的 diff-check 发现两处自有helper空白：copied conftest尾部空行、runner空白行。保留 `material_whitespace_initial` 红及原 conftest.py.raw，只修自己的helper空白，并追加材料修正提交；源码和测试/raw输入均不改。最终材料整体diff-check与manifest staged raw/Gitblob另复核。一次辅助Python写报告默认GBK读取UTF8失败，按明确encoding修正，无业务或测试输出变化。

下一步：原非作者reviewer在自己的新run按同same7/强合法merge断言定向复核本code和材料；root核0024guard一致性后决定集成。材料manifest/raw/Gitblob与report/codeSHA分别封存，作者停在awaiting_review、未push、未accepted，未更新progress。
