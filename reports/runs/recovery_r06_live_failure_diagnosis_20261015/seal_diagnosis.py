"""Seal report artifacts and external input hashes, without retaining source response text."""

import hashlib
import json
import subprocess
from pathlib import Path

from replay_originals import RUN, current_time

ROOT = RUN.parents[2]
manifest = json.loads((RUN / "official_response_manifest.json").read_text(encoding="utf-8"))
external = []
for entry in manifest:
    for key in ("original_path", "tree_path"):
        if key in entry:
            path = Path(entry[key])
            body = path.read_bytes()
            external.append({"label": entry["label"], "role": key, "path": str(path),
                             "sha256": hashlib.sha256(body).hexdigest(), "size_bytes": len(body)})
files = [path for path in RUN.iterdir() if path.is_file() and path.name != "diagnosis_manifest.json"]
files.append(ROOT / "reports/tasks/R06-live-failure-diagnosis.md")
tracked_diff = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.splitlines()
output = {"sealed_at": current_time(), "source_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215",
          "worktree": str(ROOT), "task_status": "awaiting_review", "diagnosis": "complete",
          "product_implementation": "not_started", "tracked_diff": tracked_diff,
          "external_requests_by_this_agent": 0, "database_calls_by_this_agent": 0,
          "external_originals": external,
          "artifacts": [{"path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "size_bytes": path.stat().st_size} for path in sorted(files)]}
(RUN / "diagnosis_manifest.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(json.dumps({"sealed_at": output["sealed_at"], "artifacts": len(files),
                  "external_original_entries": len(external), "tracked_diff": tracked_diff}))
