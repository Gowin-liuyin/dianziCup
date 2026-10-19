"""Freeze reviewable materials without changing the raw archived browser evidence."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/tasks/R17-integrated-sbom-browser.md"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
commands = []


def execute(arguments):
    began = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True)
    commands.append({"argv": arguments, "cwd": str(ROOT), "started_at": began, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": result.returncode})
    assert result.returncode == 0
    return result.stdout


modified = execute(["git", "diff", "--name-only"]).decode().splitlines()
assert all(path == "reports/tasks/R17-integrated-sbom-browser.md" or path.startswith("reports/runs/recovery_r17_integrated_sbom_browser_20261016/") for path in modified)
report_hash = hashlib.sha256(REPORT.read_bytes()).hexdigest()
(RUN / "report_write_receipt.json").write_text(json.dumps({"path": str(REPORT), "raw_sha256": report_hash, "observed_at": started, "created_at_filesystem": datetime.fromtimestamp(REPORT.stat().st_ctime, ZoneInfo("Asia/Shanghai")).isoformat(), "modified_at_filesystem": datetime.fromtimestamp(REPORT.stat().st_mtime, ZoneInfo("Asia/Shanghai")).isoformat()}) + "\n", encoding="utf8")
execute(["git", "add", "-f", "--", "reports/tasks/R17-integrated-sbom-browser.md", "reports/runs/recovery_r17_integrated_sbom_browser_20261016", ":(exclude)**/__pycache__/**"])
staged = execute(["git", "diff", "--cached", "--name-only"]).decode().splitlines()
assert all(path == "reports/tasks/R17-integrated-sbom-browser.md" or path.startswith("reports/runs/recovery_r17_integrated_sbom_browser_20261016/") for path in staged)
execute(["git", "commit", "-m", "Record default API SBOM browser validation and raw evidence"])
material = execute(["git", "rev-parse", "HEAD"]).decode().strip()
main_hash = hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
assert main_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipt = {"source": "4a17fa3fb7357a8c2b9d647f62c875958a24a27d", "material": material, "source_report_raw_sha256": report_hash, "started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "commands": commands, "protected_main_buildinfo_sha256": main_hash, "staged_material_files": len(staged)}
(RUN / "finish_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf8")
execute(["git", "add", "-f", "reports/runs/recovery_r17_integrated_sbom_browser_20261016/finish_receipt.json"])
execute(["git", "commit", "-m", "Attach SBOM material commit receipt"])
print(json.dumps({"source": receipt["source"], "material": material, "receipt_commit": execute(["git", "rev-parse", "HEAD"]).decode().strip(), "files": len(staged)}))
