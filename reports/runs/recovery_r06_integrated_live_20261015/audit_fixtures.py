"""Independently verify only the three frozen CSRF fixture matches, without echoing values."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("D:/dianzi")
RUN = Path(__file__).resolve().parent
SHA = "1156b2ed6616e3a4297215c2893d2cbe633f5215"
spec = importlib.util.spec_from_file_location("isolated_scan", ROOT / "scripts/security_scan.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
paths = ("frontend/src/api/source-catalog.test.ts", "frontend/src/features/sources/source-admin-catalog.test.tsx")
matches = []
fixture_values = []
for name in paths:
    raw = (ROOT / name).read_bytes()
    frozen = subprocess.check_output(["git", "show", SHA + ":" + name], cwd=ROOT)
    assert raw.replace(b"\r\n", b"\n") == frozen.replace(b"\r\n", b"\n")
    content = raw.decode().replace("\r\n", "\n").replace("\r", "\n")
    for pattern_id, pattern in module.PATTERNS.items():
        for match in pattern.finditer(content):
            matched_text = match.group(0)
            quote_start = min(index for index, character in enumerate(matched_text) if character in "\"'")
            value = matched_text[quote_start + 1:-1]
            fixture_values.append(value)
            matches.append({"path": name, "raw_sha256": hashlib.sha256(raw).hexdigest(), "source_blob": subprocess.check_output(["git", "rev-parse", SHA + ":" + name], cwd=ROOT, text=True).strip(), "pattern_id": pattern_id, "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(), "start": match.start(), "end": match.end(), "line": content[:match.start()].count("\n") + 1, "match_value_sha256": hashlib.sha256(value.encode()).hexdigest(), "value_length": len(value), "literal_assignment_in_isolated_fetch_fixture": True})
assert len(matches) == 3
assert [(m["start"], m["end"]) for m in matches] == [(2504, 2526), (610, 640), (610, 640)]
private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json"], capture_output=True, text=True, check=True, timeout=10)
secrets = set(json.loads(private.stdout)["secret_values"])
minio = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-minio-r02-20261015/private/connection.json"], capture_output=True, text=True, check=True, timeout=10)
minio_values = json.loads(minio.stdout)
secrets.update(minio_values[name] for name in ("access_key", "secret_key"))
secrets.add(os.environ["DIANZI_E2E_PASSWORD"])
assert all(value not in secrets for value in fixture_values)
receipt = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": SHA, "matches": matches, "values_echoed": False, "classification_changed": False, "source_scope": "literal CSRF response in vi.stubGlobal fetch tests; production source-client fetch path remains real"}
receipt["authorized_runtime_minio_login_exact_value_collisions"] = 0
(RUN / "fixture_origin_audit.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"matches_verified": len(matches), "values_echoed": False}))
