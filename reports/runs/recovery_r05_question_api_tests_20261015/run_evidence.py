"""Run isolated acceptance commands and record output without exposing private PG config."""

import json
import hashlib
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNS = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
git_path = (ROOT / ".git").read_text().strip().removeprefix("gitdir: ")
if os.name != "nt" and len(git_path) > 1 and git_path[1] == ":":
    git_path = "/mnt/" + git_path[0].lower() + git_path[2:].replace("\\", "/")
git_command = ["git", "-c", "core.fsmonitor=false", "--git-dir=" + git_path, "--work-tree=" + str(ROOT)]
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
mode = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else mode
environment = dict(os.environ)
environment["PYTHONPATH"] = str(BACKEND / "src")
environment["CBM_CACHE_DIR"] = "/tmp/dianzi-cbm-r05-api-tests-20261015"
commands = {
    "cbm_help": [CBM, "--help"],
    "cbm_cli_help": [CBM, "cli", "--help"],
    "cbm_index": [CBM, "cli", "--json", "index_repository", "--repo-path", str(BACKEND / "src"), "--name", "dianzi-r05-api-tests", "--mode", "fast"],
    "cbm_trace": [CBM, "cli", "--json", "trace_path", "--project", "dianzi-r05-api-tests", "--function-name", "GroundedQuestionService.ask", "--direction", "both"],
    "cbm_search": [CBM, "cli", "--json", "search_graph", "--project", "dianzi-r05-api-tests", "--name-pattern", "ask"],
    "cbm_trace_ask": [CBM, "cli", "--json", "trace_path", "--project", "dianzi-r05-api-tests", "--function-name", "ask", "--direction", "both"],
    "rg_trace": ["/mnt/c/Users/yinha/.kimi-code/bin/rg.exe", "-n", "build_question_router|build_question_service|questions.ask|read_grounded_answer|require_current|generate_grounded_answer", "src/ai_intel/api/app.py", "src/ai_intel/api/question_routes.py", "src/ai_intel/answering/service.py", "src/ai_intel/retrieval/service.py"],
    "unit": [sys.executable, "-m", "pytest", "tests/unit/test_r05_question_routes.py", "tests/contract/test_r05_question_contracts.py", "--no-cov", "-v"],
    "pg": [sys.executable, "-m", "pytest", "tests/integration/test_r05_question_api_pg.py", "--no-cov", "-v"],
    "regression": [sys.executable, "-m", "pytest", "tests/unit/test_r05_grounded_answer.py", "tests/unit/test_r05_generation.py", "tests/unit/test_r05_generation_review_fixes.py", "tests/unit/test_r05_semantic.py", "tests/integration/test_r05_vector_persistence.py", "--no-cov", "-v"],
    "unit_gate": [sys.executable, "-m", "pytest", "tests/unit", "-q"],
    "ruff": [sys.executable, "-m", "ruff", "check", "tests/integration/test_r05_question_api_pg.py", "tests/unit/test_r05_question_routes.py"],
    "format": [sys.executable, "-m", "ruff", "format", "--check", "tests/integration/test_r05_question_api_pg.py", "tests/unit/test_r05_question_routes.py"],
    "mypy": [sys.executable, "-m", "mypy", "src/ai_intel"],
    "secrets": [sys.executable, str(RUNS / "check_evidence_secrets.py")],
    "package": [sys.executable, str(RUNS / "package_large_diagnostic.py")],
    "diff": ["/mnt/c/Program Files/Git/cmd/git.exe", "-C", "D:/wt/r05-api-tests", "diff", "--check"],
}
command = commands[mode]
if mode in {"pg", "regression"}:
    configuration = json.loads(Path("/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json").read_bytes())
    environment["TEST_DATABASE_URL"] = configuration["TEST_DATABASE_URL"]
    environment["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
if mode in {"unit", "pg", "regression", "unit_gate"}:
    command += ["--junitxml=" + str(RUNS / (label + ".xml"))]
zone = timezone(timedelta(hours=8))
started = datetime.now(zone).isoformat(timespec="seconds")
test_hashes = {
    str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (
        BACKEND / "tests/integration/test_r05_question_api_pg.py",
        BACKEND / "tests/unit/test_r05_question_routes.py",
    )
}
result = subprocess.run(command, cwd=BACKEND, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
ended = datetime.now(zone).isoformat(timespec="seconds")
output = result.stdout + result.stderr
secret = environment.get("TEST_DATABASE_URL", "")
if secret:
    from urllib.parse import unquote, urlsplit
    output = output.replace(secret, "[redacted test connection]")
    output = output.replace(unquote(urlsplit(secret).password or ""), "[redacted test credential]")
(RUNS / (label + ".log")).write_text(output, encoding="utf-8")
sha = subprocess.check_output([*git_command, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
record = {"command": command, "cwd": str(BACKEND), "started_at": started, "ended_at": ended, "exit_code": result.returncode, "sha": sha, "test_files_sha256": test_hashes, "data_mode": "fixture" if mode in {"unit", "unit_gate", "pg", "regression"} else "not_applicable", "real_isolated_postgresql": mode in {"pg", "regression"}}
xml = RUNS / (label + ".xml")
if mode in {"unit", "pg", "regression", "unit_gate"} and xml.exists():
    cases = ET.parse(xml).getroot().findall(".//testcase")
    record["counts"] = {"tests": len(cases), "failures": sum(case.find("failure") is not None for case in cases), "errors": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)}
(RUNS / (label + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, ensure_ascii=False))
print(output[-10000:])
sys.exit(result.returncode)
