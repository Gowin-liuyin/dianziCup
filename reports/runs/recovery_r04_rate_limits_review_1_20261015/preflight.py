"""冻结候选、规范及独立依赖的可复核收据，不读取秘密或用户材料。"""

from datetime import datetime
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
WT = Path("C:/Users/yinha/.codex/worktrees/r04-rate-limits-independent-review-1/dianzi")
BASE = "3ab23574298d872350587f273c739397e114c2d9"
paths = ["AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/11_full_delivery_recovery_20261014.md",
         "docs/plan/12_recovery_task_cards_20261014.md", "docs/plan/05_api_and_tool_contracts.md",
         "docs/tasks/T08_network_and_sources.md", "docs/tasks/T12_vendor_blog_connectors.md",
         "docs/tasks/T16_incremental_monitoring.md", "docs/decisions/CR-R04-R04_source_jobs.md",
         "progress/task_state.json", "progress/context_handoff.md", "backend/uv.lock", "backend/pyproject.toml"]
changed = subprocess.run(["git", "diff", "--name-only", BASE, "HEAD"], cwd=WT, capture_output=True, text=True, check=True).stdout.splitlines()
revision = subprocess.run(["git", "rev-parse", "HEAD", "HEAD^{tree}"], cwd=WT, capture_output=True, text=True, check=True).stdout.splitlines()
status = subprocess.run(["git", "status", "--short"], cwd=WT, capture_output=True, text=True, check=True).stdout
diff_check = subprocess.run(["git", "diff", "--check", BASE, "HEAD"], cwd=WT, capture_output=True, text=True)
import ai_intel.ingestion.source_jobs
import ai_intel.infrastructure.http_transport
versions = {name: importlib.metadata.version(name) for name in ["pytest", "pytest-cov", "ruff", "mypy", "SQLAlchemy", "psycopg"]}
coverage = ElementTree.parse(RUN / "full_unit_coverage.xml").getroot().attrib
receipt = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
           "worktree": str(WT), "base": BASE, "sha": revision[0], "tree": revision[1],
           "branch": "codex/r04-rate-limits-independent-review-1", "status": status,
           "changed_files": changed, "hashes": {path: sha256((WT / path).read_bytes()).hexdigest() for path in paths + changed},
           "python": sys.executable, "python_version": sys.version, "versions": versions,
           "source_jobs_import": ai_intel.ingestion.source_jobs.__file__,
           "http_transport_import": ai_intel.infrastructure.http_transport.__file__,
           "diff_check": {"exit_code": diff_check.returncode, "output": diff_check.stdout + diff_check.stderr},
           "coverage": coverage}
(RUN / "preflight.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
for log in RUN.glob("*.log"):
    import re
    value = log.read_text(encoding="utf-8")
    value = re.sub(r"postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^\s)<>'\"]+", "[redacted isolated test connection]", value)
    log.write_text(value, encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False))
