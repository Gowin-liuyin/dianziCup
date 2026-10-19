"""Push only the reviewed recovery branch and record the verified remote receipt."""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BRANCH = "codex/full-delivery-recovery"
ORIGIN = "https://github.com/Gowin-liuyin/dianziCup.git"
HEAD = "c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7"
BASE = "fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4"
os.environ["GIT_TERMINAL_PROMPT"] = "0"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


assert git("branch", "--show-current") == BRANCH
assert git("rev-parse", "HEAD") == HEAD
assert git("remote", "get-url", "origin") == ORIGIN
assert git("remote", "get-url", "--push", "origin") == ORIGIN
assert not git("diff", "--cached", "--name-only")
for directory in ("backend", "frontend", "contracts", "scripts", "infra", "config"):
    assert git("rev-parse", f"{HEAD}:{directory}") == git("rev-parse", f"1927eeb:{directory}")
for path, expected in (
    ("reports/reviews/recovery/G-B-checkpoint-review-1.md", "50cbd2152686af6d436514208ddd3f5fcd7116cb86b7729cfc0050974594ea32"),
    ("reports/reviews/recovery/G-B-checkpoint-registration-review-1.md", "678dc0bdde71248600088f795ca44c8eb93b4e692b379371f3994fc025ec510a"),
):
    assert hashlib.sha256(subprocess.check_output(["git", "show", f"{HEAD}:{path}"], cwd=ROOT)).hexdigest() == expected
tree = subprocess.check_output(["git", "ls-tree", "-rlz", HEAD], cwd=ROOT).split(b"\0")
oversized = []
for entry in tree:
    if not entry:
        continue
    metadata, filename = entry.split(b"\t", 1)
    size = metadata.split()[-1]
    if size != b"-" and int(size) > 50 * 1024 * 1024:
        oversized.append(filename.decode())
assert not oversized, "large committed file requires explicit review"
changed = git("diff", "--name-only", f"{BASE}..{HEAD}").splitlines()
assert not any(any(piece in path.lower().split("/") for piece in (".venv", "node_modules", ".env", "holdout")) or "keys-and-usage" in path.lower() for path in changed)
scans = ["gb_final_registration_secret_scan.json", "gb_final_report_bytes_secret_scan_recheck.json", "gb_registration_review_final_secret_scan.json"]
for filename in scans:
    receipt = json.loads((ROOT / "reports/runs/recovery_r01_controller_20261014" / filename).read_text(encoding="utf-8"))
    assert receipt["matches"] == 0 and receipt["checked_secret_references"] == 9
start = now()
commands = []


def execute(label: str, argv: list[str]) -> int:
    began = now()
    with (RUN / (label + ".log")).open("wb") as stream:
        result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
    commands.append({"argv": argv, "cwd": str(ROOT), "started_at": began, "ended_at": now(), "exit_code": result.returncode, "log": f"reports/runs/recovery_r05_controller_20261015/{label}.log"})
    return result.returncode


receipt = {"stage": "G-B", "started_at": start, "branch": BRANCH, "reviewed_code_sha": "1927eeb00a7e0c1335f76340b0382f46102f08f2", "reviewed_document_sha": "1ca2ea34c224e23776431fa6eac5fe6549d8c65f", "local_sha": HEAD, "origin": ORIGIN, "status": "not_pushed", "secret_scan_refs": scans, "changed_paths_checked": len(changed), "large_files_over_50_mib": oversized}
try:
    assert execute("gb_push_fetch", ["git", "fetch", "origin"]) == 0
    remote_before = git("ls-remote", "--heads", "origin", "refs/heads/" + BRANCH).split()[0]
    receipt["remote_before_sha"] = remote_before
    assert remote_before == BASE, "remote branch changed; safe integration review required"
    assert execute("gb_push_ancestry", ["git", "merge-base", "--is-ancestor", remote_before, HEAD]) == 0
    assert git("remote", "get-url", "origin") == ORIGIN
    code = execute("gb_push_command", ["git", "push", "origin", "HEAD:refs/heads/" + BRANCH])
    receipt["exit_code"] = code
    assert code == 0, "push failed; preserve local commit and classify recorded failure"
    remote_after = git("ls-remote", "--heads", "origin", "refs/heads/" + BRANCH).split()[0]
    receipt["remote_sha"] = remote_after
    assert remote_after == HEAD, "remote verification mismatch"
    receipt["status"] = "pushed_and_remote_verified"
finally:
    receipt["ended_at"] = now()
    receipt["commands"] = commands
    path = ROOT / "reports/push/recovery_push_log.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    (RUN / "gb_push_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("stage", "status", "branch", "local_sha", "remote_sha", "started_at", "ended_at", "exit_code")}, ensure_ascii=False))
