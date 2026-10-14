"""Append corrected tool lookup and targeted security/collection observations."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
LOCAL_ZONE = timezone(timedelta(hours=8))


def run(name: str, directory: Path, argv: list[str], timeout: int = 30) -> str:
    started = datetime.now(LOCAL_ZONE).isoformat(timespec="seconds")
    try:
        result = subprocess.run(argv, cwd=directory, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"), capture_output=True, timeout=timeout)
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        code = result.returncode
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode("utf-8", errors="replace")
        stderr = (error.stderr or b"").decode("utf-8", errors="replace") + f"\nTIMEOUT_AFTER_{timeout}_SECONDS"
        code = 124
    ended = datetime.now(LOCAL_ZONE).isoformat(timespec="seconds")
    log = OUTPUT / (name + ".log")
    log.write_text(stdout + "\nSTDERR:\n" + stderr, encoding="utf-8")
    commands_path = OUTPUT / "commands.json"
    records = json.loads(commands_path.read_text(encoding="utf-8"))
    records.append({"name": name, "cwd": str(directory), "argv": argv, "started_at": started, "ended_at": ended, "exit_code": code, "log": str(log.relative_to(ROOT))})
    commands_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "exit_code": code, "started_at": started, "ended_at": ended}), flush=True)
    return stdout


def main() -> None:
    """Correct the exact method name after using the tool's search surface."""
    run("behavior-probes-with-logout-negative", ROOT / "backend", ["uv", "run", "--locked", "--offline", "python", str(OUTPUT / "behavior_probes.py")])
    collected = run("backend-selected-collection", ROOT / "backend", ["uv", "run", "--locked", "--offline", "pytest", "tests/unit", "tests/contract", "tests/security", "tests/integration/test_t16_incremental_monitoring.py", "tests/integration/test_t21_claims_entities_conflicts.py", "--ignore=tests/contract/test_t07_jobs_outbox.py", "--no-cov", "-p", "no:cacheprovider", "--collect-only", "-q"])
    layer_counts = {layer: sum(line.startswith("tests/" + layer + "/") for line in collected.splitlines()) for layer in ("unit", "contract", "security", "integration")}
    (OUTPUT / "test_layer_counts.json").write_text(json.dumps(layer_counts, indent=2), encoding="utf-8")
    run("docker-version-bounded-recheck", ROOT, ["docker", "version", "--format", "{{.Client.Version}}|{{.Server.Version}}"], timeout=20)
    executable = "XDG_CACHE_HOME=/tmp/dianzi-cbm-recovery-baseline-probe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json "
    response = run("cbm-search-publish-claims", ROOT, ["wsl", "-e", "sh", "-c", executable + "search_graph --project dianzi-recovery-baseline-probe-8e265dc --name-pattern publish_claims --format json"])
    print(response[:5000], flush=True)
    run("cbm-trace-publish-claims-corrected", ROOT, ["wsl", "-e", "sh", "-c", executable + "trace_path --project dianzi-recovery-baseline-probe-8e265dc --function-name publish_claims --direction both --include-tests false --format json"])
    run("git-source-tree", ROOT, ["git", "rev-parse", "HEAD:backend/src"])
    run("git-product-diff", ROOT, ["git", "diff", "--stat", "--", "backend", "frontend"])
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT / "backend/src").rglob("*.py")}
    (OUTPUT / "indexed_source_hashes.json").write_text(json.dumps(source_hashes, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
