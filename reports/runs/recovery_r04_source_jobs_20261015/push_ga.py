"""仅推送授权集成分支，先核远端和祖先关系，成功由远端SHA核对确认。"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent / "push_ga"
RUN.mkdir(exist_ok=False)
CLOCK = ZoneInfo("Asia/Shanghai")
BRANCH = "codex/full-delivery-recovery"
EXPECTED = "fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4"
ORIGIN = "https://github.com/Gowin-liuyin/dianziCup.git"
environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never",
                   GIT_TRACE="0", GIT_TRACE_CURL="0", GIT_CURL_VERBOSE="0")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def execute(label, arguments, *, timeout=60, allowed=(0,)):
    started = now()
    result = subprocess.run(["git", *arguments], cwd=ROOT, env=environment,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    (RUN / (label + ".json")).write_text(json.dumps({"started_at": started,
        "ended_at": now(), "command": ["git", *arguments], "cwd": str(ROOT),
        "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, indent=2))
    if result.returncode not in allowed:
        raise RuntimeError("git command failed: " + label)
    return result.stdout.strip()


record = {"stage": "G-A", "started_at": now(), "branch": BRANCH,
    "reviewed_code_sha": "b27a79d9bce769564e86034a164010b3fd176080",
    "reviewed_document_sha": "a8362baa7ea042075ca53125495a080d86274bae",
    "local_sha": EXPECTED, "origin": ORIGIN, "status": "not_pushed"}
try:
    assert execute("origin", ["remote", "get-url", "origin"]) == ORIGIN
    assert execute("branch", ["branch", "--show-current"]) == BRANCH
    assert execute("head", ["rev-parse", "HEAD"]) == EXPECTED
    assert execute("staged", ["diff", "--cached", "--name-only"]) == ""
    execute("fetch", ["fetch", "--no-tags", "origin"])
    remote_head = execute("remote_head", ["ls-remote", "--symref", "origin", "HEAD"])
    default_refs = [line.split()[1] for line in remote_head.splitlines() if line.startswith("ref:")]
    assert len(default_refs) == 1 and default_refs[0].startswith("refs/heads/")
    default_name = default_refs[0][len("refs/heads/"):]
    execute("default_ancestor", ["merge-base", "--is-ancestor", "origin/" + default_name, EXPECTED])
    existing = execute("branch_before", ["ls-remote", "--heads", "origin", "refs/heads/" + BRANCH])
    if existing:
        remote_sha = existing.split()[0]
        assert re.fullmatch("[0-9a-f]{40}", remote_sha)
        execute("target_ancestor", ["merge-base", "--is-ancestor", remote_sha, EXPECTED])
    execute("push", ["push", "--porcelain", "origin",
        "refs/heads/" + BRANCH + ":refs/heads/" + BRANCH])
    remote = execute("remote_verification", ["ls-remote", "--heads", "origin", "refs/heads/" + BRANCH])
    assert remote.split()[0] == EXPECTED
    record.update(status="pushed_and_remote_verified", remote_sha=remote.split()[0], exit_code=0)
except Exception as error:
    record.update(status="not_verified", error_type=type(error).__name__, exit_code=1,
        detail="Inspect bounded raw command receipts; no force/rebase/remote substitution attempted")
record["ended_at"] = now()
(RUN / "result.json").write_text(json.dumps(record, indent=2))
ledger = ROOT / "reports/push/recovery_push_log.jsonl"
ledger.parent.mkdir(parents=True, exist_ok=True)
with ledger.open("a", encoding="utf-8") as target:
    target.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record), flush=True)
raise SystemExit(record["exit_code"])
