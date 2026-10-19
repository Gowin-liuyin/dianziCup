"""Read the complete current locator DTO and actual default callers without executing services."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def main():
    commands = {
        "fixed_identity": ["git", "rev-parse", "HEAD", "HEAD^{tree}"],
        "tracked_protection": ["git", "diff", "--exit-code", "HEAD", "--", "backend", "contracts", "config", "docs", "progress", "AGENTS.md"],
        "actual_callers": ["rg", "-n", "safe_sbom_sidecar|safe_sbom_snapshot|freeze_sbom_sidecar|get_snapshot_sbom|parse_inventory_input", "backend/src", "scripts", "frontend/src"],
        "default_wiring": ["rg", "-n", "inventory_router|graph_router|enrichment_router|build_engine", "backend/src/ai_intel/api/app.py"],
        "forbidden_scope_changes": ["git", "diff", "--name-only", "6aeeeec5489b92bb49613fe5daa4eec379182348", "HEAD", "--", "backend/migrations", "backend/pyproject.toml", "backend/uv.lock", "contracts", "config", "progress", "docs/decisions", "backend/src/ai_intel/api", "backend/src/ai_intel/assets/inventory.py", "backend/src/ai_intel/assets/inventory_routes.py", "backend/src/ai_intel/assets/sbom_inventory_contracts.py"],
    }
    for label, argv in commands.items():
        started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
        completed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert completed.returncode == 0
        (RUN / (label + ".log")).write_text(completed.stdout + completed.stderr, encoding="utf-8")
        (RUN / (label + ".command.json")).write_text(json.dumps({"argv": argv, "cwd": str(ROOT), "started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "exit_code": completed.returncode}, indent=2) + "\n")
    paths = ["backend/src/ai_intel/assets/sbom_inventory.py", "backend/src/ai_intel/assets/sbom_inventory_contracts.py", "backend/src/ai_intel/assets/inventory.py", "backend/src/ai_intel/assets/inventory_routes.py", "backend/src/ai_intel/api/app.py", "AGENTS.md"]
    rows = []
    excerpts = []
    for name in paths:
        content = (ROOT / name).read_bytes()
        blob = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
        rows.append({"path": name, "raw_sha256": hashlib.sha256(content).hexdigest(), "git_lf_sha256": hashlib.sha256(blob).hexdigest(), "lf_matches": content.replace(b"\r\n", b"\n") == blob})
        if "sbom_inventory" in name:
            excerpts.append("FILE " + name + "\n" + "\n".join(f"{index}:{line}" for index, line in enumerate(content.decode().splitlines(), 1)))
    (RUN / "current_typed_dto_and_locator_source.txt").write_text("\n\n".join(excerpts), encoding="utf-8")
    (RUN / "current_source_hashes.json").write_text(json.dumps(rows, indent=2) + "\n")
    print("Current typed DTO, default callers and protected scope captured")


if __name__ == "__main__":
    main()
