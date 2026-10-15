"""Fail before commit if any selected evidence differs from its archived original bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def main() -> None:
    manifest = json.loads((RUN / "delivery_files.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        blob = subprocess.check_output(["git", "show", ":" + item["path"]], cwd=ROOT)
        if hashlib.sha256(blob).hexdigest() != item["sha256"]:
            raise ValueError(f"evidence blob mismatch: {item['path']}")
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
    print(
        json.dumps(
            {
                "checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
                    timespec="seconds"
                ),
                "files_checked": len(manifest["files"]),
                "blob_hash_mismatches": 0,
                "code_sha": "6b7dd7e881bb822e83b55f8302f7aefe565f4940",
            }
        )
    )


if __name__ == "__main__":
    main()
