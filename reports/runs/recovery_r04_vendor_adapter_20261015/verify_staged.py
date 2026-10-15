"""Check only this work package's four explicitly staged source files."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
expected = {
    "backend/src/ai_intel/ingestion/sources/vendor_advisories.py",
    "backend/tests/unit/test_r04_vendor_advisories.py",
    "fixtures/recorded/vllm_vendor_20261015_public.json",
    "fixtures/recorded/vllm_vendor_20261015_public.provenance.json",
}
staged = set(
    subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
    ).splitlines()
)
assert staged == expected
files = []
secret_pattern = re.compile(rb"(?:sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
for path in sorted(staged):
    body = subprocess.check_output(["git", "show", f":{path}"], cwd=root)
    assert len(body) < 2_000_000
    assert secret_pattern.search(body) is None
    files.append({"path": path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    if path.endswith("vllm_vendor_20261015_public.json"):
        assert hashlib.sha256(body).hexdigest() == (
            "f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf"
        )
coverage = json.loads((Path(__file__).parent / "pure_unit_coverage.json").read_bytes())
assert coverage["totals"]["percent_covered"] >= 60
receipt = {
    "checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "staged_files": files,
    "generic_secret_pattern_matches": 0,
    "actual_secret_store_scan": "not_run; root integrator must perform its authorized scan",
    "pure_unit_raw_coverage": coverage["totals"],
    "note": "source fixture index bytes match recorded HTTP bytes exactly",
}
(Path(__file__).parent / "source_freeze_check.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({"staged_file_count": len(files), "raw_coverage": coverage["totals"]}))
