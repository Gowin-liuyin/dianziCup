"""Hash explicit task evidence without inspecting any secret storage."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

run_root = Path(__file__).parent
root = Path(__file__).resolve().parents[3]
sha = "5ca56649bc87d7a9a74f4d52595cdd94f50a233a"
tree = subprocess.check_output(["git", "rev-parse", sha + "^{tree}"], cwd=root, text=True).strip()
paths = [root / "reports/tasks/R04-vendor-cursor.md"]
paths.extend(
    path for path in sorted(run_root.iterdir()) if path.is_file() and path.name != "evidence_index.json"
)
pattern = re.compile(rb"(?:sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
files = []
for path in paths:
    body = path.read_bytes()
    assert pattern.search(body) is None
    relative_path = path.relative_to(root).as_posix()
    index_body = subprocess.check_output(["git", "show", f":{relative_path}"], cwd=root)
    files.append(
        {
            "path": relative_path,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "git_index_bytes": len(index_body),
            "git_index_sha256": hashlib.sha256(index_body).hexdigest(),
        }
    )
receipt = {
    "sealed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "source_sha": sha,
    "source_tree": tree,
    "baseline_sha": "7184dc63525ae3e8ea439ec64fc03dfaa629f7a8",
    "report_and_run_files": files,
    "generic_secret_pattern_matches": 0,
    "actual_secret_scan": "author own PG credential scan 0; product credential scan by root integrator pending",
    "independent_review": "not_run; awaiting_review",
    "product_integration": "recorded-source actual PG passed; live not_run",
    "push": "not_run",
    "hash_semantics": "raw working files and Git index bytes recorded separately for CRLF filtering",
}
(run_root / "evidence_index.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({"files": len(files), "bytes": sum(item["bytes"] for item in files)}))
