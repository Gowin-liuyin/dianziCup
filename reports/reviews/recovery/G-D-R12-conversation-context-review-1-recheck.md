# G-D · R12 conversation/context 独立定向复核 fix1

本变更做了什么：关闭初审四项内部会话边界问题，新增 turn UPDATE/DELETE 不可变 guard。当前/历史读取重新鉴权，但历史对象失去 active 资格不再等同失去访问权限；新轮仍重新取当前对象与 PG 证据。

判定：**限定 Ship**，初审 4 Must 已由原反例与真实 PG 复跑闭环，本轮没有新 Must。仅签固定 code 的 conversation/context 内部行为；任务仍按原流程 `awaiting_review`，不自行登记 `accepted`，不签整 R12/T31/T35、G-D 或真实问答能力。

## 1. 固定版本与本轮权限

审查 WT/branch：`D:/wt/r12-conversation-context-review1-fix1` / `codex/r12-conversation-context-review1-fix1`。材料起点 `eb030458009812ec037928e4bc2f1a4cdbe64c46`，tree `db969301e3473fd0e75f338e3142bf022ddc1cf8`，commit 时间 `2026-10-16T09:56:02+08:00`；业务 code `1e210090d74d1444101330f0c8b8637ad1dd50a3`，4 源码改动、2 新测试文件。审查者仍为原非作者，未实现这 6 文件，只新增本报告及自己的 run/probes/fixture。

作者报告原字节 SHA256 `77131b5673d3a42613c773ce6e34c71edfab9dbe3fa8fd551561c45b474c06e2`；作者 `material_manifest.json` 104 项，SHA256 `f49a0789874620ebae2a1d040a6e140b8ffb1cbfd621e2376ec6a0e747e47bb2`。独立核验全部匹配；新 checkout 的报告/源码正常换行转换用 clean Git blob 单独证明。

复核沿用并重新核对 AGENTS、00、R12 卡、T31/T35、03/04/06 合同、设计提案与 task_state；这些旧冻结输入的 50 个 caller/合同/writer blob 均匹配。使用新版 Ponytail review 5.2.0；假设多个用户/服务进程并发，而不是内存单实例。没有改业务代码、公共 API/grounding、root tokenizer、迁移、原测试、进度、金标、阈值或分母，没有 push。

## 2. 原 4 Must 的定向闭环

| 初审问题 | 修复源码与真实复查结果 |
|---|---|
| 无父轮/对象的代词被准入 | `conversation_context.py:136` 在 event/asset/显式标识均缺失时产生 `reference_ambiguous`，没有检索 query。原 same7 的 pure+PG 两红均转绿；新增 failed-only/未绑定 completed 父轮及普通首问/显式唯一对象对照通过。PG 拒绝不创建新答案。 |
| 拒绝新轮时回滚已过期轮恢复 | `admit:492` 先执行 `_recover_expired_active_turn:440` 的独立 auth→owner conversation 行锁→既有 reservation/state CAS 短事务，准入事务再次鉴权/锁会话。原 stale version 红、新 clarification 拒绝/current-version 单轮控制通过；新增在两事务之间真实 logout，第二次鉴权拒绝而 expired receipt/清槽仍提交，answer 数量保持 1。未放宽版本检查或重发原 key。 |
| 继承父 context 绕过 hash | `admit:548–577` 只读取成功父 turn ID，再走 `_turn:367–383`；canonical digest、保存摘要、conversation ID/base version/原问题均验证。bundle 使用同一 `validate_context_integrity`。原篡改父 hash 红及原 corrupted SHA、作者新有效 hash 但身份错配案例均应用层固定 503 拒绝；新轮不增加 answer。 |
| 合法 merge 后历史轮被 current-active 过滤拒绝 | 历史/replay 的 `_authorize_turn_references:403` 独立检查当前 ACL/asset read 权限，原 context 和快照不改，inactive/快照变化标 `reference_freshness=stale`，其余 `unknown`。真实 `EventRepository.merge_events` 原红转绿；当前新轮仍经 `_references:295` 拒绝 inactive 身份，不继承撤回事实为当前真值。历史 ACL 改为他租户后拒读、asset 权限撤销后拒读也通过。 |

same7 原 `.py` 字节和输入/断言保留：SHA256 `9e813862bbf5def30138a7ea67ae140a4ad5c599c6362f142f91f88d8401e9d7`，Git blob `e4214bb50966ce53ef8fb9d34899d4225a14eb05`。合法 merge、source ACL、反向 enrichment writer 的原边界文件也直接复制原 review commit `6383926b169e7f9ac657e9a32a5802f116937d25` 的字节，没有改断言或用当前实现生成期望。

新增 immutable guard 没有遮住旧数据的应用校验：经 root 明确允许，自己的 fixture 仅对三个精确测试名禁自己 UUID schema 的这个 guard：`test_pg_child_admission_verifies_saved_parent_hash`、`test_pg_corrupted_context_sha_does_not_become_a_valid_replay`、`test_pg_legacy_parent_identity_mismatch_fails_closed`。每例 PG 查询确认 `tgenabled=D` 并写 `fixture_guard_receipts.jsonl`；测试结束安全 Drop 自有 schema。其他 conversation fixture 确认 `tgenabled=O`，新 UPDATE/DELETE 负例真实拒绝。

旧 owner UPDATE 负例会被 guard 提前拒绝，因此本轮另加 3 个 **guard 开启的 INSERT** 对照，分别为 wrong owner、wrong tenant、tenant=NULL，均由 deferred ownership 触发器明确以 `conversation owner mismatch`/23514 拒绝并回滚。这证明 nullable tenant 一致性，不能仅把不可变错误当 ownership 证明。

## 3. 真实测试、命令与分类

run：`reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/`。所有 command receipt 保存完整 argv、cwd、+08 起止时间、exit、wall time 和固定源 commit；对应 log/JUnit 原始脱敏字节一并封存。cwd 均为本审查 WT，Python 为 `D:/dianzi/backend/.venv/Scripts/python.exe`。

| 运行 | 实际时间 +08 / exit | 结果 |
|---|---|---|
| `unit` | 10:01:15.681→10:01:17.681 / 0 | 原 unit/contract＋fix1 unit：37 passed，0 failed/error/skip。 |
| `pg` | 10:01:46.982→10:03:35.362 / 0 | 完整原定 70：69 真实 PG＋1 pure，70 passed，0 failed/error/skip。包含原 41、fix1 新 11、same7、原 4 边界及原 R05 7。 |
| `pg_extra` | 10:04:14.353→10:04:22.472 / 0 | 5 个定向真实 PG passed：两事务之间 revoke、历史 ACL writer 锁等待/后读拒绝、3 个 insert owner/tenant/NULL tenant。 |
| `regression` | 10:04:44.267→10:04:51.957 / 0 | 原 R05/R12 7 文件 unit/contract/security：156 passed，0 failed/error/skip。 |
| `ruff` | 10:05:23.052→10:05:23.276 / 0 | 6 个修复源码/测试文件检查通过。 |
| `mypy` | 10:05:23.034→10:05:33.046 / 0 | 4 个业务源码无类型错误。 |
| `pg_hook` | 10:05:45.113→10:05:46.691 / 1 | 故意失败 1 次；实际 SecretStr DSN/password 经原失败 hook 脱敏，保留真实失败 outcome，不计业务失败或通过。 |

业务测试执行合计 **268 passed = 37＋156＋70＋5**，无业务 failure/error/skip。测试向量和完成正文为显式 synthetic/fixture；PG 和旧 API fixture 通过不等于真实 semantic/模型问答。

原 70 完整 argv 在 `pg.command.json`，直接复跑入口为：

```powershell
& D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/review_runner.py pg -m pytest reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_replay_test_r12_conversation_assets_pg.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_replay_test_r12_conversation_context_pg.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_replay_test_r12_conversation_lock_pg.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_replay_test_r12_conversation_process_pg.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_replay_test_r12_conversation_security_pg.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_replay_test_r12_evidence_bundle_pg.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_replay_new_fix1_pg.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_review_negative.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_review_boundaries.py reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/test_review_r05_pg.py -q --override-ini=addopts= --junitxml=reports/runs/recovery_r12_conversation_context_review1_fix1_20261016/pg.xml
```

运行器拒绝重复输出 label，复跑须新 label 和自己的资源 fixture。`--override-ini=addopts=` 仅关闭此限定回归的全库 coverage 配置，未修改任何业务断言、评分分母、门槛或金标。

## 4. 原材料保护、独立调用与 metadata

`source_audit.json` 独立验证：旧作者 173 材料、50 caller、13 原源码/测试 raw；旧独立 review 81 项 raw；fix1 104 材料与 6 源/测试 raw/clean blob。原 4 源码变动在明确 fix ownership 中，原 9 测试 clean blob 全匹配；新 checkout 换行差异单独记录。初审 instrumentation 红、作者 same7 初红、a7 material whitespace 红、eb helper 修正均保留。作者初 CBM 日志被自身复用标签覆盖，只认可其最终 1708/9063，不能声称旧初日志存在。

本轮另建 project `dianzi-r12-conversation-context-review1-fix1` 和新 cache `/tmp/dianzi-cbm-r12-context-review1-fix1-20261016`：实际 source 1708 nodes/9063 edges，assets 窄索引 236/1039，parse partial/unusable 均 0。首次复制运行器沿用旧 cache 但 project 不同，随后以 `fresh_` 新 label 在新 cache 重新完整索引/trace；两组日志均保留，仅用 fresh 组支撑本轮。默认排除 assets，已经窄索引和真实 InventoryService PG 用例补查，不称全仓覆盖。

独立 architecture/schema/admit/read_bundle/ack、原 ask、assets writer trace 和 rg 对源码交叉核对。公共路由仍调用旧 `GroundedQuestionService`，没有新公共 conversation caller。旧 source/document/revision→event 的 publisher 顺序、读 bundle 的共同 hybrid authority fence 与末尾 epoch、库存 asset→publication/epoch 顺序均读实际源码；真实正/逆向 publisher、source ACL 构建期等待与 hidden row 独立性回归通过。新历史读锁 auth→conversation→events/assets，追加 ACL writer 等待测试通过。没有从这些证据外推未来 producer 的锁序正确。

`metadata_authority.json` 独立读取 2 Table 的 columns/FK/checks/index 和 deferred ownership/immutable 原 DDL。immutable 函数/trigger 的 strip UTF8 摘要分别为 `579d7b1a844c6c3efc295bbb5ae41a6a2096693e09af275fa4d5416d1f460d43`、`76472dea4ba24248e49eacc50897f7903dd8cbfd38f402eac138ed3808a9c585`；与冻结的 root 批准 statement artifact 精确相等，见 `approved_0024_guard_read.json`。这只是 DDL 输入一致性，不是生产 0024 升级验证。

## 5. 资源释放、秘密与签署边界

仅授权现存 WSL `127.0.0.1:25432` test PG；pwsh7 解密 DPAPI 引用后 Python 内存捕获并核 host/port/原 test marker。自己的 fresh DB `test_dianzi_r12_ctx_recheck1_20261016`，随机 `test_r12_recheck1_<uuid>` /必要 `test_r05_recheck1_<uuid>` schema；每个 fixture NullPool、显式 dispose。一个重 PG 槽位、每次一个 pytest 串行，没有增 PG 上限、kill 他人、改生产库、downgrade 或访问盲测答案。

最终 release：`2026-10-16T10:05:46.758193+08:00`，own schemas=0、其他 own DB sessions=0，槽位已交回 root；之后无 PG 操作。数据库保留。原失败 hook 预先加载、动态秘密以 SecretStr 登记；raw log/JUnit 和本 run 实际 DSN/password/8 字符 password fragment 扫描 0 命中。公共用户名与 database marker 的精确位置/窄上下文分类保留，不全局 ignore。

本 run 的局部 `* -text` 仅保留 raw artifact 字节。实际全 staged artifact diff-check exit=2，诊断为保留的 Windows CRLF/CRCRLF raw 字节；摘要和输出 SHA 在 `diffcheck_raw_artifacts.json`。限定报告/Python probes/局部 attributes 的 `diffcheck_code` exit=0，没有 root attributes 或业务检查忽略。

生产 schema/current producer 接线、正式 0024 升级/search_path、公共 API 合同、最终 grounding fence/model 两调用、private-egress/tokenizer/完整 deadline、OpenSearch、真实 semantic/model live、前端/e2e/manual 均 `not_run`。本轮远端模型调用 0，无付费/大模型下载/外网扫描。只能登记 F3/E1 内部引用与权限/并发证据，不能计多跳质量、在线能力或 P3 达标。

下一步：root 可在此内部限定 Ship 基础上继续已授权 producer/迁移/API 集成，并对其新的 source/合同/真实测试另行独审；保留原 4 Must 的同断言、legacy fault-injection 与真 merge controls。此签署不能替代整张 R12/T31/T35 或 G-D 检查点。
