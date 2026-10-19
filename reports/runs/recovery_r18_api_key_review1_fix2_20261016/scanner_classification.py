"""Classify retained scan shapes before runtime decryption, without changing scanner policy."""

import json
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
sys.path.insert(0, str(ROOT))
from scripts.security_scan import SAFE_CATEGORIES, load_fixture_classifications, scan_repository

old = {
    "frontend/src/features/assets/asset-client.test.ts",
    "frontend/src/features/assets/asset-scope.test.tsx",
    "reports/runs/recovery_r07_idempotency_scope_20261016/probes/test_independent_idempotency_scope.py",
    "reports/runs/recovery_r07_idempotency_scope_20261016/red_064015.log",
    "reports/runs/recovery_r07_idempotency_scope_20261016/red_064241.log",
    "reports/runs/recovery_r17_assets_workbench_fix1_20261016/scope_unit_red.log",
}
copies = {
    "reports/runs/recovery_r18_api_key_expiry_fix2_20261016/independent_pg_probe.py",
    "reports/runs/recovery_r18_api_key_review1_fix2_20261016/independent_pg_probe.py",
}
classifications = load_fixture_classifications(ROOT, ROOT / "reports/security/recovery_fixture_false_positives.json")
findings = [entry for entry in scan_repository(ROOT, classifications) if entry.category not in SAFE_CATEGORIES]
rows = []
for entry in findings:
    assert entry.path in old | copies
    row = {"path": entry.path, "pattern_id": entry.pattern_id, "category": entry.category}
    if entry.path in old:
        base = subprocess.check_output(["git", "show", "cd91b875:" + entry.path], cwd=ROOT)
        row["original_baseline_unchanged"] = base.replace(b"\r\n", b"\n") == (ROOT / entry.path).read_bytes().replace(b"\r\n", b"\n")
        assert row["original_baseline_unchanged"]
    else:
        original = Path("D:/wt/r18-api-key-review1-fix1/reports/runs/recovery_r18_api_key_review1_fix1_20261016/independent_pg_probe.py").read_bytes()
        row["frozen_synthetic_probe_copy"] = (ROOT / entry.path).read_bytes().replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n")
        assert row["frozen_synthetic_probe_copy"]
    rows.append(row)
(RUN / "scanner_observation.json").write_text(json.dumps({"rejected": len(rows), "findings": rows,
    "status": "failed retained; no policy, classification or findings changed",
    "phase": "before reviewer DPAPI decode or PG use"}, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"rejected": len(rows), "original_baseline": sum(entry["path"] in old for entry in rows),
                  "copied_synthetic_probe": sum(entry["path"] in copies for entry in rows)}))
