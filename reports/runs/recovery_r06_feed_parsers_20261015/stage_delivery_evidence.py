"""Select only owned public evidence, keeping complete unknown-licence RSS and caches outside commits."""

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
    excluded = {"targeted_green.log", "targeted_green.xml"}
    chosen = [ROOT / "reports/tasks/R06-feed-parsers.md"]
    commands: list[dict[str, object]] = []
    for path in sorted(RUN.iterdir()):
        if (
            not path.is_file()
            or path.name in excluded
            or path.name.startswith(".coverage")
        ):
            continue
        if (
            path.suffix not in {".json", ".log", ".xml", ".gz", ".py", ".body"}
            and path.name != ".gitattributes"
        ):
            continue
        if path.name == "doh_05_trailofbits_feed.body":
            raise ValueError("complete unknown-licence RSS must never be staged")
        chosen.append(path)
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and "command" in value:
                commands.append(value)
    (RUN / "all_command_index.json").write_text(
        json.dumps(commands, indent=2), encoding="utf-8"
    )
    chosen.append(RUN / "all_command_index.json")
    entries = []
    for path in chosen:
        raw = path.read_bytes()
        licence = "project-generated report or diagnostic"
        if path.name == "doh_06_arxiv_ai_security.body":
            licence = "arXiv API metadata CC0 according to source preparation; no PDF"
        if path.name == "trailofbits_metadata_excerpt.xml":
            licence = "original full RSS unknown; facts and 9-word excerpt only, explicitly curated"
        if path.name.startswith("doh_") and path.suffix == ".json":
            licence = "project-generated public-source request metadata, no body"
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "licence_status": licence,
            }
        )
    receipt = RUN / "delivery_files.json"
    receipt.write_text(
        json.dumps(
            {
                "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
                    timespec="seconds"
                ),
                "file_count_without_self": len(entries),
                "total_bytes_without_self": sum(item["bytes"] for item in entries),
                "files": entries,
                "exclusions": {
                    "private_full_rss": "outside repository; hash/path in sample_storage_receipt.json",
                    "large_diagnostics": "raw originals retained locally; lossless gzip included",
                    "cache_and_coverage_binary": "not delivery evidence; not staged",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    chosen.append(receipt)
    paths = [path.relative_to(ROOT).as_posix() for path in chosen]
    subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True)
    print(
        json.dumps(
            {
                "staged_evidence_files": len(paths),
                "bytes_without_self": sum(item["bytes"] for item in entries),
                "private_full_rss_packaged": False,
                "exact_manifest": str(receipt),
            }
        )
    )


if __name__ == "__main__":
    main()
