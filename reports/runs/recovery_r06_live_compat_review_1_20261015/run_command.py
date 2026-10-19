"""Record independent review commands; private test credentials stay only in memory."""

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


parser = argparse.ArgumentParser()
parser.add_argument("label")
parser.add_argument("cwd")
parser.add_argument("--pg", action="store_true")
parser.add_argument("argv", nargs=argparse.REMAINDER)
args = parser.parse_args()
argv = args.argv[1:] if args.argv and args.argv[0] == "--" else args.argv
if Path(args.cwd, argv[0]).is_file():
    argv[0] = str(Path(args.cwd, argv[0]).resolve())
env = dict(os.environ, PYTHONUTF8="1")
secrets = []
if args.pg:
    result = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, timeout=15, check=True,
    )
    private = json.loads(result.stdout)
    if "TEST_DATABASE_URL" not in private:
        print("Private connection keys only:", sorted(private))
        raise SystemExit(2)
    from sqlalchemy.engine import make_url
    url = make_url(private["TEST_DATABASE_URL"]).set(database="test_dianzi_r06_catalog_worker_20261015")
    assert url.host in {"127.0.0.1", "localhost", "::1"}
    assert url.username.startswith("test_")
    env["TEST_DATABASE_URL"] = url.render_as_string(hide_password=False)
    env["DIANZI_TEST_RUN_ID"] = "r06_catalog_worker_20261015"
    secrets = [url.password, env["TEST_DATABASE_URL"], private["TEST_DATABASE_URL"]]
started_at = now()
result = subprocess.run(argv, cwd=args.cwd, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=1200)
output = result.stdout + result.stderr
for secret in secrets:
    if secret:
        output = output.replace(secret, "[redacted test credential]")
(RUN / (args.label + ".log")).write_text(output, encoding="utf-8")
receipt = {"argv": argv, "cwd": args.cwd, "started_at": started_at, "finished_at": now(), "exit_code": result.returncode,
           "environment_override": {"PYTHONUTF8": "1"}, "database": "test_dianzi_r06_catalog_worker_20261015" if args.pg else None}
(RUN / (args.label + "_command.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
print(output[-1200:])
raise SystemExit(result.returncode)
