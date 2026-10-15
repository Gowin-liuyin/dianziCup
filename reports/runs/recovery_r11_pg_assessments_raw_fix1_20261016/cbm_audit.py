"""Reindex final sources independently; the initial pre-business graph remains separate."""

import json
import subprocess

from run_checks import ROOT, RUN, now

CLI = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
TASKS = (
    (
        "final_src_index",
        [
            "index_repository",
            "--repo-path",
            "/mnt/d/wt/r11-pg-assessments/backend/src",
            "--name",
            "r11-pg-assessments-raw-fix1-final-20261016",
            "--mode",
            "fast",
        ],
    ),
    (
        "final_assets_index",
        [
            "index_repository",
            "--repo-path",
            "/mnt/d/wt/r11-pg-assessments/backend/src/ai_intel/assets",
            "--name",
            "r11-pg-assessments-raw-fix1-final-assets-20261016",
            "--mode",
            "fast",
        ],
    ),
    (
        "final_src_schema",
        ["get_graph_schema", "--project", "r11-pg-assessments-raw-fix1-final-20261016"],
    ),
    (
        "final_src_architecture",
        [
            "get_architecture",
            "--project",
            "r11-pg-assessments-raw-fix1-final-20261016",
            "--aspects",
            "all",
        ],
    ),
    (
        "final_assessment_trace",
        [
            "trace_path",
            "--project",
            "r11-pg-assessments-raw-fix1-final-20261016",
            "--function-name",
            "r11-pg-assessments-raw-fix1-final-20261016.ai_intel.assessment.assessment_service.AssessmentService.commit",
            "--direction",
            "outbound",
            "--depth",
            "2",
            "--limit",
            "60",
        ],
    ),
    (
        "final_assets_trace",
        [
            "trace_path",
            "--project",
            "r11-pg-assessments-raw-fix1-final-assets-20261016",
            "--function-name",
            "r11-pg-assessments-raw-fix1-final-assets-20261016.inventory.InventoryService.import_manifest",
            "--direction",
            "outbound",
            "--depth",
            "2",
            "--limit",
            "60",
        ],
    ),
    (
        "callers_rg",
        [
            "rg",
            "-n",
            "lock_rule_inputs|RuleService|AssessmentService|load_rule_inputs",
            "backend/src",
            "backend/tests",
        ],
    ),
)


def main():
    for label, arguments in TASKS:
        command = (
            arguments
            if label == "callers_rg"
            else ["wsl", "-e", CLI, "cli", "--json", *arguments]
        )
        started_at = now()
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, timeout=45, check=False
        )
        for name, value in (("stdout", result.stdout), ("stderr", result.stderr)):
            path = RUN / f"{label}.{name}.log"
            retained = RUN / f"first_{label}.{name}.log"
            if path.exists() and not retained.exists():
                retained.write_bytes(path.read_bytes())
            path.write_bytes(value)
        with (RUN / "commands.jsonl").open("a", encoding="utf-8") as log:
            log.write(
                json.dumps(
                    {
                        "label": label,
                        "command": command,
                        "cwd": str(ROOT),
                        "started_at": started_at,
                        "finished_at": now(),
                        "exit_code": result.returncode,
                    }
                )
                + "\n"
            )
        if result.returncode:
            raise RuntimeError("bounded final source audit failed: " + label)
    print(
        "Final CBM src/assets indexes, schema, architecture, traces and source callers saved."
    )


if __name__ == "__main__":
    main()
