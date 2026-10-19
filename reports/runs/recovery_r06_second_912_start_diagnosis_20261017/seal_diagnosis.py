"""Seal diagnostic evidence and verify original runtime artifacts remained unchanged."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = Path("D:/dianzi")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    installation = json.loads(
        (ROOT / "reports/runs/r06_root_native_control_install_20261017/installation_receipt.json").read_bytes()
    )
    controls = [
        {
            "file": item["target"], "sha256": digest(Path(item["target"])),
            "matches_installed_candidate": digest(Path(item["target"])) == item["candidate_raw_sha256"],
        }
        for item in installation["files"]
    ]
    evidence = json.loads((RUN / "sanitized_actual_evidence.json").read_bytes())
    originals = [
        {"file": row["file"], "sha256": digest(Path(row["file"])),
         "matches_first_read": digest(Path(row["file"])) == row["sha256"]}
        for row in evidence["rows"] + evidence["logs"]
    ]
    syntax = []
    for path in sorted(RUN.glob("*.py")):
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        syntax.append(str(path))
    artifacts = [
        {"file": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(RUN.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    report = ROOT / "reports/tasks/R06-second-912-start-diagnosis.md"
    corrected_cwd = "D:/wt/r06-product-912-runtime-20261017/backend"
    record = {
        "sealed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "controls": controls, "originals": originals, "syntax_checked": syntax,
        "artifacts": artifacts, "report": {"file": str(report), "sha256": digest(report)},
        "metadata_corrections": [
            {"receipt": str(RUN / (label + ".command.json")), "field": "cwd",
             "actual_value": corrected_cwd,
             "reason": "Original copied runner recorded ROOT while its Popen uses ROOT/backend; original bytes preserved."}
            for label in ("cold_worker", "cold_beat", "cold_api")
        ],
        "paid_requests": 0, "live_reproduction": False,
        "source_or_database_started": False, "formal_six_hour_pass": False,
    }
    (RUN / "artifact_manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    controls_match = all(row["matches_installed_candidate"] for row in controls)
    originals_match = all(row["matches_first_read"] for row in originals)
    print(json.dumps({
        "controls": len(controls), "controls_match": controls_match,
        "originals": len(originals), "originals_match": originals_match,
        "syntax_checked": len(syntax), "artifacts": len(artifacts),
    }))
    raise SystemExit(0 if controls_match and originals_match else 1)


if __name__ == "__main__":
    main()
