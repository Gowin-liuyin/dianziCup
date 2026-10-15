"""Record the final independent CBM index and every new pure entry point's call graph."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = timezone(timedelta(hours=8))
PREFIX = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env",
          "XDG_CACHE_HOME=/tmp/r11-condition-rules-cbm",
          "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
CHECKS = [("cbm_src_index_final", ["index_repository", "--repo-path",
           "/mnt/d/wt/r11-condition-rules/backend/src", "--name", "r11-condition-rules-src", "--mode", "fast"])]
for name in ("conditions.evaluate_condition_tree", "conditions.parse_condition_tree",
             "conditions.condition_digest", "rules.evaluate_rule", "rules.validate_rule",
             "version_ranges.evaluate_version_assertion"):
    for direction in ("inbound", "outbound"):
        CHECKS.append((f"cbm_{name.replace('.', '_')}_{direction}", ["trace_path", "--project",
                      "r11-condition-rules-src", "--function-name",
                      "r11-condition-rules-src.ai_intel.assessment." + name,
                      "--direction", direction, "--depth", "2", "--max-output-tokens", "2000"]))
RECEIPTS = []
for label, arguments in CHECKS:
    started = datetime.now(ZONE).isoformat(timespec="seconds")
    result = subprocess.run([*PREFIX, *arguments], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (RUN / f"{label}.json").write_bytes(result.stdout)
    receipt = dict(label=label, command=[*PREFIX, *arguments], cwd=str(ROOT), started_at=started,
                   completed_at=datetime.now(ZONE).isoformat(timespec="seconds"), exit_code=result.returncode)
    RECEIPTS.append(receipt)
    (RUN / "audit_commands.json").write_text(json.dumps(RECEIPTS, indent=2), encoding="utf-8")
    print(json.dumps(receipt), flush=True)
raise SystemExit(1 if any(item["exit_code"] for item in RECEIPTS) else 0)
