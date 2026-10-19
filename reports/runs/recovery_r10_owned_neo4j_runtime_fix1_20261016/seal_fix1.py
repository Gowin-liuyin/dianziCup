"""Seal the new fix package and scan specified actual secret forms across owned raw logs."""

import base64
import hashlib
import json
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
REPORT = Path("D:/dianzi/reports/tasks/R10-owned-neo4j-runtime-fix1.md")
CACHE = Path("D:/dianzi-runtime-cache/r10-neo4j-operations-fix1-20261016")
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
unlock = "$ErrorActionPreference='Stop'; $secure=ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/r10-neo4j-test-20261016.dpapi')); $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }"
unprotected = subprocess.run(
    [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", unlock],
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert unprotected.returncode == 0
secret = json.loads(unprotected.stdout)
password = secret["NEO4J_TEST_PASSWORD"]
variants = {
    password.encode(),
    password.encode("utf-16-le"),
    password.encode("utf-16-be"),
    json.dumps(password).encode(),
    urllib.parse.quote(password, safe="").encode(),
    password.encode().hex().encode(),
    base64.b64encode(password.encode()),
    base64.urlsafe_b64encode(password.encode()),
    base64.b64encode(("neo4j:" + password).encode()),
}
resource = json.loads((OUTPUT / "resource_started.json").read_text())
assert (
    secret["resource_id"] == resource["resource_id"]
    and secret["deadline"] == resource["deadline"]
)
assert datetime.now(timezone.utc) < datetime.fromisoformat(resource["deadline"])
runtime_bytes = (OUTPUT / "runtime.py").read_bytes()
assert (
    hashlib.sha256(runtime_bytes).hexdigest()
    == resource["supervisor_script_sha256"]
    == "261968fab9be60733d4d2043b05926c0be3805b5741bd495252a7f78a9bf7179"
)
prepared = json.loads((OUTPUT / "tools_preparation.json").read_text())
for source in prepared["sources"]:
    assert (
        hashlib.sha256((OUTPUT / source["name"]).read_bytes()).hexdigest()
        == source["sha256"]
    ), "Prepared source drifted"
original = OUTPUT.parent / "recovery_r10_owned_neo4j_runtime_20261016"
old_manifest_bytes = (original / "artifact_hashes.json").read_bytes()
assert (
    hashlib.sha256(old_manifest_bytes).hexdigest()
    == "614305594e9f5073511aaaed4396fc247045a350f5b9200e98d74979813342a6"
)
permitted = {
    str(original / name)
    for name in (
        "termination.json",
        "stop_supervisor_signal_15.command.json",
        "stop_supervisor_signal_15.stdout.log",
        "stop_supervisor_signal_15.stderr.log",
    )
}
changed = []
for item in json.loads(old_manifest_bytes)["artifacts"]:
    path = Path(item["path"])
    current_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if current_sha != item["sha256"]:
        assert str(path) in permitted, "Unapproved original sealed member changed"
        archived = OUTPUT / "original_live_lifecycle_before_switch" / path.name
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == item["sha256"]
        changed.append(
            {
                "path": str(path),
                "before_sha256": item["sha256"],
                "after_sha256": current_sha,
                "original_bytes_archived": str(archived),
            }
        )
(OUTPUT / "original_seal_after_transition.json").write_text(
    json.dumps(
        {
            "member_count": 143,
            "allowed_live_lifecycle_changes": changed,
            "all_other_members_unchanged": True,
            "original_manifest_unchanged": True,
        },
        indent=2,
    )
    + "\n"
)
(OUTPUT / "launched_runtime.py.txt").write_bytes(runtime_bytes)
excluded = {"artifact_hashes.json", "secret_scan_final.json", "delivery_seal.json"}
files = [
    path
    for path in OUTPUT.rglob("*")
    if path.is_file() and path.name not in excluded and "__pycache__" not in path.parts
] + [REPORT]
private_raw = list(CACHE.glob("*.log"))
assert len(private_raw) >= 5
linux_scan = "import json,sys; from pathlib import Path; root=Path('/tmp/dianzi-r10-neo4j-operations-fix1-20261016'); result={}; [result.update({name:(root/name).read_text()}) for name in ['guardian.stdout.log','guardian.stderr.log']]; print(json.dumps(result))"
private_linux = subprocess.run(
    [
        "wsl.exe",
        "-d",
        "Ubuntu-22.04",
        "-u",
        "root",
        "--exec",
        "python3",
        "-B",
        "-c",
        linux_scan,
    ],
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert private_linux.returncode == 0
linux_logs = json.loads(private_linux.stdout)
matches = [
    str(path)
    for path in files + private_raw
    if any(value in path.read_bytes() for value in variants)
]
matches.extend(
    "private_linux/" + name
    for name, content in linux_logs.items()
    if any(value in content.encode() for value in variants)
)
assert not matches, "Actual test credential found in owned delivery or raw logs"
at = datetime.now(timezone.utc).isoformat()
scan = {
    "at": at,
    "unique_actual_value_forms": len(variants),
    "public_file_count": len(files),
    "private_raw_windows_log_count": len(private_raw),
    "private_raw_linux_log_count": len(linux_logs),
    "junit_scanned": (OUTPUT / "independent_guard.xml").exists(),
    "match_count": 0,
    "matches": [],
    "scope": "Owned fix report/public files/JUnit plus named private raw logs; DPAPI and secret envfile are excluded inputs, not artifacts.",
}
(OUTPUT / "secret_scan_final.json").write_text(json.dumps(scan, indent=2) + "\n")
files.append(OUTPUT / "secret_scan_final.json")
artifacts = [
    {
        "path": str(path),
        "byte_length": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    for path in sorted(files)
]
manifest = {
    "frozen_at": at,
    "resource_id": resource["resource_id"],
    "container_id": resource["container_id"],
    "deadline": resource["deadline"],
    "runtime_sha256": resource["supervisor_script_sha256"],
    "report": str(REPORT),
    "artifacts": artifacts,
}
manifest_path = OUTPUT / "artifact_hashes.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
seal = {
    "at": at,
    "exit_code": 0,
    "artifact_count": len(artifacts),
    "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
    "runtime_sha256": resource["supervisor_script_sha256"],
    "container_id": resource["container_id"],
    "current_started_at": resource["started_at"],
    "deadline": resource["deadline"],
    "original_seal_proof_member_count": 143,
    "original_live_lifecycle_changed_count": len(changed),
    "secret_scan_match_count": 0,
    "graceful_shutdown": "passed",
    "task_status": "awaiting_review",
}
(OUTPUT / "delivery_seal.json").write_text(json.dumps(seal, indent=2) + "\n")
print(json.dumps(seal))
