# R07 持久输入审计 ACL 并发修复 1

状态 `awaiting_review`；实现 `complete`（此修复切片）；unit/contract/integration/security 见真实结果。原 R07 整卡、生产 0023、live/frontend/e2e/manual 未据此完成。

## 冻结版本与改动边界

- 基线及原材料：`014de585413c8a82a04d00b1ff2fbd1ff62d733b`；其代码 `1363591064020b350dad1ccce10f9cee33ea7569` 保持冻结。
- 工作树 `D:/wt/r07-input-audit-fix1`，分支 `codex/r07-input-audit-fix1`。
- 新代码 `0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5`，代码 tree `295ecfd6f68422a63118b9e70069fc4b0085ea9b`；2 文件 253 insertions / 8 deletions。
- 业务仅改 `backend/src/ai_intel/enrichment/job_service.py`；新增 `backend/tests/security/test_r07_input_audit_fix1_acl_pg.py`。
- 自有材料 `reports/runs/recovery_r07_input_audit_fix1_20261016`；材料提交 SHA 与最终 raw manifest SHA 在独立提交交接中给出，避免把材料提交自身哈希写进其内容。
- 未改 job_contracts/job_models/job_types、共享 loader/auth/API/default worker/settings、迁移、锁文件、attrs、progress、旧测试/input/assert/gold/阈值；无 push/accepted。

## 原红与共根因

原非作者评审 `independent_pg_third` 为 13 pass / 4 fail / 0 error / 0 skip，其中 3 条业务红分别是 source/document/revision 父 ACL；另 1 条是 codec key 仪器问题。`original_review/red_probe_handoff_receipt.json` 与其中 10 个原文件按实测 raw SHA 复制，原函数摘录 SHA `e5032e8b97082e209ba640a8aedbc8a1bbd79833caf0b2dcdcf324a74b50d8ab` 保留。第三轮整 probe 没有运行前 snapshot；后续反向重建文件明确只撤回已知 codec `max_tokens`→`max_completion_tokens` 修正，不能称第三轮运行时预测 hash。三个 race 的输入/assert 未变。

本工作树修复前真实复现 3 fail：三路均 `writer_committed=true / reader_denied=false / returned_texts=true`。auth_sessions/users 已有 SHARE 锁，但父 ACL 普通 SELECT 之后，另一个真实 PG transaction 能提交 tenant 改写，再由审计 reader 返回冻结 quoted texts。

`read_input_audit` 现在先用已冻结 context 校验 fingerprint 与 event/revision 身份，按真实来源 writer 的父对象顺序取得 source、document、revision `FOR SHARE`，再取得 event、workflow `FOR SHARE`，核对重新读取的 workflow 身份未变，然后执行 fresh `read_workflow` 当前 ACL 校验，最后验证并构造 immutable audit。锁保持到调用方事务结束，正常父行 UPDATE 不能穿过这个窗口。历史 refs 不依赖 is_current、active event_documents 或当前 roster；旧 revision 退出当前关联后，当前授权者仍能读真实历史审计，父 ACL 撤回后拒绝。

源码与 CBM 交叉：独立 index 144 Python files、2067 nodes、11364 edges，partial/unusable/skipped 均 0；schema/architecture/audit trace/writer trace 的实际 CLI 结果归档。实际 source writer `ensure_source_registration` 先 source advisory/row，随后 document/revision，最终 event；publication 也是 source→document/revision→event。reader 使用相同父行先后顺序，保留 SQL SHARE 并发语义，不调用只认可 current roster 的 publication helper。

所有 callers 已核：public `read_workflow` 的 enrichment/job 两个 API caller只接收安全 DTO；`_step_view` 只给 token/provider/model/time/hash 等安全 trace，不输出 request/input_context/input_selection/quoted source/session hash。它仍检查当前 ACL；唯一 quoted text 出口为内部 `read_input_audit`，现在调用上述检查前持有历史父/event/workflow 锁。未增加公共字段或第二任务状态。

## 真实检查

全部命令、cwd、开始/结束 Asia/Shanghai 秒级时钟、退出码、JUnit 数量、运行 HEAD 见 run 内对应 `.json/.log/.xml`。组件测试显式 `--no-cov`，未改全库 60% coverage 门槛。首次过滤 green 3 pass 的命令仍因窄切片覆盖不足 exit1，日志保留；后续完整指定用例命令 exit0。最初 guessed path / unsupported trace flag / PowerShell tree 参数仪器错误及两条初始静态问题均保留说明，未冒充业务红。

| 批次 | 真实结果 | 退出码 |
|---|---:|---:|
| `original_acl_red` 原 3 probes | 3 fail / 0 error / 0 skip | 1 |
| `acl_fix_pg_second` 原3 + 当时新12 | 15 pass | 0 |
| `audit_unit_contract` 原 unit12 / contract6 | 18 pass | 0 |
| `audit_pg_full` 原 audit PG27 + security12 + 新 ACL13 + 独立17 | 69 pass | 0 |
| `job_contract_regression` 相关 unit/contract/security | 69 pass | 0 |
| `default_scope_metadata` 默认33 + scope24 + metadata20 | 76 pass / 1 原 NVD fail | 1 |
| `baseline_nvd` 原 5b29 service，同原 input/assert | 1 原 NVD fail | 1 |
| final source Ruff / format / mypy 4 owned modules | pass | 0 |
| source staged/diff whitespace | pass | 0 |
| marked own database release | schemas0 / other sessions0 / disposed | 0 |

最终主回归去重 233 cases，232 pass / 1 fail / 0 error / 0 skip；重复红/基线重跑不累加到 unique count。`final_unique_counts.json` 有逐模块数量与唯一失败身份。测试时 HEAD 为原材料或新 code，早期在原 HEAD 上的工作区最终源码相同；提交只冻结文件，不声称早期日志已有后续 commit SHA。最新命令另外记录运行 service raw SHA，基线命令显式记录原 service blob。

新 13 PG cases：writer-first source/document/revision/event 等待后 fresh 拒绝；reader-first session/user/event/workflow writer 必须等待；历史 non-current、无任何 active/current 输入、非空 tenant 三类父授权读与撤回拒绝；当前 session/user 撤权。原三 reader-first 父探针修后实际 `writer_blocked=true / writer_committed=false`。原 cap/Unicode/hash corruption/receipt immutable/transaction rollback/duplicate/concurrency/legacy/no-repeat-call 用例完整复跑，没有把 stale 返回空成功或伪装角色。

## 保留的原 NVD 红

旧 `test_r07_job_execution_pg.py::test_full_recorded_nvd_budget_failure_is_retained_without_wire_or_losing_other_dimensions` 第 528 行仍原样断言四模型维度 failed，第 529 行仍原 0 wire oracle；本修复和 5b29 baseline 都在 Atlas partial 与旧 failed 预期处失败。原输入 SHA `c5cf6c0b00bc691dd97f1b8fd26504b7c104e047dfda0c278f54a6e70a66735a`、原 source/assert、原 32/1 与 baseline 红证据保留。

完整 roster 67 blocks，PG context 25956 UTF-8 bytes；已批准 CBE 预算针对实际发送 selected blocks，保留全 source refs/hash、Unicode omitted 补集与 incomplete。诊断 probe 中 Atlas taxonomy missing/partial、0 receipt；versions 11+1 records/8696 bytes/56 omitted，literature 7+1/5875/60，PoC 6+1/5148/61，三维全部 refs/incomplete 保留。3 次明确 offline codec 产生真实 fixture attempt metadata，但输出引用另一 fixture revision，三维 `field_evidence_revision_invalid`；9 维最终 publication partial，CVSS available。`independent_nvd_observation.json` 原值归档。不是 live、不是 0 codec calls、不是全成功。原 oracle 未关闭，仍由 root 的合同处理与非作者审查决定。

## 资源、安全与兼容

只从已批准 DPAPI resource 内存取 TEST_DATABASE_URL，driver/127.0.0.1:25432/original test DB/test_* user guard 后仅替换为自有 `test_dianzi_r07_input_audit_fix1_20261016`。database/file owner marker 一致，自有随机 schema，cap80；全部自有 fixture NullPool、仅一个 serial pytest process。没有 patch production build_engine、raise PG limit、kill 他人、复用旧测试数据库或接触真实采集队列。已向 root 明确释放 slot。

外部 probe 明确加载 repository shared failure hook；动态 DSN/password 为 SecretStr 登记到实际 hook stash。runner 写 log 前脱敏、写 JUnit 后 actual-value scan；最终独立检查 actual approved test DSN/password 的 raw/URI/HTML/JSON escaped 形式，不记录值或其 hash，不读 prodsecret/holdout/cache。实际扫描结果见 `actual_sensitive_value_scan.json`。

`predecessor_protection.json` 核原 408 unowned 文件与原 run 93 材料 Git/raw bytes 保持，原 DDL two nullable columns + immutability proposal SHA `ee2fde666548f57cdd56376e443d00592ee107a3efb4d6c169e9c1df6581bbd6` 未变；metadata/schema/version/hash/legacy replay/binding/namespace 均未新增或重写。生产 0023 仍 root-owned pending。

本 run 不新增 attrs；raw 材料使用一次性 `git -c core.autocrlf=false add` 保字节并逐 Git blob 与 raw SHA 核对。原 raw whitespace 不修剪；默认材料 cached whitespace exit2、1140 诊断行，完整实际输出以 base64 保存在 whitespace_check.json，源 diff/check exit0。此归档 red 不伪装 pass、不新增 attrs 忽略规则。首次材料 helper 将93误当run内数量而 assertion fail，日志保留；核实正确边界为91 run文件 + 原CR/report2文件后第二次408/93 pass。旧WT93 raw bytes全部匹配原Git；新WT两md checkout CRLF差异明确单列。

live/frontend/e2e/manual `not_run`，0 外部模型/付费/测绘/来源网络调用；所有 fee `unknown`。由原非作者 reviewer 定向复核新冻结 commit/materials 后再交 root 合入，作者不签 accepted。
