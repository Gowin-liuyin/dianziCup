"""Keep failed diagnostics losslessly without packaging oversized raw parameter IDs."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent


def main() -> None:
    receipts: list[dict[str, object]] = []
    for name in ("targeted_green.log", "targeted_green.xml"):
        source = RUN / name
        original = source.read_bytes()
        archive = RUN / f"{name}.gz"
        if archive.exists():
            raise FileExistsError(archive)
        archived = gzip.compress(original, mtime=0)
        archive.write_bytes(archived)
        assert gzip.decompress(archived) == original
        receipts.append(
            {
                "original_path": str(source),
                "original_bytes": len(original),
                "original_sha256": hashlib.sha256(original).hexdigest(),
                "archive": archive.name,
                "archive_bytes": len(archived),
                "archive_sha256": hashlib.sha256(archived).hexdigest(),
                "original_retained_locally": True,
            }
        )
    (RUN / "large_diagnostic_archives.json").write_text(
        json.dumps(
            {
                "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
                    timespec="seconds"
                ),
                "archives": receipts,
                "reason": "Windows pytest parameter ID length failures retained",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
