"""Check only explicitly staged files without disclosing any matched secret material."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
names = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")
for name in filter(None, names):
    assert name != "frontend/tsconfig.tsbuildinfo"
    assert not any(part.lower() in {".env", "holdout", "keys-and-usage"} for part in Path(name).parts)
    raw = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
    assert len(raw) < 2 * 1024 * 1024
    assert not re.search(rb"(?i)\bsk-[a-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|postgres(?:ql)?(?:\+psycopg)?://[^\s:]+:[^\s@]+@", raw), "sensitive staged value detected"
assert subprocess.check_output(["git", "rev-parse", ":reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"], cwd=ROOT, text=True).strip() == "82c40263274fb65517037ab5e3f2d3982f151d67"
print(json.dumps({"staged_files_checked": len(list(filter(None, names))), "secret_patterns": 0, "user_file_staged": False, "fixture_blob_verified": True}))
