"""Copy exact public-source discovery responses with original provenance for offline replay."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ORIGIN = Path(
    "C:/Users/yinha/.codex/worktrees/r06-src/dianzi/reports/runs/recovery_r06_source_preparation_20261015"
)
DESTINATION = Path(__file__).resolve().parent


def main() -> None:
    copied: list[dict[str, object]] = []
    for prefix in ("doh_05_trailofbits_feed", "doh_06_arxiv_ai_security"):
        for extension in ("body", "metadata.json"):
            source = ORIGIN / f"{prefix}.{extension}"
            destination = DESTINATION / source.name
            raw = source.read_bytes()
            if destination.exists():
                raise FileExistsError(destination)
            destination.write_bytes(raw)
            copied.append(
                {
                    "source": str(source),
                    "destination": destination.name,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    receipt = {
        "copied_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "usage": "internal offline replay; not new live requests or article/PDF fetches",
        "files": copied,
    }
    (DESTINATION / "sample_import.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
