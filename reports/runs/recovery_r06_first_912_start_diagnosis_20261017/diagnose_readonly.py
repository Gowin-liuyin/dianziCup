"""Extract only approved static error fields; no application import or connection."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
CORE = Path("D:/dianzi-runtime-cache/r06-f3-core-20261017")
OPS = Path("D:/dianzi-runtime-cache/r06-f3-ops-20261017")
ZONE = ZoneInfo("Asia/Shanghai")


def main() -> None:
    started = datetime.now(ZONE).isoformat()
    reasons = []
    for directory in (CORE, OPS):
        for source in directory.glob("*.py"):
            reasons.extend(
                re.findall(
                    r"raise\s+(?:RuntimeError|ValueError|TypeError|OSError|OwnershipError)"
                    r"\([\"']([^\"']+)[\"']\)",
                    source.read_text(encoding="utf-8"),
                )
            )
    rows = []
    for directory in (CORE, OPS):
        for path in sorted(directory.glob("*.log")):
            raw = path.read_bytes()
            content = raw.decode("utf-8", errors="replace")
            frames = []
            for match in re.finditer(
                r'File "([^"\n]+)", line (\d+)(?:, in ([A-Za-z_][A-Za-z_0-9<>]*))?',
                content,
            ):
                module = Path(match.group(1)).name
                if module.endswith(".py"):
                    frames.append(
                        {
                            "module_file": module,
                            "line": int(match.group(2)),
                            "function": match.group(3),
                        }
                    )
            rows.append(
                {
                    "file": str(path),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "frames": frames,
                    "error_types": sorted(
                        set(re.findall(r"(?m)^([A-Za-z_][\w.]*(?:Error|Exception))\s*:", content))
                    ),
                    "missing_module_identifiers": re.findall(
                        r"ModuleNotFoundError: No module named '([A-Za-z_][A-Za-z_0-9.]*)'",
                        content,
                    ),
                    "known_static_reasons": [reason for reason in reasons if reason in content],
                }
            )
    for directory, names in (
        (CORE, ("owned_stop_failure.json",)),
        (OPS, ("guardian_start.json", "guardian_end.json", "minio_start.json", "minio_end.json", "minio_controller_end.json", "source_identity.json")),
    ):
        for name in names:
            path = directory / name
            raw = path.read_bytes()
            content = json.loads(raw)
            rows.append(
                {
                    "file": str(path),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "fields": {
                        key: content[key]
                        for key in (
                            "reason", "started_at", "ended_at", "formal_six_hour_pass",
                            "actual_actor_stop", "actual_source_kernel_exit_ack", "exit_code",
                            "guardian_pid", "launcher_pid", "actual_pid", "creation_ticks",
                            "target_empty", "whole_tree_cleanup_guaranteed", "error_types",
                            "helper_pidfd_kernel_exit_ack", "emergency_kernel_empty_ack",
                        )
                        if key in content
                    },
                }
            )
    result = {
        "started_at": started,
        "ended_at": datetime.now(ZONE).isoformat(),
        "scope": "static exception identifiers, module frames, known source reasons and selected lifecycle fields only",
        "rows": rows,
        "ready_directory_exists": (CORE / "control").exists(),
        "runtime_start_exists": (CORE / "runtime_start.json").exists(),
        "runtime_end_exists": (CORE / "runtime_end.json").exists(),
    }
    (RUN / "sanitized_actual_evidence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"rows": len(rows), "ready_directory_exists": result["ready_directory_exists"], "runtime_start_exists": result["runtime_start_exists"], "runtime_end_exists": result["runtime_end_exists"]}))


if __name__ == "__main__":
    main()
