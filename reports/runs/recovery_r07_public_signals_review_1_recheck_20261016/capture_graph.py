"""Build a fresh source-only graph and trace the qualified changed functions."""

from run_commands import ROOT, run

PREFIX = ["wsl", "-d", "Ubuntu-22.04", "--", "env",
          "XDG_CACHE_HOME=/tmp/dianzi-cbm-r07-public-signals-review-fix1-20261016",
          "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
PROJECT = "r07-public-signals-review-fix1-facf6cc"
COMMANDS = {
    "cbm_index": ["index_repository", "--repo-path", "/mnt/d/wt/r07-public-signals-review-fix1/backend/src",
                  "--name", PROJECT, "--mode", "moderate", "--persistence", "false"],
    "cbm_schema": ["get_graph_schema", "--project", PROJECT],
    "cbm_architecture": ["get_architecture", "--project", PROJECT],
}
for name, arguments in COMMANDS.items():
    if run(name, PREFIX + arguments, ROOT):
        raise SystemExit(1)
for function in ("enrich_structured_fields", "_scope", "_cwe_candidates"):
    qualified = PROJECT + ".ai_intel.enrichment.signals." + function
    if run("cbm_qualified_" + function.strip("_"), PREFIX + ["trace_path", "--project", PROJECT,
        "--function-name", qualified, "--direction", "both", "--depth", "3", "--max-output-tokens", "4000"], ROOT):
        raise SystemExit(1)
