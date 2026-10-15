"""Index isolated source copies before modifying migration code."""

import shutil
import tempfile
from pathlib import Path

from run_checks import ROOT, execute

CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
temporary = Path(tempfile.mkdtemp(prefix="r11-r08-forward-cbm-"))


def linux_path(path):
    return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]


def cbm(label, tool, arguments):
    return execute(
        label,
        [
            "wsl.exe",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            CBM,
            "cli",
            "--json",
            tool,
            *arguments,
        ],
        cwd=ROOT,
    )


for name, source in (
    ("src", ROOT / "backend/src"),
    ("assets", ROOT / "backend/src/ai_intel/assets"),
):
    target = temporary / name
    shutil.copytree(
        source, target, ignore=shutil.ignore_patterns("__pycache__", ".codebase-memory", "*.pyc")
    )
    project = f"r11_r08_forward_{name}_20261016"
    cbm(
        f"cbm_{name}_index",
        "index_repository",
        [
            "--repo-path",
            linux_path(target),
            "--name",
            project,
            "--mode",
            "fast",
            "--persistence",
            "false",
        ],
    )
    cbm(f"cbm_{name}_schema", "get_graph_schema", ["--project", project])
    cbm(f"cbm_{name}_architecture", "get_architecture", ["--project", project, "--format", "json"])

for symbol in ("import_manifest", "_cache", "run_migrations"):
    project = f"r11_r08_forward_{'src' if symbol == 'run_migrations' else 'assets'}_20261016"
    cbm(
        "cbm_search_" + symbol.strip("_"),
        "search_graph",
        ["--project", project, "--name-pattern", symbol],
    )
