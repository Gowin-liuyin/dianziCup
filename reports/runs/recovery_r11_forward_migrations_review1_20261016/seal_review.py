"""Seal independent raw evidence and scan actual authorized resource values in memory."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from review_checks import DATABASE, ROOT, RUN, database_reference, now
from sqlalchemy.engine import make_url

REPORT = ROOT / "reports/reviews/recovery/G-D-R11-forward-migrations-review-1.md"
MATERIAL = "569d8a7dc81fcea6b524b4fa172a5c7977388b93"
CODE = "2fe903eaff4030b64b3f5789e8027e1e11e41694"


def git_blob(reference, name):
    result = subprocess.run(
        ["git", "show", reference + ":" + name],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0
    return result.stdout


def main():
    started_at = now()
    url = make_url(database_reference())
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, "test_dianzi_r01_20261014")
    assert url.username and url.username.startswith("test_") and url.password
    password = url.password.encode()
    dsns = [
        url.render_as_string(hide_password=False).encode(),
        url.set(database=DATABASE).render_as_string(hide_password=False).encode(),
    ]
    audit = json.loads((RUN / "material_validation_frozen.json").read_text())
    excluded = {"__pycache__", "mypy-cache"}
    owned = [
        path
        for path in RUN.rglob("*")
        if path.is_file()
        and not excluded.intersection(path.parts)
        and path.name not in {"review_manifest.json", "review_manifest.sha256"}
    ]
    names = {
        item["path"]
        for item in audit["source_results"] + audit["artifact_results"] + audit["old_results"]
    }
    scan_paths = {*(ROOT / name for name in names), *owned, REPORT}
    password_matches, dsn_matches = [], []
    for path in sorted(scan_paths):
        raw = path.read_bytes()
        if password in raw:
            password_matches.append(str(path.relative_to(ROOT)))
        if any(value in raw for value in dsns):
            dsn_matches.append(str(path.relative_to(ROOT)))
    blob_count = 0
    blob_matches = []
    for reference, entries in (
        (CODE, audit["source_results"]),
        (MATERIAL, audit["artifact_results"]),
    ):
        for item in entries:
            raw = git_blob(reference, item["path"])
            blob_count += 1
            if password in raw or any(value in raw for value in dsns):
                blob_matches.append(item["path"])
    result = {
        "scanned_at": now(),
        "raw_files_scanned": len(scan_paths),
        "frozen_blobs_scanned": blob_count,
        "actual_password_match_count": len(password_matches),
        "actual_dsn_match_count": len(dsn_matches),
        "frozen_blob_match_count": len(blob_matches),
        "matched_paths": sorted(set(password_matches + dsn_matches + blob_matches)),
        "excluded": ["mypy-cache/", "__pycache__/", "private DPAPI reference contents"],
    }
    (RUN / "actual_secret_scan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not result["matched_paths"]
    (RUN / "seal_phase_receipt.json").write_text(
        json.dumps(
            {
                "command": [sys.executable, *sys.argv],
                "cwd": str(Path.cwd()),
                "started_at": started_at,
                "scan_finished_at": now(),
                "phase": "actual_scan_passed_before_raw_manifest_write",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    owned.append(RUN / "seal_phase_receipt.json")
    members = []
    for path in sorted([*owned, RUN / "actual_secret_scan.json", REPORT]):
        if any(item["path"] == str(path.relative_to(ROOT)).replace("\\", "/") for item in members):
            continue
        raw = path.read_bytes()
        members.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    report_sha = hashlib.sha256(REPORT.read_bytes()).hexdigest()
    manifest = {
        "created_at": now(),
        "baseline": audit["baseline"],
        "code": CODE,
        "material": MATERIAL,
        "review_commit": None,
        "report_sha256": report_sha,
        "scope": "R11/G-D production forward 0021/0022 migrations only",
        "members": members,
    }
    raw = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    (RUN / "review_manifest.json").write_bytes(raw)
    manifest_sha = hashlib.sha256(raw).hexdigest()
    (RUN / "review_manifest.sha256").write_text(manifest_sha + "\n", encoding="ascii")
    print(
        json.dumps(
            {
                "report_sha256": report_sha,
                "manifest_sha256": manifest_sha,
                "members": len(members),
                "actual_secret_scan": result,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
