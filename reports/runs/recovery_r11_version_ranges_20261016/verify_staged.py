"""Verify this manifest's files and staged Git blobs against their original filesystem bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def main() -> None:
    run_directory = Path(__file__).resolve().parent
    workspace = run_directory.parents[2]
    manifest_path = run_directory / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = []
    for artifact in manifest["artifacts"]:
        path = workspace / artifact["path"]
        original = path.read_bytes()
        assert len(original) == artifact["bytes"], path
        assert hashlib.sha256(original).hexdigest() == artifact["sha256"], path
        paths.append(path)
    paths.append(manifest_path)
    for path in paths:
        relative = path.relative_to(workspace).as_posix()
        blob = subprocess.run(
            ["git", "show", f":{relative}"],
            cwd=workspace,
            capture_output=True,
            check=True,
        ).stdout
        assert blob == path.read_bytes(), relative
    print(
        json.dumps(
            {
                "verified_files_including_manifest": len(paths),
                "mismatches": 0,
                "manifest_sha256": hashlib.sha256(
                    manifest_path.read_bytes()
                ).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
