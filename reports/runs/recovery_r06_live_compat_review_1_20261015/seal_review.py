"""Seal exact reviewer artifacts and code identities without mutating product or status."""

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-live-compat-review-1.md"
CODE = "e900cd6b95dde7c6fe8d11d8c15122eb48a4acdc"
MATERIAL = "837fd22e655e6f2fb39eaf828e6ad91a78914ba4"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


started_at = now()
report = REPORT.read_text(encoding="utf-8")
report = re.sub(r"记录时间：2026-10-15T[0-9:+-]+。命令", "记录时间：" + started_at + "。命令", report, count=1)
REPORT.write_text(report, encoding="utf-8")
for args in [("rev-parse", "HEAD"), ("diff", "--name-only", "--", "backend/src", "backend/tests", "progress", "contracts")]:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", check=True)
    if args[0] == "rev-parse":
        assert result.stdout.strip() == MATERIAL
    else:
        assert not result.stdout.strip()
counts = {}
for file in sorted(RUN.glob("*.xml")):
    root = ET.parse(file).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    counts[file.name] = {field: sum(int(s.get(field, 0)) for s in suites) for field in ("tests", "failures", "errors", "skipped")}
for name in ("unit.xml", "contract_security.xml", "offline_inputs_recheck.xml", "handler_pg_recheck.xml", "pg_regression_serial.xml", "advisory_lock_namespace.xml"):
    assert all(counts[name][field] == 0 for field in ("failures", "errors", "skipped"))
assert sum(counts[name]["tests"] for name in ("unit.xml", "contract_security.xml", "offline_inputs_recheck.xml", "handler_pg_recheck.xml", "pg_regression_serial.xml", "advisory_lock_namespace.xml")) == 479
receipt = {"argv": [str(ROOT / "backend/.venv/Scripts/python.exe"), str(Path(__file__).resolve())], "cwd": str(ROOT),
           "started_at": started_at, "finished_at": now(), "exit_code": 0, "mode": "seal after all required scope checks; no product or state mutation"}
(RUN / "sealing_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
files = sorted([REPORT, *(f for f in RUN.iterdir() if f.is_file() and f.name not in {"immutable_manifest.json", "immutable_manifest.sha256"})])
artifacts = [{"path": str(file.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "size_bytes": file.stat().st_size} for file in files]
manifest = {"sealed_at": now(), "reviewer": "/root/r06_live_compat_independent_review", "base_sha": "1a52e17ffe327fb8a0c1d4f97372948a699910e3",
            "code_sha": CODE, "material_sha": MATERIAL, "worktree": str(ROOT), "branch": "codex/r06-live-compat-review-1", "verdict": "Ship",
            "verdict_scope": "only fixed release/AVID compatibility code package; no R06, T-card or G-C accepted",
            "product_or_state_changes": 0, "commits": 0, "pushes": 0, "external_requests": 0, "model_calls": 0, "measurement_calls": 0,
            "fee": "unknown", "real_pg_executed": True, "database": "test_dianzi_r06_catalog_worker_20261015", "final_distinct_passed_tests": 479,
            "junit_counts_including_failed_attempts": counts, "report_sha256": next(item["sha256"] for item in artifacts if item["path"].endswith("G-C-R06-live-compat-review-1.md")),
            "artifact_count": len(artifacts), "artifacts": artifacts,
            "excluded": ["manifest self and companion hash", "ignored Python caches", "source body bytes in external cache", "private connection file", "holdout", "product files unchanged and recorded separately in scope_audit.json"]}
path = RUN / "immutable_manifest.json"
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
digest = hashlib.sha256(path.read_bytes()).hexdigest()
(RUN / "immutable_manifest.sha256").write_text(digest + "  immutable_manifest.json\n", encoding="utf-8")
print(json.dumps({"sealed_at": manifest["sealed_at"], "verdict": "Ship", "report_sha256": manifest["report_sha256"], "manifest_sha256": digest,
                  "artifact_count": len(artifacts), "final_distinct_passed_tests": 479}))
