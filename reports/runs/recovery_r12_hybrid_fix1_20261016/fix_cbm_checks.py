"""Trace this worktree's narrowed reader fence and every existing epoch publication writer."""

from fix_checks import FIX_RUN, ROOT, run_checks

PREFIX = [
    "wsl",
    "--exec",
    "/usr/bin/env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-r12-hybrid-fix1-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp",
    "cli",
]
PROJECT = "dianzi-r12-hybrid-fix1-backend"


def main() -> int:
    run_checks.RUN = FIX_RUN
    run_checks.ROOT = ROOT
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
    ]
    for name, function, direction in (
        ("reader", "retrieval.hybrid.HybridRetriever.retrieve", "outbound"),
        ("publisher", "knowledge.persistence.KnowledgeRepository.publish", "outbound"),
        ("change_publication", "knowledge.persistence.save_change_publication", "outbound"),
        ("epoch_writers", "knowledge.revisions.bump_scope_epoch", "inbound"),
        ("event_publication", "knowledge.event_linking.EventRepository.publish_events", "outbound"),
        (
            "catalog_publication",
            "ingestion.catalog_documents.persist_catalog_documents",
            "outbound",
        ),
    ):
        commands.append(
            (
                "cbm_" + name,
                [
                    "trace_path",
                    "--project",
                    PROJECT,
                    "--function-name",
                    PROJECT + ".ai_intel." + function,
                    "--direction",
                    direction,
                    "--depth",
                    "3",
                    "--include-tests",
                    "false",
                    "--format",
                    "json",
                ],
            )
        )
    failures = []
    for name, arguments in commands:
        if run_checks.execute(name, PREFIX + arguments, cwd=ROOT):
            failures.append(name)
    if run_checks.execute(
        "rg_reader_writers",
        [
            "rg",
            "-n",
            r"\bbump_scope_epoch\b|\bscope_epochs\b|HybridSelection|lock_candidate_authorities|save_change_publication",
            "backend/src/ai_intel/retrieval",
            "backend/src/ai_intel/knowledge",
            "backend/src/ai_intel/ingestion/catalog_documents.py",
            "backend/src/ai_intel/answering/service.py",
        ],
        cwd=ROOT,
    ):
        failures.append("rg_reader_writers")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
