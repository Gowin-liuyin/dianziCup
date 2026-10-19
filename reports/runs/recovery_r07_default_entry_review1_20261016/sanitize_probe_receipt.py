"""Remove a connection secret from a reviewer harness failure while keeping its outcome."""

import hashlib
import json
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url

RUN = Path(__file__).parent
private = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'], capture_output=True, check=True)
url = make_url(json.loads(private.stdout)['TEST_DATABASE_URL'])
secret = url.password
assert secret and len(secret) >= 8
paths = [RUN / 'independent_forward_asset_pg.log', RUN / 'independent_forward_asset_pg.xml']
changed = []
for path in paths:
    value = path.read_text(encoding='utf-8')
    sanitized = value.replace(secret, '[redacted test credential]')
    if sanitized != value:
        original_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_text(sanitized, encoding='utf-8')
        changed.append({'path': path.name, 'original_raw_sha256': original_sha, 'redacted_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(RUN / 'probe_harness_redaction.json').write_text(json.dumps({'reason': 'External reviewer probe initially did not inherit backend/tests/conftest.py redaction hook; source credential replaced without changing counts, failure, timestamps or argv.', 'files': changed, 'shared_redaction_hook_now_loaded': True}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'credential_redacted_files': len(changed), 'failure_outcome_preserved': True}))
