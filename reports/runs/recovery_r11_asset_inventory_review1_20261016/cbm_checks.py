"""Index only copied source trees; no report, credentials, holdout or cache."""

import json
import shutil
import subprocess
from pathlib import Path

from review_runner import ROOT, RUN, now

CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PROJECT_SRC = "r11_inventory_review1_src_20261016"
PROJECT_ASSETS = "r11_inventory_review1_assets_20261016"


def linux_path(path: Path):
    return "/mnt/d/" + path.as_posix()[3:]


def main():
    temporary = RUN / "tmp"
    temporary.mkdir(exist_ok=True)
    for name, source in [
        ("cbm-src", ROOT / "backend/src"),
        ("cbm-assets", ROOT / "backend/src/ai_intel/assets"),
    ]:
        target = temporary / name
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", ".codebase-memory", "*.pyc"),
        )
    operations = [
        (
            "cbm_src_index",
            "index_repository",
            [
                "--repo-path",
                linux_path(temporary / "cbm-src"),
                "--name",
                PROJECT_SRC,
                "--mode",
                "fast",
                "--persistence",
                "false",
            ],
        ),
        (
            "cbm_assets_index",
            "index_repository",
            [
                "--repo-path",
                linux_path(temporary / "cbm-assets"),
                "--name",
                PROJECT_ASSETS,
                "--mode",
                "fast",
                "--persistence",
                "false",
            ],
        ),
        (
            "cbm_architecture",
            "get_architecture",
            ["--project", PROJECT_SRC, "--format", "json"],
        ),
        ("cbm_schema", "get_graph_schema", ["--project", PROJECT_ASSETS]),
        (
            "cbm_inventory_callers",
            "trace_path",
            [
                "--project",
                PROJECT_SRC,
                "--function-name",
                PROJECT_SRC + ".InventoryService.import_manifest",
                "--direction",
                "both",
                "--format",
                "json",
            ],
        ),
        (
            "cbm_router_callers",
            "trace_path",
            [
                "--project",
                PROJECT_SRC,
                "--function-name",
                PROJECT_SRC + ".build_inventory_router",
                "--direction",
                "inbound",
                "--format",
                "json",
            ],
        ),
        (
            "cbm_find_function",
            "search_graph",
            ["--project", PROJECT_ASSETS, "--name-pattern", "import_manifest"],
        ),
    ]
    receipts = []
    for label, tool, args in operations:
        command = [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            CBM,
            "cli",
            "--json",
            tool,
            *args,
        ]
        started = now()
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
        (RUN / (label + ".json")).write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        receipts.append(
            {
                "label": label,
                "argv": command,
                "cwd": str(ROOT),
                "started_at": started,
                "finished_at": now(),
                "exit_code": result.returncode,
            }
        )
        (RUN / "cbm_commands.json").write_text(
            json.dumps(receipts, indent=2), encoding="utf-8"
        )
        print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)


if __name__ == "__main__":
    main()
