"""Independent bounded source/assets indexes exclude secrets, holdout and tool caches."""

import json
import subprocess
import time

from run_checks import ROOT, RUN, now

CLI = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
CACHE = "/tmp/dianzi-cbm-r11-forward-rules-sbom-20261016"
PROJECT = "r11-forward-rules-sbom-20261016"


def main():
    operations = [
        (
            "src_index",
            [
                "index_repository",
                "--repo-path",
                "/mnt/d/wt/r11-forward-rules-sbom/backend/src",
                "--name",
                PROJECT,
                "--mode",
                "fast",
                "--persistence",
                "false",
            ],
        ),
        (
            "assets_index",
            [
                "index_repository",
                "--repo-path",
                "/mnt/d/wt/r11-forward-rules-sbom/backend/src/ai_intel/assets",
                "--name",
                PROJECT + "-assets",
                "--mode",
                "fast",
                "--persistence",
                "false",
            ],
        ),
        ("schema", ["get_graph_schema", "--project", PROJECT]),
        ("architecture", ["get_architecture", "--project", PROJECT, "--aspects", "all"]),
        (
            "assessment_trace",
            [
                "trace_path",
                "--project",
                PROJECT,
                "--function-name",
                PROJECT + ".ai_intel.assessment.assessment_service.AssessmentService.commit",
                "--direction",
                "outbound",
                "--depth",
                "2",
                "--limit",
                "60",
            ],
        ),
        (
            "rule_trace",
            [
                "trace_path",
                "--project",
                PROJECT,
                "--function-name",
                PROJECT + ".ai_intel.assessment.rule_service.RuleService.publish",
                "--direction",
                "outbound",
                "--depth",
                "2",
                "--limit",
                "60",
            ],
        ),
        (
            "assets_trace",
            [
                "trace_path",
                "--project",
                PROJECT + "-assets",
                "--function-name",
                PROJECT + "-assets.inventory.InventoryService.import_manifest",
                "--direction",
                "outbound",
                "--depth",
                "2",
                "--limit",
                "60",
            ],
        ),
        (
            "table_callers",
            [
                "rg",
                "-n",
                "asset_snapshot_sbom_sidecars|condition_rule_versions|rule_support_bindings|rule_leaf_reviews|rule_validation_receipts|assessment_results|assessment_scope_watches|load_rule_inputs",
                "backend/src",
            ],
        ),
    ]
    for label, arguments in operations:
        command = (
            arguments
            if label == "table_callers"
            else ["wsl", "-e", "env", "XDG_CACHE_HOME=" + CACHE, CLI, "cli", "--json", *arguments]
        )
        started_at, started = now(), time.monotonic()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=45, check=False)
        for name, value in (("stdout", result.stdout), ("stderr", result.stderr)):
            path = RUN / f"cbm_{label}.{name}.log"
            assert not path.exists()
            path.write_bytes(value)
        record = {
            "label": "cbm_" + label,
            "command": command,
            "cwd": str(ROOT),
            "started_at": started_at,
            "finished_at": now(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "exit_code": result.returncode,
        }
        with (RUN / "commands.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")
        if result.returncode:
            raise RuntimeError("source_audit_failed_" + label)
    print("Independent source/assets schema, architecture, traces and table callers captured.")


if __name__ == "__main__":
    main()
