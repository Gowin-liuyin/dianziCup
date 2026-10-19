"""独立离线审查命令回执；不读取服务凭据，不覆盖已有标签。"""

import hashlib
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
PROJECT = "r05-timeout-review-1"
CBM = [
    "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-r05-timeout-review-1-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json",
]
label = sys.argv[1]
record_path = RUN / (label + ".command.json")
if record_path.exists():
    raise FileExistsError(label)
cwd = ROOT / "backend"
if label == "environment":
    command = ["uv", "sync", "--offline", "--frozen", "--all-extras", "--no-install-project", "--project", "backend"]
    cwd = ROOT
elif label in {"regression", "original_272", "new_17", "unit", "contract", "security", "independent"}:
    files = REGRESSION
    if label == "original_272":
        files = [file for file in REGRESSION if "predispatch" not in file]
    elif label == "new_17":
        files = [file for file in REGRESSION if "predispatch" in file]
    elif label in {"unit", "contract", "security"}:
        files = [file for file in REGRESSION if "/" + label + "/" in file]
    elif label == "independent":
        files = [str(RUN / "test_independent_generation_timeout.py")]
    command = [str(PYTHON), "-m", "pytest", *files, "--no-cov", "-q", "-p", "no:cacheprovider", "--basetemp=" + str(RUN / (label + "_temp")), "--junitxml=" + str(RUN / (label + ".xml"))]
elif label in {"ruff", "format"}:
    command = [str(PYTHON), "-m", "ruff", "check" if label == "ruff" else "format", *( [] if label == "ruff" else ["--check"]), "src/ai_intel/infrastructure/models", "tests/unit/test_r05_generation_predispatch_timeout.py", "--cache-dir", str(RUN / "ruff_cache")]
elif label == "mypy":
    command = [str(PYTHON), "-m", "mypy", "src", "--cache-dir", str(RUN / "mypy_cache")]
elif label == "cbm_index":
    command = CBM + ["index_repository", "--repo-path", "/mnt/d/wt/gen-tmo-r1/backend/src", "--name", PROJECT, "--mode", "fast"]
elif label == "cbm_schema":
    command = CBM + ["get_graph_schema", "--project", PROJECT, "--format", "json"]
elif label == "cbm_trace":
    command = CBM + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + ".ai_intel.infrastructure.models.generation.GenerationClient.generate", "--direction", "inbound", "--include-tests", "false"]
elif label == "callers":
    command = ["rg", "-n", "GenerationClient|\\.generate\\(|except GenerationFailure|remaining_seconds", "src/ai_intel", "tests/unit/test_r05_grounded_answer.py", "D:/wt/r07-model-fields-two-root-causes-fix/backend/src/ai_intel/enrichment/model_fields.py", "C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi/backend/src/ai_intel/enrichment/card_extraction.py"]
elif label == "diff_check":
    command = ["git", "diff", "--check", "595a13197a2c1bba6ad79957f8fde3750ba2a6c6", "47c47bc2b5d537166ee47a01c2ab14c035466e3d", "--", "backend/src/ai_intel/infrastructure/models/generation.py", "backend/tests/unit/test_r05_generation_predispatch_timeout.py"]
elif label in {"audit", "scope", "seal"}:
    command = [str(PYTHON), str(RUN / (label + ".py"))]
    cwd = ROOT
else:
    external = json.loads((RUN / (label + ".request.json")).read_text(encoding="utf-8-sig"))
    command = external["command"]
    cwd = Path(external["cwd"])
environment = dict(os.environ, PYTHONPATH=os.pathsep.join([str(cwd / "src"), str(cwd / "tests"), str(cwd / "tests/unit"), str(cwd / "tests/security")]), PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
for name in tuple(environment):
    if name.startswith("TEST_") or name in {"DATABASE_URL", "GENERATION_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"}:
        del environment[name]
zone = timezone(timedelta(hours=8))
started = datetime.now(zone).isoformat()
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=cwd, text=True).strip()
result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
(RUN / (label + ".stdout.log")).write_text(result.stdout, encoding="utf-8", newline="")
(RUN / (label + ".stderr.log")).write_text(result.stderr, encoding="utf-8", newline="")
record = {"label": label, "command": command, "cwd": str(cwd), "head_sha": sha, "head_tree": tree, "started_at": started, "completed_at": datetime.now(zone).isoformat(), "exit_code": result.returncode, "scope": "explicit offline unit/contract/socket fixtures or static review; zero live/model/PG/browser"}
source = cwd / "src/ai_intel/infrastructure/models/generation.py"
if source.exists():
    record["executed_generation_path"] = str(source)
    record["executed_generation_raw_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
if cwd == Path("D:/wt/gen-card-r1/backend") and label != "r09_original_red":
    record["combined_tree_binding"] = json.loads((RUN / "combo_tree_binding.json").read_text(encoding="utf-8"))
record["command_file_inputs"] = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for argument in command for path in [Path(argument) if Path(argument).is_absolute() else cwd / argument] if path.suffix == ".py" and path.is_file()]
xml = RUN / (label + ".xml")
if xml.exists():
    suites = list(ElementTree.parse(xml).iter("testsuite"))
    record["pytest"] = {key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
print(json.dumps(record, ensure_ascii=False))
print((result.stdout + result.stderr)[:12000])
raise SystemExit(result.returncode)
