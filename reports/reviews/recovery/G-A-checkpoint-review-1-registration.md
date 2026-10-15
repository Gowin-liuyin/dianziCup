# G-A · 独立阶段意见的纯登记定向复核

**结论：登记一致性通过，原限定 Ship 意见保持。** 未发现新的确证阻断；本复核未重跑业务、未改状态或push。

审查者：`/root/g_a_checkpoint_review`。固定差异：`a8362baa7ea042075ca53125495a080d86274bae → fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4`；fa5 tree `7fd5ec58deb321ddbf95155e199eda49cf2ea228`。新干净WT `D:/dianzi-ga-checkpoint-review-1-registration`，分支 `codex/ga-checkpoint-review-1-registration`；首末clean。只检查主控依据[完整阶段意见](G-A-checkpoint-review-1.md)登记的有限范围。

实际差异23个路径均为progress/reports，backend/frontend/contracts/scripts/config/infra/CI与依赖锁无变化。G-A、R01–R03的accepted引用本reviewer已测b27、已审文档a836及最终Ship，recovery_stage转G-B；没有把本意见扩到新来源UI/semantic等未集成或后段代码。

| 工作包 | 登记的manifest.output_slices |
|---|---|
| R01 | R01:T02、R01:T03、R01:T06、R01:T40 |
| R02 | R02:T04、R02:T05、R02:T06、R02:T17、R02:T19、R02:T21 |
| R03 | R03:T07、R03:T08、R03:T16 |

13条恰好等于manifest输出集合，各自original_task匹配，review_ref与阶段/任务证据存在，每条保留此前history与完整prior_record。原60张T卡除上述slice_acceptance外的所有字段完全不变，整卡status未提高，其他切片不变。R01–R03各层verification字典与a836完全一致，manual/live仍not_run；其他recovery_tasks完全不变。原T最终前置/全部切片/六验收规则继续成立。

主控第一次仅登记工作包导致19项结构错误，原stdout未单独保存的事实已写入ga_slice_registration.json。本审用固定最终state在内存恢复原切片状态，调用固定check_task_state独立重现19项OUTPUT_SLICE/REQUIRED_SLICE错误；当前精确登记13条后严格检查通过，未把登记工具失败冒称业务测试失败。

| 独立检查（2026-10-15，+08:00） | cwd/实际结果 |
|---|---|
| 15:36:39–15:36:39，`python ../scripts/verify_plan.py --root <固定WT>` | 固定WT/backend；exit0、PLAN_OK；registration_plan_fa5.command.json/log |
| 15:38:59–15:38:59，`audit_registration_fa5.py` | 固定WT；exit0；严格重复键、13切片、历史、整卡、not_run、其他R与初始19错误核查，registration_fa5_audit.json |

登记引用的review_report_sha256=`e52057e...`与fa5 Windows工作副本实际字节一致；Git规范LF blob为`02dacbbe44bac5e4cac62941995ee46b04bf7c743f679453fd39785074e1fb6b`，仅CRLF规范差异、文本完全相同。本审最初把工作副本hash直接与Git blob比较的辅助assert失败已纠正；没有把换行口径误报成报告被改写。

**Verdict: Ship，允许按既有用户授权与阶段规则交付该登记版本。** 本复核不执行push，也不声称远端SHA已核对。manual、云端CI实际执行、正式评测、后段live及生产恢复等仍不在G-A限定通过范围。

证据目录：`reports/runs/recovery_ga_checkpoint_review_1_20261015/`。不需要重跑源码未变的1200项；本中文补充可随下一阶段证据提交，fa5已包含原完整最终Ship报告。

登记复核封存：2026-10-15T15:40:11+08:00。
