"""Collect safe occurrence metadata using the existing scanner's candidate boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
scanner_spec = importlib.util.spec_from_file_location("security_scan", ROOT / "scripts/security_scan.py")
assert scanner_spec is not None and scanner_spec.loader is not None
security_scan = importlib.util.module_from_spec(scanner_spec)
sys.modules[scanner_spec.name] = security_scan
scanner_spec.loader.exec_module(security_scan)

RUN = Path(__file__).resolve().parent


def inspect_candidates() -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    table = ROOT / "reports/security/recovery_fixture_false_positives.json"
    classifications = security_scan.load_fixture_classifications(ROOT, table)
    reviewed = set(classifications)
    metadata = []
    file_snapshots = []
    for relative_root in security_scan.SCAN_ROOTS:
        source_root = ROOT / relative_root
        if not source_root.exists():
            continue
        for source_path in sorted(source_root.rglob("*")):
            if not source_path.is_file() or source_path.suffix not in security_scan.SCAN_SUFFIXES:
                continue
            relative_path = source_path.relative_to(ROOT).as_posix()
            checked_path = security_scan._canonical_path(ROOT, relative_path)
            raw = checked_path.read_bytes()
            raw_sha = hashlib.sha256(raw).hexdigest()
            content = raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
            unclassified_file = False
            for pattern_id, pattern in security_scan.PATTERNS.items():
                for match in pattern.finditer(content):
                    matched_text = match.group(0)
                    quote_start = min(index for index, character in enumerate(matched_text) if character in "\"'")
                    matched_value = matched_text[quote_start + 1:-1]
                    item = security_scan.FixtureClassification(relative_path, raw_sha, pattern_id, match.start(), match.end(), matched_value)
                    category = "unclassified_credential_shape"
                    if item in reviewed:
                        category = "verified_synthetic_fixture"
                    elif pattern_id == "original_secret_value_pattern":
                        if matched_value in security_scan.DOCUMENTED_DEV_PLACEHOLDERS:
                            category = "documented_dev_placeholder"
                        elif source_path.suffix == ".py" and security_scan.is_public_authentication_failure_comparison(content, content[:match.start()].count("\n") + 1):
                            if matched_value == "password authentication failed":
                                category = "public_failure_comparison"
                    if category in security_scan.SAFE_CATEGORIES:
                        continue
                    unclassified_file = True
                    line = content[:match.start()].count("\n") + 1
                    metadata.append({"path":relative_path,"pattern_id":pattern_id,"start":match.start(),"end":match.end(),"line":line,"raw_sha256":raw_sha,"match_sha256":hashlib.sha256(matched_value.encode()).hexdigest(),"category":category})
            if unclassified_file:
                file_snapshots.append({"path":relative_path,"sha256":raw_sha,"observed_at":datetime.now(timezone.utc).isoformat(),"mtime_ns":checked_path.stat().st_mtime_ns,"bytes":len(raw)})
    head = subprocess.check_output(["git", "rev-parse", "HEAD"],cwd=ROOT,text=True).strip()
    result = {"started_at":started_at,"ended_at":datetime.now(timezone.utc).isoformat(),"head":head,"exact_secret_scan":"not_run","manifest_sha256":hashlib.sha256(table.read_bytes()).hexdigest(),"existing_record_count":len(classifications),"unclassified_count":len(metadata),"path_count":len(file_snapshots),"by_path":dict(Counter(item["path"] for item in metadata)),"file_snapshots":file_snapshots,"occurrences":metadata}
    (RUN / "unclassified_metadata.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("started_at","ended_at","head","exact_secret_scan","manifest_sha256","existing_record_count","unclassified_count","path_count","by_path")},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    inspect_candidates()
