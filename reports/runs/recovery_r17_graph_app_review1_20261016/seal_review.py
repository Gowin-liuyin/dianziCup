"""Seal review artifacts as raw bytes, with separate LF text identifiers."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-E-R17-graph-app-review-1.md"
EXCLUDED = {"artifact_manifest.json", "artifact_manifest.sha256"}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def entry(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
        lf_sha256 = digest(raw.replace(b"\r\n", b"\n"))
    except UnicodeDecodeError:
        lf_sha256 = None
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "raw_sha256": digest(raw), "lf_text_sha256": lf_sha256}


def main() -> None:
    source_changes = subprocess.check_output(["git", "diff", "HEAD", "--name-only", "--", "frontend", "backend", "contracts", "progress", "tests", "fixtures"], cwd=ROOT).decode().splitlines()
    if source_changes:
        raise RuntimeError(f"Protected changes: {source_changes}")
    commands = [json.loads(line) for line in (RUN / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
    report_bytes = REPORT.read_bytes()
    (RUN / "report.sha256").write_text(f"{digest(report_bytes)}  {REPORT.relative_to(ROOT).as_posix()}\n", encoding="utf-8", newline="\n")
    files = sorted(path for path in RUN.rglob("*") if path.is_file() and path.name not in EXCLUDED)
    manifest = {"schema_version": 1, "review": "G-E-R17-graph-app-review-1", "verdict": "Ship", "scope": "default App frontend graph wiring only",
        "sealed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="milliseconds"),
        "code_git": "baa9fa7e024981f8a5516bd840e49910ce7cd1f9", "material_git": "164cae93ac888180b056a4c694011402ee387383",
        "author_manifest_sha256": "7231a79cc2142172dd4c0339483b4100a89fa849ffc7444c2ed7b4c429b97a2b",
        "backend_read_only_git": "08b141bd437c1de70a8435a1f7f6c448a131ed0d", "command_records": len(commands),
        "protected_changed_paths": source_changes, "report": entry(REPORT), "artifacts": [entry(path) for path in files],
        "limits": {"backend_pg_api_integration": "not_run", "live": "not_run", "whole_r17_manual": "not_run", "g_e_accepted": False},
        "hash_note": "Raw hashes identify sealed local bytes; report LF hash is separate because Git core.autocrlf can transform checkout bytes. The run-local .gitattributes preserves raw run bytes only."}
    raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    (RUN / "artifact_manifest.json").write_bytes(raw)
    (RUN / "artifact_manifest.sha256").write_text(f"{digest(raw)}  artifact_manifest.json\n", encoding="utf-8", newline="\n")
    print(json.dumps({"manifest_sha256": digest(raw), "report_sha256": digest(report_bytes), "artifacts": len(files), "command_records": len(commands)}))


if __name__ == "__main__":
    main()
