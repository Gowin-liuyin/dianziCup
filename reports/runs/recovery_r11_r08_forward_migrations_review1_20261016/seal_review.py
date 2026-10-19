"""Freeze reviewer raw artifacts and report; avoid self-referential checksums."""

import hashlib
import json
import subprocess
from pathlib import Path

from review_runner import ROOT, RUN, now

REPORT = "reports/reviews/recovery/G-D-R11-R08-forward-migrations-review-1.md"


def digest(path):
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "length": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def main():
    started = now()
    changed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "HEAD",
            "--",
            "backend",
            "contracts",
            "fixtures",
            "progress",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    assert changed == b""
    files = [
        digest(path)
        for path in sorted(RUN.rglob("*"))
        if path.is_file()
        and path.name not in {"artifact_manifest.json", "freeze_receipt.json"}
        and "__pycache__" not in path.parts
    ]
    files.append(digest(ROOT / REPORT))
    manifest = {
        "sealed_at": now(),
        "code_sha": "c842333fe56a4ab3018a3216a8ddcd6a34639ae1",
        "material_sha": "99fec14d1a64f9c5adaa5beb294e804da3e1d18d",
        "basis": "raw file bytes; manifest and receipt excluded to avoid circular hashes",
        "files": files,
    }
    target = RUN / "artifact_manifest.json"
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for entry in files:
        assert digest(ROOT / entry["path"]) == entry
    receipt = {
        "started_at": started,
        "finished_at": now(),
        "exit_code": 0,
        "frozen_files": len(files),
        "manifest": digest(target),
        "report": digest(ROOT / REPORT),
        "command": [str(ROOT / "backend/.venv/Scripts/python.exe"), str(Path(__file__).resolve())],
        "cwd": str(ROOT),
        "source_tests_contracts_progress_changes": 0,
    }
    (RUN / "freeze_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
