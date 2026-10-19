"""Seal owned source, final evidence and credential checks without changing original materials."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from checks import credential_values

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE = (
    "backend/migrations/versions/0023_enrichment_input_audit.py",
    "backend/migrations/versions/0024_conversation_context.py",
    "backend/migrations/versions/0025_graph_projection.py",
    "backend/migrations/versions/0026_api_key_credentials.py",
    "backend/tests/contract/test_recovery_forward_migrations_0023_0026.py",
    "backend/tests/integration/test_recovery_forward_migrations_0023_0026_pg.py",
)


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def main() -> None:
    credentials = tuple(value.encode() for value in credential_values())
    source = []
    for relative in CODE:
        raw = (ROOT / relative).read_bytes()
        assert not any(value in raw for value in credentials), "credential scan rejected owned source"
        stored = git("show", f"HEAD:{relative}")
        assert raw.replace(b"\r\n", b"\n") == stored
        source.append({"path": relative, "sha256_raw": hashlib.sha256(raw).hexdigest(),
                       "sha256_git_lf": hashlib.sha256(stored).hexdigest(),
                       "git_blob": git("rev-parse", f"HEAD:{relative}").decode().strip()})
    assert git("diff", "--", "backend/src", "progress", ".gitattributes") == b""
    assert git("diff", "--cached", "--", "backend/src", "progress", ".gitattributes") == b""
    for item in json.loads((RUN / "frozen_inputs.json").read_text(encoding="utf-8")):
        with ZipFile(RUN / item["raw_archive"]) as archive:
            assert hashlib.sha256(archive.read(item["raw_archive_entry"])).hexdigest() == item["sha256_raw"]
        assert hashlib.sha256((RUN / item["snapshot"]).read_bytes()).hexdigest() in {
            item["sha256_raw"], item["sha256_git_lf"],
        }
    assert json.loads((RUN / "pg_2.json").read_text())["counts"] == {
        "tests": 60, "failures": 0, "errors": 0, "skipped": 0,
    }
    assert json.loads((RUN / "cleanup.json").read_text())["sessions_before_drop"] == 0
    artifacts = []
    paths = [*RUN.rglob("*"), ROOT / "reports/tasks/R07-R12-R10-R18-forward-migrations.md"]
    for path in sorted(paths):
        if not path.is_file() or path.name == "manifest.json" or "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        assert not any(value in raw for value in credentials), "credential scan rejected owned artifact"
        artifacts.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
                          "sha256_raw": hashlib.sha256(raw).hexdigest(),
                          "sha256_git_lf": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
    receipt = {
        "created_at": datetime.now().astimezone().isoformat(),
        "base": "456320b6c78e2936fd9f9767724ec3eb17f5c88b",
        "source_commit": git("rev-parse", "HEAD").decode().strip(),
        "source": source,
        "business_source_worktree_diff_bytes": 0,
        "business_source_cached_diff_bytes": 0,
        "protected_progress_gitattributes_diff_bytes": 0,
        "artifacts": artifacts,
        "manifest_excluded_from_own_hash": True,
        "artifact_inventory_scope": "files present at this timestamp; later sealing/git receipts are not retroactively covered",
        "credential_scan_actual_dsn_and_password_matches": 0,
        "verification": {"unit": "not_run", "contract": "passed", "integration": "passed",
                         "security": "passed", "frontend": "not_run", "e2e": "not_run",
                         "live": "not_run", "manual": "not_run", "pg_server_restart": "not_run"},
        "history_log_limitation": "pg_1 top-level log/xml/json retained; fixture artifact filenames reused by pg_2",
    }
    (RUN / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                       encoding="utf-8", newline="\n")
    print(json.dumps({"source_commit": receipt["source_commit"], "sources": len(source),
                      "artifacts": len(artifacts), "credential_matches": 0}))


if __name__ == "__main__":
    main()
