# Root · 批次23 总结（裁决落地 + 审计族解锁 + 大件立项）

- 文档首次创建时间：2026-10-25T11:00:00+08:00
- 本次写作开始时间：2026-10-25T11:00:00+08:00
- 最后更新时间：2026-10-25T11:00:00+08:00
- 任务状态：awaiting_review；工作分支 codex/full-delivery-recovery；起点 HEAD 0f72e6d85。
- 授权形态：GOAL 指令（批次23 起）——裁决区按**方式B**执行（原批次23 提示词的留空裁决区被 GOAL 授权边界第1条覆盖）；立项卡实施按 GOAL 授权边界第2条待非作者复核后逐卡进行（属批次24+，本批未实施任何大件）。

## 工作项结果

| 工作项 | 结果 |
| --- | --- |
| W1 审计族预置库拓扑 | **完成：5 文件 52 passed / 0 failed，容器 exit=0**（`reports/runs/batch23_audit_family/fixed_run3/audit_family_batch23.txt` 末行）。三层独立根因逐层解锁（见下）。 |
| W2 简报 | `progress/DECISIONS_pending.md` 三节齐全（现象/例数引原始输出行、选项 A/B 与不可逆性、建议项、验证命令）。 |
| W2 裁决① r05 legacy-0013（19 例） | **闭环**：CR `docs/decisions/CR-r05_legacy_seed_annotation_batch23.md`；`question_api` fixture 层种子标注 `{"data_mode": "fixture"}`，种子文件/断言零改动；容器 24 passed / 0 failed（`reports/runs/batch23_decisions/test_r05_question_api_pg_pf.txt`）。 |
| W2 裁决② r04 evidence 计数（1 例） | **闭环**：CR `docs/decisions/CR-r04_evidence_count_oracle_alignment_batch23.md`；断言改 locator 排序等值（实测构成 `/description`+`/ghsa_id`×2+`/vulnerabilities/0/package/name`）；容器 25 passed / 0 failed（run3）。 |
| W2 裁决③ 公网读错误码映射（5 例） | **闭环**：CR `docs/decisions/CR-public_read_projection_error_mapping_batch23.md`；产品 `public_extension_reads.py` 新增 `public_knowledge_projection` 包装（4 个投影调用点，`KnowledgeProjectionError`→`PublicReadUnavailable`）；容器 fix1 28 / fix2 38 / producer 9 全 passed；宿主公网离线定向 767 passed / 4 设计内 blocked。 |
| W3 大件立项卡 | 四张入库 `docs/plan/projects/`：P-01 多跳问答（5 批）/ P-02 推荐历史与变化重判（4 批）/ P-03 MCP/OAuth/CLI 三插件（4 批，OQ-4 /tasks producer 并入并附理由）/ P-04 安全/CI/索引恢复框架（4 批）。现状路径 106 项逐一 `ls` 核对（1 处误写已修正，`reports/runs/batch23_projects_path_check.txt`）；"写不出路径的能力"逐项确认不存在。 |
| W4 顺手收尾 | OQ-1 状态收束 + 宿主复测精确化；OQ-5 审计族解锁记录 + 三项裁决收束；handoff 顶部批次23 条目；task_state 最小更新（updated_by_task=Root-batch23-checkpoint，T31/T35 追加 history，status 零改动）；goal_state notes 追加。 |
| W5 质量门 | backend 全量 **6253 passed / 0 failed / 1 xfailed / 83 设计内 blocked**（对照基线 6252–6253/0：failed 仍 0，无新增红）；ruff check / ruff format / mypy src 全 0；前端 lint 0 / typecheck 0 / test **799 passed** / build 0；tsbuildinfo 恢复原样（SHA 前缀 3c587edfd308fb5c 核对一致）。 |
| W5 宿主探测 | `docker run --rm hello-world` exit=0（用户已部分修复）；独立 `docker run -p` 端口发布+数据面正常；**compose 端口发布仍静默失败**（见偏差2）。 |
| W6 收尾 | 本报告 + 8 个 checkpoint 提交 + 1 次 push（见下）。 |

## W1 三层根因与修复（全在 harness/fixture 层，业务代码零改动、断言零改动）

1. **迁移状态冲突（诊断精确化修正）**：OQ-5 原归因"provisioning 迁移 head 与 helper install 冲突"不成立——实测冲突是 helper 在 fresh schema 里 `run_migrations(head)`（0023 已采纳 test proposal 的 DDL）与 `install=True` 重装的内在冲突（复现证据 `repro_conflict/`，6 errors 全部 DuplicateObject）。修复：helper 迁移目标钉 `0022_sbom_sidecars`（恢复 helper docstring 自述的"proposal 是安装者"合同；`backend/tests/r07_input_audit_helpers.py` 一行）。
2. **observation 写入**：原目标目录不存在且容器 /repo 只读；镜像 batch22 的 R06_PROOF_TRACE_DIR 读写分离先例，测试层加 `R07_INPUT_AUDIT_TRACE_DIR` 重定向 + harness 注入 `/out/r07_input_audit_trace`（观察文件实测落盘 `fixed_run3/r07_input_audit_trace/`，冻结目录零触碰）。
3. **组端口钉定**：security 2 文件含裸导入需同组收集（fixed_run 的 ModuleNotFoundError 证据），helper 断言 25432 而 harness 组模式硬编码 5432（fixed_run2 的 52 端口断言错误证据）；harness 组模式增加可选 `port` 字段（缺省 5432，历史组计划零影响）。

## W2 执行轮次（非同根因扩补丁：每轮解锁一层新证据）

- run1（5 文件）：r05 24 全绿；producer 9 全绿；fix1 剩 1（missing-mode 探针）、fix2 全 38 error（计划端口钉错）。
- run2（3 文件）：fix2 端口修复后 36 passed + 2 failed；fix1 legacy=True 包装把 2 个 dimension 用例改红——**发现 recheck 探针拷贝 fix1 测试函数、`__globals__` 指向 fix1 模块字典**，且 legacy 分支连带 parse_status/canonical_uri 改变。
- run3（3 文件）：包装改为"仅清空 source_metadata"，fix1 28 / fix2 38 全绿；r04 构成断言按实测修正后 25 全绿。
- 执行中发现的两处 triage 归因修正：①裁决③的真实逃逸点是 `KnowledgeProjectionError`（ValueError 子类）而非 triage 所述的 :228 包装点（该包装 48f96b5ba 已存在）；②裁决②的 2→4 来自 identifier qualifier 行而非 CVSS qualifier（vendor 路径无 ScoreValue fact）。
- 执行中发现的批次22 波及面：共享 seeder stamp 改变了冻结探针观察到的"missing mode"场景（batch22 未重跑 fix1/fix2 故未暴露）——本批在探针种子引用层恢复前置，探针文件与断言零改动。

## 真实测试与验证命令（全部退出码落盘）

| 验证 | 退出码 | 结果 |
| --- | --- | --- |
| 审计族容器（组模式，5 文件） | 0 | 52 passed / 0 failed / 0 errors（136.21s） |
| 裁决验证容器 run1/run2/run3 | run3=0 | r05 24、r04 25、fix1 28、fix2 38、producer 9 全 passed |
| backend 全量（unit+contract+security，宿主） | 1* | **6253 passed / 0 failed / 1 xfailed / 83 设计内 blocked**（1088.48s） |
| ruff check / format --check / mypy src | 0/0/0 | 全 0 |
| 前端 lint / typecheck / test / build | 0/0/0/0 | 64 文件 799 tests 全绿 |
| 宿主 hello-world / 独立 run -p 数据面 | 0 | 通过（宿主部分恢复） |
| 宿主 compose 冒烟 | 2 | database unreachable（compose 端口发布静默失败，见偏差2） |

*exit=1 与基线同因：仅由 83 设计内 blocked（real_pg 用例宿主无隔离资源显性化）贡献。

## 未通过 / 未运行 / 外部阻塞

- 3 例 B 类取证（r07_job_execution outcome 映射、r14_read_adapters ACL 隐藏态映射、r14_default_runtime 0 行机制）——裁决证据已在册，待评审。
- pgvector 0.8.2 钉版（pgdg main 无该版本，r05_vector_persistence 的 A 例与 2 例同根 B 例）——外部阻塞。
- R19 人工标注窗、R22 资源窗、6 小时采集窗——用户资源窗。
- compose 端口发布静默失败——宿主侧（偏差2）。
- 大件实现（P-01～P-04 的实施批次）——按 GOAL 排批次24+，本批只立项。

## 合同与计划偏差

1. **W2 执行超原批次23 提示词的"方式A"**：GOAL 指令明示"裁决按方式B执行"，按权威顺序（用户当前明确指令居首）执行；简报保留供复核。
2. **宿主 compose 冒烟未通过**：W5.3 探测成功（hello-world）故按授权加跑；冒烟因 compose 特有的端口发布静默失败退出 2（`reports/runs/batch23_quality_gates/host_port_diag.txt`：compose 容器 `NetworkSettings.Ports={"5432/tcp":[]}`，同刻独立容器端口发布正常）。本机 Docker Compose **v5.0.2**（README 要求 ≥2.24.4），版本兼容性归用户排查；未做任何宿主修复，重试 5 次后按"失败一行记录即止"停止（诊断记录多于一行为精确归因所需）。
3. **OQ-5/ triage 的两处归因修正**与批次22 种子 stamp 波及面发现——已在 CR 与 OQ-5 记录，全部以实测证据为准。
4. 裁决②的 CR 断言形态在执行中由"计数+后缀构成"修正为"locator 全集排序等值"（首轮构成假设被容器实测否定后按证据改写，CR 已同步修订）。

## 评分项证据索引

- 审计族（R07 输入审计）：`reports/runs/batch23_audit_family/`
- 三项裁决：`progress/DECISIONS_pending.md`、`docs/decisions/CR-r05_legacy_seed_annotation_batch23.md`、`docs/decisions/CR-r04_evidence_count_oracle_alignment_batch23.md`、`docs/decisions/CR-public_read_projection_error_mapping_batch23.md`、`reports/runs/batch23_decisions/`
- 立项卡：`docs/plan/projects/P-01..P-04`、`reports/runs/batch23_projects_path_check.txt`
- 质量门：`reports/runs/batch23_quality_gates/`
- 时间线真相源：`reports/runs/batch23_timeline.md`

## 下一任务建议

1. 批次24：四张立项卡**非作者视角复核**（GOAL 要求，三个全新子代理分卡核对现状路径与步骤可验收性，结论落 `reports/reviews/batch23/`）。
2. 复核通过后按 P-01→P-02→P-03→P-04 顺序逐卡实施（每批先写 plan、测试先行/同步实现、全量回归、独立 commit）。
3. 用户侧：compose v5.0.2 端口发布排查（恢复后可回归宿主 compose 冒烟）；R19 标注窗；3 例 B 类取证的裁决意见；R22 资源窗（R24-A 硬前置）。

本次写作结束时间：2026-10-25T11:00:00+08:00；本报告为有界批次的证据索引，不是阶段验收（无任何 status 被写为 accepted）。
