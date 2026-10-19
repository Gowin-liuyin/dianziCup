"""Record source and original oracle identity without loading runtime credentials."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "8c48b61c02860166bdda0986e984058e8a824188"
SOURCE = "9cd6381eacc67853c055643d634ffb1812875214"
PATHS = (
    "backend/src/ai_intel/retrieval/opensearch_client.py",
    "backend/src/ai_intel/retrieval/runtime_policy.py",
    "backend/tests/contract/test_r12_projection_failure_budget.py",
    "backend/tests/contract/test_r12_projection_total_budget_fix2.py",
    "backend/src/ai_intel/retrieval/indexing.py",
    "backend/src/ai_intel/workers/runtime.py",
    "backend/src/ai_intel/workers/executor.py",
)


def git(*arguments):
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, check=False, timeout=10
    )
    return result.returncode, result.stdout


manifest = {"recorded_at": datetime.now(UTC).isoformat(), "baseline": BASELINE, "source": SOURCE}
manifest["head"] = git("rev-parse", "HEAD")[1].decode().strip()
manifest["diff_names"] = git("diff", "--name-status", BASELINE, SOURCE)[1].decode().splitlines()
manifest["inputs"] = []
for relative in PATHS:
    raw = (ROOT / relative).read_bytes()
    baseline_code, baseline_bytes = git("show", BASELINE + ":" + relative)
    source_bytes = git("show", SOURCE + ":" + relative)[1]
    source_blob = git("rev-parse", SOURCE + ":" + relative)[1].decode().strip()
    manifest["inputs"].append(
        {
            "path": relative,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
            "source_blob": source_blob,
            "source_lf_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "source_lf_matches_raw": source_bytes == raw.replace(b"\r\n", b"\n"),
            "baseline_blob": git("rev-parse", BASELINE + ":" + relative)[1].decode().strip()
            if baseline_code == 0
            else None,
            "baseline_lf_unchanged": baseline_bytes == source_bytes if baseline_code == 0 else None,
        }
    )
oracle = manifest["inputs"][3]
assert oracle["source_blob"] == "14b93c44927a005393150aa4b0fece869b99da79"
assert oracle["raw_sha256"] == "d0d43ee90a50590a225f3a5154c91d529eefee2298a631c2143862664d08b6d3"
assert oracle["baseline_lf_unchanged"]
path = RUN / "source_manifest.json"
assert not path.exists()
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source": SOURCE, "paths": len(PATHS), "original_oracle_unchanged": True}))
