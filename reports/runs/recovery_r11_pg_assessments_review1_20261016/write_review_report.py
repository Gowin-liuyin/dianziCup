"""Record checked facts and the reproduced blocker without changing task acceptance."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from review_runner import ROOT, RUN, now

REPORT = ROOT / "reports/reviews/recovery/G-D-R11-pg-assessments-review-1.md"
counts = {}
for path in sorted(RUN.glob("*.xml")):
    suites = ET.parse(path).getroot()
    rows = list(suites.iter("testsuite"))
    counts[path.stem] = {key: sum(int(row.get(key, "0")) for row in rows) for key in ("tests", "failures", "errors", "skipped")}
    counts[path.stem]["passed"] = counts[path.stem]["tests"] - sum(counts[path.stem][key] for key in ("failures", "errors", "skipped"))
(RUN / "test_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
proof = json.loads((RUN / "author_raw_and_source_proof.json").read_text(encoding="utf-8"))
database = json.loads((RUN / "database_receipt.json").read_text())
observation = json.loads((RUN / "damaged_raw_observation.json").read_text())
commands = [json.loads(line) for line in (RUN / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
lines = [
    "# G-D / R11 PostgreSQL 规则与研判内部切片 · 新非作者独立初审",
    "",
    f"记录时间：{now()}。任务 R11:T27–T28 内部 PG 切片：**needs_changes**；整 R11/T27/T28 保持 partial，本审查不写 accepted，不签 G-D 或产品验收。",
    "",
    "这次改动把规则候选、独立审核、发布/退役和固定资产快照研判落到 PostgreSQL，并保存四态树、来源位置、准备收据和范围关注。当前生产 API/worker 尚未调用这两个内部服务。",
    "",
    "审查工作树 `D:/wt/r11-pg-assessments-review1`，分支 `codex/r11-pg-assessments-review1`，固定候选代码 `d56a1ed306d975be408a2f6f8fbe3e905d940643`，材料/审查基线 `ad122224b02ec16194e03f937b02a218ff6faaa5`。作者工作树未用于执行或复用连接；根工作区未提交修改保留。仅新增本报告及 `reports/runs/recovery_r11_pg_assessments_review1_20261016/` 内 probes、资源适配、日志和制品；业务、原 tests、公共 schema、迁移、limits/gold/locks/progress 均未改，无 spawn/push。",
    "",
    "## Must fix",
    "",
    "1. **准备后或历史读取时原文损坏仍返回 current**（`backend/src/ai_intel/assessment/assessment_service.py:230`、`:352–354`；实际完整性检查在 `rule_persistence.py:526–540`）。",
    "",
    "- 职责：提交与读取应核对证据输入仍有效，原文不可验证时显式失败。当前 prepare 传 content_store 核验对象，commit 和 _read_result 都传 None，随后仅核对 PostgreSQL 中的 hash/坐标/摘要；原文对象变化不会进入 input_digest。",
    "- 具体输入与影响：通过真实 PG 与 synthetic 独立审核发布版本规则，prepare 成功后把所引用 CAS 对象实际改为损坏 bytes。`read_verified` 随即报告 hash mismatch，但候选 commit 新增一条 `supported_applicability/current`，之后 read 仍返回同状态。独立红用例 `test_prepare_then_corrupt_raw_must_not_commit_current` 和 `test_current_history_read_checks_raw_integrity` 均为 DID NOT RAISE；没有环境错误或 skip。实测身份/状态/行数见 damaged_raw_observation.json。",
    "- 最小修复：使 commit 与历史 read 都重查所引用 PG hash 对应的 CAS 完整性。直接在现有 loader 调用传 self.content_store 可复用既有单对象/总量校验；若要求避免锁内文件 IO，则先在锁外重查，再在短事务中比较同一 PG 输入，缺失/损坏显式失败。不得把准备收据当作永久的对象完整性证明。",
    "- 已运行的修复方向对照：审查 probe 仅 monkeypatch 两调用处的 loader 参数，让 None 使用实际 store；commit/read 两个对照均通过，损坏时异常且结果行数不增加。未改候选源码，因此该对照不表示问题已修复。保留本根因两个红例，交作者修复后复跑这些负例及 33 PG，不能删掉红例或更改预期。若跳过，当前结论依赖的原文可能已经无法验证，违反 AGENTS §5、提案“原文不存在或损坏显式失败”和 W07 current 约束。",
    "",
    "## 已核对的行为与调用链",
    "",
    "已读取 AGENTS、00 地图、恢复 R11/U04/U05/U08、T27/T28/T36、03 §3.6–3.9、04 W06/W07/W08、05/06、CR-R11_pg_assessments_proposal 和作者报告/状态/交接；按最新 Ponytail Review 5.2.0 审正确性、安全、并发、测试、性能和复杂度。没有把作者结论直接当独立通过。",
    "",
    "首次本 WT src 独立 fast index：1585 nodes/8401 edges，assets 被排除后单独 index 198/823，两个 index 都没有 unusable/partial source。项目名 `r11-pg-assessments-review1-20261016-73c73ffa`，assets 同名后缀 -assets。schema/architecture、Assessment prepare/commit/read 与 Rule create_candidate/review/validate/publish/retire 的完整 qualified traces 及 InventoryService.import_manifest trace 全部实际 exit0，另 rg 当前源码及测试。未用短名 function_not_found 当成功；未写 ADR 或业务图作为事实库。",
    "",
    "实际 callers：RuleService/AssessmentService 仅新增 assessment 服务之间及直属测试；default API/worker 无构造或调用。写方另亲读 ingestion/source_documents.py 的 ensure_source_registration/persist_source_response/_persist_member、knowledge/revisions.py 的 save_document_revision/register_source_revision_blocks、KnowledgeRepository.publish/_validate_submission/_apply_relation、InventoryService.import_manifest 与 auth_state.lock_authenticated_scope。source/document→publication→event/claim 与 asset→tenant publication 的锁序和当前服务一致；publication 前未持 claim 锁。源码 rg 结果见 callers_rg.stdout.log，图只辅助查找。",
    "",
    "原 33 PG 用例的源码和标记未变，由审查文件 re-export 原测试函数，仅改外部 pg_engine fixture 的隔离资源守卫。独立重跑覆盖正常发布、未知版本、冲突、无审批/model_hypothesis、必要性待审/非作者审批、family 统一身份、显式 retire 后发布、两个 publisher 竞争及 partial unique、prepared receipt 的 actor/完整对象比较、角色/会话/ACL 改变、Unicode quote 与原文核验、资产/source roster 变化、四态树/历史/replay/rollback。synthetic reviewer 不是真人标签，human_labels=0。",
    "",
    "额外真实 PG 负例：withdrawn/superseded/unverified claim 均使旧 prepared 保存 stale、重新 validate 不 eligible、publish 被拒；foreign family 即使新 version 仍 404；持第三租户 publication lock 时本租户 commit 在 3 秒界内成功；合法 InventoryService 在 commit 的 asset 锁窗口等待，随后写新版，旧结果 read 返回 stale；所有五张 append-only 子表实际 UPDATE 都被真实 trigger 拒绝。两次 CAS 损坏红例与两个最小 seam 对照另列，不混成全绿。",
    "",
    "六局部表 metadata 与实际 PostgreSQL reflection（columns/PK/unique/check/FK/index/trigger definitions）完整保存。condition_rule_versions 的生命周期 trigger 与 published partial unique 原 suite 真实负例通过，其余五张表补实际 append-only 负例。knowledge_epoch 是 public 投影，缺行为 null；当前性使用完整 scope_epoch_map 和 source/asset/rule/review digest。公共规则追踪资产租户 epoch，不用 scalar 未变判 current。",
    "",
    "当前已知 candidate 无 published 时，实际结果保存 insufficient_evidence/no_published_rule scope watch。完全无 rule 行的任意空查询、T36 反向索引/重判调度、OpenVEX、默认 API 与 worker 尚未实施。四态条件不把 missing/no hit 变 safe；网络与软件适用分栏，缓解条件没有资产确认通道时 unknown。",
    "",
    "## 真实命令、资源与结果",
    "",
    f"专属数据库 `{database['database']}`，随机 schema `{database['schema']}`。WSL root-owned connection.json 捕获到内存，未打印 URL/password；没有复用作者 hardcoded DSN。forward 从新空 schema 升到 `{database['migration']}` 后创建六局部 Table；无 downgrade/drop、未改生产。生产 0021 文件在当前候选 HEAD 不存在，正式迁移 not_run。只使用既有 PG 25432；Redis DB15、来源 6h/e310 自有服务和其他 ports 均未触碰。",
    "",
    "所有外部 probe 前加载候选 backend/tests/conftest.py shared redaction hook；外部 tests 的 autouse fixture 以 SecretStr 显式登记实际连接/密码，runner 同时 exact-value 脱敏。最终 scanner 以实际值逐文件匹配，非 regex-only；seal 见 secret_scan.json。",
    "",
    "| 检查 | tests | passed | fail/error/skip | 结果 |",
    "|---|---:|---:|---|---|",
]
for label, value in counts.items():
    lines.append(f"| {label} | {value['tests']} | {value['passed']} | {value['failures']}/{value['errors']}/{value['skipped']} | {'failed' if value['failures'] or value['errors'] else 'passed'} |")
lines += [
    "",
    "scope_contract 是 7 unit +5 contract；related_pure 是 354；original_pg 是 33。额外 independent_negative 初轮为 10 cases/8 pass/2 fail，冻结版 independent_frozen 为12 cases/10 pass/同2 fail；actual_observation 与 appendonly 各1 pass。重复运行不累加为独立通过数量，没有额外的缺测 skip。mypy src 实测126 source files通过，候选8代码/tests Ruff与format-check均通过；--no-cov不冒充全局覆盖门通过。",
    "",
    "命令均以秒级 +08 时钟记录，cwd 除 CBM/rg/prepare 为本 WT 根外均为 `D:/wt/r11-pg-assessments-review1/backend`；完整命令 argv 与 cwd 逐条见 commands.jsonl。下表保持实际失败；各 label 对应同名 stdout/stderr.log，pytest另对应 XML。",
    "",
    "| label / 实际命令 | 开始 +08 | 结束 +08 | exit | 秒 |",
    "|---|---|---|---:|---:|",
]
for row in commands:
    command = " ".join(row["command"])
    lines.append(f"| {row['label']}: `{command}` | {row['started_at']} | {row['finished_at']} | {row['exit_code']} | {row['elapsed_seconds']} |")
lines += [
    "",
    "作者字节审查首次 exit1 是审查脚本把新 Windows checkout 的 CRLF raw hash 误要求与作者 LF raw hash相同。原红与初稿 proof 已保留；调整为同时记录 raw/LF/blob后复验，不改原文件。原始118 artifact 每个文件发现、长度与 exact raw hash全部匹配；没有未声明/缺失；12个 source Git blob ID/hash全部匹配，9个本 WT raw为CRLF但LF与作者一致，另3个raw一致。author_raw_and_source_proof.json逐行提供 raw与LF证明；作者 report 的 expected_sha256 未给，明确null，actual由实际文件计算。",
    "",
    f"作者 exact artifact manifest SHA256 `{proof['manifest_actual_sha256']}`，{proof['manifest_actual_bytes']} bytes；其 exact bytes 与 source manifest 原字节已独立复制并冻结。没有只检查清单而漏掉实际文件。",
    "",
    "## 性能、复杂度与未验证",
    "",
    f"Ponytail 按多个用户/并发 PG 服务审查。输入受20来源/64支持绑定/64 AST节点约束；来源 rosters 有界，scope locks只覆盖 public/规则scope/资产租户，没有持无关第三租户锁。每绑定分别查 claim、span、assertion、block、reviews，属于 O(B) SQL往返；绑定查来源 O(B×S)，tree 绑定refs O(N×B)，不是无界增长。单来源单binding的实际 commit 捕获 {observation['commit_sql_count']} 条SQL，未记录参数。未做64-binding吞吐或正式时延基准，不能因此声称P1/P3达标；没有足以成立的性能 Must，不以linecount猜删行。原文最终核验应保留2MiB/8MiB边界并测最大输入。",
    "",
    "本报告实际查看/复跑范围有限：未复跑全后端suite、原T24专库PG suite、生产0021、API/jobs/worker/REST接线、frontend/e2e、完整T36、真人语义审批、3→5真人产品可靠真值、真实来源/模型/provider、FOFA、OpenVEX、正式金标/holdout、容量与性能阈值。external source/provider/model调用0，未开启付费任务；费用上限仍unknown。fixture审批不计manual/live。",
    "",
    "合同与计划：公共合同/分母/金标/阈值未变；仅指出候选漏掉原文完整性窗口，没有批准替代算法或扩范围。评分证据只支持 F2/F3 内部四态与证据追踪的已核验部分；P2准确率/召回率、U04/U05/U08产品闭环、A1 Agent及阶段G-D均未签。",
    "",
    "Verdict：**needs_changes，先修复 finding 1，再由本审查人复跑负例及相关 PG 回归。** 下一项建议仅该最小修复；不继续R12，不自行 accepted。冻结报告/自身raw manifest/source proof的最终hash见交付receipt。",
]
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(dict(report=str(REPORT), report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(), checked_at=now(), counts=counts), ensure_ascii=False))
