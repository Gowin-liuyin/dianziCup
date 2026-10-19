"""Freeze only this fix's records and verify source, old evidence and Git raw bytes."""

import gzip
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/tasks/R17-sbom-workbench-fix1.md"
SOURCE = "18d05f1c5842ed7a57f3be9f0351ede4af0b018a"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if git("rev-parse", "HEAD").decode().strip() != SOURCE or git("diff", "--cached", "--name-only"):
    raise RuntimeError("unexpected material baseline/staging")
if git("diff", "--name-only", SOURCE, "--", "frontend/src", "frontend/tests", "frontend/e2e"):
    raise RuntimeError("source changed after frozen checks")
raw_diff = (RUN / "source_change.diff").read_bytes()
(RUN / "source_change.diff.gz").write_bytes(gzip.compress(raw_diff, mtime=0))
receipt = json.loads((RUN / "source_receipt.json").read_text())
proof = []
for name in receipt["source_files"]:
    frozen = git("show", SOURCE + ":" + name)
    raw = (ROOT / name).read_bytes()
    if frozen.replace(b"\r\n", b"\n") != raw.replace(b"\r\n", b"\n"):
        raise RuntimeError("source LF drift")
    proof.append({"path": name, "git_lf_sha256": digest(frozen), "worktree_raw_sha256": digest(raw), "lf_equal": True})
(RUN / "source_byte_proof.json").write_text(json.dumps({"source_sha": SOURCE, "files": proof, "diff_raw_sha256": digest(raw_diff), "diff_gzip_lossless": gzip.decompress((RUN / "source_change.diff.gz").read_bytes()) == raw_diff}, indent=2) + "\n", encoding="utf-8", newline="\n")
dist = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path.read_bytes())} for path in sorted((ROOT / "frontend/dist").rglob("*")) if path.is_file()]
(RUN / "dist_byte_proof.json").write_text(json.dumps({"source_sha": SOURCE, "files": dist, "build_not_committed": True}, indent=2) + "\n", encoding="utf-8", newline="\n")
excluded = {"raw_manifest.json", "raw_manifest.sha256", "source_change.diff", "material_receipt.json", "material_commit.log", "git_byte_audit.json"}
members = [REPORT] + [path for path in sorted(RUN.rglob("*")) if path.is_file() and path.name not in excluded and path.suffix != ".pyc" and "__pycache__" not in path.parts]
for path in members:
    if any(re.search(pattern, path.read_bytes()) for pattern in (rb"sk-[A-Za-z0-9]{24,}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")):
        raise RuntimeError("unclassified credential-like value")
now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
manifest = {"run_id": RUN.name, "created_at": now, "source_sha": SOURCE, "baseline_sha": "7a653880af12e4160ca8edf26fccbaf5d1e6f0f0", "data_mode": "synthetic_isolated", "status": "awaiting_review",
            "report_sha256": digest(REPORT.read_bytes()), "members": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path.read_bytes())} for path in members],
            "policy_exclusions": ["postcommit receipts/audit (no self-hash loop)", "source_change.diff (identical bytes committed as gzip)", "node_modules/dist/tsbuildinfo/generated cache"],
            "prior_author_120_review_272_hash_drift": 0, "product_credentials_loaded": 0, "paid_model_provider_calls": 0,
            "synthetic_uri_strings_are_test_values": True}
manifest_path = RUN / "raw_manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
manifest_hash = digest(manifest_path.read_bytes())
(RUN / "raw_manifest.sha256").write_text(manifest_hash + "\n", encoding="utf-8", newline="\n")
paths = [path.relative_to(ROOT).as_posix() for path in members] + [manifest_path.relative_to(ROOT).as_posix(), (RUN / "raw_manifest.sha256").relative_to(ROOT).as_posix()]
git("add", "--", *paths)
if set(git("diff", "--cached", "--name-only").decode().splitlines()) != set(paths):
    raise RuntimeError("material ownership mismatch")
check = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, capture_output=True)
if check.returncode:
    (RUN / "material_check_failed.log").write_bytes(check.stdout + check.stderr)
    print(json.dumps({"material_check_exit": check.returncode, "raw_failure_bytes": len(check.stdout) + len(check.stderr)}))
    raise SystemExit(check.returncode)
result = subprocess.run(["git", "commit", "-m", "G-E R17 preserve PURL Must red reproduction and source-frozen fix evidence"], cwd=ROOT, capture_output=True)
(RUN / "material_commit.log").write_bytes(result.stdout + result.stderr)
if result.returncode:
    raise SystemExit(result.returncode)
material = git("rev-parse", "HEAD").decode().strip()
audits = []
for name in paths:
    frozen = git("show", material + ":" + name)
    raw = (ROOT / name).read_bytes()
    if frozen != raw:
        raise RuntimeError("raw differs from committed material")
    audits.append({"path": name, "sha256": digest(frozen), "raw_equals_git_blob": True})
(RUN / "git_byte_audit.json").write_text(json.dumps({"material_sha": material, "files": audits, "mismatches": 0}, indent=2) + "\n", encoding="utf-8", newline="\n")
output = {"source_sha": SOURCE, "material_sha": material, "manifest_sha256": manifest_hash, "manifest_members": len(members), "raw_git_matching_files": len(paths), "report_sha256": manifest["report_sha256"], "frozen_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "diff_check_exit": check.returncode, "status": "awaiting_review", "push": "not_run"}
(RUN / "material_receipt.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(output))
