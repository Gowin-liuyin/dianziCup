"""为明确拥有的修复证据生成原字节/Git blob双摘要，不扫描产品秘密。"""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
report = ROOT / "reports/tasks/R05-generation-client.md"
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
content = report.read_text(encoding="utf-8")
if "本修复批次写作收据：" not in content:
    report.write_text(content + f"\n\n本修复批次写作收据：{now}，追加本节实际写作结束/最后更新时间/证据截止；本节首字写作开始秒未独立记载，写历史未记录，不根据文件mtime推断。前文首次创建时间保持。本节仅awaiting_review，独立复验结果另由审查者登记。\n", encoding="utf-8")
original = Path("D:/dianzi/reports/runs/recovery_r05_generation_review_1_20261015/test_generation_independent_boundaries_v2.py")
copied = RUN / "reviewer_probe_v2.py"
assert original.read_bytes() == copied.read_bytes()
paths = [report, ROOT / "backend/src/ai_intel/infrastructure/models/generation.py", ROOT / "backend/tests/unit/test_r05_generation_review_fixes.py"]
paths.extend(path for path in RUN.iterdir() if path.is_file() and path.name not in {"evidence_index.json", "static_scan.json"})
subprocess.run(["git", "add", "--", str(report.relative_to(ROOT)), str(RUN.relative_to(ROOT))], cwd=ROOT, check=True)
entries = []
pattern = re.compile(rb"sk-[a-zA-Z0-9_-]{24,}")
matches = []
for path in sorted(paths):
    relative = path.relative_to(ROOT).as_posix()
    captured = path.read_bytes()
    blob = subprocess.check_output(["git", "show", ":" + relative], cwd=ROOT)
    entries.append({"path": relative, "captured_sha256": hashlib.sha256(captured).hexdigest(), "captured_size_bytes": len(captured), "git_blob_sha256": hashlib.sha256(blob).hexdigest(), "git_blob_size_bytes": len(blob)})
    if pattern.search(captured):
        matches.append(relative)
(RUN / "evidence_index.json").write_text(json.dumps({"created_at": now, "code_sha": "691a20db07d6594faf35c2cb1de738edcca6c617", "copied_reviewer_probe_matches_original": True, "entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
(RUN / "static_scan.json").write_text(json.dumps({"created_at": now, "files": len(paths), "method": "static long sk-token pattern only; no actual key read or fragment scan", "matched_paths": matches, "actual_key_scan": "not_run; parent integration owns secret full/fragment scan"}, indent=2), encoding="utf-8")
assert not matches
print(json.dumps({"time": now, "files": len(paths), "static_matches": len(matches)}))
