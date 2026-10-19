"""Summarize immutable local receipts without converting retained failures into passes."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parents[3]
run = Path(__file__).parent
report = root / "reports/reviews/recovery/G-F-R19-annotation-tool-review-1.md"
counts = {}
for name in ("unit_writer", "process_interruption", "contract_labels", "security_cli", "security_registry"):
    suite = ET.parse(run / f"{name}.xml").getroot()
    cases = list(suite.iter("testcase"))
    counts[name] = {"methods": len(cases), "failures": len(list(suite.iter("failure"))),
                    "errors": len(list(suite.iter("error"))), "skipped": len(list(suite.iter("skipped"))),
                    "ids": [case.attrib["classname"] + "::" + case.attrib["name"] for case in cases]}
all_ids = [test_id for value in counts.values() for test_id in value["ids"]]
assert len(all_ids) == len(set(all_ids)) == 69
assert not any(value[key] for value in counts.values() for key in ("failures", "errors", "skipped"))
commands = []
for path in run.glob("*.command.json"):
    record = json.loads(path.read_text(encoding="utf-8"))
    record["label"] = path.name.removesuffix(".command.json")
    record["tool_outer_exit"] = int(bool(record["exit_code"] or record["failure"] or record["remaining_owned_processes"] or record["remaining_owned_linux_processes"]))
    commands.append(record)
commands.sort(key=lambda row: row["started_at"])
inventory = json.loads((run / "input_inventory.json").read_text(encoding="utf-8"))
cbm_exit = json.loads((run / "cbm_identity_exit.json").read_text(encoding="utf-8"))
cbm_index = json.loads((run / "cbm_source_index.stdout.log").read_text(encoding="utf-8"))["structuredContent"]
snapshot = run / "cbm_source/scripts/annotation/prepare.py"
assert snapshot.read_bytes() == (root / "scripts/annotation/prepare.py").read_bytes()
summary = {"commands": commands, "pytest": counts, "unique_methods": len(set(all_ids)),
           "plan_matches": inventory["plan_closure_matches"], "plan_total": inventory["plan_closure_total"],
           "cbm": cbm_index, "cbm_exit": cbm_exit,
           "cbm_source_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
           "business_source_modified": False, "human_gold_count": 0, "formal_denominator": None,
           "verification": {"unit": "passed", "contract": "passed", "integration": "not_run",
                            "security": "passed", "frontend": "not_run", "e2e": "not_run",
                            "live": "not_run", "manual": "not_run"}}
(run / "verification_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
table = ["| command | 真实开始 → 结束 +08:00 | child / tool exit | 方法数 | Win峰 / Linux峰 / 保守和 | 自有残留 |",
         "|---|---|---:|---:|---:|---:|"]
for row in commands:
    table.append(f"| {row['label']} | {row['started_at']} → {row['ended_at']} | {row['exit_code']} / {row['tool_outer_exit']} | {counts.get(row['label'], {}).get('methods', '—')} | {row['windows_peak_count']} / {row['linux_peak_count']} / {row['conservative_windows_plus_linux_peak_sum']} | {len(row['remaining_owned_processes']) + len(row['remaining_owned_linux_processes'])} |")
body = """What this change does: It publishes complete annotation JSON without replacing an existing file. It closes owned file descriptors when metadata or stream creation fails, and leaves files with an unknown owner for manual validation.

Looks good. Ship the three-file source slice within the limits below. No new reproducible Must fix or Should fix was found. This verdict does not accept all R19/T46 or G-F.

## R19 / G-F · 新非作者独立审查

任务状态：review complete，建议此源码切片限定通过；整 R19/T46 保持 partial/awaiting_human_label，G-F未通过。没有改共享状态或accepted，没有push。审查WT `D:/wt/r19-annotation-tool-review-1`，分支 `codex/r19-annotation-tool-review-1`；起点材料 `3b001f288a63a336eb27cd8ef1b985745437cef4`，其直接父源码 `982532dd564f3eda5d85a6e252b2cf9ce16f98d1`，基线 `9726363e0d9b33467ba40a06a8bde9548b46bccf`；Root派单快照 `bc089809c03472582f6256b495a6f9a2a308a5d2`。

实际修改范围经rg与Git确认是 `scripts/annotation/prepare.py`、`scripts/annotation/tests/test_crash_recovery.py`、`scripts/annotation/tests/test_fd_metadata_error.py`，不是newtest前缀。685新增/7删除；source.diff.patch SHA256 `266c4278d4f6263dafe3d987d8241e648525c0df40941bb82ef9e7b867643c8e`。本review只新增本报告与本run，没有业务、公共合同、认证、状态、金标、阈值或分母修改。

已读AGENTS、执行地图、R19恢复卡/manifest、T46卡、评测合同、progress state/交接、冻结作者报告及Ponytail 5.3.1 review正文。R19工具可在R04后独立开始，正式冻结仍需要R07–R16完整覆盖和两位真人独立核验/分歧裁决。`input_inventory.json`绑定17份合同/源码/材料及严格重复JSON键解析、LF等价。当前冻结state中T46仍pending/not_started；本报告不替主控改写它。

## 审查路径和判断

输入是schema/hash/time/来源/许可/家族split已校验的candidate bundle，以及可选仓外标签。输出是UTF-8/LF完整JSON，CLI成功exit0，拒绝固定错误exit2；gold恒0，formal status not_run、分子分母null。main:551是生产write_new唯一直接调用；rg原始调用日志与源码对照见本run。read_document只将严格JSON loader移为延迟导入，未换解析器。

prepare.py:359拒输出父路径symlink/junction；393–438在同目录mkstemp写完、flush/fsync后检查父目录与临时文件身份，使用no-clobber hard link发布；381–391仅清理证明是自身创建的regular临时文件。405–410 Path/fstat/fdopen异常关闭自有FD；未获身份时保留空pending且失败，不将残留当成功。文件fsync失败不发布；发布后目录sync/清理失败保留完整final且报告错误。unsupported hard link失败关闭，不退化成非原子写；重放拒OUTPUT_EXISTS。

本轮29个writer/FD/中断方法覆盖上述行为、foreign保留、身份替换、并发先成功者、partial/prepublish/postpublish。3个ProcessInterruptionTests实际启动并kill本机Python子进程，在既定屏障验证partial无final、完整pending经原CLIvalidate/reexport、已发布final不被重放覆盖。它们是Windows TerminateProcess恢复测试，不是Linux SIGKILL、真实断电或远程文件系统耐久证明。

25合同与15原CLI方法复跑家族别名/跨字段/transitive split隔离、真实与合成分开、许可/来源/时间缺失、candidate/annotation hash、重复JSON键、0/1标签拒孤儿review、双人当前label hashes、独立身份核验、独立裁决、修订理由/影响/重测、holdout prompt/index/image与答案泄漏拒绝、注册新WT和resolved junction仓内落点拒绝。所有标签为显式synthetic fixtures；不读取真实holdout答案或用户人工资料。

Ponytail判断：正常负载按一个操作员启动本地准备CLI、允许测试中的并发导出来审。发布/FD核心可单独测，IO和标签判断保持分离；没有引入依赖、通用抽象、fallback伪成功或新的事实权威。辅助静态子审仅一次只读读取且无shell后续、编辑或测试；其结论只辅助我审读，不替代本轮独立复跑。已记载的同权限恶意父目录/临时路径并发替换TOCTOU不被扩大为支持能力，也不制造无证的新阻断。

## 实际执行

cwd均本review WT；入口为本run/run_step.py，固定base CPython 3.12.13，PYTHONPATH仅本WT及既有锁定venv site-packages，APP_ENV=test/DATA_MODE=fixture。凭据环境过滤；无数据库、浏览器、DPAPI、模型、外部网络或付费API。所有受控检查≤60秒，普通cap10；Root明确独占允许CBM cap16，未与自己的tests/CLI并行。每次完整argv、起止+08时钟、child退出、Windows出生身份全树/控制链、Linux自身+Relay+SessionLeader完整祖先/后代、残留和当时helper/source hash在command.json。child非零被PowerShell工具外层折为1，表内区分两层。行政读文件/worktree操作不冒充测试，也不由下表声称其全任务瞬时合计已采样。

""" + "\n".join(table) + """

69唯一pytest方法全部通过，fail/error/skip均0；29unit、25contract、15标注边界security。它们是fixture行为分母，不是正式评分分母。`-o addopts=`只沿冻结annotation入口禁生产覆盖率附加参数，未删题/改oracle/改金标/阈值/skip。原完整测试类分组各自≤60s，无本轮测试超时。原始stdout/stderr/JUnit及verification_summary保留。

Ruff依据冻结backend配置三文件exit0；annotation默认88 format三文件exit0。定向mypy按冻结backend配置、explicit-package-bases及本轮独立cache source+FD exit0。首次我未用正确namespace配置，source重复module名exit2；该诊断失败保留，不算源类型通过。完整annotation mypy真实exit1，仍 `test_prepare.py:224 Value of type object is not indexable`；未修旧测试，不能称完整类型检查通过。首次报告helper漏指定UTF-8读取，Windows默认GBK解码inventory失败exit1；只修自身helper编码后重跑，失败日志保留，非业务测试失败。

## CBM实测与资源

固定官方WSL portable `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`；本轮独立cache `/tmp/dianzi-cbm-r19-annotation-review1-20261017`。真实cli --help与get_graph_schema --help留raw；仅将prepare.py原字节复制为source snapshot并哈希校验，不索引测试fixture、答案、人工包或用户资料。最终直接索引snapshot的annotation目录：41nodes/137edges，skipped/partial/unusable/not-indexed均0；schema有72CALLS并显示已索引单File。用全repo rg及真实源码补校入口，不把源码快照图当整仓调用闭包。architecture/trace未运行，not_run。

第一次索引snapshot上层目录被CBM默认排除scripts，只得2nodes/1edge骨架，不能称代码已索引；第一次schema误用--repo实际exit1，保留。按实际help改--project后schema底层与控制器exit0；未再调用网络或其他服务。Linux结束等待3秒后核自身后代为0，再独立以UNC/proc逐项复核所有已观测PID+birth，`cbm_identity_exit.json`剩余0/unknown0、检查exit0；WindowsWsl hosts等待且出生树残留0。各CBM峰值见表，以Windows峰+Linux峰的保守和核≤16，非数学硬上限证明。help/schema/index各自日志完整；索引/cache生命周期不改写作者旧CBM即时残留失败。

## 必须保留的历史失败与未查项

旧094cd3c3524f59337b80751cb1ecba486198579b的Ship只关闭M01 FD生命周期，不能替代本新完整整合审查。旧原首审cap4进程树峰10违规保持；作者原合并CLI60s超时/exit124/无JUnit，不由12个点推算通过；原117/115红、原format红和原mypy224红保持。作者CBM跨系统PermissionError、即时残留/receipt缺口保留，当前独立证据不把旧失败重写为成功。

本轮独立plan raw核对仍10/23匹配，13缺失/不匹配列input_inventory；没有替换输入、造空材料或静默修复。verify_plan全量、历史plan47 not_run。整R19候选规模、R07–R16覆盖、正式冻结、真人身份和冻结签字均不在本源码切片中完成。空two_rater_evidence_packet_template不是标注结果；gold0、正式分母null不变。

| 类别 | 本切片验证 | 实际限制 |
|---|---|---|
| unit | passed，29 | 本地synthetic filesystem/Windows kill；非断电 |
| contract | passed，25 | 候选/标签/家族/裁决fixture，非真人金标 |
| integration | not_run | 未启动PG/Redis/index产品服务 |
| security | passed，15 | 只标注CLI文件边界/holdout fixture；全产品security not_run |
| frontend | not_run | 无前端改动/浏览器 |
| e2e | not_run | 无产品全链路验收 |
| live | not_run | 无授权真实模型/来源/FOFA；正式live仍有资源缺口 |
| manual | not_run | 0真人label/0gold/无签字 |

Linux SIGKILL/断电、Windows目录断电耐久、NFS/FAT/网络卷、实际人工数据与最终holdout均not_run；不据本机kill替代。D1支持冻结源码+原始日志+hash可复核；A1/P2/P3仅有工具/隔离/裁决准备证据，不能从69个fixture断言推断准确率、召回、性能或评分优秀。产品model/API付费调用0，编程Agent费用unknown。

交付文件仅本报告、本run日志/XML/JSON/source patch/源码快照及审查helper；没有新增忽略规则。下一步由Root核本review冻结SHA后决定集成；按变更流程补齐旧类型与13项plan原件，再由两位实际人工和独立裁决者建立完整候选/标签/冻结签字，最终依原T46与G-F门验收。

Verdict: Ship this source slice within the stated limits. Not checked: whole R19/T46/G-F acceptance, real human gold, formal evaluation, product live/e2e, power-loss durability and complete historical plan evidence.
"""
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(body, encoding="utf-8")
print(json.dumps({"unique_methods": 69, "report": str(report), "commands": len(commands),
                  "ordinary_peak": max(row["windows_peak_count"] for row in commands if row["owned_process_cap"] == 10),
                  "cbm_conservative_peak": max(row["conservative_windows_plus_linux_peak_sum"] for row in commands if row["owned_process_cap"] == 16)}))
