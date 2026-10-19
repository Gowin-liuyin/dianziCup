"""Explicit dependency checkpoint; no stage acceptance or remote push."""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
FILES = ["backend/pyproject.toml", "backend/uv.lock", "docs/decisions/CR-R11_R07_parser_dependencies.md"]


def command(argv):
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=True)
    return result.stdout


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
assert command(["git", "diff", "--cached", "--name-only"]).strip() == b""
command(["git", "diff", "--check", "--", *FILES])
command(["git", "add", "--", *FILES])
staged = command(["git", "diff", "--cached", "--name-only"]).decode().splitlines()
assert set(staged) == set(FILES)
diff = command(["git", "diff", "--cached", "--", *FILES])
assert not re.search(rb"sk-[a-zA-Z0-9]{24,}|BEGIN (?:RSA |OPENSSH )?PRIVATE KEY|apikey\s*[:=]\s*['\"]?[a-zA-Z0-9]{24}", diff)
(RUN / "parser_dependency_staged_diff.log").write_bytes(diff)
with (RUN / "parser_dependency_commit.log").open("xb") as output:
    result = subprocess.run(["git", "commit", "-m", "checkpoint R11/R07 pin SBOM and taxonomy parser dependencies"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=30)
assert result.returncode == 0
head = command(["git", "rev-parse", "HEAD"]).decode().strip()
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "commit_sha": head, "selected_files": FILES, "exit_code": result.returncode, "stage_accepted": False, "push": "not_run", "user_changes": "frontend/tsconfig.tsbuildinfo excluded"}
(RUN / "parser_dependency_commit_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
