"""Create a single-instance secret in memory and protect it with current-user DPAPI."""

import hashlib
import json
import secrets
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
PRIVATE = Path("D:/dianzi-private/r10-neo4j-test-20261016.dpapi")
CACHE = Path("D:/dianzi-runtime-cache/r10-neo4j-operations-20261016")
NAME = "dianzi-r10-neo4j-test-20261016"
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"

assert not PRIVATE.exists(), "Unknown existing private credential must not be replaced"
assert not CACHE.exists(), "Unknown owned Windows cache must not be replaced"
assert PRIVATE.parent.exists()
started = datetime.now(timezone(timedelta(hours=8)))
deadline = min(
    started + timedelta(hours=12), datetime.fromisoformat("2026-10-17T21:49:15+08:00")
)
assert deadline > started
proposal = Path(
    "D:/wt/r10-neo4j-projection/reports/runs/recovery_r10_neo4j_projection_20261016/neo4j_resource_proposal.json"
)
resource = {
    "resource_id": NAME,
    "deadline": deadline.isoformat(),
    "creator_token": str(uuid.uuid4()),
    "prepared_at": started.isoformat(),
    "input_git_sha": "3baeb8809d3950a091e8db114be7a28049b74b36",
    "input_proposal_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
}
password = secrets.token_urlsafe(48)
secret = {
    "NEO4J_TEST_BOLT_URL": "bolt://127.0.0.1:27687",
    "NEO4J_TEST_USERNAME": "neo4j",
    "NEO4J_TEST_PASSWORD": password,
    "resource_id": NAME,
    "deadline": resource["deadline"],
}
protect_script = "$ErrorActionPreference='Stop'; $payload=[Console]::In.ReadToEnd(); $protected=ConvertFrom-SecureString (ConvertTo-SecureString $payload -AsPlainText -Force); [IO.File]::WriteAllText('D:/dianzi-private/r10-neo4j-test-20261016.dpapi', $protected); [Console]::Write('protected_current_user_dpapi')"
protected = subprocess.run(
    [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", protect_script],
    input=json.dumps(secret),
    text=True,
    capture_output=True,
    timeout=25,
    check=False,
)
assert (
    protected.returncode == 0 and protected.stdout == "protected_current_user_dpapi"
), "DPAPI protection failed"
try:
    CACHE.mkdir()
    initialize_script = "import json,os,sys; from pathlib import Path; value=json.load(sys.stdin); root=Path('/tmp/dianzi-r10-neo4j-operations-20261016'); assert not root.exists(); root.mkdir(mode=0o700); resource=root/'resource.json'; resource.write_text(json.dumps(value['resource'],indent=2)); resource.chmod(0o600); auth=root/'neo4j-auth.env'; auth.write_text('NEO4J_AUTH=neo4j/'+value['password']+'\\n'); auth.chmod(0o600); print('private_owned_inputs_prepared')"
    initialized = subprocess.run(
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
            initialize_script,
        ],
        input=json.dumps({"resource": resource, "password": password}),
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert (
        initialized.returncode == 0
        and initialized.stdout.strip() == "private_owned_inputs_prepared"
    ), "Owned secret staging failed"
finally:
    password = None
    secret = None
resource["credential_reference"] = str(PRIVATE)
(OUTPUT / "credential_preparation.json").write_text(
    json.dumps(resource, indent=2) + "\n"
)
(CACHE / "resource_reference.json").write_text(json.dumps(resource, indent=2) + "\n")
print(
    json.dumps(
        {
            "operation": "credential_prepared",
            "resource_id": NAME,
            "deadline": resource["deadline"],
            "credential_reference": str(PRIVATE),
            "plaintext_logged": False,
        }
    )
)
