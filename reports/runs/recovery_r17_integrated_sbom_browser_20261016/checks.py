"""Bounded commands and source receipts for this isolated browser work package."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def execute(label, argv, cwd, timeout=240, environment=None):
    started = now()
    result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, timeout=timeout)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    receipt = {
        "argv": argv, "cwd": str(cwd), "started_at": started, "ended_at": now(),
        "exit_code": result.returncode,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    (RUN / (label + "_command.json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    return result.returncode


def metadata():
    files = ["frontend/src/features/assets/asset-client.ts", "frontend/src/features/assets/asset-contracts.ts", "frontend/src/features/assets/sbom-contracts.ts", "frontend/src/features/assets/asset-detail.tsx", "frontend/src/features/assets/asset-import.tsx", "frontend/src/features/assets/sbom-detail.tsx", "frontend/src/features/assets/assets.css", "backend/src/ai_intel/api/app.py", "backend/src/ai_intel/assets/inventory_routes.py", "backend/src/ai_intel/assets/sbom_public.py"]
    result = {"observed_at": now(), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "sources": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files if (ROOT / path).exists()}, "protected_main_buildinfo_sha256": hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()}
    (RUN / "initial_source_metadata.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": "recorded", "main_buildinfo_matches": result["protected_main_buildinfo_sha256"] == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"}))


if __name__ == "__main__":
    label = sys.argv[1]
    if label == "metadata":
        metadata()
        raise SystemExit(0)
    if label.startswith("cbm_"):
        argv = ["wsl.exe", "-d", "Ubuntu-22.04", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json", *sys.argv[2:]]
        raise SystemExit(execute(label, argv, ROOT, timeout=60))
    environment = os.environ.copy()
    if label.startswith("material_"):
        raise SystemExit(execute(label, [str(PYTHON), *sys.argv[2:]], ROOT, environment=environment))
    if label.startswith("edge_"):
        raise SystemExit(execute(label, ["C:/Program Files/nodejs/node.exe", "node_modules/@playwright/test/cli.js", *sys.argv[2:]], ROOT / "frontend", environment=environment))
    raise SystemExit(execute(label, ["C:/Program Files/nodejs/npm.cmd", *sys.argv[2:]], ROOT / "frontend", environment=environment))
