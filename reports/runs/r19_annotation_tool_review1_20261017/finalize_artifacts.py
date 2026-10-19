"""Bind final sealing diagnostics and every raw artifact after all checks have exited."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[3]
run = Path(__file__).parent
report = root / "reports/reviews/recovery/G-F-R19-annotation-tool-review-1.md"
assert json.loads((run / "staged_diff_check_initial.json").read_text(encoding="utf-8"))["exit_code"] == 2
assert json.loads((run / "staged_diff_check_final.json").read_text(encoding="utf-8"))["exit_code"] == 0
body = report.read_text(encoding="utf-8").replace("任务状态：review complete，建议此源码切片限定通过", "任务状态：源码切片仍awaiting_review，本审查建议限定通过")
body += "\n封存复核：首次staged diff --check因保留原始CRLF报exit2，完整原始日志保留；仅本run的JSON/helper/技能正文允许cr-at-eol后check exit0，其他空白错误仍检查。未禁用源码检查，业务diff仍为空。Linux收尾3秒采用终态核查，非连续峰采样；本轮用实际出生身份和已观测峰核对，不把采样当硬上限证明。行政封存日志不计入69测试或21受控检查分母。\n"
report.write_text(body, encoding="utf-8")
manifest_path = run / "raw_manifest.json"
record = json.loads(manifest_path.read_text(encoding="utf-8"))
rows = []
for path in sorted(run.rglob("*")):
    if path.is_file() and "__pycache__" not in path.parts and path != manifest_path:
        raw = path.read_bytes()
        rows.append({"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
record.update(files=rows, report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
              finalized_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds"),
              sealing_diff_check={"initial_exit": 2, "final_exit": 0})
manifest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"artifacts": len(rows), "report_sha256": record["report_sha256"], "finalized_at": record["finalized_at"]}))
