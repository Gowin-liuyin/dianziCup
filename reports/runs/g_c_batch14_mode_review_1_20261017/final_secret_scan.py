"""Scan this review's local delivery bytes with memory-only authorized PostgreSQL references."""

import hashlib
import json
import sys
from pathlib import Path

import review_checks

ROOT, RUN = review_checks.ROOT, review_checks.RUN
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend/src"))
from tests.integration.test_r01_migration_engine_disposal_pg import load_parent_url


def main():
    started = review_checks.checks.now()
    url = load_parent_url()
    values = {url.render_as_string(hide_password=False), url.set(drivername="postgresql").render_as_string(hide_password=False), url.password or ""}
    for receipt in RUN.glob("*pg_controller.command.json"):
        database = json.loads(receipt.read_bytes())["database"]
        values.add(url.set(database=database, query={}).render_as_string(hide_password=False))
    fragments = {(url.password or "")[offset:offset + 8] for offset in range(max(0, len(url.password or "") - 7))}
    files = [path for path in RUN.rglob("*") if path.is_file() and path.suffix != ".pyc"]
    report = ROOT / "reports/reviews/recovery/G-C-batch14-revision-mode-review-1.md"
    reports = list(report.parent.glob("G-C-batch14-revision-mode-review-1*.md"))
    files.extend(reports)
    hits = []
    for path in files:
        raw = path.read_bytes()
        if any(value and value.encode() in raw for value in values) or any(fragment.encode() in raw for fragment in fragments):
            hits.append(str(path.relative_to(ROOT)))
    record = {"started_at": started, "ended_at": review_checks.checks.now(), "files_scanned": len(files), "credential_reference_loaded_memory_only": True, "pg_connections_opened": 0, "exact_dsn_password_or_8char_fragment_hits": hits, "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "report_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in reports}, "source_sha": review_checks.checks.QUALIFIED}
    label = sys.argv[1] if len(sys.argv) > 1 else "final_secret_scan"
    (RUN / (label + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))
    raise SystemExit(bool(hits))


if __name__ == "__main__":
    main()
