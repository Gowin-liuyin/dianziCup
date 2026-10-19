"""Restage the same DPAPI credential only for the approved exited-container repair."""

import json
import subprocess
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
unlock = "$ErrorActionPreference='Stop'; $secure=ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/r10-neo4j-test-20261016.dpapi')); $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }"
result = subprocess.run(
    [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", unlock],
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert result.returncode == 0, "DPAPI unprotect failed"
secret = json.loads(result.stdout)
resource = json.loads((OUTPUT / "rebuild_preparation.json").read_text())
assert secret["resource_id"] == resource["resource_id"]
assert secret["deadline"] == resource["deadline"]
assert secret["NEO4J_TEST_BOLT_URL"] == "bolt://127.0.0.1:27687"
assert secret["NEO4J_TEST_USERNAME"] == "neo4j"
stage = "import json,sys; from pathlib import Path; from datetime import datetime; value=json.load(sys.stdin); root=Path('/tmp/dianzi-r10-neo4j-operations-20261016'); resource=json.loads((root/'resource.json').read_text()); assert resource['deadline']==value['deadline']; assert datetime.now().astimezone()<datetime.fromisoformat(value['deadline']); path=root/'neo4j-auth.env'; assert not path.exists(); assert path.parent.resolve()==root; path.write_text('NEO4J_AUTH=neo4j/'+value['NEO4J_TEST_PASSWORD']+'\\n'); path.chmod(0o600); print('same_owned_auth_restaged')"
staged = subprocess.run(
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
        stage,
    ],
    input=json.dumps(secret),
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert staged.returncode == 0 and staged.stdout.strip() == "same_owned_auth_restaged", (
    "Owned auth restaging failed"
)
print(
    json.dumps(
        {
            "operation": "same_owned_auth_restaged",
            "deadline": resource["deadline"],
            "password_regenerated": False,
        }
    )
)
