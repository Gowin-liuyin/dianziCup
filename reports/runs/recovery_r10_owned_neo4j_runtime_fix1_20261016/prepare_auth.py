"""Stage the original DPAPI test credential in a new private fix namespace."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
CACHE = Path("D:/dianzi-runtime-cache/r10-neo4j-operations-fix1-20261016")
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
assert not CACHE.exists(), "Unknown fix cache must not be replaced"
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
assert secret["resource_id"] == "dianzi-r10-neo4j-test-20261016"
assert secret["deadline"] == "2026-10-16T19:35:43.312788+08:00"
assert datetime.now(timezone.utc) < datetime.fromisoformat(secret["deadline"])
assert secret["NEO4J_TEST_BOLT_URL"] == "bolt://127.0.0.1:27687"
assert secret["NEO4J_TEST_USERNAME"] == "neo4j"
stage = "import json,sys; from pathlib import Path; value=json.load(sys.stdin); root=Path('/tmp/dianzi-r10-neo4j-operations-fix1-20261016'); assert not root.exists(); root.mkdir(mode=0o700); auth=root/'neo4j-auth.env'; auth.write_text('NEO4J_AUTH=neo4j/'+value['NEO4J_TEST_PASSWORD']+'\\n'); auth.chmod(0o600); print('original_test_auth_staged')"
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
assert (
    staged.returncode == 0 and staged.stdout.strip() == "original_test_auth_staged"
), "Private fix auth staging failed"
CACHE.mkdir()
receipt = {
    "at": datetime.now(timezone.utc).isoformat(),
    "credential_reference": "D:/dianzi-private/r10-neo4j-test-20261016.dpapi",
    "deadline": secret["deadline"],
    "password_regenerated": False,
    "private_ops_path": "/tmp/dianzi-r10-neo4j-operations-fix1-20261016",
    "exit_code": 0,
}
(OUTPUT / "auth_preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
