"""Bind source blobs, unchanged probes and raw QA material to the frozen namespace fix."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "e61d9d6dd1215c337755d32d112dfe70f13d9e94"
CODE = "ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce"
SERVICE = "backend/src/ai_intel/enrichment/job_service.py"
REVIEW = Path("D:/wt/r07-default-entry-review1/reports/runs/recovery_r07_default_entry_review1_20261016/probes")
(RUN / "job_service_frozen.py").write_bytes(subprocess.check_output(["git", "show", CODE + ":" + SERVICE], cwd=ROOT))
changed = subprocess.check_output(["git", "diff", "--name-only", BASE, CODE], cwd=ROOT, text=True).splitlines()


def entry(path):
    raw = path.read_bytes()
    result = {"path": path.relative_to(ROOT).as_posix(), "size_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()}
    try:
        value = raw.decode("utf-8")
        if "\0" not in value:
            result["lf_sha256"] = hashlib.sha256(value.replace("\r\n", "\n").encode()).hexdigest()
    except UnicodeError:
        pass
    return result


probes = []
for name in ("test_independent_idempotency_scope.py", "conftest.py"):
    original = (REVIEW / name).read_bytes()
    copy = RUN / "probes" / name
    assert original == copy.read_bytes()
    probes.append({"original_path": str(REVIEW / name), "copy": copy.relative_to(ROOT).as_posix(), "raw_sha256": hashlib.sha256(original).hexdigest(), "byte_identical": True})
materials = [*sorted(RUN.rglob("*")), ROOT / "reports/tasks/R07-idempotency-scope.md", ROOT / "docs/decisions/CR-R07_idempotency_scope_proposal.md"]
manifest = {"created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "base_sha": BASE, "code_sha": CODE, "changed_source": [entry(ROOT / path) for path in changed], "original_probes": probes, "materials": [entry(path) for path in materials if path.is_file() and path.name not in {"raw_manifest.json", "material_fingerprint.json"}], "private_values_or_their_hashes": "excluded", "task_state": "awaiting_review"}
raw = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
(RUN / "raw_manifest.json").write_bytes(raw)
(RUN / "material_fingerprint.json").write_bytes(json.dumps({"created_at": manifest["created_at"], "code_sha": CODE, "raw_manifest_sha256": hashlib.sha256(raw).hexdigest()}, indent=2).encode())
print(json.dumps({"changed_files": len(changed), "probes_byte_identical": True, "materials": len(manifest["materials"]), "raw_manifest_sha256": hashlib.sha256(raw).hexdigest()}))
