"""保存本次离线修复的确定性命令、退出码和时间；不读取服务凭据。"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
CBM = [
    "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-r05-predispatch-timeout-fix-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json",
]
PROJECT = "r05-predispatch-timeout-fix"
REGRESSION = [
    "tests/unit/test_r05_generation.py",
    "tests/unit/test_r05_generation_review_fixes.py",
    "tests/unit/test_r05_generation_predispatch_timeout.py",
    "tests/unit/test_r05_grounded_answer.py",
    "tests/contract/test_r05_generation_wire.py",
    "tests/contract/test_r05_grounded_answer_contract.py",
    "tests/contract/test_t18_model_clients.py",
    "tests/security/test_r05_http_post.py",
    "tests/security/test_r05_transport_timeouts.py",
]

label = sys.argv[1]
if (RUN / (label + ".json")).exists():
    raise FileExistsError("evidence label already exists")
if label.startswith("cbm_help"):
    command = CBM + ["trace_path", "--help"]
elif label == "cbm_binary_help_frozen":
    command = CBM[:-2] + ["--help"]
elif label.startswith("cbm_index"):
    command = CBM + ["index_repository", "--repo-path", "/mnt/d/wt/gen-timeout/backend/src", "--name", PROJECT, "--mode", "fast"]
elif label.startswith("cbm_schema"):
    command = CBM + ["get_graph_schema", "--project", PROJECT, "--format", "json"]
elif label.startswith("cbm_search"):
    command = CBM + ["search_graph", "--project", PROJECT, "--name-pattern", "generate", "--file-pattern", "generation.py"]
elif label.startswith("cbm_trace"):
    command = CBM + ["trace_path", "--project", PROJECT, "--function-name", "ai_intel.infrastructure.models.generation.GenerationClient.generate" if label == "cbm_trace_initial" else PROJECT + ".ai_intel.infrastructure.models.generation.GenerationClient.generate", "--direction", "inbound", "--include-tests", "false"]
elif label in {"baseline", "red", "green", "frozen_regression"}:
    files = ["tests/unit/test_r05_generation_predispatch_timeout.py"] if label in {"red", "green"} else REGRESSION
    if label == "baseline":
        files = [file for file in files if "predispatch" not in file]
    command = [str(PYTHON), "-m", "pytest", *files, "--no-cov", "-q", "--junitxml=" + str(RUN / (label + ".xml"))]
elif label == "ruff":
    command = [str(PYTHON), "-m", "ruff", "check", "src/ai_intel/infrastructure/models", "tests/unit/test_r05_generation_predispatch_timeout.py"]
elif label == "format":
    command = [str(PYTHON), "-m", "ruff", "format", "--check", "src/ai_intel/infrastructure/models", "tests/unit/test_r05_generation_predispatch_timeout.py"]
elif label == "mypy":
    command = [str(PYTHON), "-m", "mypy", "src"]
elif label == "caller_search_frozen":
    command = ["rg", "-n", "GenerationClient|\\.generate\\(|except GenerationFailure|remaining_seconds", "src/ai_intel/infrastructure/models", "src/ai_intel/answering", "src/ai_intel/enrichment", "src/ai_intel/infrastructure/settings.py", str(ROOT / "config/models"), "C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi/backend/src/ai_intel/enrichment/card_extraction.py", "D:/wt/r07-model-fields-two-root-causes-fix/backend/src/ai_intel/enrichment/model_fields.py"]
elif label == "diff_check_frozen":
    command = ["git", "diff", "--check", "595a13197a2c1bba6ad79957f8fde3750ba2a6c6", "HEAD", "--", "backend/src/ai_intel/infrastructure/models/generation.py", "backend/tests/unit/test_r05_generation_predispatch_timeout.py"]
else:
    raise ValueError("unknown bounded check")
environment = dict(os.environ, PYTHONPATH=str(ROOT / "backend/src"), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
for name in tuple(environment):
    if name.startswith("TEST_") or name in {"DATABASE_URL", "GENERATION_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"}:
        del environment[name]
zone = timezone(timedelta(hours=8))
started = datetime.now(zone).isoformat()
source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
result = subprocess.run(command, cwd=ROOT / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
(RUN / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"label": label, "command": command, "cwd": str(ROOT / "backend"), "source_sha": source_sha, "started_at": started, "completed_at": datetime.now(zone).isoformat(), "exit_code": result.returncode, "log": label + ".log", "scope": "offline unit/contract/static; no live, database or asset operations"}
xml = RUN / (label + ".xml")
if xml.exists():
    record["pytest"] = {key: sum(int(suite.get(key, "0")) for suite in ElementTree.parse(xml).iter("testsuite")) for key in ("tests", "failures", "errors", "skipped")}
(RUN / (label + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, ensure_ascii=False))
if label.startswith("cbm_") or result.returncode:
    print((result.stdout + result.stderr)[:12000])
raise SystemExit(result.returncode)
