"""Index this worktree's backend/src only, then inspect retrieval architecture and traces."""

from run_checks import ROOT, execute

PREFIX = [
    "wsl",
    "--exec",
    "/usr/bin/env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-hybrid-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp",
    "cli",
]
PROJECT = "dianzi-r12-hybrid-backend"


def main() -> int:
    commands = [
        (
            "cbm_index",
            [
                "index_repository",
                "--repo-path",
                "/mnt/d/wt/r12-hybrid-retrieval/backend/src",
                "--name",
                PROJECT,
                "--mode",
                "fast",
                "--persistence",
                "false",
            ],
        ),
        ("cbm_schema", ["get_graph_schema", "--project", PROJECT]),
        (
            "cbm_architecture",
            [
                "get_architecture",
                "--project",
                PROJECT,
                "--path",
                "ai_intel/retrieval",
                "--aspects",
                "overview",
                "--format",
                "json",
            ],
        ),
        (
            "cbm_trace",
            [
                "trace_path",
                "--project",
                PROJECT,
                "--function-name",
                PROJECT + ".ai_intel.retrieval.hybrid.HybridRetriever.retrieve",
                "--direction",
                "outbound",
                "--depth",
                "2",
                "--include-tests",
                "false",
                "--format",
                "json",
            ],
        ),
        (
            "rg_retrieval",
            [
                "rg",
                "-n",
                "HybridRetriever|HybridIndexer|facts_query|SemanticModels|scope_epoch",
                "backend/src/ai_intel/retrieval",
                "backend/src/ai_intel/answering",
            ],
        ),
    ]
    failures = []
    for name, arguments in commands:
        argv = arguments if name.startswith("rg") else PREFIX + arguments
        code = execute(name, argv, cwd=ROOT)
        if code:
            failures.append(name)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
