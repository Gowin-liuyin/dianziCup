"""Preserve failed logs losslessly and create a bounded evidence inventory."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
ZONE = timezone(timedelta(hours=8))


def main() -> int:
    if (RUN / "evidence_seal.json").exists():
        raise RuntimeError("Evidence seal already exists")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip()
    archives = []
    for name in ("focused_post_implementation.log", "focused_post_implementation.junit.xml"):
        path = RUN / name
        raw = path.read_bytes()
        archived = gzip.compress(raw, mtime=0)
        target = RUN / (name + ".gz")
        target.write_bytes(archived)
        assert gzip.decompress(target.read_bytes()) == raw
        archives.append(
            {
                "original_path": name,
                "original_size_bytes": len(raw),
                "original_sha256": hashlib.sha256(raw).hexdigest(),
                "archive_path": target.name,
                "archive_size_bytes": len(archived),
                "archive_sha256": hashlib.sha256(archived).hexdigest(),
                "original_retained_untracked": True,
            }
        )
    (RUN / "lossless_failure_archives.json").write_text(
        json.dumps(archives, indent=2) + "\n", encoding="utf-8"
    )
    counts = []
    for path in sorted(RUN.glob("*.junit.xml")):
        suites = list(ET.parse(path).getroot().iter("testsuite"))
        cases = list(ET.parse(path).getroot().iter("testcase"))
        counts.append(
            {
                "path": path.name,
                "tests": sum(int(suite.get("tests", "0")) for suite in suites),
                "failures": sum(int(suite.get("failures", "0")) for suite in suites),
                "errors": sum(int(suite.get("errors", "0")) for suite in suites),
                "skipped": sum(int(suite.get("skipped", "0")) for suite in suites),
                "case_layers": {
                    layer: sum(case.get("classname", "").startswith("tests." + layer + ".") for case in cases)
                    for layer in ("unit", "contract", "security")
                },
            }
        )
    (RUN / "test_counts.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    ignored = {entry["original_path"] for entry in archives}
    files = []
    for path in sorted(RUN.iterdir()):
        if path.is_file() and path.name not in ignored and path.name != "evidence_seal.json":
            raw = path.read_bytes()
            files.append({"path": path.name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    record = {
        "created_at": datetime.now(ZONE).isoformat(timespec="seconds"),
        "code_sha": sha,
        "code_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=WORKTREE, text=True).strip(),
        "scope": "R06-B isolated adapter candidate; no product live acceptance",
        "archives": archives,
        "files": files,
    }
    (RUN / "evidence_seal.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"created_at": record["created_at"], "sha": sha, "files": len(files), "test_counts": counts}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
