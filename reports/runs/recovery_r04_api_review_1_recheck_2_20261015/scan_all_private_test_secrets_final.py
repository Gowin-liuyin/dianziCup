"""Final scan of all three independently captured review batches with private test credentials."""

import json
from pathlib import Path
from urllib.parse import unquote,urlsplit

private_names = ['dianzi-r04-api-review-1-20261015','dianzi-r04-api-review-1-recheck-20261015','dianzi-r04-api-review-1-recheck-2-20261015']
full_values = set()
credential_values = set()
for name in private_names:
    directory = Path('/tmp')/name
    connection_file = directory/'connection.json'
    assert connection_file.stat().st_mode & 0o777 == 0o600
    dsn = json.loads(connection_file.read_text())['TEST_DATABASE_URL']
    full_values.add(dsn)
    credential_values.add(unquote(urlsplit(dsn).password or ''))
    ledger = directory/'review_registered_secrets.json'
    if ledger.exists():
        assert ledger.stat().st_mode & 0o777 == 0o600
        credential_values.update(json.loads(ledger.read_text()))
full_values.update(credential_values)
fragments = {value[index:index+8] for value in credential_values if value for index in range(max(0,len(value)-7))}
root = Path('/mnt/d/dianzi')
folders = ['recovery_r04_api_review_1_20261015','recovery_r04_api_review_1_recheck_20261015','recovery_r04_api_review_1_recheck_2_20261015']
paths = []
for name in folders:
    paths.extend(path for path in (root/'reports/runs'/name).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
paths.extend((root/'reports/reviews/recovery'/name) for name in ['G-B-R04-api-review-1.md','G-B-R04-api-review-1-recheck.md','G-B-R04-api-review-1-recheck-2.md'])
hits = []
for path in paths:
    contents = path.read_bytes()
    kinds = []
    if any(value.encode() in contents for value in full_values if value):
        kinds.append('full_value')
    if any(fragment.encode() in contents for fragment in fragments):
        kinds.append('8_character_fragment')
    if kinds:
        hits.append({'path':str(path),'match_kinds':kinds})
result = {'scanned_file_count':len(paths),'credential_full_value_count':len(credential_values),
    'dsn_full_value_count':3,'fragment_count':len(fragments),'hits':hits,
    'secrets_printed':False,'scope':'three reviewer-owned batches only; no product credentials or holdout read'}
run = Path(__file__).resolve().parent
(run/'all_private_test_secret_scan_final.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
raise SystemExit(1 if hits else 0)

