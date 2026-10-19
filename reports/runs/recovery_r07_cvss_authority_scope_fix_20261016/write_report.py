"""Write factual Chinese task evidence from sealed command receipts and Git identities."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET

from run_checks import ROOT, RUN, git, now, write_json

CODE = "2ba07cbfbdb5d24d0bf3214dcf522ddfce3ed184"
paths = git("diff", "--name-only", "71e594cb958bd93d21fb7ed66574b3cba4cc47e1", CODE).decode().splitlines()
identities = []
for path in paths:
    work = (ROOT / path).read_bytes()
    blob = git("show", CODE + ":" + path)
    identities.append({"path": path, "work_bytes": len(work), "work_sha256": hashlib.sha256(work).hexdigest(), "git_bytes": len(blob), "git_sha256": hashlib.sha256(blob).hexdigest(), "git_blob_id": git("rev-parse", CODE + ":" + path).decode().strip(), "lf_normalized_equal": work.replace(b"\r\n", b"\n") == blob})
assert all(i["lf_normalized_equal"] for i in identities)
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "contracts").strip()
write_json(RUN / "frozen_code_identity.json", {"at": now(), "code_sha": CODE, "files": identities, "src_tree_listing_sha256": hashlib.sha256(git("ls-tree", "-r", CODE, "backend/src")).hexdigest()})
write_json(RUN / "instrumentation_deviations.json", {"recorded_at": now(), "items": [
    {"operation": "initial workdir", "result": "os267 before execution", "reason": "parent path/branch text initially parsed as a combined path; root clarified D:/wt/r07-cvss-scope", "product_tests_executed": 0},
    {"operation": "initial new test collection", "receipt": "baseline_new_red.command.json", "result": "1 collection error", "reason": "unit and contract same basename; renamed only new contract file before behavioral red", "business_failure": False},
    {"operation": "initial static_initial/format_apply invocation", "result": "WinError2 before child execution", "reason": "Windows relative executable resolution; corrected to absolute interpreter", "product_checks_executed": 0, "exact_initial_times": "not recorded"},
    {"operation": "initial Ruff", "receipt": "ruff_initial.command.json", "result": "9 E501 findings", "resolution": "formatter and split literal URL; ruff_frozen and format_frozen pass"},
    {"operation": "read/search probes", "result": "some Get-Content paths absent in fixed71; rg literal wildcard paths unsupported on Windows", "resolution": "read main reports only; used rg real files/directories; corrected caller search rg_preflight exit0"},
    {"operation": "first report/seal generation", "result": "guard assertion then missing report file", "reason": "lexical connection scan initially flagged SQLAlchemy's already password-masked Engine representation in the red log", "resolution": "require any matched representation to contain literal masked password; original red log and outcome unchanged; report then manifest successfully written"},
    {"operation": "material diff checks", "receipts": ["material_diff_initial.command.json", "material_diff_check.command.json"], "result": "default check flags CR; command-local cr-at-eol still finds genuine whitespace in pytest's original failure excerpts", "resolution": "preserve original log/XML bytes; check authored source/docs/scripts/JSON receipts separately in material_authored_check; no global config or ignore file"},
]})
labels = ["baseline_new_red_v2", "baseline_pg_red", "old_expectation_red", "old_public_case_red", "related_202_frozen", "new_32_frozen", "source_regression_146_frozen", "publication_pg_frozen", "ruff_frozen", "format_frozen", "mypy_frozen"]
rows = []
for label in labels:
    receipt = json.loads((RUN / (label + ".command.json")).read_text())
    count = receipt["counts"]
    result = "非pytest检查" if count is None else "/".join(str(count[k]) for k in ("tests", "failures", "errors", "skipped"))
    rows.append(f'| {label} | {receipt["started_at"]} → {receipt["ended_at"]} | {receipt["exit_code"]} | {result} |')
groups = {}
for case in ET.parse(RUN / "related_202_frozen.xml").findall(".//testcase"):
    name = case.attrib["classname"]
    groups[name] = groups.get(name, 0) + 1
pg_groups = {}
for case in ET.parse(RUN / "publication_pg_frozen.xml").findall(".//testcase"):
    name = case.attrib["classname"]
    pg_groups[name] = pg_groups.get(name, 0) + 1
write_json(RUN / "test_groups.json", {"related_202": groups, "publication_pg": pg_groups})
for path in RUN.glob("*.log"):
    content = path.read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(r"postgresql(?:\+psycopg)?://[^\s]+:[^\s]+@", content):
        assert ":***@" in match.group(), "unmasked connection must not enter evidence"
stamp = now()
report_path = ROOT / "reports/tasks/R07-cvss-authority-scope-fix.md"
first_created = stamp
if report_path.exists():
    match = re.search(r"2026-10-16T[0-9:]+\+08:00", report_path.read_text(encoding="utf-8"))
    if match:
        first_created = match.group()
report = f'''# R07 · CVSS 评分机构作用域最小修复

首次创建：{first_created}；本次写作开始/写作结束/最后更新/证据截止：{stamp}，均为真实 +08 时刻；代码编写起止未逐秒记录，不从 mtime 推造。状态 **awaiting_review**，实现 complete；作者自检不等于独立评审。工作树 D:/wt/r07-cvss-scope，分支 codex/r07-cvss-authority-scope-fix，起点 71e594cb958bd93d21fb7ed66574b3cba4cc47e1，业务冻结 **{CODE}**。没有 push、accepted 或共享 progress 修改。

## 目标、范围与实现

本次输入仍是已有合同的已核目标身份、版本、评分机构与精确字段证据；输出仍是四维 DimensionAttempt。唯一产品行将 CVSS scope 补入 authority；同一机构/版本内继续比较完整 score/vector，真实分歧保留 conflict，不同机构并列 available。没有取最大、首项、平均、来源投票或改分值。

已读 AGENTS、00 执行图、R07 卡、T19/T21、03/04/05/06、候选/v3/多源发布 CR、类型及导出 schema、源范围规则、旧公共字段报告和已有状态/交接；使用 Ponytail 插件5.2.0 full。authority 依现有必填有界字符串合同精确比较，不额外 trim/casefold；空/缺/错误类型保持原校验和失败信息，unknown 不借用已知机构。source level 不取消同 scope 冲突，2.0/3.0/3.1/4.0 各版本分组独立。

业务修改6文件：signals.py；两份经主控精确授权的旧 unit；新 unit、contract、PG各一。另新增自己的 CR、报告和本 run 材料。文件完整列表、工作字节/Git blob字节、SHA256与LF等同性见 frozen_code_identity.json。没有修改 signal_sources、inputs、publication、knowledge、DB迁移、API、认证、锁、依赖/配置/运行时/UI、原独立审查探针或评分材料。

旧测试偏差及逐case迁移见 [CR-R07_cvss_authority_scope](../../docs/decisions/CR-R07_cvss_authority_scope.md)。冻结71两个原 unit 完整 Git blob 原字节分别保存 old_test.original.raw、old_public_test.original.raw，SHA与blob身份在identity JSON；旧expectation在新代码上真实产生5 failed/8 passed及单例1 failed再迁移，原参数数量不删不skip。原101仅改获授权的一个case；原fix1的13实例仍13，CWE11不变。先前说明曾误说6个偏差参数实例，实际JUnit证实5个，另原101单例1个，分别封存，不混为一轮。

## 前红后绿与冻结验证

所有pytest cwd为本工作树 backend，使用独有离线 uv sync --offline --frozen 的Python3.12环境；实际完整 argv、cwd、+08起止、exit、源hash前后在同名.command.json，原输出和JUnit同名.log/.xml。定向pytest以 -o addopts= 明确关闭自动全仓coverage汇总，不声称覆盖率，也没修改配置中的原60门槛。

| 检查 | +08实际起止 | exit | tests/failures/errors/skipped |
|---|---|---:|---|
{chr(10).join(rows)}

新红29=18 unit+11 contract（7 failed/22 passed），其后补3个独立控制，最终32=21 unit+11 contract；原失败是不同机构被错误标conflict。PG前红2项中不同机构失败、同机构冲突对照通过；最终同一两对照通过。old_expectation_red和old_public_case_red是合同偏差迁移的独立红证据，不冒充源代码回归。

related_202_frozen准确构成为原公共101（51 unit+50 contract）+原fix1 24（13 unit+11 CWE合同）+根领域原77，未重复相加；每文件计数见test_groups.json。来源146为原NVD/vendor/T19/T10/T12/T23七文件附加回归，不改旧断言。publication_pg_frozen共32（各文件实数见test_groups.json），含本次2个对照及原publication/inputs 30；不是独立reviewer的8个扩展probe。Ruff/format6文件passed；full src mypy 99源文件passed。冻结后源码与测试无修改。

## 真实PG路径和边界

专有数据库 test_dianzi_r06_catalog_r07_cvss_fix_20261016，DIANZI_TEST_RUN_ID=r06_catalog_r07_cvss_fix_20261016；每例使用原catalog_engine的UUID schema并只清理该schema。连接文件仅由runner捕获到内存/测试环境，未打印、未放argv或报告。用合成改写的NVD响应输入（fixture，非live）实际persist_source_response→load_event_enrichment_inputs→enrich_structured_fields→publish_enrichment_attempts→新session PG重读→KnowledgeReadService.event_detail，再重放相同request_id验证结果ID/claim IDs/计数不增加。

同CVE/3.1下9.8/8.1，两不同机构为available，同一机构为conflict；两组都保留两个claim。断言object_json机构/分值、claim_assertions.scoring_authority、两个原文source叶引用、quote SHA/坐标版本/support标记、event_detail状态/claim IDs/citations和显示机构。不是只运行纯比较函数，引用并不被当作真实性或live证明。

## CBM、封存与未完成项

修改前官方WSL Ubuntu-22.04 root portable CBM actual CLI独有cache /tmp/dianzi-cbm-r07-cvss-authority-scope-fix-20261016，仅backend/src。baseline为1358 nodes/6993 edges，frozen为1358 nodes/6997 edges，not_indexed/skipped/parse_partial/parse_unusable均0；schema与限定名_scope/enrich_structured_fields trace保存完整原输出。_scope←_attempt←enrich_structured_fields←publish_enrichment_attempts 与 rg_preflight调用者/测试/schema/config核对一致。CBM边数不是源码身份，源码以冻结Git blob与hash为准。

artifact_manifest.json收录本报告、CR、本run及6业务文件的字节数/SHA256/raw Git blob身份；不自含manifest hash，材料提交由root最终固定。材料按命令级core.autocrlf=false保留raw证据字节。首次材料diff默认把CR当行尾空白报错，命令局部cr-at-eol后仍发现pytest原失败摘录的真实行尾空白；两个红输出material_diff_initial/material_diff_check保留，不改原log/XML。最终material_authored_check仅检查本轮编写的源码、文档、脚本与JSON收据，不把原始失败输出当新手写代码，不改全局配置或ignore文件。初期路径误解、同名新测试collection error、Windows相对解释器路径、静态长行红和错误只读路径均在instrumentation_deviations.json如实登记，修正后的业务检查才计passed。

unit/contract/integration本切片passed；security只沿用现有PG回归，不声称完整安全验收。独立8probe原字节未运行/未改，ACL和死锁4red由另一作者处理，不能说8全过。旧CPU full pure 1944 passed/1 failed/10 real_pg deselected继承红仍保留，本轮未无意义重跑全仓/改门槛；源真实性、模型、测绘、正式live/manual、UI/e2e、性能和人工金标准确率均未证明。新增外部来源/模型/provider/network/资产调用0；仅本地受控测试PG，不启动新服务或付费任务。

既有事实/维度/收据不原地改写，无DB/API/schema迁移。后续历史conflict须在获授权的调度/规则版本更新中创建新判定并保留历史，本包不执行批量重判。F2/P2仅登记T19-C01/C05及T21/W04机构作用域的这组候选/PG可追溯证据，不代表R07/G-C或原T全卡accepted。

下一步：主控组合本业务冻结与另作者ACL/锁修复，派原独立publication reviewer固定新版本复核；仍awaiting_review，不用旧A的Ship给新代码背书。

未检查：独立扩展8probe、全仓pure/CPU、真实外部来源与模型、UI/e2e/live/manual/性能；已知ACL/锁和历史重判仍有各自后续工作。
'''
(ROOT / "reports/tasks/R07-cvss-authority-scope-fix.md").write_text(report, encoding="utf-8")
print(json.dumps({"report_written_at": stamp, "code_sha": CODE, "product_files": len(paths)}))
