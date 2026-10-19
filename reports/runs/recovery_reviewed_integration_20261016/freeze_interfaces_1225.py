"""Freeze explicitly owned interfaces and isolated dependency evidence without pushing."""

import hashlib
import json
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_reviewed_integration_20261016"
PROTECTED = ROOT / "frontend/tsconfig.tsbuildinfo"
EXPECTED = "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
DOCUMENTS = [
    "docs/decisions/CR-R14_langgraph_persistence_interfaces.md",
    "docs/decisions/CR-R15_persistent_subscription_interfaces.md",
    "docs/decisions/CR-R12_projection_terminal_constraint_budget.md",
    "docs/decisions/CR-R06_preheld_emergency_cleanup_scope.md",
    "docs/decisions/CR-R18_durable_actor_reference.md",
]
FILES = DOCUMENTS + [
    "backend/pyproject.toml", "backend/uv.lock",
    "reports/runs/recovery_r14_langgraph_dependencies_20261016/dependency_receipt.json",
    "reports/runs/recovery_r14_langgraph_dependencies_20261016/isolated_sync.stdout.log",
    "reports/runs/recovery_r14_langgraph_dependencies_20261016/isolated_sync.stderr.log",
]


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode("utf-8")


assert hashlib.sha256(PROTECTED.read_bytes()).hexdigest() == EXPECTED
assert not git("diff", "--cached", "--name-only").strip()
old = tomllib.loads(git("show", "6878863202709dbe7b1ea77225c191bf1835be40:backend/uv.lock"))
new = tomllib.loads((ROOT / "backend/uv.lock").read_text(encoding="utf-8-sig"))
old_versions = {row["name"]: row["version"] for row in old["package"]}
new_versions = {row["name"]: row["version"] for row in new["package"]}
assert all(new_versions[name] == version for name, version in old_versions.items())
assert len(new_versions) - len(old_versions) == 20
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
for name in DOCUMENTS:
    path = ROOT / name
    body = path.read_text(encoding="utf-8")
    body = body.replace("本次写作结束时间：2026-10-16T12:25:25+08:00", "本次写作结束时间：" + ended)
    body = body.replace("最后更新时间：2026-10-16T12:25:25+08:00", "最后更新时间：" + ended)
    path.write_text(body, encoding="utf-8", newline="\n")
git("add", "--", *FILES)
assert set(git("diff", "--cached", "--name-only").splitlines()) == set(FILES)
staged = git("diff", "--cached", "--", *FILES)
for forbidden in ("-----BEGIN PRIVATE KEY-----", "postgresql://", "postgresql+psycopg://", "sk-"):
    assert forbidden not in staged
check = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, capture_output=True)
(RUN / "interface_checkpoint_staged_check.log").write_bytes(check.stdout + check.stderr)
assert check.returncode == 0
before = git("rev-parse", "HEAD").strip()
commit = subprocess.run(["git", "commit", "-m", "checkpoint G-D/G-E: freeze persistent workflow and subscription interfaces"], cwd=ROOT, capture_output=True)
(RUN / "interface_checkpoint_commit.log").write_bytes(commit.stdout + commit.stderr)
assert commit.returncode == 0
after = git("rev-parse", "HEAD").strip()
assert hashlib.sha256(PROTECTED.read_bytes()).hexdigest() == EXPECTED
receipt = {"created_at": ended, "before": before, "after": after, "files": FILES,
           "git_exit_code": commit.returncode, "pushed": False, "phase_passed": False,
           "user_file_sha256": EXPECTED, "old_package_count": len(old_versions),
           "new_package_count": len(new_versions), "existing_versions_unchanged": True}
(RUN / "interface_checkpoint_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
