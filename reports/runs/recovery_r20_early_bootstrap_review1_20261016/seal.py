"""Seal reviewer report and exact raw bytes without modifying reviewed sources."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from review_runner import CODE, MATERIAL, ROOT, RUN, SOURCES, now, write_json

REPORT = ROOT / "reports/reviews/recovery/G-F-R20-early-bootstrap-review-1.md"


def raw_identity(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_git_blob_sha1": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
            "crlf_count": raw.count(b"\r\n"), "lf_count": raw.count(b"\n")}


def main() -> None:
    original_diff = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True)
    assert original_diff == ""
    source_identities = json.loads((RUN / "source_identity.json").read_text())
    for row in source_identities["sources"]:
        assert raw_identity(ROOT / row["path"])["raw_sha256"] == row["raw_sha256"]
    summary = json.loads((RUN / "execution_summary.json").read_text())
    assert summary["primary_count"] == 12 and summary["all_observed_signaled"]
    assert all(row["final"]["success"] and row["final"]["win32_error"] == 0 for row in summary["owned_process_instances"])
    paths = [REPORT]
    for path in RUN.rglob("*"):
        if not path.is_file() or path.name in ("artifact_manifest.json", "manifest_identity.json"):
            continue
        if any(part.endswith(("_cache", "_temp")) or part == "__pycache__" for part in path.relative_to(RUN).parts):
            continue
        paths.append(path)
    rows = [raw_identity(path) for path in sorted(paths)]
    manifest = {"sealed_at": now(), "code_sha": CODE, "material_sha": MATERIAL,
                "root": str(ROOT), "artifact_count": len(rows), "artifacts": rows,
                "source_changes": [], "primary_count": 12,
                "excluded_scratch": ["*_cache/", "*_temp/", "__pycache__/"],
                "git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)}
    write_json("artifact_manifest.json", manifest)
    identity = raw_identity(RUN / "artifact_manifest.json")
    identity.update(sealed_at=now(), artifact_count=len(rows), report_raw_sha256=raw_identity(REPORT)["raw_sha256"])
    write_json("manifest_identity.json", identity)
    print(json.dumps(identity))
    for row in rows:
        assert raw_identity(ROOT / row["path"]) == row
    print("verified all sealed raw byte identities")


if __name__ == "__main__":
    main()
