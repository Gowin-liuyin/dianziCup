"""Resolve exact graph names in the separate assets index after source exclusion."""

import json
import subprocess

from cbm_checks import CBM, PROJECT_ASSETS
from review_runner import ROOT, RUN, now

operations = [
    (
        "cbm_router_name_recheck",
        "search_graph",
        ["--project", PROJECT_ASSETS, "--name-pattern", "build_inventory_router"],
    ),
    (
        "cbm_inventory_trace_recheck",
        "trace_path",
        [
            "--project",
            PROJECT_ASSETS,
            "--function-name",
            PROJECT_ASSETS + ".inventory.InventoryService.import_manifest",
            "--direction",
            "both",
            "--format",
            "json",
        ],
    ),
    (
        "cbm_router_trace_recheck",
        "trace_path",
        [
            "--project",
            PROJECT_ASSETS,
            "--function-name",
            PROJECT_ASSETS + ".inventory_routes.build_inventory_router",
            "--direction",
            "inbound",
            "--format",
            "json",
        ],
    ),
    (
        "cbm_assets_architecture",
        "get_architecture",
        ["--project", PROJECT_ASSETS, "--format", "json"],
    ),
]
receipts = []
for label, tool, args in operations:
    command = [
        "wsl",
        "-d",
        "Ubuntu-22.04",
        "-u",
        "root",
        "--exec",
        CBM,
        "cli",
        "--json",
        tool,
        *args,
    ]
    started = now()
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    (RUN / (label + ".json")).write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    receipts.append(
        {
            "label": label,
            "argv": command,
            "cwd": str(ROOT),
            "started_at": started,
            "finished_at": now(),
            "exit_code": result.returncode,
        }
    )
    (RUN / "cbm_recheck_commands.json").write_text(
        json.dumps(receipts, indent=2), encoding="utf-8"
    )
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
