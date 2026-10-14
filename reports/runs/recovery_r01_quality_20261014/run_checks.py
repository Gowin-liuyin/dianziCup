"""执行本包真实回归，将私有测试配置仅注入子进程，原始输出脱敏落盘。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent / datetime.now().astimezone().strftime("recheck_%Y%m%d_%H%M%S")
RUN.mkdir()
HEAD = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
environment = dict(os.environ)
environment["PYTHONIOENCODING"] = "utf-8"
private_file = os.environ.get("DIANZI_TEST_CONNECTION_FILE")
if not private_file:
    raise RuntimeError("DIANZI_TEST_CONNECTION_FILE is required; never reuse another worktree database")
private = subprocess.run(
    ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-c",
     "import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())", private_file],
    capture_output=True, text=True, check=True, timeout=10,
)
configuration = json.loads(private.stdout)
if configuration.get("DIANZI_TEST_RUN_ID") != "r01_quality_20261014":
    raise RuntimeError("private configuration must belong to this worktree")
for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID", "NO_PROXY"):
    environment[key] = configuration[key]
secret_values = [configuration[key] for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL")]
secret_values += [unquote(urlsplit(configuration[key]).password or "") for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL")]
configuration.clear()
private = None


def execute(name: str, command: list[str], cwd: Path, configured: dict[str, str] | None = None) -> None:
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    completed = subprocess.run(command, cwd=cwd, env=environment if configured is None else configured,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    ended = datetime.now().astimezone().isoformat(timespec="seconds")
    stdout, stderr = completed.stdout, completed.stderr
    for secret in secret_values:
        if secret:
            stdout, stderr = stdout.replace(secret, "[redacted test secret]"), stderr.replace(secret, "[redacted test secret]")
    (RUN / f"{name}.stdout.log").write_text(stdout, encoding="utf-8")
    (RUN / f"{name}.stderr.log").write_text(stderr, encoding="utf-8")
    receipt = {"name": name, "command": command, "cwd": str(cwd), "start": started, "end": ended,
               "exit_code": completed.returncode, "baseline_sha": HEAD, "stdout": f"{name}.stdout.log", "stderr": f"{name}.stderr.log"}
    for argument in command:
        if argument.startswith("--junitxml="):
            report = Path(argument.split("=", 1)[1])
            if report.is_file():
                output = report.read_text(encoding="utf-8")
                for secret in secret_values:
                    if secret:
                        output = output.replace(secret, "[redacted test secret]")
                report.write_text(output, encoding="utf-8", newline="\n")
    (RUN / f"{name}.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(name, completed.returncode, flush=True)


backend = ROOT / "backend"
files = ["../scripts/dev.py", "tests/conftest.py", "tests/contract/test_r01_quality_checks.py", "tests/contract/test_t07_jobs_outbox.py", "tests/integration/test_t03_development_services.py", "tests/integration/test_t05_persistence_and_raw_store.py", "tests/integration/test_t07_jobs_and_outbox.py", "tests/unit/test_t02_project_skeleton.py"]
execute("quality_contract", ["uv", "run", "--locked", "pytest", "tests/contract/test_r01_quality_checks.py", "--cov-fail-under=0", f"--junitxml={RUN / 'quality_contract.xml'}", "-q"], backend)
execute("unit", ["uv", "run", "--locked", "pytest", "tests/unit", f"--junitxml={RUN / 'unit.xml'}", "-q"], backend)
execute("contract", ["uv", "run", "--locked", "pytest", "tests/contract", "--cov-fail-under=0", f"--junitxml={RUN / 'contract.xml'}", "-q"], backend)
execute("postgres_integration", ["uv", "run", "--locked", "pytest", "tests/integration/test_t05_persistence_and_raw_store.py", "tests/integration/test_t07_jobs_and_outbox.py", "--cov-fail-under=0", f"--junitxml={RUN / 'postgres_integration.xml'}", "-q"], backend)
execute("security", ["uv", "run", "--locked", "pytest", "tests/security", "--cov-fail-under=0", f"--junitxml={RUN / 'security.xml'}", "-q"], backend)
execute("ruff", ["uv", "run", "--locked", "ruff", "check", *files], backend)
execute("format", ["uv", "run", "--locked", "ruff", "format", "--check", *files], backend)
execute("mypy", ["uv", "run", "--locked", "mypy", "src", "../scripts/dev.py"], backend)
execute("scope_contract", [str(backend / '.venv/Scripts/python.exe'), "scripts/dev.py", "check", "--scope", "contract"], ROOT)
execute("scope_frontend", [str(backend / '.venv/Scripts/python.exe'), "scripts/dev.py", "check", "--scope", "frontend"], ROOT)
without_resources = {key: value for key, value in environment.items() if key not in {"TEST_DATABASE_URL", "DIANZI_TEST_RUN_ID"}}
execute("scope_missing_resources", [str(backend / '.venv/Scripts/python.exe'), "scripts/dev.py", "check", "--scope", "integration"], ROOT, without_resources)
execute("scope_e2e", [str(backend / '.venv/Scripts/python.exe'), "scripts/dev.py", "check", "--scope", "e2e"], ROOT)
hashes = {filename: hashlib.sha256((backend / filename).read_bytes()).hexdigest() for filename in files}
(RUN / "source_hashes.json").write_text(json.dumps({"baseline_sha": HEAD, "files": hashes}, indent=2) + "\n", encoding="utf-8")
