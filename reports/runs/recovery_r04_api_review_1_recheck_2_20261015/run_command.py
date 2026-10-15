"""Independent fixed-snapshot review command recorder; no product secrets are read."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WINDOWS_ROOT = "C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1-recheck-2/dianzi"
FROZEN_SHA = "7af91b3796ef14a545ba2413acd8254a7f8a095a"


def timestamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def git_command():
    if os.name == "nt":
        return ["git", "-C", WINDOWS_ROOT]
    return ["/mnt/c/Program Files/Git/cmd/git.exe", "-C", WINDOWS_ROOT]


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--pg", action="store_true")
    parser.add_argument("--cache", default="")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if (RUN / (args.name + ".receipt.json")).exists():
        raise RuntimeError("refusing to overwrite an existing command receipt")
    current_sha = subprocess.check_output(git_command() + ["rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(git_command() + ["status", "--porcelain"], text=True).strip()
    if current_sha != FROZEN_SHA or dirty:
        raise RuntimeError("review checkout is not the frozen clean snapshot")
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["DIANZI_REVIEW_RUN_NAME"] = args.name
    environment["PYTHONPATH"] = str(Path(args.cwd) / "src")
    coverage_cache = Path("C:/Users/yinha/.codex/review-cache/r04-api-review-1-recheck-2-20261015" if os.name == "nt" else "/tmp/dianzi-r04-api-review-1-recheck-2-20261015/coverage")
    coverage_cache.mkdir(parents=True, exist_ok=True)
    environment["COVERAGE_FILE"] = str(coverage_cache / (args.name + ".coverage.sqlite"))
    if args.cache:
        environment["XDG_CACHE_HOME"] = args.cache
    secret_values = []
    if args.pg:
        connection = json.loads(Path("/tmp/dianzi-r04-api-review-1-recheck-2-20261015/connection.json").read_text())
        environment.update(connection)
        from sqlalchemy.engine import make_url
        secret_values = [connection["TEST_DATABASE_URL"], make_url(connection["TEST_DATABASE_URL"]).password]
    started = timestamp()
    result = subprocess.run(command, cwd=args.cwd, env=environment, text=True, encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ended = timestamp()
    output = result.stdout
    for value in secret_values:
        if value:
            output = output.replace(value, "[REDACTED_TEST_SECRET]")
            for offset in range(max(0, len(value) - 7)) if value == secret_values[-1] else ():
                output = output.replace(value[offset:offset + 8], "[REDACTED_TEST_SECRET_FRAGMENT]")
    (RUN / (args.name + ".log")).write_text(output, encoding="utf-8")
    receipt = {
        "started_at": started, "ended_at": ended, "timezone": "Asia/Shanghai",
        "cwd": args.cwd, "argv": command, "exit_code": result.returncode,
        "code_sha": current_sha, "tree_sha": subprocess.check_output(git_command() + ["rev-parse", "HEAD^{tree}"], text=True).strip(),
        "clean_status": not dirty, "test_mode": "isolated synthetic fixture / actual PG" if args.pg else "unit or static / no external model calls",
        "log_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "platform": os.name,
        "coverage_file": environment["COVERAGE_FILE"],
    }
    (RUN / (args.name + ".receipt.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    print(output[-7000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())


