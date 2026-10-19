"""Independent review commands; outputs stay within the owned evidence directory."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = r"D:\dianzi\backend\.venv\Scripts\python.exe"
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
LOCAL_ZONE = timezone(timedelta(hours=8))


def execute(name, command, cwd=ROOT):
    started = datetime.now(LOCAL_ZONE).isoformat(timespec="seconds")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend" / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["RUFF_CACHE_DIR"] = str(RUN / "ruff_cache")
    output = subprocess.run(command, cwd=cwd, env=environment, capture_output=True)
    log = RUN / f"{name}.log"
    log.write_bytes(output.stdout + output.stderr)
    receipt = {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "started_at": started,
        "finished_at": datetime.now(LOCAL_ZONE).isoformat(timespec="seconds"),
        "exit_code": output.returncode,
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "log": str(log.relative_to(ROOT)),
        "environment_overrides": {
            "PYTHONPATH": environment["PYTHONPATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    }
    (RUN / f"{name}.command.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    print(output.stdout.decode("utf-8", errors="replace")[-1800:])
    print(output.stderr.decode("utf-8", errors="replace")[-1000:])
    return output.returncode


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "cbm":
        name, tool, *arguments = sys.argv[2:]
        sys.exit(execute(name, ["wsl", "--", CBM, "cli", "--json", tool, *arguments]))
    if action == "pytest":
        name, *targets = sys.argv[2:]
        sys.exit(execute(name, [PYTHON, "-m", "pytest", "--no-cov", "-o", "addopts=", "-o", f"cache_dir={RUN / 'pytest_cache'}", "--junitxml", str(RUN / f"{name}.xml"), "-q", *targets], ROOT / "backend"))
    if action == "python":
        name, *arguments = sys.argv[2:]
        sys.exit(execute(name, [PYTHON, *arguments], ROOT / "backend"))
    if action == "ruff":
        name, *arguments = sys.argv[2:]
        sys.exit(execute(name, [PYTHON, "-m", "ruff", *arguments], ROOT / "backend"))
    if action == "mypy":
        name, *arguments = sys.argv[2:]
        sys.exit(execute(name, [PYTHON, "-m", "mypy", "--cache-dir", str(RUN / "mypy_cache"), *arguments], ROOT / "backend"))
    if action == "command":
        name, *arguments = sys.argv[2:]
        if arguments[0] not in {"git", "rg"}:
            raise SystemExit("review command not permitted")
        sys.exit(execute(name, arguments))
    raise SystemExit("unknown review action")
