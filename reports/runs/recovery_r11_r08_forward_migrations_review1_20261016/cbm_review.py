"""Build independent source and assets graphs; retain real callers and graph limits."""

import json
import shutil
import tempfile
from pathlib import Path

from review_runner import ROOT, RUN, execute

CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"


def cbm(label, tool, arguments):
    result = execute(
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
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert not payload.get("isError", False)
    return payload


def linux_path(path):
    return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]


def main():
    temporary = Path(tempfile.mkdtemp(prefix="r11r08-review1-cbm-"))
    projects = {}
    for name, source in (
        ("src", ROOT / "backend/src"),
        ("assets", ROOT / "backend/src/ai_intel/assets"),
    ):
        target = temporary / name
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", ".codebase-memory", "*.pyc"),
        )
        project = "r11r08_review1_20261016_" + name
        projects[name] = project
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
        cbm(
            f"cbm_{name}_architecture",
            "get_architecture",
            ["--project", project, "--format", "json"],
        )
    for key, symbol, module in (
        ("assets", "import_manifest", "inventory.InventoryService.import_manifest"),
        (
            "assets",
            "save_observation",
            "aggregate_repository.PostgresAggregateRepository.save_observation",
        ),
        (
            "assets",
            "collect_provider_aggregate_observation",
            "aggregate_service.AggregateService.collect_provider_aggregate_observation",
        ),
        ("src", "run_migrations", "ai_intel.infrastructure.database.run_migrations"),
    ):
        project = projects[key]
        cbm(
            "cbm_search_" + symbol, "search_graph", ["--project", project, "--name-pattern", symbol]
        )
        cbm(
            "cbm_trace_" + symbol,
            "trace_path",
            [
                "--project",
                project,
                "--function-name",
                project + "." + module,
                "--direction",
                "both",
                "--format",
                "json",
            ],
        )
    (RUN / "cbm_source_copy.json").write_text(
        json.dumps(
            {
                "temporary": str(temporary),
                "projects": projects,
                "excludes": ["__pycache__", ".codebase-memory", "*.pyc"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
