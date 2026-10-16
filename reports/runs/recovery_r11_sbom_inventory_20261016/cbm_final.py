"""复核最终source/assets独立索引与真实caller，原输出和起止由run_checks保存。"""

from run_checks import ROOT, run

CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
SRC_PROJECT = "r11-sbom-inventory-src-20261016"
ASSETS_PROJECT = "r11-sbom-inventory-assets-20261016"
PREFIX = ["wsl.exe", "-e", CBM, "cli", "--json"]


def main():
    for name, path, project in (
        ("src", "/mnt/d/wt/r11-sbom-inventory/backend/src", SRC_PROJECT),
        ("assets", "/mnt/d/wt/r11-sbom-inventory/backend/src/ai_intel/assets", ASSETS_PROJECT),
    ):
        result = run(
            "cbm_final_" + name + "_index",
            [*PREFIX, "index_repository", "--repo-path", path, "--name", project, "--mode", "fast"],
            cwd=ROOT,
        )
        assert result == 0
        for tool in ("get_graph_schema", "get_architecture"):
            result = run(
                "cbm_final_" + name + "_" + tool,
                [*PREFIX, tool, "--project", project, "--format", "json"],
                cwd=ROOT,
            )
            assert result == 0
    for function in (
        "import_manifest",
        "parse_inventory_input",
        "parse_manifest",
        "get_snapshot_sbom",
    ):
        result = run(
            "cbm_final_" + function + "_trace",
            [
                *PREFIX,
                "trace_path",
                "--project",
                ASSETS_PROJECT,
                "--function-name",
                function,
                "--direction",
                "both",
                "--depth",
                "3",
            ],
            cwd=ROOT,
        )
        assert result == 0


if __name__ == "__main__":
    main()
