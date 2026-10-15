"""Capture a complete source index and traces in a separate external CBM cache."""

from run_commands import ROOT, run

PREFIX = ["wsl", "-d", "Ubuntu-22.04", "--", "env",
          "XDG_CACHE_HOME=/tmp/dianzi-cbm-r07-public-signals-fix1-20261016",
          "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
PROJECT = "r07-public-signals-fix1"
COMMANDS = {
    "cbm_index": ["index_repository", "--repo-path", "/mnt/d/wt/r07-public-signals-fix1/backend/src",
                  "--name", PROJECT, "--mode", "moderate", "--persistence", "false"],
    "cbm_schema": ["get_graph_schema", "--project", PROJECT],
    "cbm_architecture": ["get_architecture", "--project", PROJECT],
    "cbm_enrichment_trace": ["trace_path", "--project", PROJECT, "--function-name", "enrich_structured_fields",
                             "--direction", "both", "--depth", "3", "--max-output-tokens", "5000"],
    "cbm_scope_trace": ["trace_path", "--project", PROJECT, "--function-name", "_scope",
                        "--direction", "both", "--depth", "3", "--max-output-tokens", "4000"],
    "cbm_candidates_trace": ["trace_path", "--project", PROJECT, "--function-name", "_cwe_candidates",
                             "--direction", "both", "--depth", "3", "--max-output-tokens", "5000"],
    "cbm_catalog_trace": ["trace_path", "--project", PROJECT, "--function-name", "select_cwe_catalog_document",
                          "--direction", "both", "--depth", "2", "--max-output-tokens", "3000"],
}
if __name__ == "__main__":
    import sys
    prefix = sys.argv[1] + "_" if len(sys.argv) > 1 else ""
    for name, arguments in COMMANDS.items():
        if run(prefix + name, PREFIX + arguments, ROOT, timeout=60):
            raise SystemExit(1)
