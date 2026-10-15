"""冻结源码后用独立项目名更新source/assets图，不覆盖修复前图与日志。"""

import json

from run_checks import ROOT, run


def main():
    prefix = [
        "wsl.exe",
        "-e",
        "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp",
        "cli",
        "--json",
    ]
    for suffix, path in (("src", "backend/src"), ("assets", "backend/src/ai_intel/assets")):
        project = "r11-sbom-inventory-privacy-followup-" + suffix + "-20261016"
        code = run(
            "cbm_followup_" + suffix + "_index",
            [
                *prefix,
                "index_repository",
                json.dumps(
                    {
                        "repo_path": "/mnt/d/wt/r11-sbom-inventory/" + path,
                        "name": project,
                        "mode": "fast",
                    }
                ),
            ],
            cwd=ROOT,
        )
        if code:
            return code
        for name in ("get_graph_schema", "get_architecture"):
            code = run(
                "cbm_followup_" + suffix + "_" + name,
                [*prefix, name, json.dumps({"project": project, "format": "json"})],
                cwd=ROOT,
            )
            if code:
                return code
        if suffix == "assets":
            for function in ("safe_sbom_sidecar", "safe_sbom_snapshot", "get_snapshot_sbom"):
                code = run(
                    "cbm_followup_trace_" + function,
                    [
                        *prefix,
                        "trace_path",
                        json.dumps(
                            {
                                "project": project,
                                "function_name": function,
                                "direction": "both",
                                "depth": 3,
                            }
                        ),
                    ],
                    cwd=ROOT,
                )
                if code:
                    return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
