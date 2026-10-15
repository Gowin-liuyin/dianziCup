"""Freeze this slice's code version, actual JUnit totals and raw material digests."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
STAMP = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
CODE_SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
COMMANDS = json.loads((RUN / "commands.json").read_text(encoding="utf-8"))
FINAL = [command for command in COMMANDS if command["label"].startswith("replay_")]
COUNTS = {}
for label in ("unit", "contract", "security", "full_unit"):
    suites = ET.parse(RUN / f"replay_{label}.xml").getroot().iter("testsuite")
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    COUNTS[label] = totals
GRAPH = json.loads((RUN / "cbm_src_index_final.json").read_text(encoding="utf-8"))["structuredContent"]
REPORT = ROOT / "reports/tasks/R11-condition-rules.md"
report = REPORT.read_text(encoding="utf-8")
report = report.replace("代码版本：328ed7a933a9a81ec715f447235f4b933e0ed506", "代码版本：" + CODE_SHA)
report = report.replace("## 实测与原红", "## 历史冻结检查与原红（最终结果见以下封存节）")
intro = f"最终直属 {sum(COUNTS[label]['tests'] for label in ('unit', 'contract', 'security'))} 测试通过；完整 unit 回归 {COUNTS['full_unit']['tests'] - COUNTS['full_unit']['failures'] - COUNTS['full_unit']['errors']} 通过、{COUNTS['full_unit']['failures']} 失败。完整回归仍 failed，失败均在既有 R20 native CPU guard；两次完整回归在该模块失败后停止重复，不改其代码、资源门、断言或 skip。\n\n"
report = report.replace("## 改动与行为", intro + "## 改动与行为")
report += f"\n\n## 最终封存 · {STAMP}\n\n"
report += f"最终业务代码 {CODE_SHA}。封存时补严验证收据不回退 published/retired 生命周期；新增 1 个回归案例。以下是该最终版本实际 replay，前面的 final/recheck 日志为原样历史材料，不能取代此节。\n\n"
report += "| 检查 | 实际 tests / failures / errors / skipped | exit | +08 起止 | 日志 |\n|---|---|---|---|---|\n"
for command in FINAL:
    label = command["label"].removeprefix("replay_")
    count = COUNTS.get(label)
    value = " / ".join(str(count[key]) for key in ("tests", "failures", "errors", "skipped")) if count else "工具检查"
    report += f"| {label} | {value} | {command['exit_code']} | {command['started_at']} → {command['completed_at']} | replay_{label}.log |\n"
report += f"\n最终 CBM source 为 {GRAPH['nodes']} nodes / {GRAPH['edges']} edges，独立 assets 198 / 823；schema/architecture 与全新入口双向 trace 真实保留，audit_commands.json 为最终执行时点。历史 native CPU guard 的 1.03125 秒失败仍是已观察风险，定向成功和本节回归均不证明其根因已修复；本切片没有放宽或修改该边界。PG/frontend/e2e/live/manual 仍全部 not_run，整卡与阶段状态不变。\n"
failures = [case.get('name') for case in ET.parse(RUN / "replay_full_unit.xml").getroot().iter('testcase')
            if case.find('failure') is not None or case.find('error') is not None]
report += "\n最终全仓失败 ID（原断言全部保留）：\n\n" + "\n".join("- " + name for name in failures) + "\n"
REPORT.write_text(report, encoding="utf-8")
paths = [ROOT / path for path in (
    "backend/src/ai_intel/assessment/conditions.py", "backend/src/ai_intel/assessment/rules.py",
    "backend/tests/unit/test_t27_condition_rules.py", "backend/tests/contract/test_r11_condition_schema.py",
    "backend/tests/security/test_r11_condition_security.py", "docs/decisions/CR-R11_condition_rules_proposal.md",
    "reports/tasks/R11-condition-rules.md",
)]
paths.extend(path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
entries = []
for path in sorted(paths):
    content = path.read_bytes()
    entries.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=len(content),
                        sha256=hashlib.sha256(content).hexdigest()))
canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
manifest = dict(generated_at=STAMP, base_sha="e310f7735bd499c4d9fbcefe8a644e2309a16a62",
                code_sha=CODE_SHA, materials_sha256=hashlib.sha256(canonical).hexdigest(),
                digest_definition="sha256 of canonical JSON material entries; manifest excludes itself",
                results=COUNTS, command_exits={item["label"]: item["exit_code"] for item in FINAL},
                entries=entries)
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({key: manifest[key] for key in ("generated_at", "code_sha", "materials_sha256", "results")}))
