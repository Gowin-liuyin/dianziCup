"""Seal byte hashes for the independent review without staging or changing Git attributes."""

import datetime
import hashlib
import json
import subprocess

from review_run import ROOT, RUN

report = ROOT / "reports/reviews/recovery/G-C-R07-single-model-dimension-review-1.md"
paths = sorted(path for path in RUN.iterdir() if path.is_file() and
               path.name not in {"review_manifest.json", "review_manifest.sha256"}) + [report]
entries = []
for path in paths:
    raw = path.read_bytes()
    entries.append({"path": path.relative_to(ROOT).as_posix(), "raw_size_bytes": len(raw),
                    "raw_sha256": hashlib.sha256(raw).hexdigest()})
source_paths = subprocess.check_output(["git", "diff", "--name-only", "63e4caf", "d8a3189"], cwd=ROOT).decode().splitlines()
sources = []
for relative in source_paths:
    blob_id = subprocess.check_output(["git", "rev-parse", f"d8a3189:{relative}"], cwd=ROOT).decode().strip()
    blob = subprocess.check_output(["git", "cat-file", "blob", blob_id], cwd=ROOT)
    sources.append({"path": relative, "code_git_blob": blob_id, "blob_size_bytes": len(blob),
                    "blob_sha256": hashlib.sha256(blob).hexdigest()})
manifest = {"recorded_at_shanghai": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            "reviewer": "/root/r07_single_model_dimension_independent_review",
            "material_sha": "b05e63462f1b513eabc183d0a8d42b03196696d2",
            "code_sha": "d8a3189bb7bc1cfde24825f5478920e37eac9556",
            "baseline_sha": "63e4cafe1363530eb08cdfe7fec56cfc07a81b8a",
            "author_manifest_sha256": "9d267434cca417d4a0a8eb3216956473f91b98b49148711e7b9dcb5950d85c0b",
            "verdict": "Ship: single-dimension offline unit/contract/security slice only",
            "not_run": ["integration", "frontend", "e2e", "live", "manual"],
            "frozen_source_blobs": sources, "artifact_count": len(entries), "artifacts": entries,
            "exclusions": ["review_manifest.json", "review_manifest.sha256", "__pycache__"],
            "note": "Raw bytes only. No claim about uncreated review Git blobs; preserve bytes on archive."}
raw = (json.dumps(manifest, ensure_ascii=False, indent=2)+"\n").encode("utf-8")
(RUN / "review_manifest.json").write_bytes(raw)
digest = hashlib.sha256(raw).hexdigest()
(RUN / "review_manifest.sha256").write_text(digest+"  review_manifest.json\n", encoding="utf-8")
print(json.dumps({"artifact_count": len(entries), "review_manifest_sha256": digest,
                  "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest()}))
