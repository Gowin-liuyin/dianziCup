"""只登记已分配R01/R02证据路径的显式文件清单；不添加未知目录或用户材料。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
target = RUN / "ga_evidence_explicit_manifest.json"
assert not target.exists()
prefixes = ("reports/runs/recovery_r01_", "reports/runs/recovery_r02_",
            "reports/reviews/recovery/G-A-", "reports/tasks/R01", "reports/tasks/R02")
paths = sorted(path.decode("utf-8") for path in subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT).split(b"\0")
    if path and path.decode("utf-8").startswith(prefixes))
assert paths
files = []
for path in paths:
    source = ROOT / path
    assert source.is_file() and source.stat().st_size <= 10 * 1024 * 1024
    assert not any(part.lower() in {".env", "node_modules", ".venv", "holdout", ".codebase-memory"}
                   for part in source.relative_to(ROOT).parts)
    files.append({"path": path, "captured_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                  "bytes": source.stat().st_size})
target.write_text(json.dumps({"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "selection": "explicit root-owned R01/R02 run/review/task evidence prefixes only",
    "files": files, "count": len(files), "bytes": sum(file["bytes"] for file in files),
    "stage_acceptance_claim": False}, indent=2), encoding="utf-8")
for start in range(0, len(paths), 75):
    subprocess.run(["git", "add", "--", *paths[start:start + 75]], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(json.dumps({"staged_paths": len(paths), "bytes": sum(file["bytes"] for file in files)}))
