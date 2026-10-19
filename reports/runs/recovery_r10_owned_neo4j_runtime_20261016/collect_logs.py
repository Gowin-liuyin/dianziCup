"""Keep raw startup output private and export only scanned, redacted owned logs."""

import base64
import json
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
CACHE = Path("D:/dianzi-runtime-cache/r10-neo4j-operations-20261016")
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
unlock = "$ErrorActionPreference='Stop'; $secure=ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/r10-neo4j-test-20261016.dpapi')); $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }"
unprotected = subprocess.run(
    [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", unlock],
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert unprotected.returncode == 0, "DPAPI unprotect failed"
secret = json.loads(unprotected.stdout)
password = secret["NEO4J_TEST_PASSWORD"]
variants = {
    password,
    urllib.parse.quote(password, safe=""),
    base64.b64encode(password.encode()).decode(),
    base64.urlsafe_b64encode(password.encode()).decode(),
    password.encode().hex(),
    base64.b64encode(("neo4j:" + password).encode()).decode(),
}
resource = json.loads((OUTPUT / "resource_created.json").read_text())
container_id = resource["container_id"]
assert len(container_id) == 64
command = [
    "wsl.exe",
    "-d",
    "Ubuntu-22.04",
    "-u",
    "root",
    "--exec",
    "/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker",
    "--config",
    "/tmp/dianzi-docker-static-r01-20261014/runtime/client-config",
    "--host",
    "unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock",
    "logs",
    "--timestamps",
    container_id,
]
started = datetime.now(timezone.utc)
logs = subprocess.run(command, capture_output=True, timeout=25, check=False)
assert logs.returncode == 0, "Owned log collection failed"
raw = logs.stdout + logs.stderr
raw_path = CACHE / (container_id[:12] + ".container_startup.raw.log")
raw_path.write_bytes(raw)
redacted = raw
removed = 0
for value in variants:
    removed += redacted.count(value.encode())
    redacted = redacted.replace(value.encode(), b"[REDACTED_OWNED_TEST_SECRET]")
(OUTPUT / "container_startup.redacted.log").write_bytes(redacted)
files = list(OUTPUT.rglob("*"))
report = Path("D:/dianzi/reports/tasks/R10-owned-neo4j-runtime.md")
if report.exists():
    files.append(report)
matches = []
for path in files:
    if path.is_file():
        content = path.read_bytes()
        if any(value.encode() in content for value in variants):
            matches.append(str(path))
receipt = {
    "at": datetime.now(timezone.utc).isoformat(),
    "command": command,
    "started_at": started.isoformat(),
    "exit_code": logs.returncode,
    "raw_log_private_path": str(raw_path),
    "redacted_log_path": str(OUTPUT / "container_startup.redacted.log"),
    "redacted_occurrences": removed,
    "secret_scan_file_count": sum(path.is_file() for path in files),
    "secret_scan_matches": matches,
}
(OUTPUT / "logs_and_secret_scan.json").write_text(json.dumps(receipt, indent=2) + "\n")
assert not matches, "Owned delivery contains secret material"
print(json.dumps(receipt))
print(redacted.decode(errors="replace")[-6000:])
