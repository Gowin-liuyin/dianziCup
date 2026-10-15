"""Seal the initial review artifacts without changing the business checkout."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

run = Path(__file__).resolve().parent
report = Path("D:/dianzi/reports/reviews/recovery/G-B-R05-grounded-answer-review-1.md")
checkout = Path("C:/Users/yinha/.codex/worktrees/r05-grounded-answer-independent-review/dianzi")
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
status = subprocess.check_output(["git", "status", "--porcelain"], cwd=checkout, text=True)
assert sha == "c1804d0a38cd4e451b801f1ec88df9c3c47629e0"
assert status == ""
missing_links = [target for target in re.findall(r"\]\((D:/[^)]+)\)", report.read_text(encoding="utf-8")) if not Path(target).is_file()]
assert not missing_links, missing_links
files = [report, *(file for file in run.iterdir() if file.is_file() and file.name not in {"seal_manifest.json", "seal.log", "seal.receipt.json"})]
manifest = {
    "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "code_sha": sha,
    "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=checkout, text=True).strip(),
    "checkout": str(checkout),
    "git_status_porcelain": status,
    "report_local_link_check": "passed",
    "files": [{"path": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "bytes": file.stat().st_size} for file in sorted(files)],
}
(run / "seal_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"code_sha": sha, "clean": status == "", "links": "passed", "sealed_files": len(files)}, ensure_ascii=False))
