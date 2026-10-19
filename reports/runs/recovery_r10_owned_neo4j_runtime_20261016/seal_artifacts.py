"""Freeze owned delivery bytes after scanning actual test-secret representations."""

import base64
import hashlib
import json
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
REPORT = Path("D:/dianzi/reports/tasks/R10-owned-neo4j-runtime.md")
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
unlock = "$ErrorActionPreference='Stop'; $secure=ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/r10-neo4j-test-20261016.dpapi')); $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }"
result = subprocess.run(
    [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", unlock],
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert result.returncode == 0, "DPAPI scan input unavailable"
secret = json.loads(result.stdout)
password = secret["NEO4J_TEST_PASSWORD"]
variants = {
    password,
    urllib.parse.quote(password, safe=""),
    password.encode().hex(),
    base64.b64encode(password.encode()).decode(),
    base64.urlsafe_b64encode(password.encode()).decode(),
    base64.b64encode(("neo4j:" + password).encode()).decode(),
}
resource = json.loads((OUTPUT / "resource_started.json").read_text())
assert (
    secret["resource_id"] == resource["resource_id"]
    and secret["deadline"] == resource["deadline"]
)
assert datetime.now(timezone.utc) < datetime.fromisoformat(resource["deadline"])
for source_name, frozen_name, hash_key in (
    ("runtime.py", "launched_runtime.py.txt", "supervisor_script_sha256"),
    (
        "usage_reporting_transition.py",
        "launched_usage_reporting_transition.py.txt",
        "supervisor_wrapper_sha256",
    ),
):
    source = (OUTPUT / source_name).read_bytes()
    assert source == (OUTPUT / frozen_name).read_bytes()
    assert hashlib.sha256(source).hexdigest() == resource[hash_key]
excluded = {"artifact_hashes.json", "secret_scan_final.json", "delivery_seal.json"}
paths = [
    path for path in OUTPUT.rglob("*") if path.is_file() and path.name not in excluded
] + [REPORT]
matches = [
    str(path)
    for path in paths
    if any(value.encode() in path.read_bytes() for value in variants)
]
assert not matches, "Actual secret found in delivery bytes"
scanned_at = datetime.now(timezone.utc).isoformat()
scan = {
    "at": scanned_at,
    "actual_value_and_encoded_variants": len(variants),
    "scanned_file_count": len(paths),
    "match_count": len(matches),
    "matches": matches,
    "scope": "Owned run files and owned task report only; no secrets/cache/raw private logs in artifact manifest.",
}
(OUTPUT / "secret_scan_final.json").write_text(json.dumps(scan, indent=2) + "\n")
paths.append(OUTPUT / "secret_scan_final.json")
artifacts = [
    {
        "path": str(path),
        "byte_length": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    for path in sorted(paths)
]
manifest = {
    "frozen_at": scanned_at,
    "input_git_sha": resource["input_git_sha"],
    "resource_id": resource["resource_id"],
    "container_id": resource["container_id"],
    "deadline": resource["deadline"],
    "runtime_core_sha256": resource["supervisor_script_sha256"],
    "runtime_wrapper_sha256": resource["supervisor_wrapper_sha256"],
    "report": str(REPORT),
    "artifacts": artifacts,
}
manifest_path = OUTPUT / "artifact_hashes.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
seal = {
    "at": scanned_at,
    "exit_code": 0,
    "artifact_file_count": len(artifacts),
    "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "manifest_path": str(manifest_path),
    "source_freeze_matched": True,
    "secret_scan_match_count": 0,
    "current_service_started_at": resource["started_at"],
    "deadline": resource["deadline"],
    "current_container_id": resource["container_id"],
    "runtime_awaiting_review": True,
    "graceful_shutdown": "failed",
}
(OUTPUT / "delivery_seal.json").write_text(json.dumps(seal, indent=2) + "\n")
print(json.dumps(seal))
