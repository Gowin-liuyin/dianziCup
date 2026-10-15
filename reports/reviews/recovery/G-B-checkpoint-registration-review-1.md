# G-B 检查点登记定向复核 1

**结论：Ship，固定登记候选 `1ca2ea34c224e23776431fa6eac5fe6549d8c65f` 可进行正常阶段push。** 产品批准仍指向 `1927eeb00a7e0c1335f76340b0382f46102f08f2` 的R04/R05阶段切片。本复核没有新增产品能力、没有提升原T整卡或后段范围，也未实际执行push/accepted/state修改。

审查者 `/root/g_b_checkpoint_review`；本轮首个实际时钟2026-10-15T19:10:36+08:00。使用Ponytail5.2 review/full既有流程；不派subagent。仅修改本报告及 `reports/runs/recovery_gb_checkpoint_registration_review_1_20261015/`。

## 固定依据和代码身份

- 初次登记候选 `ab097347bba7e0008b4337fa2c985452308feed6`，父为原产品Ship 1927；独立 detached WT `D:/wt/gb-register-review`，创建前确认未占用。
- 字节修复候选 `1ca2ea34c224e23776431fa6eac5fe6549d8c65f`；独立全新 detached WT `D:/wt/gb-register-final`，创建前确认未占用；完整tree=`8a0125a4601988e7102f67e2a4c71d43cd704cd5`。
- backend/src=`2e85b41a18456d462619959e22622a23e4ca7b78`、frontend/src=`5862a0f0a690bf66f3f3ea7f3fdbd2caa9b62e8a`仍与1927相同。独立Git object比较确认整个backend/frontend/contracts/scripts/infra/config/AGENTS/docs-plan/docs-tasks树均不变，依赖锁、scanner、合同、验收门与分母不变。1ca的state也与ab097逐字节相同。
- 已读frozen AGENTS、00索引、11/12及R04/R05原依据、最新state/阶段/任务/交接；此次逐条读三CR登记追加、state差异、主控登记/失败/切片修复/secret scan/MinIO3结束收据与原独立交付清单。只评登记/归档差异，不重新审主控开发目录或G-C草稿。

## 状态与文档范围

真实结构核验：11条输出切片为R04:T09/T10/T12/T17/T40/T41及R05:T18/T20/T30/T31/T43，恰好等于原阶段意见；都accepted、引用原独立报告，保留pending原记录与2026-10-15T19:08:27+08:00历史。原60张T任务除这些slice_acceptance外的全部字段逐项相等，其它切片也未改变，不仅检查status/implementation/verification。

R04/R05聚合status由awaiting_review登记accepted，七个限定验证层passed、manual仍not_run，history前缀及旧失败保留，review_ref为原独立报告。R06只是pending/not_started→in_progress/partial，verification不变，注明未冻结未审未装配，不计R06/live通过；没有用本次Ship验收R06。当前G-C仅表示进入后续工作，不意味着G-C accepted。

三份CR `CR-R04-R04_source_commit`、`CR-R04-R05_question_commit`、`CR-R04_schema_format_checks`仅追加既有授权落实的独立登记；原文本前缀保留，没有新增重大决策。兼容/前向迁移/关闭入口回滚保持：历史裸key不猜actor，旧无lease pending人工恢复，不自动重付费，不降库或退回fixture。

阶段顶部accepted仅批准切片，live明确属于早前分段并经独立溯源，新1927来源HTTP由真实PG证明；23c/dc014/1927没有混为同版live。10212.6966ms、20旧同空间块复用、累计8供应商调用fee unknown、RFC850非阻断债务及新CPU偶发timeout诊断均公开保留。R12/R17整卡、金标/人工/质量/≤5秒/容器/持续运行等未提升。

阶段首次创建13:48:37、R04首次14:44:29、R05首次16:17:02保持。1ca将G-B最后更新时间校正为真实19:14:59，R04/R05顶部新增当前限定accepted横幅；原needs_changes/in_progress/awaiting历史不删，末尾登记解释当前范围。R05旧“最后更新时间16:17”处位于已明确历史区，不冒充当前更新。此前阶段写作19:06、切片修订19:08、归档修订19:14各自留时，不改成连续运行。

MinIO3 service_end原收据实际16:57:02→18:57:02、deadline/exit0/OOM0；段4从18:57:49开始、47秒间断不拼连续时长。该资源留档没有业务变化，也没有再次读取PG/MinIO或发起来源/模型访问。

## Confirmed缺陷与关闭

1. **初登记归档阻断，已关闭：原独立报告Git blob与交付hash不符。** ab097的 `reports/reviews/recovery/G-B-checkpoint-review-1.md` text未指定；`artifact_manifest.json` L4要求SHA256 `50cbd2152686af6d436514208ddd3f5fcd7116cb86b7729cfc0050974594ea32`。Windows checkout仍匹配，但Git blob实际为 `9d1dca36a88d102a2fd9012f648f4cd5649632e3fee3c09488313ea8d4c0e4bb`。根因autocrlf规范化CRLF→LF；Linux或无转换checkout不能按immutable manifest验证报告。最小修复是根 `.gitattributes` L120仅该path设-text/-diff并按原交付字节renormalize，不改报告/manifest/scanner。1ca独立fresh checkout及Git blob均恢复50cbd，完整审计exit0。初ab失败与主控首次普通git add/assert失败均保留。此缺陷只阻断登记归档push，未推翻1927产品Ship。
2. **已关闭的非阻断清晰度项：** ab097阶段“最后更新时间19:06”落后于19:08修订，R04/R05顶部旧状态易误读。1ca校正真实更新时间、加当前限定横幅，首次及历史文本保持。

主控首次登记遗漏11输出切片导致原计划49pass/7fail，红log/XML仍在controller；19:08基于同一Ship补齐原切片，未改检查器/合同。本人初audit过严把合法R06进行中更新当不允许，exit1为审查仪器断言错误；修正后才继续完整审计，未把它计成产品缺陷。其后原报告blob mismatch为真实归档问题，ab完整审计exit2；最终1ca同样完整检查exit0。

## 归档与安全事实

独立逐文件核验原交付→candidate checkout→Git blob：artifact_manifest中265索引项全部匹配；manifest自身与delivery_receipt另行匹配，共267原RUN文件，controller267文件清单也逐一匹配。原delivery说266是265项+manifest、尚未计receipt自身，口径有原收据依据。候选RUN唯一新增文件是范围内.gitattributes，所以候选目录268文件；不能把属性新增误算为原raw变化。原独立报告正文也完整匹配50cbd，未删失败/EOF/截图。

RUN属性仅本目录所有raw -text、log/xml与原test_review_recheck.py -diff保留EOF；原报告属性只有精确单path。它们控制Git行尾/展示，不是scanner忽略；原scanner与ignore规则tree不变。51共享分类manifest全文、每条raw hash/HEAD blob/span/value均不变并精确通过；14唯一source_origin路径的blob也与1927相同，两个混合行尾R02 probe原字节保持。

实际secret逐值扫描为核对主控收据，非本人亲测：19:09:23→19:09:41、9refs/321patterns/0match；精确修复另外19:14:12与19:15:00两份收据仍9refs/321patterns/0match。本人未读任何真实secret/.env/DPAPI，没有把授权秘密值复制到报告；本轮付费调用0。

## 实际命令与计数

以下均由独立WT运行，PYTHONPATH指向所审WT/backend/src，解释器仅复用原已冻结1927环境；backend锁树相同，没有pip补依赖。56plan及15T06是本轮登记定向复跑，不是产品全套重跑；它们实际版本ab097，1ca仅精确原报告字节/属性、文档说明变化，state/合同/测试/scanner树全等。最终1ca另亲测完整归档/状态审计。旧1419/真实PG/254/17结果由原1927独立报告保留，本轮不重新记为亲测。

| label / 实际argv | cwd | ISO+08 起止 | exit / 计数 |
|---|---|---|---|
| `plan_registration`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe -m pytest tests/plan -q --junitxml=D:/wt/gb-register-review/reports/runs/recovery_gb_checkpoint_registration_review_1_20261015/plan_registration.xml` | `D:/wt/gb-register-review` | 2026-10-15T19:11:45+08:00<br>2026-10-15T19:12:13+08:00 | 0；total=56, pass=56, fail=0, error=0, skip=0 |
| `security_registration`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe -m pytest tests/security/test_t06_authentication_and_scope.py --no-cov -q --junitxml=D:/wt/gb-register-review/reports/runs/recovery_gb_checkpoint_registration_review_1_20261015/security_registration.xml` | `D:/wt/gb-register-review/backend` | 2026-10-15T19:11:45+08:00<br>2026-10-15T19:12:01+08:00 | 0；total=15, pass=15, fail=0, error=0, skip=0 |
| `archive_state_audit`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe reports/runs/recovery_gb_checkpoint_registration_review_1_20261015/audit_registration.py` | `D:/wt/gb-register-review` | 2026-10-15T19:12:38+08:00<br>2026-10-15T19:12:40+08:00 | 1；非pytest；结构/hash断言 |
| `archive_state_audit_recheck`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe reports/runs/recovery_gb_checkpoint_registration_review_1_20261015/audit_registration.py` | `D:/wt/gb-register-review` | 2026-10-15T19:13:15+08:00<br>2026-10-15T19:13:32+08:00 | 1；非pytest；结构/hash断言 |
| `archive_state_audit_complete_ab097`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe reports/runs/recovery_gb_checkpoint_registration_review_1_20261015/audit_registration.py` | `D:/wt/gb-register-review` | 2026-10-15T19:14:04+08:00<br>2026-10-15T19:14:46+08:00 | 2；非pytest；结构/hash断言 |
| `archive_state_audit_final`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe D:/wt/gb-register-review/reports/runs/recovery_gb_checkpoint_registration_review_1_20261015/audit_registration.py 1ca2ea34c224e23776431fa6eac5fe6549d8c65f D:/wt/gb-register-final` | `D:/wt/gb-register-final` | 2026-10-15T19:16:03+08:00<br>2026-10-15T19:16:42+08:00 | 0；非pytest；结构/hash断言 |


每项完整收据/log/XML与原/最终逐文件hash见本runs；registration_audit_ab09734.json保留拒绝，registration_audit_1ca2ea3.json为最终同样断言通过。没有修改业务、共享state或accepted，没有派发subagent，没有push。新报告归档也应由主控延续精确path原字节保留，防止相同行尾问题。

**最终意见：1ca登记范围与原1927限定Ship一致、归档阻断已关闭，可正常阶段push。** 本地已知origin/codex/full-delivery-recovery仍fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4，已独立确认它是1ca祖先；实际远端访问、push/远端SHA回执本reviewer not_run，由主控按已有授权执行。此意见不新增质量金标/正式指标/人工/容器/后段整卡验收。

本报告实际写作/封存起止：2026-10-15T19:19:00+08:00 → 2026-10-15T19:19:00+08:00；本轮结束于此登记定向复核。
