"""Freeze the bounded independent repair verdict and distinguish the obsolete bug witness."""

import json
import xml.etree.ElementTree as ET

from review_runner import ROOT, RUN, now

REPORT = ROOT / "reports/reviews/recovery/G-D-R11-pg-assessments-review-1-recheck.md"
proof = json.loads((RUN / "author_raw_and_source_proof.json").read_text(encoding="utf-8"))
database = json.loads((RUN / "database_receipt.json").read_text())
counts = {}
for path in sorted(RUN.glob("*.xml")):
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    row = {key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
    row["passed"] = row["tests"] - row["failures"] - row["errors"] - row["skipped"]
    row["failed_cases"] = [case.get("name") for suite in suites for case in suite.findall("testcase") if case.find("failure") is not None or case.find("error") is not None]
    counts[path.stem] = row
(RUN / "test_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
commands = [json.loads(line) for line in (RUN / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
lines = [
    "# G-D / R11 PostgreSQL 规则与研判内部切片 · 原审查人 fix1 定向复验",
    "",
    f"记录时间：{now()}。结论：**限定 Ship**。初审 finding 1 的 CAS 原文当前性缺口已由冻结修复关闭；没有新增 Must。仅签本内部 PG 规则/四态证据包与本次 CAS 修复，整 R11/T27/T28、G-D 与产品真值验收仍 partial，不写 accepted。",
    "",
    "这次修复让提交、历史读取和重放实际重新打开来源 CAS 对象，缺失/损坏/长度或hash错误时显式失败。PostgreSQL 输入锁、历史准备收据、来源 ACL 和全部 scope epoch map 继续负责业务当前性。",
    "",
    "独立 WT `D:/wt/r11-pg-assessments-review1-fix1`，分支 `codex/r11-pg-assessments-review1-fix1`，代码 `2ddc8fe2ff3e7becfad3b1774a10407911eacbe6`，材料/HEAD `6b10f2c4ed013f4375d51fc31e1cb317409730ac`。亲核 source diff 仅两源文件与新增15-case直属PG测试；无 metadata/schema/迁移/参数阈值/金标/API/worker变化。审查只新增本报告与新run，未修改候选source、原tests、progress或初审工作树；无 spawn/push。",
    "",
    "## 原 Must 的关闭证据",
    "",
    "初审两个精确用例保持原文件 bytes、damage字面值和断言：`b\"independent review: damaged CAS object\"`，prepare之后实际改写CAS；commit应ValueError且不增结果，原正常commit之后损坏，read应ValueError。两项定向独立通过（original_two_exact）。",
    "",
    "共享 load_rule_inputs 的 store 参数现在必需 ContentStorage，没有 None跳过分支；AssessmentService.commit:230与_read_result:352–357都传真实self.content_store。当前所有7调用由新CBM qualified traces、完整 rg 与实际源码交叉核对，create/validate/review/publish/prepare 原本已传真实store；API/worker仍没有生产调用。单对象2MiB/总8MiB/20来源限制保持，读后再次核真实长度/hash。",
    "",
    "我另写14项真实PG边界，全部通过：commit/read/replay × 原文缺失、等长替换、PG size错误共9项；PG父对象锁等待时实际损坏/丢失2项；合法revision writer在raw读期间实际等待1项；source ACL拒绝先于raw IO1项；健康read/replay每次重开+正常GC/写入保护1项。数据为synthetic fixture，审核actor不是真人标签。",
    "",
    "锁窗口不是仅线程Event断言：独立连接查询pg_stat_activity实际得到wait_event_type=Lock、wait_event=transactionid。父锁等待的提交在释放前未结束，等待中对象损坏/缺失，释放后异常且result row delta=0。实际save_document_revision writer在raw核验点被现有PG锁阻塞；提交先完成当时current，writer更新后再read为stale，持久化原历史payload不覆盖。观察日志independent_fix_observations.jsonl保留PID/状态与行差，没有参数/连接秘密。",
    "",
    "健康commit/read/replay累计实际重开raw5次，replay身份幂等；随后损坏的replay被拒，历史payload原样。source ACL变不可见时read/commit先404，sentinel证明未打开raw，无新增结果。正常ContentStore.store_bytes会校验已有对象，损坏时不覆盖；cleanup_unreferenced_object按真实document/revision/fetch/source-response引用拒绝GC。亲读content_store.py:store_bytes/read_verified、knowledge/revisions.py:473以后的实际GC及MinioStore对应实现；正常路径保护不用于排除异常损坏负例。",
    "",
    "## 原12项探针的完整保留与结果解释",
    "",
    f"原test_independent_boundaries.py逐字复制到新run，SHA256 `{proof['copied_probe_sha256']}` 与初审文件一致。原12项全部运行：11 passed /1 failed /0 error/skip；唯一失败为 `test_observe_damaged_evidence_receipt_and_sql_cost`。它是初审诊断观察，明确期待已损坏原文仍commit成功/current。修复后在该commit点实际抛hash mismatch，这个旧漏洞观察预期失效，不能拿来称修复失败，也未把其改预期、删除或skip。",
    "",
    "其余11项含原规范两红、权限/claim历史/family/third-tenant/正常资产writer和seam对照均通过。两seam项只验证修复方向，不作为新增修复行为分母；旧observer留下的current/rowdelta1记录与旧2红日志保持原字节。新14项明确验证拒绝current和历史不覆，是独立的新行为证据。重复运行不累加通过数量，作者green不直接当本审查结论。",
    "",
    "## 资源、工具问题与完整实际检查",
    "",
    f"新专属数据库 `{database['database']}`、新随机schema `{database['schema']}`，forward实际升级0019后六局部Table，实际reflection保存所有columns/PK/FK/unique/check/index/trigger。未复用作者schema，无drop/downgrade；生产0021不存在/not_run。原loopback25432、root测试base库/test_账号守卫保留，再构造本freshDB环境；Redis15/来源6h/e310自有服务/其他ports未触碰。",
    "",
    "首次WSL抓连接与一个CBM read trace遇native subprocess TimeoutExpired，含负remaining秒数；最初四个suite启动失败均在pytest之前，业务0执行，不能记业务fail/pass。原完整traceback留原工具响应，tool_failure_history.json只如实转录其facts/session IDs，未伪造未捕获的开始结束或underlying exit，保留null。服务停机与并发启动根因均未证明，不作归因。",
    "",
    "root明确给出Windows当前用户DPAPI测试资源引用后，runner仅替换资源获取方式，stdout捕获/解密只在内存，未打印或写明文。每次resource_reference_receipts.jsonl记录实际时钟/守卫，shared backend/tests/conftest hook在解密前加载；external probes的register_sensitive_failure_value显式登记实际SecretStr，runner写log前exact-value脱敏。最终实际值scanner包含报告和全新run，必须0；非regex-only。",
    "",
    "新owned src fast index1585/8401，assets另198/823，图schema/architecture与Assessment prepare/commit/read、Rule五方法、Inventory writer完整qualified traces实际成功。超时的read剩余trace在同新图定向补跑exit0，未用短名function_not_found算通过；全src rg证明没有遗漏nullable调用。使用Ponytail Review5.2.0检查正确性、安全、并发、测试、性能与复杂度，不新增业务框架。",
    "",
    "| suite | tests | passed | fail/error/skip | 解释 |",
    "|---|---:|---:|---|---|",
]
for name, row in counts.items():
    explanation = "旧漏洞观察预期失效；规范行为11项通过" if name == "original_12_byte_exact" else "独立执行"
    lines.append(f"| {name} | {row['tests']} | {row['passed']} | {row['failures']}/{row['errors']}/{row['skipped']} | {explanation} |")
lines += [
    "",
    "原33PG、作者新增15PG、我新增14PG、原两个精确负例、354相关和7unit+5contract均真实运行；原12完整结果如表，不凑累计计数。mypy126源通过，固定修改3文件Ruff/format通过。--no-cov不声称全局覆盖门通过。",
    "",
    "命令的完整argv/cwd/start/end/exit/elapsed见commands.jsonl，秒级+08时钟。各label对应同名stdout/stderr.log，pytest另有JUnit XML；早期工具启动失败独列，不编造其业务数量。",
    "",
    "| label / command | cwd | start +08 | end +08 | exit | 秒 |",
    "|---|---|---|---|---:|---:|",
]
for item in commands:
    lines.append(f"| {item['label']}: `{' '.join(item['command'])}` | {item['cwd']} | {item['started_at']} | {item['finished_at']} | {item['exit_code']} | {item['elapsed_seconds']} |")
lines += [
    "",
    "## 制品与未验证范围",
    "",
    f"新增作者55raw亲核每一实际文件的长度/raw/LF SHA、声明/发现集合与已提交7个source blob ID/hash全部匹配。新exact manifest SHA256 `{proof['fix_raw']['manifest_sha256']}`；expected作者fix报告hash未给，明确null。旧作者118raw与初审80raw逐文件亲核全匹配；初审报告SHA仍`f92ba375d415b5af55252f7bcac016e227318fa2ac56dcf911436d10ed2e1643`。source的Windows CRLF与作者LF分别记录，不误报源内容变化。原80和初审报告未重写，proof/exactmanifests在本新run冻结。",
    "",
    "锁序与既有source/document→publication/event/claim、asset→tenant publication一致；没有额外hash锁引起逆序。新增每次CAS IO的成本为有界来源字节的线性读取与SHA计算，replay/read也重新打开；不会用缓存省掉正确性。未做最大20来源/8MiB或并发吞吐正式基准，不推断P1/P3性能门；原N×B/B×S有界条件复杂度保持，没有可成立的性能Must或按行数删代码建议。CAS核验保证核验点的真实bytes可验证，不承诺核验后外部存储事故永不发生。",
    "",
    "未运行/未签：全后端suite、原T24专库PG、生产0021、API/jobs/worker/default latest、完全无rule任意空查询、T36索引/调度、OpenVEX、frontend/e2e、真人必要性/范围完整性审批、3→5产品真人可靠真值、正式金标/holdout、真实模型/provider/source/FOFA及性能门。外部model/provider/source调用0，费用unknown，fixture人审不计manual/live。",
    "",
    "合同/计划/评分：两源窄修复和内部必需store不改公共合同/栈/分母/阈值/金标。限定支持F2/F3内部证据/current正确性；不据此签U04/U05/U08完整产品、P2人工准确率/召回率、A1工作流或G-D。",
    "",
    "Verdict：**Ship（仅冻结内部PG切片与CAS fix1）**。原finding1关闭；无新增Must。下一项建议由root依计划处理正式0021及独立生产接线/真人验证，不在本轮执行。报告/本run raw manifest/sourceproof hash见delivery_receipt.json。",
]
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(dict(report=str(REPORT), written_at=now(), counts=counts), ensure_ascii=False))
