"""Seal a bounded reviewer allowlist and record cleanup without opening any PG connection."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-E-R18-api-key-credential-review-1-recheck2.md"
LABELS = ("same_probe_recheck", "original_pg20", "new_pg4")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    release_rows = []
    for label in LABELS:
        row = json.loads((RUN / (label + ".json")).read_bytes())
        assert row["created"] and row["dropped"] and row["schemas_after_tests"] == 0
        assert row["other_owned_database_sessions_after_tests"] == 0
        assert not row["exact_dsn_or_password_in_raw"] and not row["exact_dsn_or_password_in_junit"]
        release_rows.append({"label": label, "started_at": row["started_at"], "ended_at": row["ended_at"],
            "owned_database": row["owned_database"], "schemas": 0, "other_sessions": 0, "dropped": True,
            "execution_exit": row["pytest_exit_code"], "receipt_sha256": sha(RUN / (label + ".json"))})
    initial_cleanup = json.loads((RUN / "initial_cleanup_receipt.json").read_bytes())
    assert initial_cleanup["exit_code"] == 0 and initial_cleanup["sessions_before"] == 0
    assert not initial_cleanup["exists_after"]
    (RUN / "pg_release_receipt.json").write_text(json.dumps({
        "verified_at": datetime.now().astimezone().isoformat(), "heavy_slot": "released to root",
        "scope": "each owned DB at original cleanup-query time; no new connection in seal",
        "pool": "NullPool; disposed", "forced_session_termination": False, "runs": release_rows,
        "initial_partial_failure_cleanup": initial_cleanup,
    }, indent=2)+"\n", encoding="utf-8")
    allowlist = [REPORT] + sorted(path for path in RUN.iterdir()
        if path.is_file() and path.name not in {"review_manifest.json", "final_secret_scan.json"})
    assert all(path.parent == RUN or path == REPORT for path in allowlist)
    reference = "D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi"
    decoded = subprocess.run([
        "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe",
        "-NoProfile", "-Command", "$r18Protected=Get-Content -LiteralPath '"+reference+"' -Raw; "
        "$r18Clear=$r18Protected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($r18Clear)",
    ], capture_output=True, timeout=15, check=True)
    original_text = json.loads(decoded.stdout)["TEST_DATABASE_URL"]
    original = make_url(original_text)
    assert original.host == "127.0.0.1" and original.port == 25432
    assert original.username and re.fullmatch(r"test_[a-z0-9_]+", original.username)
    sensitive = [original_text, original.password or "", original.set(database="postgres").render_as_string(hide_password=False)]
    for row in release_rows:
        assert re.fullmatch(r"test_dianzi_r18_rev_fix2_[0-9a-f]{32}", row["owned_database"])
        sensitive.append(original.set(database=row["owned_database"]).render_as_string(hide_password=False))
    assert re.fullmatch(r"test_dianzi_r18_rev_fix2_[0-9a-f]{32}", initial_cleanup["database"])
    sensitive.append(original.set(database=initial_cleanup["database"]).render_as_string(hide_password=False))
    hits = []
    for path in allowlist:
        raw = path.read_bytes()
        if any(value and value.encode() in raw for value in sensitive):
            hits.append(path.relative_to(ROOT).as_posix())
    assert not hits, "real runtime credential in reviewer artifact"
    (RUN / "final_secret_scan.json").write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(),
        "allowlist": [path.relative_to(ROOT).as_posix() for path in allowlist],
        "files_scanned": len(allowlist), "exact_original_owned_admin_dsn_or_password_matches": hits,
        "scope": "only declared reviewer report/run files; no broad scan or holdout read",
    }, indent=2)+"\n", encoding="utf-8")
    allowlist.append(RUN / "final_secret_scan.json")
    manifest = {"generated_at": datetime.now().astimezone().isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_commit": "8e0485231bf9367d5b4b3a79802bdf346b1fb745",
        "verdict": "Ship; limited credential seam; CI fix1 and post-lock expiry fix2 closed",
        "scope": "R18 credential seam only; no accepted or stage signature", "report_sha256": sha(REPORT),
        "files": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                   "size_bytes": path.stat().st_size} for path in sorted(allowlist)],
        "hash_mode": "reviewer working-tree raw bytes", "exclusions": ["manifest self-reference", "__pycache__"],
    }
    target = RUN / "review_manifest.json"
    target.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"manifest_sha256": sha(target), "report_sha256": sha(REPORT),
                      "files": len(allowlist), "exact_secret_matches": 0, "pg_slot": "released"}))


if __name__ == "__main__":
    main()
