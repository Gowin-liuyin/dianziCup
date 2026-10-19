"""Seal review artifacts and verify that the checked product files match the frozen commit."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-source-worker-review-1-recheck2.md"
BASE = "6dcce8b115ee3cb68bce814cf3f3ae91be9fcbf1"
PRODUCT = "1456e22f8187643a9978e9fa44d57c945e73b5bc"
CHECKOUT = "1456e22f8187643a9978e9fa44d57c945e73b5bc"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == CHECKOUT
paths = subprocess.check_output(["git", "diff", "--name-only", BASE, PRODUCT],
                                cwd=ROOT, text=True).splitlines()
files = []
for name in paths:
    frozen = subprocess.check_output(["git", "show", f"{PRODUCT}:{name}"], cwd=ROOT)
    current = (ROOT / name).read_bytes()
    expected_blob = subprocess.check_output(["git", "rev-parse", f"{PRODUCT}:{name}"],
                                            cwd=ROOT, text=True).strip()
    checkout_blob = subprocess.check_output(["git", "hash-object", f"--path={name}", name],
                                            cwd=ROOT, text=True).strip()
    assert expected_blob == checkout_blob, name
    if name.endswith("cac_generative_ai_20261015_public.html"):
        assert frozen == current, name
    files.append({"path": name, "sha256": digest(current), "bytes": len(current),
                  "frozen_git_blob": expected_blob, "checkout_filtered_git_blob": checkout_blob,
                  "raw_git_sha256": digest(frozen)})
artifacts = []
for path in sorted(RUN.iterdir()):
    if path.is_file() and not path.name.startswith(".") and path.suffix != ".pyc" and path.name != "evidence_manifest.json":
        raw = path.read_bytes()
        artifacts.append({"path": path.relative_to(ROOT).as_posix(),
                          "sha256": digest(raw), "bytes": len(raw)})
raw_report = REPORT.read_bytes()
artifacts.append({"path": REPORT.relative_to(ROOT).as_posix(),
                  "sha256": digest(raw_report), "bytes": len(raw_report)})
receipts = []
for path in sorted(RUN.glob("*.json")):
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and "argv" in value:
        receipts.append({key: value.get(key) for key in
                         ("label", "started_at", "ended_at", "exit_code", "tests",
                          "public_before", "public_after", "public_unchanged")})
manifest = {
    "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "review_status": "awaiting_review", "verdict": "Ship", "findings": [], "closed_findings": ["M1", "M2"],
    "reviewer": "/root/r06_source_worker_combined_independent_review",
    "worktree": str(ROOT), "branch": "codex/r06-source-worker-review-1-recheck2",
    "base_sha": BASE, "product_sha": PRODUCT, "checkout_sha": CHECKOUT,
    "product_git_objects_identical_to_frozen": True, "product_files": files,
    "report_sha256": digest(raw_report), "artifact_files": artifacts, "runs": receipts,
    "excluded_generated_files": ["**/__pycache__/**", "**/*.pyc", "mypy_cache/**", "CBM cache (external)", ".coverage_pure_frozen"],
    "commands": {"seal": [str(ROOT / "backend/.venv/Scripts/python.exe"), str(Path(__file__))]},
    "scope_exclusions": ["new source live", "frontend/browser", "model", "DPAPI",
                         "later polling code", "whole R06/G-C acceptance"],
}
target = RUN / "evidence_manifest.json"
assert not target.exists(), "evidence manifest must not be overwritten"
target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"report_sha256": manifest["report_sha256"],
                  "manifest_sha256": digest(target.read_bytes()), "artifacts": len(artifacts),
                  "product_files": len(files), "frozen_at": manifest["frozen_at"]},
                 ensure_ascii=False))
