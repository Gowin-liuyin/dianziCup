"""Normalize only the review report and bind the retained administrative audit failure."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[3]
run = Path(__file__).parent
report = root / "reports/reviews/recovery/G-F-R19-annotation-tool-review-1.md"
body = report.read_text(encoding="utf-8")
body += "\n额外行政staged字节核验：Git cat-file --batch先通过108份raw artifact哈希断言，随后报告hash断言exit1，因为报告CRLF被Git文本归一为LF；此路径结论见保留的失败stdout/receipt，不计业务测试。只将本报告规范为LF并重新绑定hash。unique marker/PID出生身份查询停止收据roots0/terminated0，未终止任何进程；该行政命令无连续进程树/墙钟采样，不能声称其资源已完整核定，不纳入21份受控检查结论。\n"
report.write_bytes(body.replace("\r\n", "\n").encode("utf-8"))
(run / "staged_blob_audit_initial.stderr.log").write_bytes(b'Traceback (most recent call last):\n  File "<stdin>", line 24, in <module>\nAssertionError\n')
audit = {"observed_tool_exit": 1, "failed_line": 24, "failure": "report_raw_CRLF_vs_Git_LF_hash",
         "staged_raw_artifacts_prior_assertion": 108, "raw_artifact_hash_assertion_passed": True,
         "result_basis": "execution reached line24 after line21 assert not bad", "business_test": False,
         "full_administrative_tree_or_elapsed_seconds": "not_instrumented"}
(run / "staged_blob_audit_initial.json").write_bytes((json.dumps(audit, indent=2) + "\n").encode())
manifest_path = run / "raw_manifest.json"
record = json.loads(manifest_path.read_text(encoding="utf-8"))
rows = []
for path in sorted(run.rglob("*")):
    if path.is_file() and "__pycache__" not in path.parts and path != manifest_path:
        raw = path.read_bytes()
        rows.append({"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
record.update(files=rows, report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
              finalized_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds"),
              report_newline="LF", administrative_stage_audit=audit)
manifest_path.write_bytes((json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(json.dumps({"artifacts": len(rows), "report_sha256": record["report_sha256"], "report_newline": "LF"}))
