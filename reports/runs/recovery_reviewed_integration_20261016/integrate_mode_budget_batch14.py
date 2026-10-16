"""Combine frozen disjoint read-mode and source-report fixes on the current root baseline."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "bc089809c03472582f6256b495a6f9a2a308a5d2"
sources = (
    "ff972ebb7fe1183950cf83cb20107124f4b0995b",
    "db922460dbc6b45284201be7c5cbefe35de07427",
)
manifest = []
for source in sources:
    paths = subprocess.check_output(["git", "diff", "--name-only", BASELINE, source], cwd=ROOT, text=True).splitlines()
    for relative in paths:
        previous = subprocess.run(["git", "show", BASELINE + ":" + relative], cwd=ROOT, capture_output=True)
        if previous.returncode == 0:
            subprocess.run(["git", "diff", "--exit-code", "--", relative], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
            assert subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT) == previous.stdout
        else:
            assert not (ROOT / relative).exists()
        data = subprocess.check_output(["git", "show", source + ":" + relative], cwd=ROOT)
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest.append({"path": relative, "source_sha": source, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
(RUN / "mode_budget_batch14_inputs.json").write_text(json.dumps({"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "baseline_sha": BASELINE, "files": manifest, "whole_task_accepted": False, "root_validation": "not_run"}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"frozen_files_imported": len(manifest), "unique_paths": len({item["path"] for item in manifest})}))
