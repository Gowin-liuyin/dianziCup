"""Compare authorized in-memory secret values with repository bytes without revealing matches."""

import hashlib
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
envelope = os.environ.pop("DIANZI_PRIVATE_SCAN_VALUES_JSON", None)
if envelope is None:
    raise SystemExit("authorized private scan input missing")
secret_values = json.loads(envelope)
assert isinstance(secret_values, list) and all(isinstance(value, str) and len(value) >= 8 for value in secret_values)
needles = set()
for value in secret_values:
    needles.add(value.encode("utf-8"))
    needles.add(json.dumps(value, ensure_ascii=True)[1:-1].encode("ascii"))
    needles.add(value.encode("utf-16-le"))
excluded = {".git", ".venv", "node_modules", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
forbidden_names = {".env", "keys-and-usage"}
matches = []
blocked = []
files_checked = 0
zip_members_checked = 0
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in excluded for part in path.relative_to(ROOT).parts):
        continue
    relative = path.relative_to(ROOT).as_posix()
    if any(part.lower() in forbidden_names or part.lower().startswith("keys-and-usage.") or part.lower() == "holdout" for part in path.relative_to(ROOT).parts):
        blocked.append({"path": relative, "reason": "excluded secret material or holdout boundary"})
        continue
    raw = path.read_bytes()
    files_checked += 1
    hits = sum(needle in raw for needle in needles)
    if hits:
        matches.append({"path": relative, "file_sha256": hashlib.sha256(raw).hexdigest(), "exact_value_forms_matched": hits})
    if relative == "fixtures/synthetic/security/r20_secret_provenance_20261016.zip":
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                assert member.file_size <= 2 * 1024 * 1024
                member_raw = archive.read(member)
                zip_members_checked += 1
                member_hits = sum(needle in member_raw for needle in needles)
                if member_hits:
                    matches.append({"path": relative, "member_sha256": hashlib.sha256(member_raw).hexdigest(), "exact_value_forms_matched": member_hits})
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files_checked": files_checked, "zip_members_checked": zip_members_checked, "authorized_secret_count": len(secret_values), "representation_count": len(needles), "exact_value_matches": matches, "excluded_boundaries": blocked, "scope": "known authorized DPAPI secret values in child memory; not a replacement for provenance/pattern/asset/holdout review", "raw_values_printed_or_saved": False}
(RUN / "known_secret_values_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files_checked": files_checked, "zip_members_checked": zip_members_checked, "known_secret_count": len(secret_values), "exact_value_matches": len(matches), "excluded_boundaries": len(blocked), "values_printed": False}))
raise SystemExit(1 if matches else 0)
