"""Run bounded read-only probes with exact argv and wall-clock evidence."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCAL_ZONE = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent


def now() -> str:
    return datetime.now(LOCAL_ZONE).isoformat(timespec="seconds")


def main() -> None:
    commands: list[tuple[str, Path, list[str]]] = [
        ("git-baseline", ROOT, ["git", "rev-parse", "HEAD"]),
        ("git-status", ROOT, ["git", "status", "--short"]),
        ("git-origin", ROOT, ["git", "remote", "get-url", "origin"]),
        ("system-python", ROOT, ["python", "--version"]),
        ("uv-version", ROOT, ["uv", "--version"]),
        ("project-python", ROOT / "backend", ["uv", "run", "--locked", "--offline", "python", "--version"]),
        ("node-version", ROOT, ["node", "--version"]),
        ("npm-version", ROOT, ["cmd", "/c", "npm", "--version"]),
        ("docker-version", ROOT, ["docker", "version", "--format", "{{.Client.Version}}|{{.Server.Version}}"]),
        ("docker-compose-version", ROOT, ["docker", "compose", "version", "--short"]),
        ("resources-and-environment-names", ROOT, ["powershell", "-NoProfile", "-Command",
            "$pattern='OPENAI|ANTHROPIC|MODEL|LLM|FOFA|NVD|REDIS|DATABASE|PG|OPENSEARCH|QDRANT|NEO4J'; "
            "foreach ($scopeName in 'Process','User','Machine') { "
            "$variableNames=[Environment]::GetEnvironmentVariables($scopeName).Keys | Where-Object { $_ -match $pattern }; "
            "[pscustomobject]@{scope=$scopeName;names=@($variableNames)} | ConvertTo-Json -Compress }; "
            "Get-Process | Where-Object { $_.ProcessName -match 'docker|redis|postgres|opensearch|neo4j|qdrant|uvicorn' } | "
            "Select-Object ProcessName,Id | ConvertTo-Json -Compress; "
            "[pscustomobject]@{docker_desktop_present=(Test-Path -LiteralPath 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe')} | ConvertTo-Json -Compress"]),
        ("behavior-probes", ROOT / "backend", ["uv", "run", "--locked", "--offline", "python", str(OUTPUT / "behavior_probes.py")]),
        ("pdf-independent-pypdf", ROOT, ["python", "-c",
            "from pypdf import PdfReader; import json; r=PdfReader('docs/references/competition_brief.pdf'); "
            "print(json.dumps({'pages':len(r.pages),'text_characters':sum(len(p.extract_text() or '') for p in r.pages)}))"]),
        ("backend-offline-selected", ROOT / "backend", ["uv", "run", "--locked", "--offline", "pytest",
            "tests/unit", "tests/contract", "tests/security", "tests/integration/test_t16_incremental_monitoring.py",
            "tests/integration/test_t21_claims_entities_conflicts.py", "--ignore=tests/contract/test_t07_jobs_outbox.py",
            "--no-cov", "-p", "no:cacheprovider", "-q", "-ra"]),
        ("frontend-skeleton-test", ROOT / "frontend", ["cmd", "/c", "npm", "run", "test", "--", "--run"]),
        ("cbm-version", ROOT, ["wsl", "-e", "sh", "-c", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp --version"]),
        ("cbm-index-help", ROOT, ["wsl", "-e", "sh", "-c", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli index_repository --help"]),
        ("cbm-index", ROOT, ["wsl", "-e", "sh", "-c",
            "XDG_CACHE_HOME=/tmp/dianzi-cbm-recovery-baseline-probe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository "
            "--repo-path /mnt/d/dianzi/backend/src --name dianzi-recovery-baseline-probe-8e265dc --mode fast --persistence false"]),
        ("cbm-schema", ROOT, ["wsl", "-e", "sh", "-c",
            "XDG_CACHE_HOME=/tmp/dianzi-cbm-recovery-baseline-probe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema "
            "--project dianzi-recovery-baseline-probe-8e265dc --format json"]),
        ("cbm-architecture", ROOT, ["wsl", "-e", "sh", "-c",
            "XDG_CACHE_HOME=/tmp/dianzi-cbm-recovery-baseline-probe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_architecture "
            "--project dianzi-recovery-baseline-probe-8e265dc --format json"]),
    ]
    for function_name in ("create_application", "commit_page_persisted", "normalize_nvd_record", "ClaimsLedger.publish_claims"):
        commands.append(("cbm-trace-" + function_name.replace(".", "-"), ROOT,
            ["wsl", "-e", "sh", "-c",
             "XDG_CACHE_HOME=/tmp/dianzi-cbm-recovery-baseline-probe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path "
             "--project dianzi-recovery-baseline-probe-8e265dc --function-name " + function_name + " --direction both --include-tests false --format json"]))
    records: list[dict[str, object]] = []
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    for name, directory, argv in commands:
        started = now()
        try:
            result = subprocess.run(argv, cwd=directory, env=environment, capture_output=True, timeout=120)
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
            code = result.returncode
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b"").decode("utf-8", errors="replace")
            stderr = (error.stderr or b"").decode("utf-8", errors="replace") + "\nTIMEOUT_AFTER_120_SECONDS"
            code = 124
        ended = now()
        log = OUTPUT / (name + ".log")
        log.write_text(stdout + "\nSTDERR:\n" + stderr, encoding="utf-8")
        records.append({"name": name, "cwd": str(directory), "argv": argv,
                        "started_at": started, "ended_at": ended, "exit_code": code,
                        "log": str(log.relative_to(ROOT))})
        (OUTPUT / "commands.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"name": name, "exit_code": code, "started_at": started, "ended_at": ended}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
