"""Seal raw repair evidence without rewriting earlier failures or implying runtime acceptance."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
CODE = "dc04d193185324f6913cde8efc40f4b238047dd8"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8").strip()


assert git("rev-parse", "HEAD") == CODE
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests")
assert not git("diff", "--cached", "--name-only")
records = []
for label in ("provenance_red", "provenance_green", "combined_frozen_unit", "combined_frozen_pg", "combined_frozen_ruff", "combined_frozen_format", "combined_frozen_mypy"):
    record = json.loads((RUN / (label + ".json")).read_text(encoding="utf-8"))
    junit = RUN / (label + ".xml")
    if junit.exists():
        suites = ET.parse(junit).getroot().findall("testsuite")
        record["test_counts"] = {key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
    records.append({"label": label, **record})
assert records[0]["exit_code"] == 1
assert all(row["exit_code"] == 0 for row in records[1:])
assert records[2]["test_counts"]["tests"] == 234
assert records[3]["test_counts"]["tests"] == 95
index = json.loads((RUN / "fixed_index_commands.json").read_text())
assert len(index) == 9 and all(row["exit_code"] == 0 for row in index)
started = now()
report = ROOT / "reports/tasks/R07-publication-combined-fix.md"
assert not report.exists()
verification = "\n".join(
    f"| {row['label']} | {row['started_at']} / {row['ended_at']} | {row['exit_code']} | {row.get('test_counts', '非pytest检查')} | `{RUN.relative_to(ROOT).as_posix()}/{row['label']}.log` |"
    for row in records
)
body = f"""# R07 · 发布权限、锁顺序与评分机构组合修复

文档首次创建时间：{started}
本次写作开始时间：{started}
本次写作结束时间：{{ENDED}}
最后更新时间：{{ENDED}}
证据截止时间：{started}
主控：/root；修复作者：r07_publication_acl_and_lock_fix、r07_cvss_authority_scope_fix、/root。
独立reviewer：r07_publication_first_independent_review，原初审/新定向复核。
任务状态：awaiting_review；实现状态：partial（仅发布服务切片完整）。
工作分支：codex/r07-publication-fix-combination。
已测/待审代码SHA：{CODE}；代码tree：48690bfe3531d5095dc5c188f0fa26e62544f66e。
提交/推送：本报告封存前尚未发生材料提交；0 push；整R07/G-C未验收。

## 1. 用户问题、范围与行为

R07/F2/P2/E1/T19–T23/T35富化发布必须受当前原文全来源ACL和版本约束。加载前检查来源、父文档与修订；即使候选为空、FAILED或重放历史也不能绕过父权限。已有来源事务按source→doc→scope顺序保存；发布先取全部排序source锁，再doc/revision，再scope/event，避免真实40P01。不同CVSS机构并列保存；同机构同版本的真实分歧仍conflict。模型提议保持pending/unverified，不转supported。

root只另加内部发布收据schema2可读context，保存rule_version、event版本与来源roster，而不只保留不可解释hash。旧schema1只用于既有隔离测试，默认产品未装配该新发布入口；现有claims/public API不改。

## 2. 文件与复用

修改enrichment/inputs.py、publication.py、signals.py、直属unit/contract/PG测试与CR。复用DocumentReadService的可见性语义、现有PG事务/锁/事实/维度/receipt/outbox服务；source_documents.py没有改。完整输入名单与source主锁沿已有来源持久化定义统一，不另建事务/CRUD框架。可读context新增两行及一个真实PG验证是追溯规则版本所必需。

ACL代码a80408fb35addf35c04a91d255f20fb9a987423e、材料b0a5b64014f89a689b6b1efcdd21e791b454c12f；机构代码2ba07cbfbdb5d24d0bf3214dcf522ddfce3ed184、材料fde252955fd88f537b844b0414d08967d0b2d67a。root组合20fb985后新增dc04。原两份public-signals fixture仅迁移已确认机构语义，完整旧文件/原红保留，case数量、金标/分母/门槛不改。

## 3. 问题台账

| 问题 | 输入/预期/实际与根因 | 修复/复验 | 当前状态 |
|---|---|---|---|
| PUB-ACL | source或doc父撤权仍读取对象/空FAILED发布；修订ACL不能替代整个父链 | a804全roster预检查、发布/历史再查；95PG包含新15 | 待独立复核结论 |
| PUB-LOCK | 来源source→doc→scope与原发布scope→event→doc反序；真实40P01 | a804同序；原source writer已本来有source advisory不伪改 | 待独立新时序复核 |
| PUB-CVSS | 不同authority 9.8/8.1被归conflict | 2ba把authority加入literal作用域；同authority真实冲突保留 | 待独立复核 |
| PUB-PROVENANCE | schema1只有不可读输入digest，规则追溯缺可读context | dc04 schema2/context；真实PG红1/绿1 | 待独立复核 |

前三项初次发现时间历史未在本报告记录，引用原独立G-C-R07-publication-review-1.md，不依据mtime补造。rootprovenance红/绿实际时间见下表。原旧锁屏障要求已取得scope后让source writer提交，与修后正确锁序互等；其红保留，不能称该旧探针全绿。独立reviewer另用真实pg_locks/blocking_pids核查新时序，报告单列，不由作者改旧probe。

## 4. 实际验证

cwd全部为`D:/wt/r07-pub-combined/backend`，PG为唯一隔离test_dianzi_r06_catalog_r07_pub_combined_20261016，真实PostgreSQL；source输入fixture明确合成，无外部模型/测绘/source请求。命令完整argv/退出码/源码状态在同名json，日志和JUnit原bytes保留。目标pytest使用显式--no-cov，仅限定行为检查，不当整仓原60覆盖门通过。

| 检查 | 开始/结束(+08:00) | exit | 数量 | 原始日志 |
|---|---|---:|---|---|
{verification}

234 unit/contract与95 PG均0fail/error/skip；PG执行122.94秒。provenance绿1包含在95，不相加。Ruff/format通过、mypy99源通过。此前root原发布71完整pure1992通过/1PDFguard失败保留，后续主控8a完整pure四CPU产品红未闭，本批没有复跑或签关闭CPU问题。

unit/contract：本切片passed；integration：限定真实PG passed；security：父权限/事务负例包含PG，独立203全安全范围待报告引用；frontend/e2e/live/manual：not_run。默认API/worker仍未接新九维服务，真实模型、公开资料补充、Hunter/Quake持久发布由后续批次完成。

## 5. 调用链、合同与限制

官方CBM v0.11独有r07-pub-dc04-src，对dc04 backend/src固定源码建立/architecture/schema与五trace+rg共9命令exit0，原产物在fixed_index_commands.json。默认assets未索引，源码rg交叉；publish函数目前生产入口没有调用，不能由有定义/测试调用声称API/worker装配。来源writer共用source:主锁的源码及PG链实际核对，graph边不单独作正确性结论。

CR-R07_publication_acl_lock_fix、CR-R07_cvss_authority_scope及CR-R07_multisource_enrichment_publication补充schema2记录本批兼容/迁移/回滚/测试影响；不更改原批准建设范围/官方要求/评分/盲测原则。无新增依赖、迁移或权限授予，回滚停止接线保留已持久历史，不用downgrade删证据。

## 6. 结论与下一步

作者只awaiting_review。旧三Must必须新独立reviewer对dc04复核及材料核验后才可登记切片限定通过；整R07仍partial。主控将服务与单维Generation真实客户端接持久PG工作流、API和默认worker，另行真实模型/浏览器/重启验收。此前历史和原红不被本批绿覆盖。

## 7. 修订记录

{started} /root首次编写本组合报告，实际数据由本run receipts/JUnit读取，原首次代码编写总时长历史未完整记录。{{ENDED}} 完成正文与证据表；下一材料提交与push日志独立，不使本文引用自身commit。
"""
ended = now()
report.write_text(body.replace("{ENDED}", ended), encoding="utf-8")
material_paths = sorted([report, *RUN.glob("*")])
material_paths = [path for path in material_paths if path.is_file() and path.name not in {"artifact_manifest.json", "artifact_manifest.sha256"}]
artifacts = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in material_paths]
manifest_path = RUN / "artifact_manifest.json"
manifest_path.write_text(json.dumps({"code_sha": CODE, "code_tree": git("rev-parse", CODE + "^{tree}"), "sealed_at": now(), "artifacts": artifacts, "verification": records, "scope": "source repair service only; no runtime/live/stage acceptance"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
(RUN / "artifact_manifest.sha256").write_text(manifest_hash + "\n", encoding="ascii")
attributes = ROOT / ".gitattributes"
lines = attributes.read_text().splitlines()
for line in (
    "reports/runs/recovery_r07_publication_combined_fix_20261016/* -text -diff",
    "reports/tasks/R07-publication-combined-fix.md -text",
):
    if line not in lines:
        lines.append(line)
attributes.write_text("\n".join(lines) + "\n", encoding="utf-8")
selected = [".gitattributes", *[row["path"] for row in artifacts], manifest_path.relative_to(ROOT).as_posix(), (RUN / "artifact_manifest.sha256").relative_to(ROOT).as_posix()]
subprocess.run(["git", "add", "--", *selected], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
for row in artifacts:
    blob = subprocess.check_output(["git", "show", ":" + row["path"]], cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest() == row["sha256"], row["path"]
subprocess.run(["git", "commit", "-m", "R07 seal combined publication fixes with raw evidence and readable rule provenance"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
print(json.dumps({"material_sha": git("rev-parse", "HEAD"), "code_sha": CODE, "manifest_sha256": manifest_hash, "artifacts": len(artifacts), "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "raw_blob_verified": True, "pushes": 0}))
