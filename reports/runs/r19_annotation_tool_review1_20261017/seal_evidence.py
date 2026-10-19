"""Freeze raw review artifacts while preserving all failed command receipts."""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[3]
run = Path(__file__).parent
report = root / "reports/reviews/recovery/G-F-R19-annotation-tool-review-1.md"
stamp = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds")
retry = json.loads((run / "report_build_retry.command.json").read_text(encoding="utf-8"))
assert retry["exit_code"] == 0 and not retry["failure"] and not retry["remaining_owned_processes"]
summary_path = run / "verification_summary.json"
summary = json.loads(summary_path.read_text(encoding="utf-8"))
summary["commands"].append({**retry, "label": "report_build_retry", "tool_outer_exit": 0})
summary["frozen_at"] = stamp
summary["exit_code_counts"] = {
    str(value): sum(row["exit_code"] == value for row in summary["commands"])
    for value in sorted({row["exit_code"] for row in summary["commands"]})
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
body = report.read_text(encoding="utf-8")
row = f"| report_build_retry | {retry['started_at']} → {retry['ended_at']} | 0 / 0 | — | {retry['windows_peak_count']} / 0 / {retry['windows_peak_count']} | 0 |\n"
body = body.replace("\n69唯一pytest方法", "\n" + row + "\n69唯一pytest方法", 1)
body += f"\n封存时间：{stamp}。本run共{len(summary['commands'])}份受控检查command receipt；child退出计数{json.dumps(summary['exit_code_counts'], ensure_ascii=False)}（包含保留的诊断/helper失败），不是测试通过计数。本报告和raw_manifest绑定最终工件。仅本run局部.gitattributes为日志/XML/patch保留原字节并-diff；JSON/helper源码/stat保留原字节且可diff，不新增检查忽略或公共属性。封存行政脚本不计业务测试，原始tool输出另存其实际工具回执。\n"
report.write_text(body, encoding="utf-8")
result = subprocess.run(["git", "diff", "--quiet", "3b001f288a63a336eb27cd8ef1b985745437cef4", "--", "scripts", "backend", "benchmarks", "contracts", "progress", "docs"], cwd=root, check=False)
assert result.returncode == 0
rows = []
for path in sorted(run.rglob("*")):
    if not path.is_file() or "__pycache__" in path.parts or path.name == "raw_manifest.json":
        continue
    raw = path.read_bytes()
    rows.append({"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
report_raw = report.read_bytes()
record = {"frozen_at": stamp, "source": "982532dd564f3eda5d85a6e252b2cf9ce16f98d1",
          "source_material": "3b001f288a63a336eb27cd8ef1b985745437cef4",
          "files": rows, "report_sha256": hashlib.sha256(report_raw).hexdigest(),
          "business_diff_empty": True, "excluded": ["raw_manifest.json (self)", "ignored __pycache__"]}
(run / "raw_manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(rows), "report_sha256": record["report_sha256"], "frozen_at": stamp,
                  "exit_code_counts": summary["exit_code_counts"], "business_diff_empty": True}))
