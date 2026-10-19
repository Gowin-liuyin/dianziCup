"""Build independent indexes of the frozen source and inspect connected production paths."""

from review_checks import execute

PROJECT = "dianzi-r11-forward-review1-20261016"
PREFIX = [
    "wsl.exe",
    "-d",
    "Ubuntu-22.04",
    "--exec",
    "env",
    "XDG_CACHE_HOME=/tmp/dianzi-cbm-r11-forward-review1-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp",
    "cli",
    "--json",
]

COMMANDS = [
    (
        "cbm_src_index",
        [
            "index_repository",
            "--repo-path",
            "/mnt/d/wt/r11-forward-migrations-review1/backend/src",
            "--name",
            PROJECT,
            "--mode",
            "fast",
            "--persistence",
            "false",
        ],
    ),
    (
        "cbm_assets_index",
        [
            "index_repository",
            "--repo-path",
            "/mnt/d/wt/r11-forward-migrations-review1/backend/src/ai_intel/assets",
            "--name",
            PROJECT + "-assets",
            "--mode",
            "fast",
            "--persistence",
            "false",
        ],
    ),
    ("cbm_schema", ["get_graph_schema", "--project", PROJECT]),
    ("cbm_architecture", ["get_architecture", "--project", PROJECT, "--aspects", "all"]),
]
for label, arguments in COMMANDS:
    assert execute(label, PREFIX + arguments) == 0
for label, function, direction in [
    (
        "assessment_commit",
        "ai_intel.assessment.assessment_service.AssessmentService.commit",
        "outbound",
    ),
    (
        "assessment_callers",
        "ai_intel.assessment.assessment_service.AssessmentService.commit",
        "inbound",
    ),
    ("rule_publish", "ai_intel.assessment.rule_service.RuleService.publish", "outbound"),
    ("rule_callers", "ai_intel.assessment.rule_service.RuleService.publish", "inbound"),
    ("migration_callers", "ai_intel.infrastructure.database.run_migrations", "inbound"),
]:
    assert (
        execute(
            "cbm_" + label,
            [
                *PREFIX,
                "trace_path",
                "--project",
                PROJECT,
                "--function-name",
                PROJECT + "." + function,
                "--direction",
                direction,
                "--depth",
                "2",
                "--limit",
                "60",
            ],
        )
        == 0
    )
assert (
    execute(
        "cbm_inventory",
        [
            *PREFIX,
            "trace_path",
            "--project",
            PROJECT + "-assets",
            "--function-name",
            PROJECT + "-assets.inventory.InventoryService.import_manifest",
            "--direction",
            "inbound",
            "--depth",
            "2",
            "--limit",
            "60",
        ],
    )
    == 0
)
