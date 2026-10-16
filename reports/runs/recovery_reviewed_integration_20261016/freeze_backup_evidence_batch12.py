"""Record bounded integration and freeze only owned backup sources and evidence inputs."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def timestamp():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = timestamp()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
if head != "1c3c33808053227b8502443ebdff4c848c66e62b":
    raise RuntimeError("integration head changed")
if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
    raise RuntimeError("unowned staged files")
protected = hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
if protected != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user file changed")
inputs = json.loads((RUN / "backup_evidence_batch12_inputs.json").read_text(encoding="utf-8"))
evidence_paths = [item["path"] for item in inputs["plan_evidence_inputs"]]
for item in inputs["plan_evidence_inputs"]:
    if hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() != item["raw_sha256"]:
        raise RuntimeError("historical evidence changed")
checks = json.loads((RUN / "backup_batch12_checks.json").read_text(encoding="utf-8"))
collection_checks = json.loads((RUN / "backup_batch12_collection_checks.json").read_text(encoding="utf-8"))
if len(checks) != 4 or len(collection_checks) != 2 or any(row["exit_code"] for row in [*checks, *collection_checks]):
    raise RuntimeError("required offline checks not passed")
helpers = json.loads((RUN / "backup_batch12_helper_imports.json").read_text(encoding="utf-8"))
section = f"""\n## 集成与并行续接 · {started}

本次写作开始时间：{started}；证据截止时间：{started}；Root当前代码HEAD {head}。G-C/G-D/G-E/G-F仍in_progress/partial，阶段未放行/未push；最后已核远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。原T卡、金标/阈值/分母不变。

本批采用备份source12f9e8cd2f1e7073427c2959fdbc799b90fc44fe已独审ab04855085f828548222443c31020852f7ca2970的4个文件，复用官方pg_dump/pg_restore、现有ContentStore与PG事实，没有新增依赖/平行数据库。独审40不同案例含2真PG/fresh进程，69表/18记录/2原文对象，indexes=rebuild_required；不是Root本批重新跑PG。本批Root 2026-10-17T00:56:48+08:00开始32离线案例passed（0fail/error/skip，0.49s），strict1源/Ruff3文件/backend100格式3文件均exit0。新RootPG/MinIO/实际索引重建/完整恢复/CI仍not_run。命令/起止时间见backup_batch12_checks.json。2个已冻结Windows测试依赖从ab048精确取回，PG2仅collect-only，未连接数据库；旧外层checks.py未采用，runbook改为实际存在且已测的offline命令，PG须用受控资源窗口。22个历史plan证据输入按已有immutable hash复核后入本checkpoint，不把旧报告结论迁给新代码；verify_plan exit0仅结构，不是产品验收。

新真实来源专项review ac6a0ed2efccc4b5af12888605d959937b57d982只签f3c2e41e31fd5b0f1be004b379f5ed775c95f287：339离线=318unit21contract+7实际PG；DoH配置hash6b69fe8e10f9ba85d756061fc2be242bde0a468d6b2b5d3879fed20e7b3e2076，2026-10-17T00:57:32+08:00至00:57:58+08:00，两源HTTP200/defaultAPI→outbox→真实broker普通worker→30trusted-live修订/211证据/2游标→list/detail200。各源仅1页partial/source_page_limit_reached，不能称全来源/6h。旧system DNS非公网拒绝、首次RedisAUTH红保留；旧DTO把None/fixture返回live的真实负例failed，是内部待修而非外部完成。资源最终0，角色superuser CONNLIMIT不硬限，连接峰未采不冒称通过。

R14共享读取消费者+unknown恢复最终source1dafd15ff1c25d08489fd69efa44e8481d6dda22/material43d4eeb89610d04c6eab6816d42c482f5dd6c2be，经原独立reviewer新WT 0e8352564ecd2e39c359aef9f831c90077f7e709限定Ship；348离线+38真PG=386不同用例，真实PGcheckpoint三策略incoming unknown、终态Reporter/read_result、权限/lease/epoch优先与旧37均passed。PG窗口01:18:33.849–01:21:06.606+08约152.76s、进程峰7<=10，DB/schema/连接/进程0，原固定库comment恢复NULL。原fix1/fix2的4红/5红及元数据失败保留。Root尚未集成此source，不签九完整职责/模型live/历史HTTP/UI。

R18 public read fix3 source99ea5e507d1530ce930d2cc078d929881ee3d2be/material60e3223c2be5a4d13c8a310259a5ee16c7774abf经a2ccaa0ae8940a2717536e94afc311a8b32423af限定Ship：141离线、原40PG(8+32)+独立hypothesis1共182不同用例。human完整3quote available/current且PG真实origin/assertion/source_verified保持，模型假设仍blocked/unknown。01:05:09至01:08:03+08总174s<=新240窗口，旧超时/nonce长度setup错误保留。Root还未装配公开producer/typed task/ask/stack/HTTP-MCP/三插件，整R18partial。后续diagnosis123bf91aad8bf7ed1834a370a7ac4c6f9584f80b又以10真实shape离线探针确认来源报告被强图资格误降blocked；这个新已证缺口不由早先限定Ship关闭。

R17默认UI正式bundle真实静态10断言通过，source产品a576；独审b4b1bfa8643c2caeba2e9de8c65cd99715d36c90，实际4.609s/Win峰13/资源0。原runner main500、Edge路径及控制shell错误全部留原收据。仅React挂载/匿名/390窄屏/reduced-motion，调查业务、ordinaryconsume与当前f3浏览器仍not_run。新版资源窗待分配，不能组件替业务。

R16 source d550/032 首审a55b48c49326e698fb7f264557d7271034d1b17c needs_changes：194+4离线green，26PG23pass/3fail（旧drive把retry_wait当终态两红、新assetID创建fixture404）。首PGstdout/cap未落盘，保持unknown；实际owner/OID/COMMENT清理0。fix1 b2b0d8d495bc41af14f5c0db19b7c9a4621bf222/aecfe8535f05f59d54d7785b08f6f722ef1b2d73仅3tests，业务source不变；原194+新driver20=214离线passed，3PGcollect-only；有界真实到期重试journal、原排序/终态业务assert/two-types原字节保持，待原独审定向PG，Root未集成。

滚动并行所有权：Root独占main/共享合同/App/schema/迁移/锁/progress/Gitpush。R06绑定author候选COREa13f67c2ee836c9cee1750a3477f2904efb5d21e/OPS4dfe106a505bc80d1357b3178bcf1513b1711351/materialda221caff24704c8b35f471fd5ae7a9075887cd5只自己23控制文件5处绑定与报告；Product独立D:/wt/r06-product-f3-runtime-20261017仍clean f3，217源+迁移raw/Git分开，22guardspassed，七false/readyfalse/OIDNone，无provision/start/6h。原42ledger不reset/旧namespace是否空闲未测/COMMENTexact9无字面nonce/superuser连接门尚待新独审核，不误写启动。R07内部bb04 reader、91b工厂、c2f helper（304offline）Root未接Enricher；新123bf诊断建议先来源报告分类旁路，原Graph/current_supported/unknown不放宽；graph_apply默认无消费者，另须Root冻结R10协调合同，不挪R16 fan-in。Agent只自己的WT/source/tests/报告，不push/accepted；人工双核/授权资产/CNNVD输入之外还有这些内部工作。

下一动作：冻结已合备份与历史输入，再Root集成已限定通过的R14/R18接口；在新批实现SourceEnricher实际输出UTF8预算及public typed reports后交新非作者，不沿旧审签新code。新R06激活review须先核实际parent健康/OID/COMMENT/ledger/旧namespace空闲/关机/资源，再实际开始同版本墙钟21600s+关闭900s，父deadline2026-10-17T21:49:15+08:00不延长。R19人工gold/秘密和CPU门/索引恢复与CI/R21/R22/R24仍有缺口。费用unknown；此批产品model/API付费调用0。用户tsbuildinfo hash {protected}不改不stage；push ledger不纳本批；本报告写作时push尚未发生。

本次写作结束时间：{{ended}}；修订人Root，保留各文档首次创建与所有历史修订。
"""
ended = timestamp()
section = section.replace("{ended}", ended)
documents = ["progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"]
for relative in documents:
    path = ROOT / relative
    path.write_text(section.lstrip() + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
stage = ROOT / "reports/stages/recovery/G-F.md"
stage.write_text(stage.read_text(encoding="utf-8") + section, encoding="utf-8", newline="\n")
report = ROOT / "reports/tasks/R20.md"
if report.exists():
    raise RuntimeError("existing R20 report requires explicit append")
report.write_text(f"# R20 · 主控备份切片集成\n\n文档首次创建时间：{started}\n任务状态：in_progress\n实现状态：partial\n各层验证：本切片unit/static passed；Root integration/security/frontend/e2e/live/manual not_run\n" + section, encoding="utf-8", newline="\n")

run_names = ["integrate_backup_evidence_batch12.py", "backup_evidence_batch12_inputs.json", "check_backup_batch12.py", "backup_batch12_checks.json", "backup_batch12_unit.xml", *["backup_batch12_" + label + extension for label in ("unit", "mypy", "ruff", "format") for extension in (".log", ".json")], "close_backup_fixture_imports_batch12.py", "backup_batch12_helper_imports.json", "check_backup_collection_batch12.py", "backup_batch12_collection_checks.json", "backup_batch12_collect.log", "backup_batch12_plan.log", "plan_evidence_input_closure_batch8.json", "freeze_backup_evidence_batch12.py", "source_storage_batch11_checkpoint_receipt.json"]
paths = [*(item["path"] for item in inputs["files"]), *(item["path"] for item in helpers["files"]), *evidence_paths, *documents, "reports/stages/recovery/G-F.md", report.relative_to(ROOT).as_posix(), *((RUN / name).relative_to(ROOT).as_posix() for name in run_names), ".gitattributes"]
attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
for name in run_names:
    if Path(name).suffix in {".log", ".xml"}:
        relative = (RUN / name).relative_to(ROOT).as_posix()
        raw = (RUN / name).read_bytes()
        if any(line.endswith((b" ", b"\t")) for line in raw.replace(b"\r\n", b"\n").splitlines()):
            raise RuntimeError("raw trailing whitespace requires review")
        attributes.append(relative + " -text whitespace=trailing-space,space-before-tab,cr-at-eol")
(ROOT / ".gitattributes").write_text("\n".join(attributes) + "\n", encoding="utf-8", newline="\n")
receipts = []
for label, command in [
    ("add", ["git", "add", "--", *paths]),
    ("boundary", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-I", str(RUN / "check_staged_boundary.py")]),
    ("diff", ["git", "diff", "--cached", "--check"]),
    ("commit", ["git", "commit", "-m", "checkpoint G-F: integrate qualified PG backup slice and verified plan evidence; full recovery pending"]),
]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    (RUN / ("backup_evidence_batch12_checkpoint_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"label": label, "command": command, "exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError("checkpoint stopped at " + label)
new_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
(RUN / "backup_evidence_batch12_checkpoint_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": timestamp(), "head_sha": new_head, "baseline_sha": head, "commands": receipts, "paths": paths, "stage_accepted": False, "push": "not_run", "user_file_sha256": protected}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head_sha": new_head, "files": len(paths), "stage_accepted": False, "push": "not_run"}))
